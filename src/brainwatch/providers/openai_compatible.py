"""Adapter for explicitly allowlisted OpenAI-compatible providers."""

from __future__ import annotations

import os
from collections.abc import Mapping

import requests

from brainwatch.config import ProviderConfig
from brainwatch.models import ModelCandidate, ProbeRecord
from brainwatch.security import get_secret

from .base import ProviderError, capability_tags, endpoint_url, positive_int
from .probe import perform_chat_probe


class OpenAICompatibleProvider:
    def __init__(
        self,
        config: ProviderConfig,
        *,
        request_timeout_seconds: float = 25.0,
        session: requests.Session | None = None,
        environ: Mapping[str, str] | None = None,
    ) -> None:
        self.name = config.name
        self.config = config
        self.request_timeout_seconds = request_timeout_seconds
        self.session = session or requests.Session()
        self.environ = os.environ if environ is None else environ

    def _secret(self) -> str:
        return get_secret(self.config.api_key_env, self.environ)

    def discover_models(self) -> list[ModelCandidate]:
        response = self.session.get(
            endpoint_url(self.config.base_url, self.config.models_path),
            headers={"Authorization": f"Bearer {self._secret()}"},
            timeout=(min(5.0, self.request_timeout_seconds), self.request_timeout_seconds),
        )
        if not 200 <= response.status_code < 300:
            raise ProviderError(f"{self.name} catalog returned HTTP {response.status_code}")
        try:
            payload = response.json()
        except ValueError as exc:
            raise ProviderError(f"{self.name} catalog returned invalid JSON") from exc
        rows = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(rows, list):
            raise ProviderError(f"{self.name} catalog has no data list")

        allowed = set(self.config.free_models)
        candidates: list[ModelCandidate] = []
        for raw in rows:
            if not isinstance(raw, dict) or not isinstance(raw.get("id"), str):
                continue
            model_id = raw["id"]
            name = raw.get("name") if isinstance(raw.get("name"), str) else model_id
            verified = model_id in allowed
            candidates.append(
                ModelCandidate(
                    provider=self.name,
                    model_id=model_id,
                    display_name=name,
                    context_length=positive_int(raw.get("context_length")),
                    tags=capability_tags(model_id, name),
                    cost_verified=verified,
                    prompt_price="0" if verified else None,
                    completion_price="0" if verified else None,
                )
            )
        return candidates

    def probe(self, candidate: ModelCandidate) -> ProbeRecord:
        return perform_chat_probe(
            provider_name=self.name,
            model_id=candidate.model_id,
            url=endpoint_url(self.config.base_url, self.config.chat_path),
            api_key=self._secret(),
            timeout_seconds=self.request_timeout_seconds,
            session=self.session,
        )
