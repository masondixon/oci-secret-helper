import argparse
import base64
import io
import os
import sys
import warnings

import pytest

import oci_secret_helper as helper
from oci_secret_helper import dynamic_ini


def test_importing_helper_does_not_import_oci_sdk():
    assert "oci" not in sys.modules


def test_instance_principal_secrets_client_uses_cached_client():
    sentinel_client = object()
    dynamic_ini._SECRETS_CLIENT = sentinel_client
    try:
        assert dynamic_ini.instance_principal_secrets_client() is sentinel_client
    finally:
        dynamic_ini._SECRETS_CLIENT = None


def test_oci_sdk_no_service_import_flag_is_set(monkeypatch):
    monkeypatch.delenv("OCI_PYTHON_SDK_NO_SERVICE_IMPORTS", raising=False)
    dynamic_ini.enable_oci_sdk_no_service_imports()
    assert os.environ["OCI_PYTHON_SDK_NO_SERVICE_IMPORTS"] == "1"


def test_python36_cryptography_warning_is_suppressed():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        dynamic_ini.suppress_python36_cryptography_warning()
        warnings.warn(
            "Python 3.6 is no longer supported by the Python core team. "
            "Therefore, support for it is deprecated in cryptography.",
            DeprecationWarning,
        )
        warnings.warn("some other warning", DeprecationWarning)

    assert len(caught) == 1
    assert str(caught[0].message) == "some other warning"


def test_vault_secret_requests_require_direct_values(monkeypatch):
    monkeypatch.delenv("OCI_VAULT_OCID", raising=False)
    monkeypatch.delenv("OCI_VAULT_SECRET_NAME", raising=False)

    with pytest.raises(ValueError, match="Missing vault_id"):
        list(dynamic_ini.vault_secret_requests(secret_name="app_secret"))

    with pytest.raises(ValueError, match="Missing secret_name"):
        list(dynamic_ini.vault_secret_requests(vault_id="ocid1.vault.example"))


def test_vault_secret_requests_support_environment(monkeypatch):
    monkeypatch.setenv("OCI_VAULT_OCID", "ocid1.vault.example")
    monkeypatch.setenv("OCI_VAULT_SECRET_NAME", "app_secret")

    assert list(dynamic_ini.vault_secret_requests()) == [
        {
            "vault_id": "ocid1.vault.example",
            "secret_name": "app_secret",
            "secret_name_key": "value",
            "section": "secret",
        }
    ]


def test_parse_secret_as_config_supports_ini_payload():
    config = dynamic_ini.parse_secret_as_config(
        """
[default]
api_token = token
api_endpoint = endpoint
""",
        section="secret",
        key="value",
    )

    assert config.sections() == ["default"]
    assert config["default"]["api_token"] == "token"
    assert config["default"]["api_endpoint"] == "endpoint"


def test_parse_secret_as_config_supports_headerless_key_value_payload():
    config = dynamic_ini.parse_secret_as_config(
        "app_password = example-secret-value",
        section="secret",
        key="value",
    )

    assert config.sections() == ["secret"]
    assert config["secret"]["app_password"] == "example-secret-value"


def test_parse_secret_as_config_preserves_unspaced_equals_as_raw_secret():
    config = dynamic_ini.parse_secret_as_config(
        "token==",
        section="secret",
        key="value",
    )

    assert config.sections() == ["secret"]
    assert config["secret"]["value"] == "token=="


def test_parse_secret_as_config_can_force_unspaced_key_value_payload():
    config = dynamic_ini.parse_secret_as_config(
        "app_password=example-secret-value",
        section="secret",
        key="value",
        secret_format="key_value",
    )

    assert config.sections() == ["secret"]
    assert config["secret"]["app_password"] == "example-secret-value"


def test_parse_secret_as_config_preserves_percent_characters():
    config = dynamic_ini.parse_secret_as_config(
        "abc%def",
        section="secret",
        key="value",
    )

    assert config.sections() == ["secret"]
    assert config["secret"]["value"] == "abc%def"


def test_load_runtime_config_supports_direct_secret_text():
    config = dynamic_ini.load_runtime_config(
        vault_id="ocid1.vault.example",
        secret_name="app_secret",
        secret_text="example-secret-value",
    )

    assert config.sections() == ["secret"]
    assert config["secret"]["value"] == "example-secret-value"


