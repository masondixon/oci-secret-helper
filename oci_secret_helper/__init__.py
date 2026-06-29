"""Public API for OCI Secret Helper."""

import sys
import types

from oci_secret_helper.dynamic_ini import (
    add_sections,
    fetch_vault_secret_text,
    load_runtime_config,
    load_secret_texts,
    parse_secret_as_config,
    secret_section_lines,
    secret_sections,
    suppress_python36_cryptography_warning,
    write_raw_secret_texts,
)


def load_secret_config(
    *,
    vault_id=None,
    secret_name=None,
    secret_text=None,
    **kwargs
):
    if not vault_id or not secret_name:
        raise ValueError(
            "Pass vault_id=... and secret_name=..."
        )

    return load_runtime_config(
        vault_id=vault_id,
        secret_name=secret_name,
        secret_text=secret_text,
        **kwargs
    )


def get_secret(
    *,
    vault_id=None,
    secret_name=None,
    secret_text=None,
    **kwargs
):
    secret_config = load_secret_config(
        vault_id=vault_id,
        secret_name=secret_name,
        secret_text=secret_text,
        **kwargs
    )
    return secret_value_or_config(secret_config)


def secret_value_or_config(config):
    if count_secret_values(config) == 1:
        return single_secret_value(config)
    return config


def count_secret_values(config):
    count = 0
    for section in config.sections():
        count += len(config.items(section))
    return count


def single_secret_value(config):
    values = []
    for section in config.sections():
        for key, value in config.items(section):
            values.append((section, key, value))

    if len(values) != 1:
        raise ValueError(
            "Expected exactly one secret value; found "
            f"{len(values)}. Use load_secret_config() or load_runtime_config() "
            "for multi-value secrets."
        )

    return values[0][2]


class _CallableModule(types.ModuleType):
    def __call__(self, *args, **kwargs):
        return get_secret(*args, **kwargs)


sys.modules[__name__].__class__ = _CallableModule


__all__ = [
    "add_sections",
    "fetch_vault_secret_text",
    "get_secret",
    "load_secret_config",
    "load_runtime_config",
    "load_secret_texts",
    "parse_secret_as_config",
    "secret_section_lines",
    "secret_sections",
    "secret_value_or_config",
    "single_secret_value",
    "suppress_python36_cryptography_warning",
    "write_raw_secret_texts",
]
