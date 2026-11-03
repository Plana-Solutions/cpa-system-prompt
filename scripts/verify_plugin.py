import base64
import ctypes
import json
from pathlib import Path
import sys


class Buffer(ctypes.Structure):
    _fields_ = [("ptr", ctypes.c_void_p), ("len", ctypes.c_size_t)]


Call = ctypes.CFUNCTYPE(
    ctypes.c_int,
    ctypes.c_char_p,
    ctypes.POINTER(ctypes.c_uint8),
    ctypes.c_size_t,
    ctypes.POINTER(Buffer),
)
Free = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_size_t)
Shutdown = ctypes.CFUNCTYPE(None)


class PluginAPI(ctypes.Structure):
    _fields_ = [
        ("abi_version", ctypes.c_uint32),
        ("call", Call),
        ("free_buffer", Free),
        ("shutdown", Shutdown),
    ]


def main():
    library = ctypes.CDLL(str(Path(sys.argv[1]).resolve()))
    library.cliproxy_plugin_init.argtypes = [ctypes.c_void_p, ctypes.POINTER(PluginAPI)]
    library.cliproxy_plugin_init.restype = ctypes.c_int
    api = PluginAPI()
    assert library.cliproxy_plugin_init(None, ctypes.byref(api)) == 0
    assert api.abi_version == 1

    def call(method, request):
        payload = json.dumps(request).encode()
        data = (ctypes.c_uint8 * len(payload)).from_buffer_copy(payload)
        response = Buffer()
        status = api.call(method.encode(), data, len(payload), ctypes.byref(response))
        try:
            result = json.loads(ctypes.string_at(response.ptr, response.len))
        finally:
            api.free_buffer(response.ptr, response.len)
        assert status == 0 and result["ok"], result
        return result["result"]

    def configure(rules):
        config = {"rules": rules}
        result = call(
            "plugin.reconfigure",
            {"config_yaml": base64.b64encode(json.dumps(config).encode()).decode()},
        )
        assert result["metadata"]["Version"] == version, result
        return result

    def instructions(scope=None, metadata=None):
        request = {
            "SourceFormat": "openai-response",
            "RequestedModel": "gpt-test",
            "Model": "gpt-test",
            "Body": base64.b64encode(b'{"input":"hi"}').decode(),
        }
        if scope is not None:
            request["CallerScope"] = scope
        if metadata is not None:
            request["Metadata"] = metadata
        result = call("request.intercept_after", request)
        body = result.get("Body")
        return json.loads(base64.b64decode(body))["instructions"] if body else ""

    version = json.loads(Path("registry.json").read_text())["plugins"][0]["version"]
    registration = call("plugin.register", {})
    assert registration["metadata"]["Version"] == version, registration
    scope = "a" * 64
    org = {"models": ["*"], "prompt": "organization"}
    personal = {"models": ["*"], "callers": [scope], "prompt": "personal"}
    configure([org, personal])
    assert instructions(scope) == "organization\n\npersonal"
    assert instructions("b" * 64) == "organization"
    assert instructions() == "organization"
    assert instructions(metadata={"caller_scope": scope}) == "organization\n\npersonal"
    assert instructions("b" * 64, {"caller_scope": scope}) == "organization"

    for callers in ([], None, [scope, "invalid"]):
        configure([org, {**personal, "callers": callers}])
        assert instructions(scope) == "organization"
        status = call(
            "management.handle",
            {"Method": "GET", "Path": "/v0/management/system-prompt/status"},
        )
        view = json.loads(base64.b64decode(status["Body"]))
        assert view["rules"] == 1 and len(view["problems"]) == 1, view
        assert view["problems"][0]["rule"] == 2, view

    api.shutdown()
    print(f"Native ABI verified, version {version}, 8 caller scenarios passed")


if __name__ == "__main__":
    main()
