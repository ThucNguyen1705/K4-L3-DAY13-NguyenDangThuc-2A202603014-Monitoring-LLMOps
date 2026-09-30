from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

from app.log_analytics import load_records, minute_buckets, summarize
from scripts import build_dashboard

REPO_ROOT = Path(__file__).resolve().parents[1]
T0 = datetime(2026, 9, 29, 8, 0, 5, tzinfo=timezone.utc)


def _record(offset_s: int, event: str, **fields) -> dict:
    ts = (T0 + timedelta(seconds=offset_s)).isoformat().replace("+00:00", "Z")
    return {"ts": ts, "level": "info", "service": "api", "event": event, **fields}


def _write(tmp_path: Path, records: list[dict]) -> Path:
    path = tmp_path / "logs.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n{broken\n", encoding="utf-8")
    return path


RESPONSE = {"latency_ms": 150, "ttft_ms": 50, "tokens_in": 30, "tokens_out": 100,
            "cost_usd": 0.0016, "quality_score": 0.9, "tool_name": "retrieval", "tool_success": True}


def _sample() -> list[dict]:
    return [
        _record(0, "request_received", correlation_id="req-00000001"),
        _record(1, "response_sent", correlation_id="req-00000001", **RESPONSE),
        _record(2, "request_received", correlation_id="req-00000002"),
        _record(3, "response_sent", correlation_id="req-00000002", **{**RESPONSE, "latency_ms": 2650}),
        _record(70, "request_received", correlation_id="req-00000003"),
        _record(71, "request_failed", correlation_id="req-00000003", error_type="RuntimeError",
                tool_name="retrieval", tool_success=False),
    ]


def test_summarize_matches_dashboard_contract(tmp_path: Path) -> None:
    records = load_records(_write(tmp_path, _sample()))

    summary = summarize(records)

    assert summary.requests == 3
    assert summary.failures == 1
    assert summary.error_rate_pct == 33.33
    assert summary.error_breakdown == {"RuntimeError": 1}
    assert summary.tool_success_rate_pct == 66.67
    assert summary.latency_p95 == 2650
    assert summary.cost_total == 0.0032
    assert (summary.tokens_in, summary.tokens_out) == (60, 200)
    assert summary.quality_mean == 0.9


def test_minute_buckets_split_requests_by_minute(tmp_path: Path) -> None:
    records = load_records(_write(tmp_path, _sample()))

    buckets = minute_buckets(records, T0.replace(second=0), 3)

    assert [s.requests for _, s in buckets] == [2, 1, 0]
    assert [s.failures for _, s in buckets] == [0, 1, 0]


def test_dashboard_renders_six_contract_panels_with_thresholds(tmp_path: Path) -> None:
    records = load_records(_write(tmp_path, _sample()))
    dashboard = yaml.safe_load((REPO_ROOT / "config" / "dashboard.yaml").read_text(encoding="utf-8"))["dashboard"]
    slo = yaml.safe_load((REPO_ROOT / "config" / "slo.yaml").read_text(encoding="utf-8"))

    page = build_dashboard.build(records, dashboard, slo, T0 + timedelta(minutes=5))

    for panel in dashboard["panels"]:
        assert f'id="panel-{panel["id"]}"' in page
        assert panel["title"] in page
        assert f"unit: {panel['unit']}" in page
    assert "Time range: last 60 min" in page
    assert 'http-equiv="refresh" content="30"' in page
    assert "Threshold P95 ≤ 3,000 ms" in page
    assert "SLO ≤ 2,000 ms" in page
    assert "Breach" in page  # error rate 33% vượt ngưỡng 2%


def test_dashboard_handles_empty_log_window() -> None:
    dashboard = yaml.safe_load((REPO_ROOT / "config" / "dashboard.yaml").read_text(encoding="utf-8"))["dashboard"]
    slo = yaml.safe_load((REPO_ROOT / "config" / "slo.yaml").read_text(encoding="utf-8"))

    page = build_dashboard.build([], dashboard, slo, T0)

    assert page.count('class="panel"') == 6
    assert "No data" in page
