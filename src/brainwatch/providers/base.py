"""Provider protocol and shared normalization helpers."""

from __future__ import annotations

from typing import Protocol
from urllib.parse import urlsplit

from brainwatch.models import ModelCandidate, ProbeRecord


class ProviderError(RuntimeError):
    """Raised when a provider cannot discover or probe models."""


class Provider(Protocol):
    name: str

    def discover_models(self) -> list[ModelCandidate]: ...

    def probe(self, candidate: ModelCandidate) -> ProbeRecord: ...


def endpoint_url(base_url: str, path: str) -> str:
    """Join a configured endpoint path without permitting an origin change."""
    parsed = urlsplit(path)
    if (
        not path.startswith("/")
        or path.startswith("//")
        or parsed.scheme
        or parsed.netloc
        or ".." in path.split("/")
    ):
        raise ValueError("endpoint path must be an absolute path on the configured origin")
    return f"{base_url.rstrip('/')}{path}"


def capability_tags(model_id: str, name: str = "") -> tuple[str, ...]:
    text = f"{model_id} {name}".lower()
    tags: list[str] = []
    if any(word in text for word in ("code", "coder", "coding", "laguna")):
        tags.append("coding")
    if any(word in text for word in ("reason", "thinking", "r1", "nemotron")):
        tags.append("reasoning")
    if any(word in text for word in ("vision", "vl", "multimodal")):
        tags.append("vision")
    if not tags or any(word in text for word in ("chat", "instruct", "general")):
        tags.append("general")
    return tuple(dict.fromkeys(tags))


def positive_int(value: object, default: int = 0) -> int:
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return default
