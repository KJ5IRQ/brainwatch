from __future__ import annotations

from unittest import mock

import requests

from brainwatch.models import ModelCandidate
from brainwatch.providers.base import endpoint_url
from brainwatch.providers.probe import perform_chat_probe, probe_candidate


def candidate(*, verified: bool = True) -> ModelCandidate:
    return ModelCandidate(
        provider="friend",
        model_id="allowed",
        display_name="Allowed",
        context_length=8192,
        tags=("general",),
        cost_verified=verified,
    )


def response(payload: object, status: int = 200) -> mock.Mock:
    item = mock.Mock()
    item.status_code = status
    item.json.return_value = payload
    return item


def perform(session: mock.Mock):
    return perform_chat_probe(
        provider_name="friend",
        model_id="allowed",
        url="https://models.example.test/v1/chat/completions",
        api_key="secret" + "-value",
        timeout_seconds=1,
        session=session,
    )


def test_unverified_cost_refused_without_provider_call() -> None:
    provider = mock.Mock()
    record = probe_candidate(provider, candidate(verified=False))
    assert record.status == "refused_unverified_cost"
    assert record.attempts == 0
    provider.probe.assert_not_called()


def test_content_reasoning_and_multipart_parsing() -> None:
    payloads = [
        ({"choices": [{"message": {"content": '{"ok":true,"n":42}'}}]}, "content"),
        (
            {
                "choices": [
                    {"message": {"content": None, "reasoning": 'Result: {"ok":true,"n":42}'}}
                ]
            },
            "reasoning",
        ),
        (
            {
                "choices": [
                    {
                        "message": {
                            "content": [{"type": "text", "text": '{"ok":true,"n":42}'}]
                        }
                    }
                ]
            },
            "content",
        ),
    ]
    for payload, mode in payloads:
        session = mock.Mock()
        session.post.return_value = response(payload)
        record = perform(session)
        assert record.status == "ok"
        assert record.parsed_ok is True
        assert record.mode == mode


def test_status_mapping_and_bounded_retry() -> None:
    cases = [
        (401, "auth_error", 1),
        (402, "payment_required", 1),
        (429, "rate_limited", 2),
        (500, "server_error", 2),
    ]
    for status, expected, attempts in cases:
        session = mock.Mock()
        session.post.return_value = response({"error": "Bearer secret-value"}, status)
        record = perform(session)
        assert record.status == expected
        assert record.attempts == attempts
        assert "secret-value" not in (record.error or "")


def test_timeout_retries_once_and_connection_failure_does_not() -> None:
    timed = mock.Mock()
    timed.post.side_effect = requests.Timeout("slow")
    timeout_record = perform(timed)
    assert timeout_record.status == "timeout"
    assert timeout_record.attempts == 2

    disconnected = mock.Mock()
    disconnected.post.side_effect = requests.ConnectionError("offline")
    connection_record = perform(disconnected)
    assert connection_record.status == "connection_error"
    assert connection_record.attempts == 1


def test_non_json_success_is_bad_format_and_not_retried() -> None:
    session = mock.Mock()
    item = response({}, 200)
    item.json.side_effect = ValueError("not json")
    session.post.return_value = item
    record = perform(session)
    assert record.status == "bad_format"
    assert record.http_status == 200
    assert record.attempts == 1


def test_endpoint_url_preserves_origin_and_base_path() -> None:
    assert endpoint_url("https://openrouter.ai/api", "/v1/models") == (
        "https://openrouter.ai/api/v1/models"
    )
    for path in ("https://evil.example/x", "//evil.example/x", "../x"):
        try:
            endpoint_url("https://models.example.test", path)
        except ValueError:
            pass
        else:
            raise AssertionError(f"unsafe path accepted: {path}")
