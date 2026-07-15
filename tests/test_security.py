from __future__ import annotations

import pytest

from brainwatch.security import SecretError, get_secret, redact_text


def test_get_secret_names_missing_variable_without_value() -> None:
    with pytest.raises(SecretError, match="MODEL_API_KEY") as exc:
        get_secret("MODEL_API_KEY", environ={})
    assert "secret-value" not in str(exc.value)


def test_redact_text_removes_tokens_explicit_secrets_and_truncates() -> None:
    text = "Authorization: Bearer abc.def-123 sk-or-v1-supersecret visible " + "x" * 200
    redacted = redact_text(text, secret_values=("visible",), max_length=80)
    assert "abc.def-123" not in redacted
    assert "sk-or-v1-supersecret" not in redacted
    assert "visible" not in redacted
    assert "<REDACTED>" in redacted
    assert len(redacted) <= 80


def test_empty_secret_name_rejected() -> None:
    with pytest.raises(SecretError, match="environment variable name"):
        get_secret("", environ={})
