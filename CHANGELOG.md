# Changelog

## 0.1.16

Direct-only secret loading.

- Removed legacy config-file secret reference behavior from the public API and
  CLI.
- Removed `--config`, `--target-secret`, `--secret-only`, `--print-secret`,
  and raw section/key override compatibility paths.
- Reduced test coverage to the supported direct `vault_id` plus `secret_name`
  flow and payload parsing behavior.

## 0.1.15

Safer auto-detection for raw secrets containing `=`.

- Auto-detection now treats single-line secrets such as `token==` or `abc=def`
  as raw string secrets instead of splitting them as headerless `key=value`.
- Single-line headerless values with spacing around the separator, such as
  `dbpsu_user_pw = some_pass`, still parse as `key=value` in auto mode.
- Added `secret_format` / `--secret-format` with `auto`, `raw`, `key_value`,
  `key-value`, and `ini` support for callers that need to force a payload
  shape.
- Added regression tests for Python API and CLI handling of raw secrets with
  equals signs.

## 0.1.14

Literal secret value handling.

- Disabled `ConfigParser` interpolation for app config, runtime config,
  payload parsing, INI shape detection, and CLI secret-value output.
- Prevents secrets containing `%`, such as passwords and tokens, from raising
  invalid interpolation syntax errors during parsing, merging, or lookup.
- Added regression tests for `%` in raw string, headerless `key=value`, and
  INI-style secret payloads.
- Added `.gitignore` to exclude Python caches, build artifacts, wheel output,
  egg-info metadata, virtual environments, local config files, and likely
  secret/config sample files.

## 0.1.13

Automatic raw output for plain string CLI secrets.

- `--echo-secret-values` now detects a single plain string Vault payload and
  prints only that raw value.
- INI and headerless `key=value` payloads keep the existing config-shaped
  output under `--echo-secret-values`.
- Explicit `--raw-section` or `--raw-key` keeps plain string output
  config-shaped for callers that need section/key placement.
- `--raw` / `--print-secret` remains available to force exact Vault payload
  output for any payload type.
- Refactored the CLI fetch path so auto-detection does not require a second
  Vault fetch.

## 0.1.12

Python 3.6 warning suppression.

- Added a package-level warning filter for the known cryptography deprecation
  warning emitted when the OCI SDK imports cryptography on Python 3.6.
- The filter matches `Python 3.6 is no longer supported by the Python core
  team.*`.
- Added a regression test to confirm that the targeted warning is suppressed
  without suppressing unrelated warnings.

## 0.1.11

Raw CLI secret output.

- Added `--raw` for bash callers that need only the fetched Vault payload on
  stdout.
- Added `--print-secret` as an alias for `--raw`.
- Raw mode skips the normal loaded-config summary and does not print
  `ConfigParser` section/key wrappers.
- Added tests for raw plain-string output, raw INI payload preservation, and
  direct raw secret fetching.

## 0.1.10

Consumer documentation cleanup.

- Reworked the README to lead with remote `pip install` from Artifactory.
- Added the current test Artifactory install command.
- Removed local install and editable install instructions from the consumer
  path.
- Consolidated consumer usage around `vault_id`, `secret_name`, and optional
  `config`.
- Moved wheel build and upload commands into a short maintainer section.
- Added a dependency note that `oci>=2` must be present in, or proxied by, the
  configured package index.

## 0.1.9

Simplified public parameters.

- Clarified the top-level Python API around two supported modes:
  `vault_id` plus `secret_name`, or `config=...`.
- Added support for a simple `[oci_secret_helper]` config file section with
  `vault_id` and `secret_name`.
- Added `--config` as a clearer CLI alias for `--config-ini`.
- Moved `secret_target` / `--target-secret` into the legacy compatibility path
  for older config-reference callers.
- Kept `secret_only=True` accepted as a harmless top-level compatibility
  keyword; the top-level helper is always Vault-only.
- Updated README examples to avoid presenting advanced lower-level parameters
  as the normal usage path.

## 0.1.8

