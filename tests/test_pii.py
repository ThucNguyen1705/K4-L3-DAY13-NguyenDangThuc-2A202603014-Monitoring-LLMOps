import pytest

from app.pii import scrub_text, summarize_text


def test_scrub_email() -> None:
    out = scrub_text("Email me at student@vinuni.edu.vn")
    assert "student@" not in out
    assert "REDACTED_EMAIL" in out


def test_scrub_email_with_plus_tag() -> None:
    out = scrub_text("Send to first.last+lab@example.com now")
    assert "example.com" not in out
    assert out == "Send to [REDACTED_EMAIL] now"


def test_scrub_common_vietnamese_phone_formats() -> None:
    phone_numbers = (
        "0901234567",
        "090 123 4567",
        "090.123.4567",
        "090-123-4567",
        "+84 90 123 4567",
        "84901234567",
        "(+84) 90 123 4567",
    )

    for phone_number in phone_numbers:
        out = scrub_text(f"Contact: {phone_number}")
        assert phone_number not in out
        assert "REDACTED_PHONE_VN" in out


def test_scrub_cccd() -> None:
    out = scrub_text("CCCD của tôi là 001099012345.")
    assert "001099012345" not in out
    assert out == "CCCD của tôi là [REDACTED_CCCD]."


@pytest.mark.parametrize(
    "card",
    ["4111 1111 1111 1111", "4111-1111-1111-1111", "4111111111111111", "3782 822463 10005"],
)
def test_scrub_payment_card_formats(card: str) -> None:
    out = scrub_text(f"Card {card} expires soon")
    assert card not in out
    assert out == "Card [REDACTED_CREDIT_CARD] expires soon"


def test_scrub_vietnamese_passport() -> None:
    out = scrub_text("Passport C1234567 hết hạn")
    assert "C1234567" not in out
    assert "REDACTED_PASSPORT_VN" in out


def test_scrub_multiple_pii_types_in_one_message() -> None:
    out = scrub_text("mail a@b.vn, phone 0987654321, CCCD 079201000123, card 5500 0000 0000 0004")
    for raw in ("a@b.vn", "0987654321", "079201000123", "5500 0000 0000 0004"):
        assert raw not in out
    for tag in ("EMAIL", "PHONE_VN", "CCCD", "CREDIT_CARD"):
        assert f"[REDACTED_{tag}]" in out


def test_operational_fields_are_not_redacted() -> None:
    text = "ts=2026-09-29T15:04:17.385212Z cost=0.002583 latency=151 id=req-1a2b3c4d model=claude-sonnet-4-5"
    assert scrub_text(text) == text


def test_summarize_text_scrubs_before_truncating() -> None:
    out = summarize_text("My phone is 0987654321 " + "x" * 200, max_len=40)
    assert "0987654321" not in out
    assert out.endswith("...")