def test_load_runtime_config_fetches_secret_payload(monkeypatch):
    monkeypatch.setattr(
        dynamic_ini,
        "load_secret_payloads",
        lambda **_kwargs: [
            (
                {
                    "section": "secret",
                    "secret_name_key": "value",
                },
                "example-secret-value",
            )
        ],
    )

    config = dynamic_ini.load_runtime_config(
        vault_id="ocid1.vault.example",
        secret_name="app_secret",
    )

    assert config.sections() == ["secret"]
    assert config["secret"]["value"] == "example-secret-value"


def test_load_secret_texts_fetches_and_decodes_secret(monkeypatch):
    class FakeContent:
        content = base64.b64encode(b"example-secret-value").decode("ascii")

    class FakeBundle:
        secret_bundle_content = FakeContent()

    class FakeResponse:
        data = FakeBundle()

    class FakeClient:
        def get_secret_bundle_by_name(self, secret_name, vault_id):
            assert secret_name == "app_secret"
            assert vault_id == "ocid1.vault.example"
            return FakeResponse()

    monkeypatch.setattr(
        dynamic_ini,
        "instance_principal_secrets_client",
        lambda: FakeClient(),
    )

    assert list(
        dynamic_ini.load_secret_texts(
            vault_id="ocid1.vault.example",
            secret_name="app_secret",
        )
    ) == ["example-secret-value"]


def test_package_callable_returns_single_secret_value():
    assert helper(
        vault_id="ocid1.vault.example",
        secret_name="app_secret",
        secret_text="example-secret-value",
    ) == "example-secret-value"


def test_package_callable_returns_config_for_multi_value_secret():
    config = helper(
        vault_id="ocid1.vault.example",
        secret_name="app_secret",
        secret_text="""
[default]
api_token = token
api_endpoint = endpoint
""",
    )

    assert config.sections() == ["default"]
    assert config["default"]["api_token"] == "token"


def test_package_callable_requires_direct_values():
    with pytest.raises(ValueError, match="Pass vault_id"):
        helper(secret_text="example-secret-value")


def test_secret_section_lines_redacts_values_by_default():
    config = dynamic_ini.parse_secret_as_config(
        "example-secret-value",
        section="secret",
        key="value",
    )

    assert list(dynamic_ini.secret_section_lines(config)) == [
        "[secret]",
        "value = <redacted>",
    ]
    assert list(dynamic_ini.secret_section_lines(config, reveal_values=True)) == [
        "[secret]",
        "value = example-secret-value",
    ]


def test_write_raw_secret_texts_adds_final_newline():
    stream = io.StringIO()

    dynamic_ini.write_raw_secret_texts(["one", "two\n"], stream=stream)

    assert stream.getvalue() == "one\ntwo\n"


def run_main(monkeypatch, capsys, **kwargs):
    args = argparse.Namespace(
        vault_id="ocid1.vault.example",
        secret_name="app_secret",
        secret_format="auto",
        raw=False,
        echo_secret_sections=False,
        echo_secret_values=False,
    )
    for key, value in kwargs.items():
        setattr(args, key, value)

    monkeypatch.setattr(dynamic_ini, "parse_args", lambda: args)
    monkeypatch.setattr(
        dynamic_ini,
        "load_secret_payloads",
        lambda **_kwargs: [
            (
                {
                    "section": "secret",
                    "secret_name_key": "value",
                },
                "example-secret-value",
            )
        ],
    )
    dynamic_ini.main()
    return capsys.readouterr()


def test_main_prints_raw_secret(monkeypatch, capsys):
    captured = run_main(monkeypatch, capsys, raw=True)

    assert captured.out == "example-secret-value\n"


def test_main_auto_prints_plain_secret_with_echo_values(monkeypatch, capsys):
    captured = run_main(monkeypatch, capsys, echo_secret_values=True)

    assert captured.out == "example-secret-value\n"


def test_main_prints_redacted_section_summary(monkeypatch, capsys):
    captured = run_main(monkeypatch, capsys, echo_secret_sections=True)

    assert captured.out == (
        "Loaded runtime secret config in memory. Secret sections (1): secret\n"
        "[secret]\n"
        "value = <redacted>\n"
    )


def test_parse_args_requires_direct_identifiers(monkeypatch):
    monkeypatch.delenv("OCI_VAULT_OCID", raising=False)
    monkeypatch.delenv("OCI_VAULT_SECRET_NAME", raising=False)
    monkeypatch.setattr(sys, "argv", ["oci-secret-helper"])

    with pytest.raises(SystemExit):
        dynamic_ini.parse_args()
