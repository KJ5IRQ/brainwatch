"""Credential handling and bounded redaction helpers."""

from __future__ import annotations

import os
import re
from collections.abc import Mapping, Sequence


class SecretError(RuntimeError):
    """Raised when a required credential is unavailable."""


_TOKEN_PATTERNS = (
    re.compile(r"(?i)(Bearer\s+)[A-Za-z0-9._~+/=-]+"),
    re.compile(r"\b(?:sk-(?:or-v1-|ant-)?|gsk_|pplx-|xai-|gh[pours]_-?|xox[abp]-)[A-Za-z0-9_-]{8,}\b"),
)


def get_secret(env_name: str, environ: Mapping[str, str] | None = None) -> str:
    if not isinstance(env_name, str) or not env_name.strip():
        raise SecretError("credential environment variable name must be non-empty")
    env = os.environ if environ is None else environ
    value = env.get(env_name)
    if not value:
        raise SecretError(f"required credential environment variable is not set: {env_name}")
    return value


def redact_text(
    text: object,
    *,
    secret_values: Sequence[str] = (),
    max_length: int = 512,
) -> str:
    """Redact common API tokens and explicit secret values, then bound the result."""
    result = str(text)
    for secret in sorted((item for item in secret_values if item), key=len, reverse=True):
        result = result.replace(secret, "<REDACTED>")
    for pattern in _TOKEN_PATTERNS:
        if pattern.groups:
            result = pattern.sub(r"\1<REDACTED>", result)
        else:
            result = pattern.sub("<REDACTED>", result)
    if max_length < 1:
        return ""
    if len(result) > max_length:
        suffix = "..."
        result = result[: max(0, max_length - len(suffix))] + suffix
    return result