Direct Vault targeting without `config.ini`.

- Added direct `vault_id` plus `secret_name` support for Python callers and
  CLI use.
- Direct mode no longer requires a project section or secret reference in
  `config.ini`.
- Kept config-reference mode intact for callers using `secret_target`.
- Direct INI Vault payloads keep their own sections.
- Direct headerless `key=value` payloads are placed under `[secret]`.
- Direct plain string payloads are placed under `[secret]` as `value = ...`
  when callers request a `ConfigParser`.
- Added README samples showing direct Vault calls and how callers can handle
  either a returned string or `configparser.ConfigParser`.

## 0.1.7

Auto-return convenience API.

- Updated `oci_secret_helper.get_secret(...)` and callable
  `oci_secret_helper(...)` to support both single-value secrets and full config
  payloads.
- Single-value payloads return a string.
- Multi-value payloads return a `configparser.ConfigParser`.
- `load_secret_config(...)` remains available for callers that always want a
  `ConfigParser`.

## 0.1.6

Simplified top-level Python API.

- Added `oci_secret_helper.get_secret(...)` for single-value secrets.
- Added `oci_secret_helper.load_secret_config(...)` as a friendlier alias for
  returning a `ConfigParser`.
- Made the imported package module callable as a convenience, delegating to
  `get_secret(...)`.
- Single-value helper calls use `config=...` and `secret_target=...` parameter
  names while keeping the existing lower-level API intact.

## 0.1.5

Python 3.6 OCI SDK import reduction.

- Set `OCI_PYTHON_SDK_NO_SERVICE_IMPORTS=1` before loading OCI SDK modules.
- Import only the OCI SDK pieces required for this helper:
  `NoneRetryStrategy`, `InstancePrincipalsSecurityTokenSigner`, and
  `SecretsClient`.
- Avoids Python 3.6 eager-loading every OCI service module during the first
  Vault fetch.

## 0.1.4

Import-time performance improvement.

- Lazy-load the OCI SDK only when a Vault client is actually needed.
- Cache the instance-principal `SecretsClient` for repeated secret loads within
  the same Python process.
- This makes `import oci_secret_helper` fast; the OCI SDK startup cost moves to
  the first real Vault fetch.
- Added README examples showing how to use the returned `ConfigParser`
  directly and how to merge fetched Vault values into an existing parser.

## 0.1.3

Headerless and raw secret payload support.

- Headerless `key=value` Vault payloads are supported.
- Single raw string Vault payloads are supported without requiring
  `raw_section` or `raw_key` when `target_secret` maps to a config reference.
- Raw strings are placed under the target config section using the configured
  reference key.
- Example: `[dbpsu] dbpsu_user_pw = dbpsu_password_secret` plus Vault value
  `secret-password` returns `config["dbpsu"]["dbpsu_user_pw"]`.

## 0.1.2

Vault-only return mode.

- Added `secret_only=True` for Python callers.
- Added CLI flag `--secret-only`.
- Added environment support via `RUNTIME_SECRET_ONLY=1`.
- `config.ini` is still used to resolve vault and secret references, but the
  returned config contains only the fetched Vault payload.
- Prevents local `config.ini` sections, such as `[dbpsu]`, from appearing in
  output when callers only want Vault contents.

## 0.1.1

Python 3.6 test-environment support.

- Lowered package metadata from `requires-python = ">=3.9"` to
  `requires-python = ">=3.6"`.
- Adjusted the dev pytest range for Python 3.6 compatibility.
- Bumped the version so Artifactory exposes a Python 3.6-compatible wheel.
- No Vault parsing behavior changed in this release.

## 0.1.0

Initial packaged helper.

- Created the `oci-secret-helper` package.
- Added the `oci-secret-helper` CLI.
- Added the `oci_secret_helper` Python import API.
- Added support for loading OCI Vault secrets into an in-memory
  `ConfigParser`.
- Added support for INI-style Vault payloads.
- Added `--target-secret` to choose which configured secret reference to fetch.
- Initial package metadata required Python 3.9 or newer.
