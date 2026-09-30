"""Dựng dashboard 6 panel từ data/logs.jsonl theo contract config/dashboard.yaml.

Kết quả là một file HTML tự chứa (SVG inline, không cần thư viện ngoài):

    python scripts/build_dashboard.py                  # ghi data/dashboard.html
    python scripts/build_dashboard.py --watch          # dựng lại mỗi refresh_seconds
    python scripts/build_dashboard.py --png out.png    # chụp ảnh bằng Edge/Chrome headless
"""
from __future__ import annotations

import argparse
import html
import math
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.cli import configure_utf8_stdio
from app.log_analytics import Summary, in_window, load_records, minute_buckets, resolve_end, summarize

ICT = timezone(timedelta(hours=7), "ICT")
SERIES = ("var(--s1)", "var(--s2)", "var(--s3)", "var(--s4)")
BROWSER_CANDIDATES = (
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "msedge",
    "google-chrome",
    "chromium",
    "chrome",
)

W, H = 560, 230
LEFT, RIGHT, TOP, BOTTOM = 60, 14, 14, 30


def fmt_ms(v: float) -> str:
    return f"{v:,.0f} ms"


def fmt_pct(v: float) -> str:
    return f"{v:.1f}%"


def fmt_usd(v: float) -> str:
    return f"${v:,.4f}" if v < 1 else f"${v:,.2f}"


def fmt_int(v: float) -> str:
    return f"{v:,.0f}"


def fmt_score(v: float) -> str:
    return f"{v:.2f}"


def nice_max(value: float) -> float:
    if value <= 0:
        return 1.0
    exp = 10 ** math.floor(math.log10(value))
    for m in (1, 1.2, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10):
        if value <= m * exp:
            return m * exp
    return 10 * exp


def esc(text: Any) -> str:
    return html.escape(str(text), quote=True)


