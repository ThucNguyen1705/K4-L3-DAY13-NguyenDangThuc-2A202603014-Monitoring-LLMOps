from __future__ import annotations

import hashlib
import re

# Thứ tự có ý nghĩa: chuỗi số dài (thẻ) được che trước để phone/CCCD không che mất một phần.
PII_PATTERNS: dict[str, str] = {
    "email": r"[\w.+-]+@[\w.-]+\.\w+",
    # Visa/Master 16 số (4-4-4-4) và Amex 15 số (4-6-5), cho phép dấu cách hoặc gạch.
    "credit_card": r"\b(?:\d{4}[- ]?){3}\d{4}\b|\b\d{4}[- ]?\d{6}[- ]?\d{5}\b",
    # 0xxxxxxxxx, +84/84/(+84) + 9 số, cho phép dấu cách, chấm hoặc gạch giữa các số.
    "phone_vn": r"(?<![\d+])(?:\(?\+?84\)?|0)(?:[ .-]?\d){9}(?!\d)",
    "cccd": r"\b\d{12}\b",
    # Hộ chiếu Việt Nam: 1 chữ in hoa + 7 số, ví dụ C1234567.
    "passport_vn": r"\b[A-Z]\d{7}\b",
}


def scrub_text(text: str) -> str:
    safe = text
    for name, pattern in PII_PATTERNS.items():
        safe = re.sub(pattern, f"[REDACTED_{name.upper()}]", safe)
    return safe


def summarize_text(text: str, max_len: int = 80) -> str:
    safe = scrub_text(text).strip().replace("\n", " ")
    return safe[:max_len] + ("..." if len(safe) > max_len else "")


def hash_user_id(user_id: str) -> str:
    return hashlib.sha256(user_id.encode("utf-8")).hexdigest()[:12]
