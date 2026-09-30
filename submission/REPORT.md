# Báo cáo cá nhân — K4-L3A Day 13 Monitoring & LLMOps

> Các mục đánh dấu **⏳** là ảnh chụp giao diện Langfuse (trace ID tương ứng đã ghi sẵn bên dưới) và URL/commit SHA cuối — phải điền bằng dữ liệu thật, không điền số giả.

## 1. Thông tin học viên

- **Họ và tên:** Nguyễn Đăng Thực
- **MSSV:** 2A202603014
- **Lớp:** K4-L3A
- **Repository URL:** `https://github.com/ThucNguyen1705/K4-L3-DAY13-NguyenDangThuc-2A202603014-Monitoring-LLMOps` ⏳ CẦN BỔ SUNG (xác nhận sau khi tạo repo cá nhân)
- **Commit SHA cuối:** ⏳ CẦN BỔ SUNG
- **Challenge ID:** `day13-k4-l3a-monitoring-llmops-v1` (cohort K4, seed 1311; file riêng của L3A lưu tại `config/challenge.json`, đã `.gitignore`, không commit)
- **Tên project Langfuse cá nhân:** `day13-k4-l3a-2A202603014` (Langfuse Cloud US; tên được xác nhận qua API `projects.get()` bằng key trong `.env`)

## 2. Evidence index

| Evidence | Đường dẫn | Trạng thái |
|---|---|---|
| Baseline (trước khi sửa code) | [evidence/baseline/](evidence/baseline/) | ✅ output thật |
| Pytest cuối | [evidence/01-pytest.txt](evidence/01-pytest.txt) | ✅ output thật |
| Log validator | [evidence/02-log-validator.txt](evidence/02-log-validator.txt) | ✅ output thật |
| Dashboard validator | [evidence/03-dashboard-validator.txt](evidence/03-dashboard-validator.txt) | ✅ output thật |
| Structured log | [evidence/04-structured-log.txt](evidence/04-structured-log.txt) | ✅ trích `data/logs.jsonl` |
| PII redaction | [evidence/05-pii-redaction.txt](evidence/05-pii-redaction.txt) | ✅ trích `data/logs.jsonl` |
| Trace list | `evidence/06-trace-list.png` + [evidence/langfuse-traces-export.txt](evidence/langfuse-traces-export.txt) (75 trace thật, xuất qua API) | ⏳ ảnh: Traces của project, lọc 2026-09-30 09:51–10:00 ICT |
| Trace waterfall | `evidence/07-trace-waterfall.png` | ⏳ ảnh trace `f389cd4ad2ab556423d268e9b978d429` |
| Trace metadata | `evidence/08-trace-metadata.png` | ⏳ ảnh cùng trace; **che dòng `scope.attributes.public_key`** |
| Prompt versions | `evidence/09-prompt-versions.png` | ⏳ ảnh Prompts → `day13-chat` |
| Prompt rollback | `evidence/10a-production-v2.png`, `evidence/10b-rollback-v1.png` | ⏳ ảnh trace `d4e251bd…` (v2) và `44d49656…` (v1) |
| Dashboard runtime | [evidence/11-dashboard-overview.png](evidence/11-dashboard-overview.png) (60 phút theo contract), [evidence/11b-dashboard-zoom-12min.png](evidence/11b-dashboard-zoom-12min.png) (zoom) | ✅ render từ `data/logs.jsonl` |
| Practice investigation (rag_slow) | [evidence/practice-rag-slow-investigation.txt](evidence/practice-rag-slow-investigation.txt) | ✅ output thật (practice, không phải challenge) |
| Incident metric | [evidence/12-incident-metric.png](evidence/12-incident-metric.png) (60 phút), [evidence/12b-incident-metric-zoom.png](evidence/12b-incident-metric-zoom.png) (zoom 6 phút) | ✅ render từ `data/logs.jsonl` lúc incident đang bật |
| Incident log | [evidence/13-incident-log.txt](evidence/13-incident-log.txt) | ✅ trích `data/logs.jsonl` |
| Incident trace | `evidence/14-incident-trace.png` + chi tiết trong [evidence/langfuse-traces-export.txt](evidence/langfuse-traces-export.txt) | ⏳ ảnh waterfall trace `67daa54d749f9a18e73c532b28e3d734` |

## 3. Kết quả kỹ thuật

Baseline chạy trên code gốc (chưa sửa TODO), output tại [evidence/baseline/](evidence/baseline/). Kết quả cuối chạy trên code hiện tại với workload thật: 10 request `sample_queries` × 7 lần (c=1 và c=5), 4 request kiểm tra header/PII, gồm cả 3 practice incident (`rag_slow`, `tool_fail`, `cost_spike`) — tổng 84 request, 175 log records trong 60 phút.

