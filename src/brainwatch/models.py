"""Normalized model and probe records shared by every provider."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True, slots=True)
class ModelCandidate:
    provider: str
    model_id: str
    display_name: str
    context_length: int
    tags: tuple[str, ...]
    cost_verified: bool
    prompt_price: str | None = None
    completion_price: str | None = None

    @property
    def key(self) -> str:
        return f"{self.provider}:{self.model_id}"

    def to_dict(self) -> dict[str, object]:
        result = asdict(self)
        result["model_key"] = self.key
        result["tags"] = list(self.tags)
        return result


@dataclass(frozen=True, slots=True)
class ProbeRecord:
    provider: str
    model_id: str
    timestamp: float
    status: str
    latency_ms: float | None
    parsed_ok: bool
    mode: str | None
    attempts: int
    recovered: bool
    http_status: int | None
    error: str | None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None

    @property
    def key(self) -> str:
        return f"{self.provider}:{self.model_id}"

    def to_dict(self) -> dict[str, object]:
        result = asdict(self)
        result["model_key"] = self.key
        return result