def chart(
    times: list[datetime],
    series: list[dict[str, Any]],
    *,
    fmt: Callable[[float], str],
    kind: str = "line",
    refs: tuple[dict[str, Any], ...] = (),
    y_floor: float = 0.0,
    y_fixed: float | None = None,
) -> str:
    """Vẽ một chart SVG trên 60 bucket phút. kind: line | bar | stack."""
    n = len(times)
    plot_w, plot_h = W - LEFT - RIGHT, H - TOP - BOTTOM
    values = [v for s in series for v in s["values"] if v is not None]
    if kind == "stack":
        values = [
            sum(s["values"][i] or 0 for s in series) for i in range(n)
        ]
    peak = max(values + [r["value"] for r in refs] + [y_floor])
    y_max = y_fixed if y_fixed is not None else nice_max(peak * 1.08)
    band = plot_w / n

    def x(i: int) -> float:
        return LEFT + (i + 0.5) * band

    def y(v: float) -> float:
        return TOP + plot_h - (v / y_max) * plot_h

    parts = [f'<svg viewBox="0 0 {W} {H}" role="img" class="chart">']
    for k in range(5):
        tick = y_max * k / 4
        ty = y(tick)
        parts.append(f'<line class="grid" x1="{LEFT}" x2="{W - RIGHT}" y1="{ty:.1f}" y2="{ty:.1f}"/>')
        parts.append(f'<text class="tick" x="{LEFT - 6}" y="{ty + 4:.1f}" text-anchor="end">{esc(fmt(tick))}</text>')
    step = max(1, n // 6)
    tick_indices = list(range(0, n, step))
    if n - 1 - tick_indices[-1] >= max(2, step // 2):  # thêm phút cuối nếu không đè nhãn trước
        tick_indices.append(n - 1)
    for i in tick_indices:
        parts.append(
            f'<text class="tick" x="{x(i):.1f}" y="{H - 10}" text-anchor="middle">'
            f'{times[i].astimezone(ICT):%H:%M}</text>'
        )
    parts.append(f'<line class="axis" x1="{LEFT}" x2="{W - RIGHT}" y1="{y(0):.1f}" y2="{y(0):.1f}"/>')

    for ref in refs:
        ry = y(ref["value"])
        parts.append(f'<line class="ref {ref["tone"]}" x1="{LEFT}" x2="{W - RIGHT}" y1="{ry:.1f}" y2="{ry:.1f}"/>')
        parts.append(f'<text class="ref-label" x="{LEFT + 6}" y="{ry - 5:.1f}">{esc(ref["label"])}</text>')

    bar_w = max(2.0, min(24.0, band - 2))
    if kind in ("bar", "stack"):
        for i in range(n):
            base = 0.0
            for s in series:
                v = s["values"][i]
                if not v:
                    continue
                top_v = base + v
                y_top, y_base = y(top_v), y(base)
                gap = 2 if base > 0 else 0  # khe 2px giữa các đoạn stack
                height = max(1.0, y_base - y_top - gap)
                parts.append(
                    f'<rect x="{x(i) - bar_w / 2:.1f}" y="{y_top:.1f}" width="{bar_w:.1f}" '
                    f'height="{height:.1f}" rx="1.5" fill="{s["color"]}"/>'
                )
                base = top_v
    else:
        for s in series:
            vals = s["values"]
            path, prev = [], False
            for i, v in enumerate(vals):
                if v is None:
                    prev = False
                    continue
                path.append(f'{"L" if prev else "M"}{x(i):.1f},{y(v):.1f}')
                prev = True
            if path:
                parts.append(f'<path d="{" ".join(path)}" fill="none" stroke="{s["color"]}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>')
            for i, v in enumerate(vals):
                if v is not None:
                    parts.append(f'<circle class="dot" cx="{x(i):.1f}" cy="{y(v):.1f}" r="4" fill="{s["color"]}"/>')

    # Vùng hover cả cột phút: tooltip liệt kê mọi series tại phút đó.
    for i in range(n):
        present = [(s["name"], s["values"][i]) for s in series if s["values"][i] is not None]
        if not present:
            continue
        label = f"{times[i].astimezone(ICT):%H:%M} ICT\n" + "\n".join(f"{name}: {fmt(v)}" for name, v in present)
        parts.append(
            f'<rect class="hit" x="{x(i) - band / 2:.1f}" y="{TOP}" width="{band:.1f}" height="{plot_h}">'
            f"<title>{esc(label)}</title></rect>"
        )
    parts.append("</svg>")
    return "".join(parts)


def legend(series: list[dict[str, Any]]) -> str:
    if len(series) < 2:
        return ""
    items = "".join(
        f'<span class="key"><i style="background:{s["color"]}"></i>{esc(s["name"])}</span>' for s in series
    )
    return f'<div class="legend">{items}</div>'


def tile(label: str, value: str) -> str:
    return f'<div class="tile"><div class="tile-label">{esc(label)}</div><div class="tile-value">{esc(value)}</div></div>'


def status(ok: bool | None, detail: str) -> str:
    if ok is None:
        return f'<span class="status none">– No data · {esc(detail)}</span>'
    if ok:
        return f'<span class="status good">✓ Within threshold · {esc(detail)}</span>'
    return f'<span class="status bad">✕ Breach · {esc(detail)}</span>'


def check(value: float | None, threshold: dict[str, Any]) -> bool | None:
    if value is None:
        return None
    return value <= threshold["value"] if threshold["operator"] == "lte" else value >= threshold["value"]


def meter(value: float, limit: float, fmt: Callable[[float], str]) -> str:
    ratio = value / limit if limit else 0
    tone = "good" if ratio < 0.8 else ("warn" if ratio <= 1 else "bad")
    return (
        f'<div class="meter" title="{esc(fmt(value))} / {esc(fmt(limit))}"><div class="meter-fill {tone}" '
        f'style="width:{min(ratio, 1) * 100:.1f}%"></div></div>'
        f'<div class="meter-label">{esc(fmt(value))} of {esc(fmt(limit))} limit ({ratio * 100:.1f}%)</div>'
    )


def table(times: list[datetime], columns: list[tuple[str, list[Any], Callable[[float], str]]]) -> str:
    rows = []
    for i, t in enumerate(times):
        cells = [c[1][i] for c in columns]
        if all(v is None for v in cells):
            continue
        tds = "".join(f"<td>{esc(fmt(v)) if v is not None else '–'}</td>" for (_, _, fmt), v in zip(columns, cells))
        rows.append(f"<tr><td>{t.astimezone(ICT):%H:%M}</td>{tds}</tr>")
    head = "".join(f"<th>{esc(name)}</th>" for name, _, _ in columns)
    body = "".join(rows) or f'<tr><td colspan="{len(columns) + 1}">No data in window</td></tr>'
    return f'<details><summary>Table view</summary><table><thead><tr><th>Minute (ICT)</th>{head}</tr></thead><tbody>{body}</tbody></table></details>'


def panel(cfg: dict[str, Any], body: str, threshold_text: str) -> str:
    return (
        f'<section class="panel" id="panel-{esc(cfg["id"])}"><header><h2>{esc(cfg["title"])}</h2>'
        f'<span class="unit">unit: {esc(cfg["unit"])}</span></header>'
        f'<p class="threshold">{threshold_text}</p>{body}</section>'
    )


def build(
    records: list[dict[str, Any]],
    dashboard: dict[str, Any],
    slo: dict[str, Any],
    end: datetime,
    minutes: int | None = None,
) -> str:
    minutes = minutes or dashboard["time_range_minutes"]
    zoom = minutes != dashboard["time_range_minutes"]
    last_minute = end.replace(second=0, microsecond=0)
    start = last_minute - timedelta(minutes=minutes - 1)
    window = in_window(records, start, end)
    total = summarize(window)
    buckets = minute_buckets(window, start, minutes)
    times = [t for t, _ in buckets]
    per_min: list[Summary] = [s for _, s in buckets]
    panels = {p["id"]: p for p in dashboard["panels"]}

    def col(attr: str, only_if: Callable[[Summary], bool] = lambda s: s.responses > 0) -> list[float | None]:
        return [getattr(s, attr) if only_if(s) else None for s in per_min]

    out = []

    # 1. Latency
    p = panels["latency"]
    slo_ms = slo["primary_slo"].get("latency_threshold_ms")
    series = [
        {"name": "P50", "color": SERIES[0], "values": col("latency_p50")},
        {"name": "P95", "color": SERIES[1], "values": col("latency_p95")},
        {"name": "P99", "color": SERIES[2], "values": col("latency_p99")},
        {"name": "TTFT P95", "color": SERIES[3], "values": col("ttft_p95")},
    ]
    refs = [{"label": f"Threshold P95 ≤ {fmt_ms(p['threshold']['value'])}", "value": p["threshold"]["value"], "tone": "crit"}]
    if slo_ms:
        refs.append({"label": f"SLO ≤ {fmt_ms(slo_ms)}", "value": slo_ms, "tone": "warn"})
    has = total.responses > 0
    target = slo["primary_slo"]["target_percent"]
    good = sum(1 for r in window if r.get("event") == "response_sent" and (r.get("latency_ms") or 0) <= (slo_ms or 0))
    sli = round(good / total.requests * 100, 2) if total.requests else None
    slo_line = (
        f'<p class="threshold">{status(None if sli is None else sli >= target, f"SLO good ≤ {fmt_ms(slo_ms)}: SLI {fmt_pct(sli or 0)} vs target {target}%")}</p>'
    )
    body = (
        slo_line + '<div class="tiles">'
        + tile("P50", fmt_ms(total.latency_p50)) + tile("P95", fmt_ms(total.latency_p95))
        + tile("P99", fmt_ms(total.latency_p99)) + tile("TTFT P95", fmt_ms(total.ttft_p95))
        + "</div>" + legend(series) + chart(times, series, fmt=fmt_ms, refs=tuple(refs))
        + table(times, [(s["name"], s["values"], fmt_ms) for s in series])
    )
    out.append(panel(p, body, status(check(total.latency_p95 if has else None, p["threshold"]), f"P95 ≤ {fmt_ms(p['threshold']['value'])}; SLO line {fmt_ms(slo_ms)}")))

    # 2. Traffic
    p = panels["traffic"]
    rpm = [float(s.requests) if s.requests else None for s in per_min]
    peak = max((v for v in rpm if v), default=None)
    series = [{"name": "Requests/min", "color": SERIES[0], "values": rpm}]
    body = (
        '<div class="tiles">' + tile(f"Requests ({minutes} min)", fmt_int(total.requests))
        + tile("Peak rpm", fmt_int(peak or 0)) + tile("Active minutes", fmt_int(sum(1 for v in rpm if v))) + "</div>"
        + chart(times, series, fmt=fmt_int, kind="bar",
                refs=({"label": f"Expected ≥ {p['threshold']['value']} rpm", "value": p["threshold"]["value"], "tone": "warn"},))
        + table(times, [("Requests/min", rpm, fmt_int)])
    )
    out.append(panel(p, body, status(check(peak, p["threshold"]), f"peak rate ≥ {p['threshold']['value']} rpm")))

    # 3. Errors + retrieval success
    p = panels["errors"]
    err = [s.error_rate_pct if s.requests else None for s in per_min]
    tool = [s.tool_success_rate_pct for s in per_min]
    series = [
        {"name": "Error rate", "color": SERIES[0], "values": err},
        {"name": "Retrieval success", "color": SERIES[1], "values": tool},
    ]
    breakdown = ", ".join(f"{k}: {v}" for k, v in total.error_breakdown.items()) or "none"
    body = (
        '<div class="tiles">' + tile("Error rate", fmt_pct(total.error_rate_pct))
        + tile("Failed requests", fmt_int(total.failures))
        + tile("Retrieval success", fmt_pct(total.tool_success_rate_pct) if total.tool_success_rate_pct is not None else "–")
        + "</div>" + f'<p class="note">Errors by type: {esc(breakdown)}</p>' + legend(series)
        + chart(times, series, fmt=fmt_pct, y_fixed=100,
                refs=({"label": f"Error threshold ≤ {p['threshold']['value']}%", "value": p["threshold"]["value"], "tone": "crit"},))
        + table(times, [("Error rate", err, fmt_pct), ("Retrieval success", tool, fmt_pct)])
    )
    out.append(panel(p, body, status(check(total.error_rate_pct if total.requests else None, p["threshold"]), f"error rate ≤ {p['threshold']['value']}%")))

    # 4. Cost
    p = panels["cost"]
    cost = [s.cost_total if s.responses else None for s in per_min]
    body = (
        '<div class="tiles">' + tile("Total cost", fmt_usd(total.cost_total))
        + tile("Avg / request", fmt_usd(total.cost_avg)) + "</div>"
        + meter(total.cost_total, p["threshold"]["value"], fmt_usd)
        + chart(times, [{"name": "Cost/min", "color": SERIES[0], "values": cost}], fmt=fmt_usd, kind="bar")
        + table(times, [("Cost/min", cost, fmt_usd)])
    )
    out.append(panel(p, body, status(check(total.cost_total, p["threshold"]), f"window total ≤ {fmt_usd(p['threshold']['value'])}")))

    # 5. Tokens
    p = panels["tokens"]
    t_in = [float(s.tokens_in) if s.responses else None for s in per_min]
    t_out = [float(s.tokens_out) if s.responses else None for s in per_min]
    series = [
        {"name": "tokens_in", "color": SERIES[0], "values": t_in},
        {"name": "tokens_out", "color": SERIES[1], "values": t_out},
    ]
    limit = p["threshold"]["value"]
    body = (
        '<div class="tiles">' + tile("tokens_in", fmt_int(total.tokens_in)) + tile("tokens_out", fmt_int(total.tokens_out)) + "</div>"
        + meter(max(total.tokens_in, total.tokens_out), limit, fmt_int)
        + legend(series) + chart(times, series, fmt=fmt_int, kind="stack")
        + table(times, [("tokens_in", t_in, fmt_int), ("tokens_out", t_out, fmt_int)])
    )
    out.append(panel(p, body, status(check(max(total.tokens_in, total.tokens_out), p["threshold"]), f"each field ≤ {fmt_int(limit)} per window")))

    # 6. Quality
    p = panels["quality"]
    quality = col("quality_mean")
    body = (
        '<div class="tiles">' + tile("Mean quality", fmt_score(total.quality_mean) if total.quality_mean is not None else "–")
        + tile("Responses", fmt_int(total.responses)) + "</div>"
        + chart(times, [{"name": "Mean quality", "color": SERIES[0], "values": quality}], fmt=fmt_score, y_fixed=1,
                refs=({"label": f"Threshold ≥ {p['threshold']['value']}", "value": p["threshold"]["value"], "tone": "crit"},))
        + table(times, [("Mean quality", quality, fmt_score)])
    )
    out.append(panel(p, body, status(check(total.quality_mean, p["threshold"]), f"mean ≥ {p['threshold']['value']}")))

    subtitle = (
        f"{'ZOOM (not the contract view) · ' if zoom else ''}Time range: last {minutes} min · {start.astimezone(ICT):%Y-%m-%d %H:%M}–{end.astimezone(ICT):%H:%M} ICT (UTC+7)"
        f" · auto refresh {dashboard['refresh_seconds']}s · source: data/logs.jsonl ({len(window)} records in window)"
    )
    return PAGE.format(
        title=esc(dashboard["title"]),
        refresh=dashboard["refresh_seconds"],
        subtitle=esc(subtitle),
        panels="".join(out),
        generated=f"{datetime.now(ICT):%Y-%m-%d %H:%M:%S} ICT",
    )


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="{refresh}">
<title>Day 13 Dashboard</title>
<style>
:root {{ color-scheme: light; --page:#f9f9f7; --surface:#fcfcfb; --ink:#0b0b0b; --ink2:#52514e; --muted:#898781;
  --grid:#e1e0d9; --axis:#c3c2b7; --ring:rgba(11,11,11,.10); --s1:#2a78d6; --s2:#eb6834; --s3:#1baf7a; --s4:#eda100;
  --good:#0ca30c; --good-ink:#006300; --warn:#fab219; --serious:#ec835a; --crit:#d03b3b; --track:#e8f0fb; }}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{ color-scheme: dark; --page:#0d0d0d; --surface:#1a1a19;
  --ink:#fff; --ink2:#c3c2b7; --grid:#2c2c2a; --axis:#383835; --ring:rgba(255,255,255,.10); --s1:#3987e5; --s2:#d95926;
  --s3:#199e70; --s4:#c98500; --good-ink:#0ca30c; --track:#1c2b3f; }} }}
:root[data-theme="dark"] {{ color-scheme: dark; --page:#0d0d0d; --surface:#1a1a19; --ink:#fff; --ink2:#c3c2b7; --grid:#2c2c2a;
  --axis:#383835; --ring:rgba(255,255,255,.10); --s1:#3987e5; --s2:#d95926; --s3:#199e70; --s4:#c98500; --good-ink:#0ca30c; --track:#1c2b3f; }}
* {{ box-sizing: border-box; }}
body {{ margin:0; padding:20px 16px 32px; background:var(--page); color:var(--ink); font:14px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif; }}
h1 {{ font-size:20px; margin:0 0 4px; font-weight:600; }}
.sub {{ color:var(--ink2); margin:0 0 16px; }}
.grid {{ display:grid; gap:14px; grid-template-columns:repeat(auto-fit, minmax(min(540px, 100%), 1fr)); }}
.panel {{ background:var(--surface); border:1px solid var(--ring); border-radius:10px; padding:14px 16px; min-width:0; }}
.panel header {{ display:flex; justify-content:space-between; align-items:baseline; gap:8px; }}
h2 {{ font-size:15px; margin:0; font-weight:600; }}
.unit {{ color:var(--muted); font-size:12px; white-space:nowrap; }}
.threshold {{ margin:6px 0 10px; font-size:12.5px; }}
.status {{ font-weight:600; }} .status.good {{ color:var(--good-ink); }} .status.bad {{ color:var(--crit); }} .status.none {{ color:var(--muted); }}
.tiles {{ display:flex; flex-wrap:wrap; gap:18px; margin-bottom:8px; }}
.tile-label {{ color:var(--ink2); font-size:12px; }}
.tile-value {{ font-size:20px; font-weight:600; }}
.note {{ color:var(--ink2); font-size:12.5px; margin:0 0 6px; }}
.legend {{ display:flex; gap:14px; flex-wrap:wrap; font-size:12px; color:var(--ink2); margin:2px 0 4px; }}
.key i {{ display:inline-block; width:14px; height:3px; border-radius:2px; vertical-align:middle; margin-right:5px; }}
.chart {{ width:100%; height:auto; display:block; }}
.chart .grid {{ stroke:var(--grid); stroke-width:1; }}
.chart .axis {{ stroke:var(--axis); stroke-width:1; }}
.chart .tick {{ fill:var(--muted); font-size:11px; font-variant-numeric:tabular-nums; }}
.chart .ref {{ stroke-width:1.5; stroke-dasharray:6 4; }} .chart .ref.crit {{ stroke:var(--crit); }} .chart .ref.warn {{ stroke:var(--serious); }}
.chart .ref-label {{ fill:var(--ink2); font-size:11px; }}
.chart .dot {{ stroke:var(--surface); stroke-width:2; }}
.chart .hit {{ fill:transparent; }} .chart .hit:hover {{ fill:var(--grid); fill-opacity:.35; }}
.meter {{ height:8px; border-radius:4px; background:var(--track); overflow:hidden; margin:4px 0 2px; }}
.meter-fill {{ height:100%; border-radius:4px; }} .meter-fill.good {{ background:var(--s1); }} .meter-fill.warn {{ background:var(--warn); }} .meter-fill.bad {{ background:var(--crit); }}
.meter-label {{ font-size:12px; color:var(--ink2); margin-bottom:6px; }}
details {{ margin-top:6px; font-size:12px; color:var(--ink2); }}
table {{ border-collapse:collapse; margin-top:6px; font-variant-numeric:tabular-nums; }}
th, td {{ padding:2px 10px 2px 0; text-align:right; }} th:first-child, td:first-child {{ text-align:left; }}
footer {{ margin-top:14px; color:var(--muted); font-size:12px; }}
</style></head>
<body>
<h1>{title}</h1>
<p class="sub">{subtitle}</p>
<main class="grid">{panels}</main>
<footer>Generated {generated} by scripts/build_dashboard.py · contract: config/dashboard.yaml · SLO: config/slo.yaml</footer>
</body></html>
"""


def find_browser() -> str | None:
    for candidate in BROWSER_CANDIDATES:
        resolved = shutil.which(candidate) or (candidate if Path(candidate).exists() else None)
        if resolved:
            return resolved
    return None


def screenshot(html_path: Path, png_path: Path, size: str) -> None:
    browser = find_browser()
    if not browser:
        raise SystemExit("Không tìm thấy Edge/Chrome để chụp PNG; mở file HTML và chụp thủ công.")
    png_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [browser, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--window-size={size}",
         f"--screenshot={png_path.resolve()}", html_path.resolve().as_uri()],
        check=True, capture_output=True, timeout=60,
    )


def main() -> int:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--logs", type=Path, default=REPO_ROOT / "data" / "logs.jsonl")
    parser.add_argument("--config", type=Path, default=REPO_ROOT / "config" / "dashboard.yaml")
    parser.add_argument("--slo", type=Path, default=REPO_ROOT / "config" / "slo.yaml")
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "data" / "dashboard.html")
    parser.add_argument("--end", default="now", help="now | latest | ISO timestamp; cuối cửa sổ 60 phút")
    parser.add_argument("--png", type=Path, help="chụp ảnh dashboard ra file PNG")
    parser.add_argument("--size", default="1800,1060", help="kích thước cửa sổ khi chụp PNG")
    parser.add_argument("--minutes", type=int, help="zoom cửa sổ khác contract (mặc định time_range_minutes)")
    parser.add_argument("--watch", action="store_true", help="dựng lại sau mỗi refresh_seconds")
    args = parser.parse_args()

    dashboard = yaml.safe_load(args.config.read_text(encoding="utf-8"))["dashboard"]
    slo = yaml.safe_load(args.slo.read_text(encoding="utf-8"))
    while True:
        records = load_records(args.logs)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(build(records, dashboard, slo, resolve_end(records, args.end), args.minutes), encoding="utf-8")
        print(f"Dashboard: {args.out} ({len(records)} log records)")
        if args.png:
            screenshot(args.out, args.png, args.size)
            print(f"Screenshot: {args.png}")
        if not args.watch:
            return 0
        time.sleep(dashboard["refresh_seconds"])


if __name__ == "__main__":
    raise SystemExit(main())