| Nội dung | Baseline | Kết quả cuối | Nhận xét |
|---|---|---|---|
| `validate_logs.py` | 30/100 — 20 record thiếu `correlation_id`, 20 thiếu enrichment, 0 correlation ID | **100/100** — 410 records (gồm cả các pha Langfuse và 2 lần chạy CP3), 0 thiếu field, 0 thiếu enrichment, 204 correlation ID | [evidence/02-log-validator.txt](evidence/02-log-validator.txt) |
| `validate_dashboard.py` | HỢP LỆ 6/6 | **HỢP LỆ 6/6** | Contract không đổi; dashboard runtime dựng từ chính contract |
| `pytest` | 22 passed | **45 passed** | +23 test mới: PII, correlation/context, span tree, dashboard, prompt script — [evidence/01-pytest.txt](evidence/01-pytest.txt) |
| Số traces hợp lệ | 0 (chưa có key; trace chỉ có root observation) | **75** trace `day13-agent-request` trong project cá nhân (40 ở 4 pha prompt + 35 ở CP3), **75/75** khớp `correlation_id` trong log, mỗi trace có `lab-agent-run` → `rag-retrieve` + `llm-generate` | [evidence/langfuse-traces-export.txt](evidence/langfuse-traces-export.txt); span tree còn được kiểm chứng tự động bằng `tests/test_trace_tree.py` |
| Số PII leak | 0 theo validator (preview đã qua `summarize_text`), nhưng scrubber chưa được đăng ký nên field khác không được bảo vệ | **0** — kể cả khi gửi email, SĐT, CCCD, thẻ, hộ chiếu giả qua API | [evidence/05-pii-redaction.txt](evidence/05-pii-redaction.txt) |
| Latency P95 / TTFT P95 | 151 ms / 50 ms (server-side, 10 request) | Pha bình thường: **159 ms / 51 ms** (54 request); cả cửa sổ gồm practice `rag_slow`: 2 654 ms / 51 ms | TTFT không đổi khi `rag_slow` ⇒ chậm ở trước LLM |
| Retrieval success rate | 100% (10/10) | Pha bình thường **100%**; cả cửa sổ 88.1% (10 lỗi `RuntimeError` trong practice `tool_fail`) | Hiển thị cùng error rate trên panel errors |

## 4. Logging và PII

- **Cách tạo/nhận và truyền correlation ID:** [`app/middleware.py`](../app/middleware.py) chạy đầu tiên cho mọi request: (1) `clear_contextvars()` để xóa context của request trước; (2) đọc header `x-request-id`, chỉ chấp nhận khi đúng format `req-<8-hex>` (chuẩn hóa chữ thường), ngược lại sinh mới `req-` + 8 ký tự hex từ `uuid4`; (3) `bind_contextvars(correlation_id=...)` nên mọi log trong request tự mang ID; (4) lưu vào `request.state` để agent đưa ID vào trace metadata; (5) trả lại `x-request-id` và `x-response-time-ms` trong response header.
- **Các metadata được ghi vào structured log:** [`app/main.py`](../app/main.py) bind `user_id_hash` (SHA-256 cắt 12 ký tự, không log `user_id` gốc), `session_id`, `feature`, `model`, `env` **trước** dòng `request_received`, nên cả `request_received`, `response_sent` và `request_failed` đều có đủ. `response_sent` có thêm `latency_ms`, `ttft_ms`, `tokens_in/out`, `cost_usd`, `quality_score`, `tool_name`, `tool_success` — đúng các field dashboard cần.
- **Cách bảo đảm PII được scrub trước khi ghi:** trong [`app/logging_config.py`](../app/logging_config.py), processor `scrub_event` đứng **sau** `format_exc_info` (để cả traceback đã thành chuỗi cũng được quét) và **trước** `JsonlFileProcessor` và `JSONRenderer`. Tôi viết lại `scrub_event` để quét đệ quy mọi field chuỗi (top-level, `payload` lồng nhau, list) chứ không chỉ `payload`, vì `request_failed` có `payload.detail = str(exc)` và code sau này có thể log field mới. [`app/pii.py`](../app/pii.py) có pattern cho email (kể cả `+tag`), thẻ thanh toán 16 số và Amex 15 số, điện thoại Việt Nam (`0…`, `+84`, `84`, `(+84)` với dấu cách/chấm/gạch), CCCD 12 số và hộ chiếu Việt Nam (`[A-Z]` + 7 số). Thẻ được che trước điện thoại/CCCD để chuỗi số dài không bị che một phần. Ngoài log, trace cũng chỉ nhận preview đã scrub (`summarize_text`), các observation dùng `capture_input=False, capture_output=False`.
- **Cách kiểm chứng kết quả:** unit test cho từng loại PII và cho trường hợp không được che nhầm (timestamp, cost, correlation ID, tên model) trong [`tests/test_pii.py`](../tests/test_pii.py); test end-to-end qua API trong [`tests/test_correlation_logging.py`](../tests/test_correlation_logging.py) kiểm tra file log không còn chuỗi PII thô, context không rò giữa hai request và header được trả đúng; runtime: gửi PII giả qua API thật, file log chỉ còn `[REDACTED_*]` và đếm chuỗi thô = 0 ([evidence/05-pii-redaction.txt](evidence/05-pii-redaction.txt)); `validate_logs.py` báo 0 PII leak.

