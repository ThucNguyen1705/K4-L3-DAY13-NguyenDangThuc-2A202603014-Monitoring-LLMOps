# Alert và Runbook

Mỗi alert dựa trên triệu chứng người dùng hoặc SLO, không dựa trực tiếp vào tên implementation nội bộ. Định nghĩa máy đọc được nằm trong [`../config/alert_rules.yaml`](../config/alert_rules.yaml); SLO và error budget nằm trong [`../config/slo.yaml`](../config/slo.yaml).

Quy trình chung cho mọi alert: **Metrics → Logs → Traces**. Dashboard cho biết triệu chứng và khoảng thời gian; `data/logs.jsonl` cho biết request nào bị ảnh hưởng qua `correlation_id`; trace Langfuse có cùng `correlation_id` trong metadata cho biết span nào chậm hoặc lỗi.

Lệnh hỗ trợ (chạy từ thư mục gốc repo):

```bash
python scripts/build_dashboard.py          # dựng lại dashboard 60 phút từ data/logs.jsonl
python scripts/investigate.py --since 15   # tóm tắt 15 phút gần nhất, liệt kê request bất thường
```

## Alert 1: high_latency_p95

- **Tên:** `high_latency_p95`
- **Severity:** P2-high
- **Duration:** 5m (đánh giá mỗi 1m)
- **Kênh thông báo:** Slack `#day13-k4-l3a-alerts`
- **SLI/SLO liên quan:** `fast_successful_requests` — 99.5% request thành công và `latency_ms <= 2000` trong 28 ngày.
- **Điều kiện và thời gian duy trì:** P95 của `response_sent.latency_ms` > 2000 ms liên tục 5 phút.
- **Ảnh hưởng tới người dùng:** ít nhất 5% người dùng chờ > 2 s cho một câu trả lời; mỗi request chậm đốt error budget.
- **Ba bước kiểm tra đầu tiên:**
  1. Dashboard panel *Latency percentiles and TTFT*: so sánh P95 với TTFT P95. TTFT bình thường (~50 ms) nhưng latency cao ⇒ thời gian mất ở bước trước/ sau LLM (retrieval, xử lý); TTFT cũng tăng ⇒ nghi LLM provider.
  2. Lọc log chậm: `python scripts/investigate.py --since 15 --latency-ms 2000`, lấy một `correlation_id` và `feature` bị ảnh hưởng (chỉ một feature hay tất cả?).
  3. Mở Langfuse, lọc trace theo metadata `correlation_id` đó, so sánh thời lượng `rag-retrieve` với `llm-generate` trong waterfall.
- **Mitigation tạm thời:** nếu `rag-retrieve` chậm — chuyển sang corpus/cache dự phòng, giảm top-k hoặc đặt timeout retrieval; nếu `llm-generate` chậm — chuyển model dự phòng hoặc rollback prompt label `production` về version trước; nếu do deploy mới — rollback.
- **Owner:** llmops-oncall (Nguyễn Đăng Thực)

## Alert 2: high_error_rate

- **Tên:** `high_error_rate`
- **Severity:** P1-critical
- **Duration:** 5m (đánh giá mỗi 1m)
- **Kênh thông báo:** Slack `#day13-k4-l3a-alerts`
- **SLI/SLO liên quan:** `fast_successful_requests` và guardrail `error_rate_pct_max: 2`, `retrieval_success_rate_pct_min: 90`.
- **Điều kiện và thời gian duy trì:** `request_failed / request_received` > 2% **hoặc** retrieval success < 90% liên tục 5 phút.
- **Ảnh hưởng tới người dùng:** người dùng nhận HTTP 500, không có câu trả lời. Error rate 7.2% trong 1 giờ tương đương burn rate 14.4 (đốt 2% budget 28 ngày mỗi giờ).
- **Ba bước kiểm tra đầu tiên:**
  1. Dashboard panel *Error rate and retrieval success*: xem breakdown `error_type` và retrieval success cùng giảm hay không (lỗi ở retrieval hay ở chỗ khác).
  2. Lọc log `event == "request_failed"`: `python scripts/investigate.py --since 15 --failed`, đọc `error_type`, `payload.detail` và lấy `correlation_id`.
  3. Mở trace có cùng `correlation_id`: observation nào có level `ERROR` và `status_message` là gì (ví dụ `rag-retrieve` báo `Vector store timeout`).
- **Mitigation tạm thời:** nếu vector store lỗi — bật chế độ trả lời fallback không cần retrieval (có gắn cờ chất lượng thấp) hoặc chuyển sang replica; nếu lỗi sau deploy/prompt mới — rollback; thông báo trạng thái trên Slack mỗi 30 phút đến khi error rate < 2%.
- **Owner:** llmops-oncall (Nguyễn Đăng Thực)

## Alert 3: cost_per_request_spike

- **Tên:** `cost_per_request_spike`
- **Severity:** P3-warning
- **Duration:** 15m (đánh giá mỗi 5m)
- **Kênh thông báo:** Slack `#day13-k4-l3a-alerts`
- **SLI/SLO liên quan:** guardrail `cost_per_request_usd_max: 0.005` và `daily_cost_usd_max: 2.5` trong `config/slo.yaml`.
- **Điều kiện và thời gian duy trì:** trung bình `response_sent.cost_usd` > 0.005 USD/request (baseline ~0.0021) **hoặc** tổng cost 24 giờ > 2.5 USD, duy trì 15 phút.
- **Ảnh hưởng tới người dùng:** chưa làm hỏng trải nghiệm ngay nhưng đốt ngân sách; câu trả lời dài bất thường thường kéo theo latency cao và chất lượng giảm.
- **Ba bước kiểm tra đầu tiên:**
  1. Dashboard panel *Input and output tokens* và *Cost over time*: cost tăng do `tokens_out` (câu trả lời dài) hay `tokens_in` (prompt/context phình)?
  2. Lọc log `response_sent` có `cost_usd` cao: `python scripts/investigate.py --since 60 --cost-usd 0.005`, lấy `correlation_id`, kiểm tra `feature` và prompt version liên quan.
  3. Mở trace, xem `usage_details`/`cost_details` của `llm-generate` và prompt name/version được link — so sánh với trace trước sự cố.
- **Mitigation tạm thời:** đặt `max_tokens` cho generation, rollback label `production` nếu prompt mới làm câu trả lời dài hơn, chuyển feature ít quan trọng sang model rẻ hơn; báo owner ngân sách nếu dự báo vượt 2.5 USD/ngày.
- **Owner:** llmops-oncall (Nguyễn Đăng Thực)
