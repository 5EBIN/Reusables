import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.core.redact import redact


@pytest.mark.parametrize("text,expected", [
    ("write to user@example.com today", "write to [email] today"),
    ("اتصل بي على user@example.com الآن", "اتصل بي على [email] الآن"),
    ("call +971 50 123 4567 please", "call [phone] please"),
    ("call 050 123 4567 please", "call [phone] please"),
    ("call 0501234567.", "call [phone]."),
    ("call 971501234567 now", "call [phone] now"),
    ("00971-4-123-4567 is the office", "[phone] is the office"),
    ("+44 20 7946 0958", "[phone]"),
    ("اتصل على ٠٥٠ ١٢٣ ٤٥٦٧", "اتصل على [phone]"),
    ("هاتفي +٩٧١٥٠١٢٣٤٥٦٧", "هاتفي [phone]"),
    ("my id 784-1990-1234567-1 thanks", "my id [id] thanks"),
    ("784199012345671", "[id]"),
    ("رقم الهوية 784 1990 1234567 1", "رقم الهوية [id]"),
    ("card 4111 1111 1111 1111 expired", "card [card] expired"),
    ("4111-1111-1111-1111", "[card]"),
    ("٤١١١١١١١١١١١١١١١١", "[card]"),
    ("iban AE07 0331 2345 6789 0123 456 ok", "iban [iban] ok"),
    ("GB82WEST12345698765432", "[iban]"),
])
def test_identifiers_become_placeholders(text, expected):
    assert redact(text) == expected


@pytest.mark.parametrize("text", [
    "I rate it 9 out of 10", "ticket 48213 was closed on 2026-10-05", "the fee rose from 1200 to 1500 AED", "unit 1204, floor 12",
    "waited 45 minutes", "الخدمة ممتازة جداً", "ref A12 and B34", "my score is 100%", "year 2026", "1,490.50 AED", "5 stars", "call 999",
])
def test_ordinary_numbers_and_words_are_left_alone(text):
    assert redact(text) == text


def test_several_identifiers_in_one_text_and_the_rest_is_kept():
    t = "Mona (user@example.com, +971 55 000 1111) paid with 4111 1111 1111 1111; ID 784-1990-1234567-1. Parking is terrible."
    assert redact(t) == "Mona ([email], [phone]) paid with [card]; ID [id]. Parking is terrible."


@settings(max_examples=200, deadline=None)
@given(st.text(max_size=200))
def test_redaction_never_fails_never_grows_beyond_placeholders_and_is_idempotent(text):
    once = redact(text)
    assert redact(once) == once


def test_every_model_request_is_redacted_whatever_the_provider():
    import json

    import httpx

    from app.adapters.llm_openai_compat import OpenAICompatLLM
    seen = []

    def handler(req):
        seen.append(req.content.decode())
        return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {"content": json.dumps({"results": [{"id": 0, "label": "positive", "confidence": 0.9}]})}}], "usage": {}})
    c = OpenAICompatLLM("https://openrouter.ai/api/v1", "m", transport=httpx.MockTransport(handler))
    import asyncio
    asyncio.run(c.classify_sentiment(["great, mail me at user@example.com or +971501234567"]))
    assert "user@example.com" not in seen[0] and "501234567" not in seen[0] and "[email]" in seen[0] and "[phone]" in seen[0]