## 5. Tracing và prompt versioning

- **Cách xác nhận traces do chính tôi tạo trong project cá nhân:** key trong `.env` thuộc project `day13-k4-l3a-2A202603014` (xác nhận qua API). Tôi tự chạy workload ngày 2026-09-30 09:51–10:00 ICT, rồi đọc lại observation qua `GET /api/public/v2/observations` và nối từng trace với `correlation_id` do load test in ra và có trong `data/logs.jsonl`: 75/75 trace khớp ([evidence/langfuse-traces-export.txt](evidence/langfuse-traces-export.txt)). Ảnh trace list phải thấy tên project.
- **Cấu trúc root/retrieval/generation observations:**

  ```text
  day13-agent-request (trace; user_id = hash, session_id, tags [lab, feature, model],
  │                    metadata: correlation_id, feature, model)
  └── lab-agent-run            agent       metadata: prompt_name/label/version/source, doc_count, query_preview đã scrub
      ├── rag-retrieve         retriever   input: query_preview đã scrub; output: doc_count, docs; lỗi → level ERROR
      └── llm-generate         generation  model, usage_details {input, output, total}, cost_details {input, output, total},
                                           completion_start_time (TTFT), prompt link (name + version)
  ```

  `rag-retrieve` và `llm-generate` là child observation nhờ `@observe(as_type="retriever"/"generation")` trên [`app/mock_rag.py`](../app/mock_rag.py) và [`app/mock_llm.py`](../app/mock_llm.py), được gọi bên trong root `lab-agent-run`. Prompt được link vào generation qua `propagate_attributes(prompt=managed_prompt)` có sẵn ở [`app/agent.py`](../app/agent.py). Cost trên trace và `cost_usd` trong log dùng chung hàm `cost_details()` (3 USD/1M input, 15 USD/1M output) nên hai nguồn luôn khớp. Quan hệ cha-con, loại observation, model/usage/cost, không có PII thô và level `ERROR` khi retrieval lỗi được kiểm chứng tự động bằng OpenTelemetry in-memory exporter trong [`tests/test_trace_tree.py`](../tests/test_trace_tree.py) (không cần key).
- **Cách nối trace với log:** cùng một `correlation_id` nằm trong mọi dòng log của request và trong trace metadata (`propagate_attributes(metadata={"correlation_id": ...})`). Trên Langfuse: Traces → filter Metadata `correlation_id` = ID lấy từ log.
- **Prompt name:** `day13-chat`
- **Version/label baseline:** v1 — labels `baseline`, `production` (template gốc 3 biến).
- **Version/label candidate:** v2 — label `candidate` (thêm dòng "Answer in no more than three concise bullet points.").
- **Trace ID của mỗi version** (mỗi pha: restart API với `LANGFUSE_PROMPT_LABEL` tương ứng, chạy cùng `python scripts/load_test.py` 10 request; cả 10/10 trace mỗi pha đều ghi đúng version, `prompt_source=langfuse`):

  | Pha | Label app dùng | Version | Trace ID tiêu biểu | correlation_id |
  |---|---|---|---|---|
  | Baseline (09:51:48 ICT) | `baseline` | v1 | `f389cd4ad2ab556423d268e9b978d429` | `req-cbc06987` |
  | Candidate (09:51:59) | `candidate` | v2 | `12e7b45a84be6e183e230055310e0fad` | `req-6a3935a7` |
  | Promote `production` → v2 (09:57:21), chạy lúc 09:57:25 | `production` | v2 | `d4e251bdbbf7952ea3cdf245cc949641` | `req-c350f30d` |
  | Rollback `production` → v1 (09:57:39), chạy lúc 09:57:41 | `production` | v1 | `44d49656129b4a968040179a953398a4` | `req-0ca495b4` |

  Trạng thái cuối: `baseline`→v1, `candidate`→v2, `production`→v1 (sau rollback). Generation của v2 nhận prompt có dòng "Answer in no more than three concise bullet points." trong `prompt_preview`; generation của v1 không có.
