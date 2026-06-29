"""Fetch an OCI Vault secret into an in-memory runtime config."""

import argparse
import base64
import configparser
import os
import sys
import warnings


OCI_TIMEOUT = (5, 15)
_SECRETS_CLIENT = None
DIRECT_SECRET_SECTION = "secret"
DIRECT_SECRET_KEY = "value"
SECRET_FORMAT_AUTO = "auto"
SECRET_FORMAT_RAW = "raw"
SECRET_FORMAT_KEY_VALUE = "key_value"
SECRET_FORMAT_INI = "ini"
PYTHON36_CRYPTOGRAPHY_WARNING = (
    "Python 3.6 is no longer supported by the Python core team.*"
)


def suppress_python36_cryptography_warning():
    warnings.filterwarnings(
        "ignore",
        message=PYTHON36_CRYPTOGRAPHY_WARNING,
    )


suppress_python36_cryptography_warning()


def parse_args():
    parser = argparse.ArgumentParser(
        description="Fetch an OCI Vault secret by Vault OCID and secret name."
    )
    parser.add_argument(
        "--vault-id",
        default=os.environ.get("OCI_VAULT_OCID"),
        required=not os.environ.get("OCI_VAULT_OCID"),
        help="OCI Vault OCID. Can also be set with OCI_VAULT_OCID.",
    )
    parser.add_argument(
        "--secret-name",
        default=os.environ.get("OCI_VAULT_SECRET_NAME"),
        required=not os.environ.get("OCI_VAULT_SECRET_NAME"),
        help="Vault secret name. Can also be set with OCI_VAULT_SECRET_NAME.",
    )
    parser.add_argument(
        "--secret-format",
        default=os.environ.get("RUNTIME_SECRET_FORMAT", SECRET_FORMAT_AUTO),
        choices=(
            SECRET_FORMAT_AUTO,
            SECRET_FORMAT_RAW,
            SECRET_FORMAT_KEY_VALUE,
            "key-value",
            SECRET_FORMAT_INI,
        ),
        help=(
            "Vault payload format. Defaults to auto. Use raw to preserve an "
            "exact string, key-value for headerless key=value payloads, or ini "
            "for sectioned INI payloads."
        ),
    )
    parser.add_argument(
        "--echo-secret-sections",
        action="store_true",
        help="Print loaded secret sections with values redacted.",
    )
    parser.add_argument(
        "--echo-secret-values",
        action="store_true",
        help="Print loaded secret section values. Use only in protected environments.",
    )
    parser.add_argument(
        "--raw",
        dest="raw",
        action="store_true",
        help="Print only the fetched Vault payload. Use only in protected environments.",
    )
    return parser.parse_args()


def runtime_config_parser():
    return configparser.ConfigParser(interpolation=None)


def normalize_secret_format(secret_format=None):
    normalized_format = secret_format or SECRET_FORMAT_AUTO
    normalized_format = normalized_format.replace("-", "_")
    allowed_formats = {
        SECRET_FORMAT_AUTO,
        SECRET_FORMAT_RAW,
        SECRET_FORMAT_KEY_VALUE,
        SECRET_FORMAT_INI,
    }
    if normalized_format not in allowed_formats:
        raise ValueError(
            "Unsupported secret_format "
            f"{secret_format!r}. Use auto, raw, key_value, or ini."
        )
    return normalized_format


def vault_secret_requests(vault_id=None, secret_name=None):
    resolved_vault_id = vault_id or os.environ.get("OCI_VAULT_OCID")
    resolved_secret_name = secret_name or os.environ.get("OCI_VAULT_SECRET_NAME")
    if not resolved_vault_id:
        raise ValueError("Missing vault_id.")
    if not resolved_secret_name:
        raise ValueError("Missing secret_name.")

    yield direct_secret_request(
        vault_id=resolved_vault_id,
        secret_name=resolved_secret_name,
    )


def direct_secret_request(vault_id, secret_name):
    return {
        "vault_id": vault_id,
        "secret_name": secret_name,
        "secret_name_key": DIRECT_SECRET_KEY,
        "section": DIRECT_SECRET_SECTION,
    }


