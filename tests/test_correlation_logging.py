from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

import httpx

from app import logging_config
from app.logging_config import scrub_event
from app.main import app
from app.middleware import resolve_correlation_id

ID_FORMAT = re.compile(r"^req-[0-9a-f]{8}$")
PII_MESSAGE = (
    "Refund please. Email student@vinuni.edu.vn, phone 090 123 4567, "
    "CCCD 001099012345, card 4111 1111 1111 1111"
)
RAW_PII = ("student@vinuni.edu.vn", "090 123 4567", "001099012345", "4111 1111 1111 1111")


def _post_chats(requests: list[tuple[dict, dict]]) -> list[httpx.Response]:
    async def send_all() -> list[httpx.Response]:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return [
                await client.post("/chat", json=body, headers=headers)
                for body, headers in requests
            ]

    return asyncio.run(send_all())


def _body(user_id: str, session_id: str, message: str = "Explain monitoring") -> dict:
    return {"user_id": user_id, "session_id": session_id, "feature": "qa", "message": message}


def _read_log(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_resolve_correlation_id_keeps_valid_and_replaces_invalid_ids() -> None:
    assert resolve_correlation_id("req-1a2b3c4d") == "req-1a2b3c4d"
    assert resolve_correlation_id(" REQ-1A2B3C4D ") == "req-1a2b3c4d"
    for incoming in (None, "", "MISSING", "req-xyz", "0987654321", "req-1a2b3c4d; drop"):
        generated = resolve_correlation_id(incoming)
        assert ID_FORMAT.fullmatch(generated)
        assert generated != incoming


def test_response_headers_echo_correlation_id_and_response_time(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(logging_config, "LOG_PATH", tmp_path / "logs.jsonl")

    provided, generated = _post_chats(
        [
            (_body("u01", "s01"), {"x-request-id": "req-0badc0de"}),
            (_body("u02", "s02"), {}),
        ]
    )

    assert provided.headers["x-request-id"] == "req-0badc0de"
    assert provided.json()["correlation_id"] == "req-0badc0de"
    assert ID_FORMAT.fullmatch(generated.headers["x-request-id"])
    assert generated.headers["x-request-id"] == generated.json()["correlation_id"]
    for response in (provided, generated):
        assert int(response.headers["x-response-time-ms"]) >= 0


def test_logs_are_enriched_and_context_does_not_leak(monkeypatch, tmp_path: Path) -> None:
    log_path = tmp_path / "logs.jsonl"
    monkeypatch.setattr(logging_config, "LOG_PATH", log_path)
    monkeypatch.setenv("APP_ENV", "test")

    first, second = _post_chats([(_body("u01", "s01"), {}), (_body("u02", "s02"), {})])

    events = [event for event in _read_log(log_path) if event.get("service") == "api"]
    by_request: dict[str, list[dict]] = {}
    for event in events:
        by_request.setdefault(event["correlation_id"], []).append(event)

    assert set(by_request) == {first.json()["correlation_id"], second.json()["correlation_id"]}
    for correlation_id, session_id in (
        (first.json()["correlation_id"], "s01"),
        (second.json()["correlation_id"], "s02"),
    ):
        request_events = by_request[correlation_id]
        assert [event["event"] for event in request_events] == ["request_received", "response_sent"]
        for event in request_events:
            assert event["session_id"] == session_id
            assert event["feature"] == "qa"
            assert event["model"] == "claude-sonnet-4-5"
            assert event["env"] == "test"
            assert re.fullmatch(r"[0-9a-f]{12}", event["user_id_hash"])
            assert event["user_id_hash"] not in ("u01", "u02")


def test_pii_is_scrubbed_before_log_is_written(monkeypatch, tmp_path: Path) -> None:
    log_path = tmp_path / "logs.jsonl"
    monkeypatch.setattr(logging_config, "LOG_PATH", log_path)

    (response,) = _post_chats([(_body("u05", "s05", PII_MESSAGE), {})])

    assert response.status_code == 200
    raw_log = log_path.read_text(encoding="utf-8")
    for raw in RAW_PII:
        assert raw not in raw_log
    received = next(e for e in _read_log(log_path) if e["event"] == "request_received")
    assert "[REDACTED_EMAIL]" in received["payload"]["message_preview"]


def test_scrub_event_covers_nested_and_top_level_fields() -> None:
    event = scrub_event(
        None,
        "error",
        {
            "event": "request_failed",
            "detail": "user 0987654321 failed",
            "payload": {"nested": {"emails": ["a@b.vn"]}, "count": 3},
        },
    )

    assert event["detail"] == "user [REDACTED_PHONE_VN] failed"
    assert event["payload"]["nested"]["emails"] == ["[REDACTED_EMAIL]"]
    assert event["payload"]["count"] == 3