- **Cách promote và rollback `production`:** không sửa code — chỉ di chuyển label. Có thể làm trên UI Langfuse hoặc bằng [`scripts/prompt_versions.py`](../scripts/prompt_versions.py) (`bootstrap` tạo v1/v2; `promote --version 2` là promote; `promote --version 1` là rollback). Label trong Langfuse là duy nhất giữa các version nên gán `production` cho v2 tự gỡ khỏi v1. Sau mỗi lần đổi label: restart API (tránh cache 60 s trong tiến trình), chạy `python scripts/load_test.py`, mở trace mới và xác nhận `prompt_label=production` + `prompt_version` tương ứng, `prompt_source=langfuse`. Rollback thật sự chỉ là một lệnh đổi label và một lần restart — không sửa code, không build lại, trace ngay sau đó đã quay về v1.

## 6. Dashboard, SLO và alerts

- **Dashboard và sáu panel:** [`scripts/build_dashboard.py`](../scripts/build_dashboard.py) đọc `data/logs.jsonl` và chính contract [`config/dashboard.yaml`](../config/dashboard.yaml) (tiêu đề, đơn vị, threshold lấy từ YAML, không hard-code), tổng hợp bằng [`app/log_analytics.py`](../app/log_analytics.py) và xuất HTML tự chứa: time range 60 phút (giờ ICT), tự refresh 30 s (`--watch` dựng lại liên tục), 6 panel: (1) latency P50/P95/P99 + TTFT P95, đường threshold 3000 ms và đường SLO 2000 ms; (2) traffic request/phút, đường ≥ 1 rpm; (3) error rate + retrieval success cùng thang %, breakdown `error_type`, đường 2%; (4) cost theo phút + meter tổng so với 2.5 USD; (5) tokens in/out stacked theo phút + meter so với 50 000; (6) quality trung bình, đường 0.75. Mỗi panel có trạng thái ✓/✕ kèm chữ, tooltip theo phút và bảng dữ liệu ("Table view"). Ảnh: [evidence/11-dashboard-overview.png](evidence/11-dashboard-overview.png).

  Đọc dashboard runtime (60 phút, 22:21 ICT): latency P50/P95/P99 = 153/2 654/2 675 ms, TTFT P95 = 51 ms; SLI 76.2% < 99.5% nên dòng SLO báo ✕ vì 10 request của practice `rag_slow`; error rate 11.9% (✕ > 2%), retrieval success 88.1%; cost $0.2165 (8.7% ngưỡng 2.5 USD), tokens out 13 926 (27.9% ngưỡng 50 000), quality 0.88 (✓ ≥ 0.75). Bản zoom 12 phút để nhìn rõ từng phút: [evidence/11b-dashboard-zoom-12min.png](evidence/11b-dashboard-zoom-12min.png) — spike latency ở 22:17 (`rag_slow`), error 100% ở 22:19 (`tool_fail`), tokens out/cost tăng ~3.5 lần ở 22:20 (`cost_spike`). Mỗi practice chỉ làm đúng panel liên quan thay đổi, chứng minh dashboard phản ánh dữ liệu thật.

