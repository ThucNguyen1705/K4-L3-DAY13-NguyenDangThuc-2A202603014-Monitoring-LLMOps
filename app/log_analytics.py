"""Tổng hợp data/logs.jsonl theo đúng contract trong config/dashboard.yaml.

Dùng chung cho scripts/build_dashboard.py (dashboard runtime) và scripts/investigate.py
(điều tra Metrics -> Logs) để hai công cụ luôn tính cùng một con số.
"""
from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Iterable

from .metrics import percentile


def parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def load_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict) and isinstance(record.get("ts"), str):
            record["_ts"] = parse_ts(record["ts"])
            records.append(record)
    return records


def resolve_end(records: list[dict[str, Any]], end: str | None) -> datetime:
    if end in (None, "now"):
        return datetime.now(timezone.utc)
    if end == "latest":
        return max((r["_ts"] for r in records), default=datetime.now(timezone.utc))
    return parse_ts(end)


def in_window(
    records: Iterable[dict[str, Any]], start: datetime, end: datetime
) -> list[dict[str, Any]]:
    return [r for r in records if start <= r["_ts"] <= end]


@dataclass
class Summary:
    requests: int = 0
    responses: int = 0
    failures: int = 0
    error_breakdown: dict[str, int] = field(default_factory=dict)
    error_rate_pct: float = 0.0
    tool_success_rate_pct: float | None = None
    latency_p50: float = 0.0
    latency_p95: float = 0.0
    latency_p99: float = 0.0
    ttft_p95: float = 0.0
    cost_total: float = 0.0
    cost_avg: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0
    quality_mean: float | None = None


def summarize(records: Iterable[dict[str, Any]]) -> Summary:
    records = list(records)
    received = [r for r in records if r.get("event") == "request_received"]
    responses = [r for r in records if r.get("event") == "response_sent"]
    failures = [r for r in records if r.get("event") == "request_failed"]
    tool_flags = [r["tool_success"] for r in records if isinstance(r.get("tool_success"), bool)]
    latencies = [int(r["latency_ms"]) for r in responses if r.get("latency_ms") is not None]
    ttfts = [int(r["ttft_ms"]) for r in responses if r.get("ttft_ms") is not None]
    costs = [float(r.get("cost_usd") or 0.0) for r in responses]
    qualities = [float(r["quality_score"]) for r in responses if r.get("quality_score") is not None]
    return Summary(
        requests=len(received),
        responses=len(responses),
        failures=len(failures),
        error_breakdown=dict(Counter(r.get("error_type") or "unknown" for r in failures)),
        error_rate_pct=round(len(failures) / len(received) * 100, 2) if received else 0.0,
        tool_success_rate_pct=(
            round(sum(tool_flags) / len(tool_flags) * 100, 2) if tool_flags else None
        ),
        latency_p50=percentile(latencies, 50),
        latency_p95=percentile(latencies, 95),
        latency_p99=percentile(latencies, 99),
        ttft_p95=percentile(ttfts, 95),
        cost_total=round(sum(costs), 6),
        cost_avg=round(mean(costs), 6) if costs else 0.0,
        tokens_in=sum(int(r.get("tokens_in") or 0) for r in responses),
        tokens_out=sum(int(r.get("tokens_out") or 0) for r in responses),
        quality_mean=round(mean(qualities), 3) if qualities else None,
    )


def minute_buckets(
    records: Iterable[dict[str, Any]], start: datetime, minutes: int
) -> list[tuple[datetime, Summary]]:
    """Chia cửa sổ [start, start + minutes) thành từng phút và tổng hợp mỗi phút."""
    grouped: dict[int, list[dict[str, Any]]] = {}
    for record in records:
        index = int((record["_ts"] - start).total_seconds() // 60)
        if 0 <= index < minutes:
            grouped.setdefault(index, []).append(record)
    return [
        (start + timedelta(minutes=i), summarize(grouped.get(i, [])))
        for i in range(minutes)
    ]