def load_runtime_config(
    vault_id=None,
    secret_name=None,
    secret_text=None,
    secret_format=SECRET_FORMAT_AUTO,
):
    runtime_config = runtime_config_parser()
    if secret_text is None:
        payloads = load_secret_payloads(
            vault_id=vault_id,
            secret_name=secret_name,
        )
        return add_secret_payloads(
            runtime_config,
            payloads,
            secret_format=secret_format,
        )

    secret_config = parse_secret_as_config(
        secret_text,
        section=DIRECT_SECRET_SECTION,
        key=DIRECT_SECRET_KEY,
        secret_format=secret_format,
    )
    add_sections(runtime_config, secret_config)
    return runtime_config


def load_secret_payloads(
    vault_id=None,
    secret_name=None,
):
    requests = list(vault_secret_requests(
        vault_id=vault_id,
        secret_name=secret_name,
    ))

    client = instance_principal_secrets_client()
    for request in requests:
        yield (
            request,
            fetch_vault_secret_text(
                client,
                request["vault_id"],
                request["secret_name"],
            ),
        )


def load_secret_texts(
    vault_id=None,
    secret_name=None,
):
    for _request, secret_text in load_secret_payloads(
        vault_id=vault_id,
        secret_name=secret_name,
    ):
        yield secret_text


def add_secret_payloads(
    runtime_config,
    payloads,
    secret_format=SECRET_FORMAT_AUTO,
):
    for request, secret_text in payloads:
        secret_config = parse_secret_as_config(
            secret_text,
            section=request["section"],
            key=request["secret_name_key"],
            secret_format=secret_format,
        )
        add_sections(runtime_config, secret_config)
    return runtime_config


def should_auto_raw_secret_texts(secret_texts):
    return len(secret_texts) == 1 and looks_like_raw_string_secret(secret_texts[0])


def looks_like_raw_string_secret(secret_text):
    stripped_secret = secret_text.strip()
    return (
        bool(stripped_secret)
        and not looks_like_ini(stripped_secret)
        and not looks_like_auto_key_value_secret(stripped_secret)
    )


def write_raw_secret_texts(secret_texts, stream=None):
    stream = stream or sys.stdout
    wrote_text = False
    last_text = None
    for secret_text in secret_texts:
        if wrote_text and last_text and not last_text.endswith("\n"):
            stream.write("\n")
        stream.write(secret_text)
        wrote_text = True
        last_text = secret_text
    if wrote_text and last_text and not last_text.endswith("\n"):
        stream.write("\n")


def add_sections(base_config, overlay_config):
    for section in overlay_config.sections():
        if not base_config.has_section(section):
            base_config.add_section(section)
        for key, value in overlay_config.items(section):
            base_config.set(section, key, value)
    return base_config


def secret_sections(
    config,
    excluded_sections=None,
    reference_key_suffixes=("_secret_name", "_sensitive_values", "_config"),
):
    excluded_sections = set(excluded_sections or ())
    for section in config.sections():
        if section in excluded_sections:
            continue
        values = dict(config.items(section))
        if is_secret_reference_section(values, reference_key_suffixes):
            continue
        yield section, values


def secret_section_lines(config, excluded_sections=None, reveal_values=False):
    for section, values in secret_sections(
        config,
        excluded_sections=excluded_sections,
    ):
        yield f"[{section}]"
        for key, value in values.items():
            display_value = value if reveal_values else "<redacted>"
            yield f"{key} = {display_value}"


def is_secret_reference_section(
    values,
    reference_key_suffixes=("_secret_name", "_sensitive_values", "_config"),
):
    if not values:
        return False
    return all(
        any(key.endswith(suffix) for suffix in reference_key_suffixes)
        for key in values
    )


def instance_principal_secrets_client():
    global _SECRETS_CLIENT

    if _SECRETS_CLIENT is not None:
        return _SECRETS_CLIENT

    (
        none_retry_strategy,
        instance_principals_signer,
        secrets_client,
    ) = oci_secrets_sdk()

    no_retry = none_retry_strategy()
    signer = instance_principals_signer(
        retry_strategy=no_retry,
        federation_client_retry_strategy=no_retry,
    )
    _SECRETS_CLIENT = secrets_client(
        {},
        signer=signer,
        timeout=OCI_TIMEOUT,
        retry_strategy=no_retry,
    )
    return _SECRETS_CLIENT


def oci_secrets_sdk():
    enable_oci_sdk_no_service_imports()

    from oci.auth.signers import InstancePrincipalsSecurityTokenSigner
    from oci.retry import NoneRetryStrategy
    from oci.secrets import SecretsClient

    return NoneRetryStrategy, InstancePrincipalsSecurityTokenSigner, SecretsClient


