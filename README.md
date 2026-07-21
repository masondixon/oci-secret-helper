# OCI Secret Helper

Load a named OCI Vault secret from Python or bash using instance principals.

The normal consumer inputs are:

- `vault_id`: OCI Vault OCID
- `secret_name`: name of the secret inside that Vault

See [CHANGELOG.md](CHANGELOG.md) for version history.

## Install

Install from PyPI:

```bash
python -m pip install oci-secret-helper==0.1.18
```

This installs the required `oci>=2` dependency from PyPI as well.

## Vault Secret Usage

The normal call uses a Vault OCID and secret name:

```python
import oci_secret_helper

config = oci_secret_helper(
    vault_id="ocid1.vault.oc1.iad...",
    secret_name="app_config_secret",
)
```

## Encrypted Object Storage Configs

The existing `vault_id` and `secret_name` call shape also supports encrypted
Object Storage configuration. The KMS/Object Storage arguments are optional
and default to `None`, so ordinary Vault-secret loading stays the default:

```python
import oci_secret_helper

config = oci_secret_helper(
    vault_id="ocid1.vault.oc1.iad...",
    secret_name="configs/customer-a.ini.enc",
    kms_key_id="ocid1.key.oc1.iad...",
    object_storage_bucket="runtime-config",
)
```

`vault_id` identifies the Vault containing the KMS key. `secret_name` becomes
the encrypted object name only when both `kms_key_id` and
`object_storage_bucket` are supplied; otherwise it continues to identify a
Vault secret. The helper gets the Object Storage namespace automatically.
Pass `object_storage_namespace=` to override it, or
`object_storage_object_name=` to override the object name.

The object must contain a client-side KMS encrypted, sectioned INI file. The
ciphertext is fetched and decrypted only in memory. If only part of the KMS /
Object Storage configuration is present, startup fails rather than silently
falling back to Vault-secret mode.

This test-phase build supports Python 3.6 and newer. Before production, move
`requires-python` back to `>=3.9` and publish a new version.

## Releases

The GitHub Actions release workflow runs on pushes to `main`. It tests the
package, builds distributions, validates them with Twine, and publishes to
PyPI using the repository's configured PyPI trusted-publishing environment.

Increment the version in `pyproject.toml` before merging a release:

```toml
version = "0.1.18"
```

PyPI does not allow replacing an existing release, so every publish must use a
new version. No PyPI token belongs in this repository or its workflow: the
publish job uses GitHub OIDC trusted publishing.

Consumers install the public package normally:

```bash
python -m pip install oci-secret-helper==0.1.18
```

## Python Usage

Fetch by Vault OCID and secret name:

```python
import oci_secret_helper

result = oci_secret_helper(
    vault_id="ocid1.vault.oc1.iad...",
    secret_name="app_config_secret",
)
```

Single-value secrets return a string:

```python
password = oci_secret_helper(
    vault_id="ocid1.vault.oc1.iad...",
    secret_name="app_password_secret",
)
```

INI-style secrets with multiple values return a `configparser.ConfigParser`:

```python
config = oci_secret_helper(
    vault_id="ocid1.vault.oc1.iad...",
    secret_name="app_config_secret",
)

token = config["default"]["api_token"]
```

Use `load_secret_config()` when you always want a `ConfigParser`, even for a
plain string secret:

```python
config = oci_secret_helper.load_secret_config(
    vault_id="ocid1.vault.oc1.iad...",
    secret_name="app_password_secret",
)

password = config["secret"]["value"]
```

If a single-line payload contains `=` and should be parsed as headerless
`key=value` config, force that shape:

```python
config = oci_secret_helper.load_secret_config(
    vault_id="ocid1.vault.oc1.iad...",
    secret_name="app_password_secret",
    secret_format="key_value",
)

password = config["secret"]["app_password"]
```

## Bash Usage

Fetch a secret:

```bash
oci-secret-helper \
  --vault-id "ocid1.vault.oc1.iad..." \
  --secret-name "app_config_secret"
```

Show secret values:

```bash
oci-secret-helper \
  --vault-id "ocid1.vault.oc1.iad..." \
  --secret-name "app_password_secret" \
  --echo-secret-values
```

Plain string secrets are detected automatically, so stdout is just the secret
value:

```text
example-secret-value
```

INI or `key=value` payloads keep the config-shaped output. To force the exact
Vault payload to stdout for any payload type, use `--raw`:

```bash
oci-secret-helper \
  --vault-id "ocid1.vault.oc1.iad..." \
  --secret-name "app_password_secret" \
  --raw
```

To force a headerless `key=value` payload to print as config-shaped output:

```bash
oci-secret-helper \
  --vault-id "ocid1.vault.oc1.iad..." \
  --secret-name "app_password_secret" \
  --echo-secret-values \
  --secret-format key-value
```

Without `--echo-secret-values`, the CLI redacts values. Use
`--raw` or `--echo-secret-values` only in a protected shell because secrets can
land in terminal scrollback or logs.

## Secret Payloads

The Vault secret payload can be one of these shapes:

```text
example-secret-value
```

```ini
app_password = example-secret-value
```

```ini
[default]
api_token = example-token
api_endpoint = example-endpoint
```

Plain string secrets are normalized to this shape when returned as a
`ConfigParser` or printed by the CLI:

```ini
[secret]
value = example-secret-value
```

Secret values are treated literally. Characters such as `%` are preserved and
are not interpreted as `ConfigParser` interpolation syntax.

In auto mode, a single-line secret with `=` but no whitespace around the
separator, such as `token==` or `abc=def`, is treated as a raw string to avoid
silently changing passwords or tokens. Use `secret_format="key_value"` in
Python or `--secret-format key-value` in bash when an unspaced single-line
payload should be parsed as headerless config.

## Performance Notes

The helper sets `OCI_PYTHON_SDK_NO_SERVICE_IMPORTS=1` before loading the OCI
SDK and imports only the SDK objects needed for Vault reads:

- `oci.retry.NoneRetryStrategy`
- `oci.auth.signers.InstancePrincipalsSecurityTokenSigner`
- `oci.secrets.SecretsClient`

This avoids Python 3.6 eager-loading every OCI service module during the first
Vault fetch.

The helper also suppresses the known Python 3.6 cryptography deprecation
warning emitted by OCI SDK imports in the test environment.

## Maintainers

Build the wheel:

```bash
python -m pip wheel . --no-deps --no-build-isolation -w dist
```

Upload to PyPI manually only when needed:

```bash
python -m twine upload dist/*
```
