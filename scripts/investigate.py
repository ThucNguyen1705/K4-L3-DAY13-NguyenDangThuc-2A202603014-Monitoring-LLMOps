"""Điều tra sự cố theo Metrics -> Logs trên data/logs.jsonl.

In tóm tắt metric của cửa sổ thời gian, bảng theo phút để khoanh khoảng sự cố, rồi liệt kê
request bất thường kèm correlation_id để tra trace cùng ID trên Langfuse.

    python scripts/investigate.py --since 15 --latency-ms 2000
    python scripts/investigate.py --since 15 --failed
    python scripts/investigate.py --since 60 --cost-usd 0.005
    python scripts/investigate.py --correlation-id req-1a2b3c4d
"""
from __future__ import annotations

import argparse
import sys
from datetime import timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.cli import configure_utf8_stdio
from app.log_analytics import in_window, load_records, minute_buckets, resolve_end, summarize

ICT = timezone(timedelta(hours=7), "ICT")


def is_anomalous(record: dict, args: argparse.Namespace) -> bool:
    event = record.get("event")
    if args.failed and event == "request_failed":
        return True
    if event != "response_sent":
        return False
    if args.latency_ms is not None and (record.get("latency_ms") or 0) > args.latency_ms:
        return True
    if args.cost_usd is not None and (record.get("cost_usd") or 0) > args.cost_usd:
        return True
    return False


def main() -> int:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--logs", type=Path, default=REPO_ROOT / "data" / "logs.jsonl")
    parser.add_argument("--since", type=int, default=60, help="số phút tính ngược từ --end")
    parser.add_argument("--end", default="latest", help="now | latest | ISO timestamp")
    parser.add_argument("--feature", help="chỉ xét một feature")
    parser.add_argument("--latency-ms", type=int, help="liệt kê response_sent có latency_ms lớn hơn")
    parser.add_argument("--cost-usd", type=float, help="liệt kê response_sent có cost_usd lớn hơn")
    parser.add_argument("--failed", action="store_true", help="liệt kê request_failed")
    parser.add_argument("--correlation-id", help="in toàn bộ log line của một request")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()

    records = load_records(args.logs)
    if not records:
        print(f"Không có log hợp lệ trong {args.logs}")
        return 1

    if args.correlation_id:
        for record in records:
            if record.get("correlation_id") == args.correlation_id:
                print(record["ts"], {k: v for k, v in record.items() if k not in ("_ts", "ts")})
        return 0

    end = resolve_end(records, args.end)
    start = end - timedelta(minutes=args.since)
    window = in_window(records, start, end)
    if args.feature:
        window = [r for r in window if r.get("feature") == args.feature]
    total = summarize(window)

    print(f"Cửa sổ: {start.astimezone(ICT):%Y-%m-%d %H:%M:%S} → {end.astimezone(ICT):%H:%M:%S} ICT"
          f" ({args.since} phút, {len(window)} log records{', feature=' + args.feature if args.feature else ''})")
    print(f"Traffic: {total.requests} requests | errors: {total.failures} ({total.error_rate_pct}%) {total.error_breakdown or ''}")
    print(f"Retrieval success: {total.tool_success_rate_pct}% | quality mean: {total.quality_mean}")
    print(f"Latency P50/P95/P99: {total.latency_p50:.0f}/{total.latency_p95:.0f}/{total.latency_p99:.0f} ms"
          f" | TTFT P95: {total.ttft_p95:.0f} ms")
    print(f"Cost: total ${total.cost_total:.6f}, avg ${total.cost_avg:.6f}/request"
          f" | tokens in/out: {total.tokens_in}/{total.tokens_out}")

    first_minute = start.replace(second=0, microsecond=0)
    minutes = int((end - first_minute).total_seconds() // 60) + 1
    print("\nTheo phút (chỉ phút có traffic):")
    print(f"{'phút ICT':<9} {'req':>4} {'fail':>4} {'p95 ms':>7} {'ttft95':>6} {'avg $':>9} {'tok_out':>7} {'quality':>7}")
    for minute, s in minute_buckets(window, first_minute, minutes):
        if s.requests or s.responses or s.failures:
            quality = f"{s.quality_mean:.2f}" if s.quality_mean is not None else "-"
            print(f"{minute.astimezone(ICT):%H:%M}     {s.requests:>4} {s.failures:>4} {s.latency_p95:>7.0f}"
                  f" {s.ttft_p95:>6.0f} {s.cost_avg:>9.6f} {s.tokens_out:>7} {quality:>7}")

    if args.failed or args.latency_ms is not None or args.cost_usd is not None:
        anomalies = [r for r in window if is_anomalous(r, args)]
        print(f"\nRequest bất thường: {len(anomalies)} (hiển thị tối đa {args.limit})")
        for record in sorted(anomalies, key=lambda r: r["_ts"])[: args.limit]:
            print(
                f"  {record['ts']} {record.get('correlation_id')} feature={record.get('feature')}"
                f" event={record.get('event')} latency_ms={record.get('latency_ms')}"
                f" ttft_ms={record.get('ttft_ms')} cost_usd={record.get('cost_usd')}"
                f" tokens_out={record.get('tokens_out')} error_type={record.get('error_type')}"
            )
        if anomalies:
            print("\nBước tiếp theo: mở Langfuse → Traces, lọc Metadata correlation_id = <ID ở trên>,"
                  " so sánh thời lượng/level của rag-retrieve và llm-generate.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