- **SLO và lý do chọn:** [`config/slo.yaml`](../config/slo.yaml) — `fast_successful_requests`: trong cửa sổ 28 ngày, **99.5%** request phải trả lời thành công **và** `latency_ms ≤ 2000`. Tôi siết ngưỡng từ 3000 ms xuống 2000 ms dựa trên baseline: P95 = 151 ms, TTFT P95 = 50 ms. Với 3000 ms, sự cố retrieval chậm thêm 2.5 s (latency ~2.65 s, gấp ~17 lần baseline) vẫn được tính là "tốt" và không đốt budget — SLO như vậy vô dụng cho chính loại sự cố đã biết. 2000 ms vẫn gấp >13 lần baseline P95 nên ít báo động giả và còn chỗ cho LLM thật chậm hơn fake LLM. Đường 3000 ms trên dashboard giữ nguyên theo contract như trần cứng.
- **Cách tính error budget:** budget = 1 − 99.5% = **0.5%** số request trong 28 ngày = 5 request xấu trên 1000 request, tương đương **201.6 phút** (28 × 24 × 60 × 0.005) nếu tính theo thời gian. Burn rate = tỉ lệ xấu trong cửa sổ / 0.005: burn rate 14.4 trong 1 giờ (≥ 7.2% request xấu) đốt 2% budget mỗi giờ → page; burn rate 6 trong 6 giờ (≥ 3%) → ticket. Chính sách: budget > 50% release bình thường; 0–50% mọi thay đổi prompt/model phải qua label `candidate` trước; hết budget thì đóng băng promote `production`, chỉ rollback và sửa độ tin cậy. Áp dụng vào giờ practice ở trên: 84 request, 20 request xấu (10 chậm > 2000 ms + 10 lỗi) ⇒ bad ratio 23.8% ⇒ burn rate 47.6, vượt xa ngưỡng 14.4 nên sẽ page. Nếu hệ thống phục vụ 10 000 request trong 28 ngày thì budget là 50 request xấu và giờ đó đã đốt 40% budget.
- **Ba alert và runbook tương ứng:** [`config/alert_rules.yaml`](../config/alert_rules.yaml) + [`docs/alerts.md`](../docs/alerts.md), tất cả gửi Slack `#day13-k4-l3a-alerts`, owner `llmops-oncall (Nguyễn Đăng Thực)`:
  1. `high_latency_p95` (P2-high, 5m): P95 `latency_ms` > 2000 ms — [runbook](../docs/alerts.md#alert-1-high_latency_p95).
  2. `high_error_rate` (P1-critical, 5m): error rate > 2% hoặc retrieval success < 90% — [runbook](../docs/alerts.md#alert-2-high_error_rate).
  3. `cost_per_request_spike` (P3-warning, 15m): cost trung bình > 0.005 USD/request (~2.4× baseline 0.0021) hoặc tổng 24 h > 2.5 USD — [runbook](../docs/alerts.md#alert-3-cost_per_request_spike).

  Cả ba đều theo triệu chứng người dùng/ngân sách (chậm, lỗi, tốn tiền), không theo tên component; runbook mỗi alert đi đúng thứ tự dashboard → log (`scripts/investigate.py`) → trace.

## 7. Điều tra challenge

Tôi chạy challenge hai lần với cùng file và seed. **Lần 1** (09:24–09:28 ICT) khi `.env` chưa có key Langfuse nên chỉ có metric + log; kết luận ở lần này dự đoán `rag-retrieve` ≈ 2.5 s. **Lần 2** (09:57–10:00 ICT) chạy lại đúng trình tự với tracing bật, và toàn bộ evidence 12/13/14 dưới đây lấy từ **lần 2** để metric, log và trace thuộc cùng một sự cố. API lần 2 chạy ở cổng 8010 (`LAB_BASE_URL`) vì cổng 8000 đang bị một server khác trên máy dùng.

| Thời điểm (UTC, ICT = +7) | Hành động | Client thấy |
|---|---|---|
| 02:57:54–02:57:58 | Mốc trước sự cố: sample workload + `load_test.py --challenge --concurrency 5` **khi chưa inject** | 0.5–0.8 s |
| 02:58:57 | `python scripts/inject_incident.py` (đọc `incident` từ `config/challenge.json`) | — |
| 02:58:58–02:59:12 | `python scripts/load_test.py --challenge --concurrency 5` (thứ tự theo seed 1311: u04, u01, u05, u03, u02) | 2.7–13.3 s |
| 02:59:12–02:59:39 | Sample workload khi incident vẫn bật (phạm vi ảnh hưởng) | 8.0–13.3 s |
| 02:59:59 | Mitigation `inject_incident.py --disable`, chạy lại cùng challenge queries | 0.6–0.8 s |

- **Challenge ID:** `day13-k4-l3a-monitoring-llmops-v1` (K4, seed 1311, `affected_feature=monitoring`, `latency_threshold_ms=2000`).
- **Khoảng thời gian điều tra:** 2026-09-30 **09:58:58 – 09:59:39 ICT** (02:58:58–02:59:39Z); đối chứng 09:57 (trước) và 10:00 (sau mitigation).
- **Triệu chứng từ metrics:** ([evidence/12-incident-metric.png](evidence/12-incident-metric.png) — 60 phút, thấy cả lần 1 lúc 09:25 và lần 2 lúc 09:59; [zoom 6 phút](evidence/12b-incident-metric-zoom.png)) P95 latency của feature `monitoring` tăng từ **181 ms** (09:57) lên **2 666 ms** (09:59), P50 ≈ P95 ≈ P99 ≈ 2 653–2 666 ms nghĩa là **mọi** request chậm như nhau, không phải chỉ phần đuôi. Dòng SLO báo ✕: SLI 71.4% trong 60 phút (mục tiêu 99.5%). Các tín hiệu khác **không đổi**: TTFT P95 = **50 ms**, error rate 0%, retrieval success 100%, tokens/cost/quality bình thường. Ngưỡng 3000 ms của contract vẫn báo ✓ — chỉ đường SLO 2000 ms (bằng `latency_threshold_ms` của challenge) bắt được sự cố, đúng lý do tôi siết SLO ở mục 6.
- **Log line và correlation ID liên quan:** ([evidence/13-incident-log.txt](evidence/13-incident-log.txt)) `python scripts/investigate.py --since 3 --end 2026-09-30T02:59:39Z --feature monitoring --latency-ms 2000` trả về 5/5 request challenge vượt 2000 ms. Request được chọn: **`req-ca621f18`** (`session_id=k4-l3a-challenge-s02`, câu "How should an engineer investigate tail latency?"):
  ```json
  {"event": "response_sent", "correlation_id": "req-ca621f18", "feature": "monitoring", "latency_ms": 2653, "ttft_ms": 50, "tokens_in": 34, "tokens_out": 128, "cost_usd": 0.002022, "tool_name": "retrieval", "tool_success": true, "ts": "2026-09-30T02:59:01.533715Z", "...": "..."}
  ```
  Cùng session s02 trước khi inject: `req-d8ae8866`, `latency_ms=181`. Phạm vi: 10 request `qa`/`summary` gửi trong lúc incident cũng chậm ≈ 2 653 ms ⇒ ảnh hưởng **mọi feature**; `monitoring` chỉ là feature của bộ query challenge.
- **Trace ID và span gây ảnh hưởng:** trace **`67daa54d749f9a18e73c532b28e3d734`** (metadata `correlation_id=req-ca621f18`, prompt `day13-chat`/`production`/v1). Waterfall: `lab-agent-run` **2 654 ms** = `rag-retrieve` **2 502 ms** (level DEFAULT, trả 1 doc) + `llm-generate` **152 ms** (model `claude-sonnet-4-5`, usage 34/128 token, cost 0.002022 USD, completion_start_time cách start 51 ms). Cả 5 trace challenge cùng mẫu: `rag-retrieve` 2 501–2 512 ms, `llm-generate` 151–152 ms. Trace đối chứng trước sự cố `a1fa0c269fe5ee4426d3ad17decd54de` (`req-cfb53906`): `rag-retrieve` 1 ms, `llm-generate` 152 ms. Span gây ảnh hưởng: **`rag-retrieve`**.
- **Root cause:** bước **retrieval (`rag-retrieve`, vector store) chậm thêm ~2.5 s mỗi request** (incident `rag_slow`). Ba lớp cùng chỉ về một chỗ: (1) **metric** — latency tăng một lượng cố định ≈ 2 500 ms ở mọi request và mọi feature trong khi TTFT, token, cost và error rate không đổi ⇒ không phải LLM, không phải tải hay độ dài câu trả lời; (2) **log** — `req-ca621f18` có `latency_ms=2653` nhưng `ttft_ms=50`, `tool_success=true` ⇒ retrieval vẫn trả kết quả, chỉ chậm; (3) **trace** — cùng `correlation_id`, `rag-retrieve` chiếm 2 502/2 654 ms (94%), `llm-generate` giữ nguyên 152 ms như trước sự cố.
- **Fix action:** tắt nguồn gây chậm ở retrieval (`python scripts/inject_incident.py --disable`, tương đương khôi phục vector store/rollback thay đổi retrieval) ⇒ đã kiểm chứng: cùng 5 challenge queries lúc 10:00 ICT có latency ≈ 152 ms, 0 request vượt 2000 ms, trace `8b83fa60e682ce3b6984707329327a6e` (`req-9c83dcef`) có `rag-retrieve` 0 ms. Nếu chưa khôi phục được vector store ngay: đặt timeout cho retrieval (ví dụ 500 ms) và trả về tài liệu fallback/cache cho câu hỏi phổ biến, gắn cờ chất lượng thấp thay vì để người dùng chờ.
- **Preventive measure:** (1) alert `high_latency_p95` theo SLO 2000 ms, duration 5 phút ([config/alert_rules.yaml](../config/alert_rules.yaml)) — contract 3000 ms sẽ bỏ lỡ sự cố này; (2) ghi thêm `retrieval_ms` vào log `response_sent` và vẽ lên panel latency để phân biệt retrieval với LLM ngay từ dashboard, không phải mở trace mới biết; (3) timeout + circuit breaker cho retrieval kèm fallback; (4) chạy `agent.run` trong threadpool (`def` endpoint hoặc `run_in_threadpool`) — hiện event loop bị chặn nên 2.65 s phía server thành 8–13 s phía client khi có 5 request đồng thời, sự cố bị khuếch đại ~5 lần; (5) synthetic probe định kỳ gửi một câu hỏi cố định để phát hiện retrieval chậm trước người dùng.

**Luyện tập trước CP3 (practice, chạy trước khi nhận file challenge):** Tôi chạy `--scenario rag_slow` với cùng workload để tập đúng quy trình ([evidence/practice-rag-slow-investigation.txt](evidence/practice-rag-slow-investigation.txt)). **Metrics:** bảng theo phút chỉ ra phút 22:17 ICT có P95 = 2 675 ms (bình thường ~160 ms) trong khi TTFT P95 vẫn 53 ms, error rate 0% ⇒ chậm nằm ở bước trước khi LLM sinh token đầu, không phải LLM hay lỗi. **Logs:** `investigate.py --latency-ms 2000` liệt kê 10 request chậm, ví dụ `req-3dea41cc` (`latency_ms=2653`, `ttft_ms=51`, `feature=qa`, `tool_success=true`). **Trace:** practice chạy khi chưa có key nên không có trace; dự đoán `rag-retrieve` ≈ 2.5 s, `llm-generate` ≈ 0.15 s sau đó được xác nhận đúng bằng trace thật của challenge (mục trên). Tương tự, `tool_fail` hiện ra ở panel errors (100% lỗi `RuntimeError`, retrieval success 0% lúc 22:19, log `payload.detail = "Vector store timeout"`), còn `cost_spike` hiện ra ở panel tokens/cost (avg cost 0.0077 USD/request ≈ 3.5× bình thường, tokens_out tăng trong khi latency không đổi).

## 8. Giải thích và tự đánh giá

- **Một quyết định kỹ thuật quan trọng và lý do:** đặt child observation bằng decorator ngay trên `retrieve()` và `FakeLLM.generate()` thay vì bọc thủ công trong `agent.run`. Lý do: (1) mọi nơi gọi hai hàm này đều được trace, không phụ thuộc người gọi nhớ mở span; (2) exception trong retrieval tự được ghi thành level `ERROR` trên đúng span `rag-retrieve` — đúng thứ cần để khoanh vùng sự cố; (3) generation đứng trong `propagate_attributes(prompt=...)` nên được link prompt name/version mà không phải truyền prompt object xuống mock. Đi kèm: gom bảng giá vào một hàm `cost_details()` dùng chung cho trace và log để cost không bao giờ lệch giữa hai nguồn. Quyết định thứ hai: chỉ nhận `x-request-id` đúng format `req-<8-hex>` — header tùy ý có thể chứa PII (ví dụ số điện thoại) hoặc ký tự phá log, nên an toàn hơn là sinh ID mới.
- **Một lỗi/blocker đã gặp:** (1) Máy mặc định Python 3.14; một số version được pin trong `requirements.txt` (ví dụ `pydantic==2.11.4` kéo theo `pydantic-core`) chưa có wheel cho 3.14 nên cài dễ lỗi build. Xử lý: tạo `.venv` bằng `py -3.13` — không đổi version pin để repo vẫn tái hiện đúng. (2) Sau khi sửa CP1, validator vẫn có thể báo lỗi cũ vì `validate_logs.py` đọc toàn bộ `data/logs.jsonl`. Xử lý: lưu output baseline vào `evidence/baseline/`, chuyển log baseline ra khỏi repo, khởi động lại API rồi mới đo. (3) Muốn kiểm chứng span tree mà không cần key: Langfuse client là singleton toàn tiến trình nên dựng client test trong cùng tiến trình pytest sẽ xung đột với client của test khác (SDK trả client disabled khi có nhiều instance). Xử lý: chạy agent trong subprocess với `Langfuse(span_exporter=InMemorySpanExporter())`, in span ra JSON rồi assert quan hệ cha-con, loại observation, usage/cost và PII. (4) Khi đọc output load test `rag_slow` với `--concurrency 5`, client thấy tới ~13 s trong khi log ghi `latency_ms` ≈ 2.65 s. Nguyên nhân: `/chat` là `async def` nhưng gọi `agent.run` đồng bộ (có `time.sleep`) nên chặn event loop, 5 request bị xếp hàng; `latency_ms` và `x-response-time-ms` chỉ đo lúc request đã được xử lý. Tôi ghi lại thành hạn chế thay vì đổi hành vi server trong lab. (5) Khi đọc lại trace, `GET /api/public/traces` trả HTTP 410 `LEGACY_API_UNAVAILABLE_FOR_NEW_ORGANIZATION` vì org Langfuse tạo sau 16/09/2026. Xử lý: chuyển sang `GET /api/public/v2/observations` (`api.observations.get_many`) rồi tự gom observation theo `traceId`. (6) Trong lúc chạy các pha prompt, `/health` ở cổng 8000 trả `{'status': 'ok', 'env': 'development'}` — không phải app lab: một server uvicorn `--reload` của project khác trên máy đã chiếm cổng 8000, uvicorn của lab bind lỗi `WinError 10048` và load test bắn nhầm sang server kia (nhận 404, không có side effect). Tìm ra bằng `Get-NetTCPConnection -LocalPort 8000` → PID → command line. Xử lý: không tắt server của người khác mà thêm biến `LAB_BASE_URL` cho `load_test.py`/`inject_incident.py` (mặc định vẫn cổng 8000), chạy lab ở cổng 8010, và script điều phối kiểm tra `/health` phải có `tracing_enabled` và tiến trình uvicorn còn sống trước khi gửi request. Các pha bị ảnh hưởng được chạy lại toàn bộ. (7) Metadata observation trên Langfuse tự có `scope.attributes.public_key` do SDK gắn — ảnh `08-trace-metadata` phải che dòng này, và file export đã lọc các field `scope.*`.
- **Cách tìm nguyên nhân và xử lý:** xem mục trên.
- **Cách hiểu luồng Metrics → Logs → Traces:** metrics trả lời "có vấn đề gì và từ lúc nào" với chi phí thấp nhưng mất chi tiết từng request (P95 tăng, error rate tăng). Logs có cấu trúc trả lời "request nào bị ảnh hưởng": lọc cửa sổ thời gian đó theo `latency_ms`/`event`/`feature` để lấy `correlation_id`. Trace của đúng `correlation_id` trả lời "bước nào gây ra": waterfall cho biết thời gian nằm ở `rag-retrieve` hay `llm-generate`, span nào `ERROR`. Chỉ kết luận root cause khi cả ba lớp chỉ về cùng một nguyên nhân; ví dụ ở practice `rag_slow`, TTFT P95 không đổi trong khi latency tăng đã loại trừ LLM trước cả khi mở trace.
- **Vai trò của prompt version, token/cost, SLO hoặc rollback trong vận hành LLM:** prompt là "code" của ứng dụng LLM nhưng thay đổi được mà không deploy, nên phải có version bất biến + label di động và mỗi trace phải ghi version đã dùng — nếu không sẽ không biết câu trả lời xấu đến từ prompt nào. Rollback = chuyển label `production` về version cũ, mất vài giây, không cần build lại. Token/cost là chiều thứ ba ngoài latency/error: một prompt làm câu trả lời dài gấp 4 lần không gây lỗi nhưng đốt ngân sách, nên cần dashboard và alert riêng. SLO + error budget biến "hệ thống có ổn không" thành con số, và quyết định khi nào được phép promote prompt mới (còn budget) hay phải đóng băng.
- **Điều quan trọng nhất đã học:** observability phải được thiết kế từ contract dữ liệu: log phải có đúng field cho dashboard, trace phải có cùng `correlation_id` với log, và PII phải bị chặn tại processor trước khi serialize — sửa sau khi dữ liệu đã ghi xuống là quá muộn.
- **Hạn chế hoặc phần chưa hoàn thành, nếu có:** (1) Request đầu tiên sau mỗi lần khởi động có root ~1.0–1.6 s dù `rag-retrieve` và `llm-generate` bình thường, vì app fetch prompt từ Langfuse (US) khi cache trống; nên prefetch prompt lúc startup và dùng cache TTL dài hơn cho label `production`. (2) Latency đo server-side không tính thời gian xếp hàng khi event loop bị chặn (xem blocker 4); fix đề xuất: đổi `/chat` thành `def` hoặc gọi `await run_in_threadpool(agent.run, ...)`, và đo thêm latency ở client/load balancer. (3) Pattern PII dựa trên regex nên có thể che thừa chuỗi số dài không phải PII và chưa nhận diện địa chỉ hay họ tên; bước tiếp theo là thêm NER hoặc allowlist field. (4) `quality_score` chỉ là heuristic; nên bổ sung đánh giá theo `data/expected_answers.jsonl` hoặc LLM-as-judge làm score trên Langfuse.

## 9. Checklist trước khi nộp

- [ ] Kết quả và evidence thuộc commit SHA cuối.
- [ ] Tất cả ảnh/output mở được bằng đường dẫn tương đối.
- [x] Incident evidence nối đúng metric → log → trace (cùng lần chạy thứ 2, `req-ca621f18` ↔ trace `67daa54d…`).
- [ ] Trace/prompt evidence thuộc project Langfuse cá nhân và ảnh không lộ key/secret.
- [x] Repository chạy lại được theo README.
- [x] Không có secret, API key, PII thô hoặc evidence của người khác/lớp khác.
- [ ] URL repo và commit SHA cuối đã được nộp trên LMS/Codelabs.
