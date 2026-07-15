"""Bounded structured-output probes shared by provider adapters."""

from __future__ import annotations

import json
import time
from typing import Any

import requests

from brainwatch.models import ModelCandidate, ProbeRecord
from brainwatch.security import redact_text

_RETRYABLE = {"timeout", "rate_limited", "server_error"}
_PROBE_MESSAGE = (
    "Return only this JSON object with no markdown or explanation: "
    '{"ok": true, "n": 42}'
)


def _text_content(value: object) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts = [
            item.get("text")
            for item in value
            if isinstance(item, dict) and isinstance(item.get("text"), str)
        ]
        return "".join(parts) if parts else None
    return None


def _extract_expected_json(text: str) -> bool:
    decoder = json.JSONDecoder()
    for index, character in enumerate(text):
        if character != "{":
            continue
        try:
            value, _ = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and value.get("ok") is True and value.get("n") == 42:
            return True
    return False


def _parse_success(payload: object) -> tuple[bool, str | None, int | None, int | None]:
    if not isinstance(payload, dict):
        return False, None, None, None
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        return False, None, None, None
    message = choices[0].get("message")
    if not isinstance(message, dict):
        return False, None, None, None

    content = _text_content(message.get("content"))
    mode: str | None = None
    text: str | None = None
    if content:
        mode, text = "content", content
    elif isinstance(message.get("reasoning"), str):
        mode, text = "reasoning", message["reasoning"]

    usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
    prompt_tokens = usage.get("prompt_tokens")
    completion_tokens = usage.get("completion_tokens")
    prompt = prompt_tokens if isinstance(prompt_tokens, int) and prompt_tokens >= 0 else None
    completion = (
        completion_tokens
        if isinstance(completion_tokens, int) and completion_tokens >= 0
        else None
    )
    return bool(text and _extract_expected_json(text)), mode, prompt, completion


def _http_status(status: int) -> str:
    if status in {401, 403}:
        return "auth_error"
    if status == 402:
        return "payment_required"
    if status == 429:
        return "rate_limited"
    if status >= 500:
        return "server_error"
    return "http_error"


def _record(
    *,
    provider_name: str,
    model_id: str,
    status: str,
    started: float,
    attempts: int,
    http_status: int | None = None,
    error: object | None = None,
    parsed_ok: bool = False,
    mode: str | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    secret: str = "",
) -> ProbeRecord:
    return ProbeRecord(
        provider=provider_name,
        model_id=model_id,
        timestamp=round(time.time(), 3),
        status=status,
        latency_ms=round((time.monotonic() - started) * 1000, 3),
        parsed_ok=parsed_ok,
        mode=mode,
        attempts=attempts,
        recovered=status == "ok" and attempts > 1,
        http_status=http_status,
        error=(
            redact_text(error, secret_values=(secret,), max_length=300)
            if error is not None
            else None
        ),
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
    )


def _response_error(response: requests.Response, secret: str) -> str:
    try:
        payload: Any = response.json()
    except ValueError:
        return f"HTTP {response.status_code}"
    if isinstance(payload, dict) and payload.get("error") is not None:
        return redact_text(payload["error"], secret_values=(secret,), max_length=300)
    return f"HTTP {response.status_code}"


def perform_chat_probe(
    *,
    provider_name: str,
    model_id: str,
    url: str,
    api_key: str,
    timeout_seconds: float,
    session: requests.Session,
) -> ProbeRecord:
    """Run one tiny probe with at most one retry for transient failures."""
    started = time.monotonic()
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    body = {
        "model": model_id,
        "messages": [{"role": "user", "content": _PROBE_MESSAGE}],
        "temperature": 0,
        "max_tokens": 48,
    }
    for attempt in (1, 2):
        try:
            response = session.post(
                url,
                headers=headers,
                json=body,
                timeout=(min(5.0, timeout_seconds), timeout_seconds),
            )
        except requests.Timeout as exc:
            status = "timeout"
            if attempt == 1:
                continue
            return _record(
                provider_name=provider_name,
                model_id=model_id,
                status=status,
                started=started,
                attempts=attempt,
                error=exc,
                secret=api_key,
            )
        except requests.ConnectionError as exc:
            return _record(
                provider_name=provider_name,
                model_id=model_id,
                status="connection_error",
                started=started,
                attempts=attempt,
                error=exc,
                secret=api_key,
            )
        except requests.RequestException as exc:
            return _record(
                provider_name=provider_name,
                model_id=model_id,
                status="request_error",
                started=started,
                attempts=attempt,
                error=exc,
                secret=api_key,
            )

        if not 200 <= response.status_code < 300:
            status = _http_status(response.status_code)
            if attempt == 1 and status in _RETRYABLE:
                continue
            return _record(
                provider_name=provider_name,
                model_id=model_id,
                status=status,
                started=started,
                attempts=attempt,
                http_status=response.status_code,
                error=_response_error(response, api_key),
                secret=api_key,
            )

        try:
            payload = response.json()
        except ValueError as exc:
            return _record(
                provider_name=provider_name,
                model_id=model_id,
                status="bad_format",
                started=started,
                attempts=attempt,
                http_status=response.status_code,
                error=exc,
                secret=api_key,
            )
        parsed_ok, mode, prompt_tokens, completion_tokens = _parse_success(payload)
        return _record(
            provider_name=provider_name,
            model_id=model_id,
            status="ok" if parsed_ok else "bad_format",
            started=started,
            attempts=attempt,
            http_status=response.status_code,
            parsed_ok=parsed_ok,
            mode=mode,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )

    raise AssertionError("bounded probe loop exhausted unexpectedly")


def probe_candidate(provider: object, candidate: ModelCandidate) -> ProbeRecord:
    if not candidate.cost_verified:
        return ProbeRecord(
            provider=candidate.provider,
            model_id=candidate.model_id,
            timestamp=round(time.time(), 3),
            status="refused_unverified_cost",
            latency_ms=None,
            parsed_ok=False,
            mode=None,
            attempts=0,
            recovered=False,
            http_status=None,
            error="model cost is not verified as zero",
        )
    return provider.probe(candidate)  # type: ignore[attr-defined, no-any-return]