def enable_oci_sdk_no_service_imports():
    os.environ.setdefault("OCI_PYTHON_SDK_NO_SERVICE_IMPORTS", "1")


def fetch_vault_secret_text(client, vault_id, secret_name):
    bundle = client.get_secret_bundle_by_name(
        secret_name=secret_name,
        vault_id=vault_id,
    ).data
    encoded_content = bundle.secret_bundle_content.content
    return base64.b64decode(encoded_content).decode("utf-8")


def parse_secret_as_config(
    secret_text,
    section=None,
    key=None,
    secret_format=SECRET_FORMAT_AUTO,
):
    config = runtime_config_parser()
    stripped_secret = secret_text.strip()
    secret_format = normalize_secret_format(secret_format)

    if secret_format == SECRET_FORMAT_INI:
        config.read_string(stripped_secret)
        return config

    if secret_format == SECRET_FORMAT_KEY_VALUE:
        if not section:
            raise ValueError("A section name is required for key=value secret payloads.")
        config[section] = parse_key_value_secret(stripped_secret)
        return config

    if secret_format == SECRET_FORMAT_RAW:
        if not section or not key:
            raise ValueError("Section and key are required for raw secret payloads.")
        config[section] = {key: secret_text}
        return config

    if looks_like_ini(stripped_secret):
        config.read_string(stripped_secret)
        return config

    if looks_like_auto_key_value_secret(stripped_secret):
        if not section:
            raise ValueError("A section name is required for key=value secret payloads.")
        config[section] = parse_key_value_secret(stripped_secret)
        return config

    if not section or not key:
        raise ValueError("Section and key are required for raw secret payloads.")
    config[section] = {key: secret_text}
    return config


def looks_like_ini(secret_text):
    if not secret_text.startswith("["):
        return False

    config = runtime_config_parser()
    try:
        config.read_string(secret_text)
    except configparser.Error:
        return False

    return bool(config.sections())


def looks_like_key_value_secret(secret_text):
    lines = useful_lines(secret_text)
    return bool(lines) and all("=" in line for line in lines)


def looks_like_auto_key_value_secret(secret_text):
    lines = useful_lines(secret_text)
    if not lines or not all("=" in line for line in lines):
        return False
    if len(lines) > 1:
        return True
    return has_spaced_key_value_separator(lines[0])


def has_spaced_key_value_separator(line):
    separator_index = line.find("=")
    if separator_index < 0:
        return False
    has_left_space = separator_index > 0 and line[separator_index - 1].isspace()
    has_right_space = (
        separator_index + 1 < len(line)
        and line[separator_index + 1].isspace()
    )
    return has_left_space or has_right_space


def parse_key_value_secret(secret_text):
    values = {}
    for line in useful_lines(secret_text):
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("\"'")
    return values


def useful_lines(secret_text):
    return [
        line.strip()
        for line in secret_text.splitlines()
        if line.strip() and not line.strip().startswith(("#", ";"))
    ]


def main():
    args = parse_args()
    if args.raw or args.echo_secret_values:
        payloads = list(
            load_secret_payloads(
                vault_id=args.vault_id,
                secret_name=args.secret_name,
            )
        )
        secret_texts = [secret_text for _request, secret_text in payloads]
        should_auto_raw = (
            normalize_secret_format(args.secret_format) == SECRET_FORMAT_AUTO
            and should_auto_raw_secret_texts(secret_texts)
        )
        if args.raw or should_auto_raw:
            write_raw_secret_texts(secret_texts)
            return
        config = runtime_config_parser()
        add_secret_payloads(
            config,
            payloads,
            secret_format=args.secret_format,
        )
    else:
        config = load_runtime_config(
            vault_id=args.vault_id,
            secret_name=args.secret_name,
            secret_format=args.secret_format,
        )

    runtime_sections = [
        section for section, _values in secret_sections(config)
    ]
    loaded_sections = ", ".join(runtime_sections)
    print(
        "Loaded runtime secret config in memory. "
        f"Secret sections ({len(runtime_sections)}): {loaded_sections}"
    )
    if args.echo_secret_sections or args.echo_secret_values:
        for line in secret_section_lines(
            config,
            reveal_values=args.echo_secret_values,
        ):
            print(line)


if __name__ == "__main__":
    main()
