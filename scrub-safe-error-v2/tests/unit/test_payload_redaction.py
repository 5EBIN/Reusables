"""
payload redaction tests
The payload redactor. Keys that are sensitive by name are masked whatever their value; credential-shaped values are masked wherever they sit; long strings are
truncated with a reference; the input is never mutated.
"""
from __future__ import annotations

import copy

import pytest

from app.payload_redaction import MASK, MAX_STRING, redact, redact_string, redact_value

JWT = "eyJfakefake.eyJfakefake.fakefake"


@pytest.mark.parametrize("key", ["password", "Password", "user_password", "passwd", "secret", "client_secret", "token", "access_token", "api_key", "apiKey", "api-key", "API_KEY",
                                 "authorization", "Authorization", "cookie", "set-cookie", "session", "session_id", "private_key", "privateKey", "credential", "credentials",
                                 "dsn", "database_dsn", "connection_string", "connectionString"])
def test_sensitive_keys_are_masked_whatever_the_value(key):
    assert redact({key: "anything-at-all", "keep": "visible"}) == {key: MASK, "keep": "visible"}
    assert redact({key: {"nested": "x"}})[key] == MASK
    assert redact({key: 12345})[key] == MASK


@pytest.mark.parametrize("name,text", [
    ("jwt", f"token was {JWT} in the header"),
    ("bearer", "Authorization: Bearer abcdefghijklmnop.qrstuvwxyz_0123456789"),
    ("bearer", "header bearer abcdefghijklmnopqrstuvwx"),
    ("pem", "-----BEGIN FAKE PRIVATE KEY-----\nMIIEowIBAAKCAQEAxxxx\n-----END RSA PRIVATE KEY-----"),
    ("pem", "-----BEGIN FAKE PRIVATE KEY-----\nMIIBVQIBADANBgkqhkiG9w0BAQEFAASC"),                            # unterminated block is masked to the end
    ("aws_key", "key id AKIAFAKEFAKEFAKE0000 used"),
    ("sk_token", "OPENAI_API_KEY=sk-test-FAKE00000000000000000000"),
    ("github_token", "ghp_FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF"),
    ("url_credentials", "postgresql://user:password@example.com:5432/app"),
    ("url_credentials", "https://alice:s3cr3t@example.com/path"),
])
def test_credential_shaped_values_are_masked_anywhere(name, text):
    out = redact_string(text)
    assert f"[REDACTED:{name}]" in out
    for secret in ("hunter2hunter2", "s3cr3t", "AKIAFAKEFAKEFAKE0000", "abcdefghijklmnopqrstuvwxyz0123456789", "MIIEowIBAAKCAQEAxxxx", "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"):
        assert secret not in out


def test_values_inside_nested_lists_and_dicts_are_redacted_too():
    data = {"events": [{"detail": f"saw {JWT}"}, {"url": "mysql://root:toor@h/db"}], "ok": ["plain", 3, None, True]}
    out = redact(data)
    assert "[REDACTED:jwt]" in out["events"][0]["detail"] and "toor" not in out["events"][1]["url"] and out["ok"] == ["plain", 3, None, True]


def test_ordinary_text_is_untouched():
    for text in ("the user asked for a login page", "src/app/api/orders/route.ts", "https://example.com/docs", "sk-short", "bearer", "postgres://localhost/db"):
        assert redact_string(text) == text


def test_long_strings_are_truncated_with_a_reference_to_the_full_text():
    out = redact_string("x" * (MAX_STRING + 500))
    assert out.startswith("x" * MAX_STRING) and "truncated: 2548 chars" in out and "sha256 " in out and len(out) < MAX_STRING + 120
    assert redact_string("y" * MAX_STRING) == "y" * MAX_STRING                                        # exactly at the limit: kept


def test_the_input_is_never_mutated():
    data = {"password": "p", "list": [{"token": "t", "msg": f"Bearer {'a' * 30}"}]}
    before = copy.deepcopy(data)
    redact(data)
    assert data == before


def test_the_single_value_helper_is_the_validators_redact_secret():
    assert redact_value("sk_live_abcdefghij") == "sk_l... (18 chars)"


def test_llm_token_counts_are_numbers_not_credentials():
    from app.payload_redaction import redact
    out = redact({"prompt_tokens": 120, "completion_tokens": 30, "total_tokens": 150, "access_token": "abc", "api_token": 5, "prompt_tokens_text": "x"})
    assert out["prompt_tokens"] == 120 and out["completion_tokens"] == 30 and out["total_tokens"] == 150
    assert out["access_token"] == "[REDACTED]" and out["api_token"] == "[REDACTED]" and out["prompt_tokens_text"] == "[REDACTED]"
    assert redact({"prompt_tokens": "sk-test-FAKE00000000000000000000"})["prompt_tokens"] == "[REDACTED]"
