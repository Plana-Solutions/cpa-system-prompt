# Plana ARM64 build

This repository forks [whexy's system-prompt plugin](https://github.com/whexy/whexy-cpa-store/tree/51ea66ad0df8aaea0719b7589a5f49c653e3ee20/plugins/system-prompt) at commit `51ea66ad0df8aaea0719b7589a5f49c653e3ee20`.
The MIT license and Wenxuan Shi's copyright remain in [LICENSE](LICENSE).

Plana adds optional caller selectors and a native linux/arm64 release.
The plugin keeps the ID `system-prompt` and reports version `0.1.0-plana.2`, matching [registry.json](registry.json).
Its Go module lives in `go/` and builds against the CPA v8.0.38 SDK, the version Plana's CPA runs. Building against a newer SDK registers a plugin schema that v8.0.38 refuses (`plugin schema version 10 is not supported`), so keep the SDK at or below the host version.
Model matching, prompt order, protocol injection, and the management page retain upstream behavior.

## Limit a rule to client keys

Add `callers` to a rule under `plugins.configs.system-prompt.rules`.
Each value is a caller scope, rather than an API key.
This example uses a synthetic scope that you must replace:

```yaml
plugins:
  configs:
    system-prompt:
      enabled: true
      rules:
        - models: ["*"]
          prompt: "Follow the organization's writing guidelines."
        - models: ["*"]
          callers: ["aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"]
          label: "Personal writing preferences"
          managed_by: "Plana"
          prompt: "Answer in Swedish."
```

A rule without `callers` applies to every caller whose model matches.
A rule with `callers` applies only if both the model and the caller scope match.
The plugin joins matching prompts in config order after the client's prompt.
It reads the scope from `Metadata["caller_scope"]`, which every v8 host fills for interceptors.
A request without either scope matches only rules without `callers`.

Caller entries must contain 64 hexadecimal characters after trimming spaces and converting to lowercase.
An empty list, null, a non-list value, or any malformed entry disables the entire rule.
The status route reports the rule in `problems`, such as `lists no callers` or `caller 2 is not a caller scope`.
An invalid selector never turns into a rule for everyone.
Unknown fields, including `label` and `managed_by`, do not affect parsing.

Set `KEY` privately to the client API key, then compute its caller scope with:

```sh
printf 'cli-proxy-api:caller-scope:v1\0%s' "$KEY" | shasum -a 256
```

Copy only the 64-character digest into `callers`.
Do not put the API key in the plugin config or commit it.
Configure caller selectors through YAML.
The management page edits models and prompts and preserves `callers` and other existing rule fields when saving.

## Add the registry in CPAMP

1. Open **Plugins**, then **Plugin Store**, then **Manage**.
2. Add `https://raw.githubusercontent.com/Plana-Solutions/cpa-system-prompt/main/registry.json`.
3. Refresh the store and select **System Prompts (Plana ARM64)**.
4. Confirm the source repository is `Plana-Solutions/cpa-system-prompt` before installing.

The fork shares the upstream plugin ID, so select the Plana source explicitly.
This repository's workflow builds and publishes assets. It does not install them or change a CPA host.

## Build and publish

The workflow uses Depot's `depot-ubuntu-24.04-arm-4` runner and a Go 1.26.10 Debian Bookworm container, matching `go/go.mod`.
It runs `go vet`, Go tests, race tests, and native shared-library ABI checks before publishing.
The `file` check requires an ELF aarch64 shared library.

Push a tag matching `v*-plana.*` to publish.
For `v0.1.0-plana.2`, CPA's GitHub release installer consumes `system-prompt_0.1.0-plana.2_linux_arm64.zip` and `checksums.txt`.
The zip contains `system-prompt.so` and the upstream MIT license.
Checksums use bare archive filenames, as CPA expects.

To run local checks:

```sh
cd go
go vet ./...
go test -count=1 ./...
go test -count=1 -race ./...
```
