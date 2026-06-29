# OCI Secret Helper

Load a named OCI Vault secret from Python or bash using instance principals.

The normal consumer inputs are:

- `vault_id`: OCI Vault OCID
- `secret_name`: name of the secret inside that Vault

See [CHANGELOG.md](CHANGELOG.md) for version history.

## Install

Install from your package index:

```bash
python -m pip install \
  --index-url "https://PACKAGE_INDEX_HOST/path/to/simple" \
  oci-secret-helper==0.1.16
```

This package depends on `oci>=2`. The configured Artifactory index must host or
proxy the OCI Python SDK, or the SDK must already be installed in the target
environment.

This test-phase build supports Python 3.6 and newer. Before production, move
`requires-python` back to `>=3.9` and publish a new version.

## Release Build

GitLab CI builds the wheel from the version in `pyproject.toml`:

```toml
version = "0.1.16"
```

Merge request pipelines run tests and build the wheel once for validation. When
the change lands on the default branch, the pipeline runs tests, builds the
wheel, and promotes it to the configured Artifactory PyPI repository.

Increment `pyproject.toml` for every change that should publish a new package
version:

```toml
version = "0.1.17"
```

Artifactory rejects duplicate package versions, so the default-branch promote
job expects the package version to be new.

Branch pipelines are suppressed when a merge request pipeline exists, so test
and build do not run twice for the same commit.

The promote job requires these protected GitLab CI/CD variables:

```text
ARTIFACTORY_PYPI_REPOSITORY_URL=https://PACKAGE_INDEX_HOST/path/to/repository
ARTIFACTORY_USERNAME=<username>
ARTIFACTORY_PASSWORD=<password-or-token>
```

Consumers install from the repository's `/simple` endpoint:

```bash
python -m pip install \
  --index-url "https://PACKAGE_INDEX_HOST/path/to/simple" \
  oci-secret-helper==0.1.16
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

Upload to a Python package index:

```bash
python -m twine upload \
  --repository-url "https://PACKAGE_INDEX_HOST/path/to/repository" \
  dist/oci_secret_helper-0.1.16-py3-none-any.whl
```
