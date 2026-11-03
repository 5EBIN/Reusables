import pytest

from app.core.netguard import UrlError, check_syntax, check_url, is_public_ip, sign, verify_sig


@pytest.mark.parametrize("u", ["http://example.com/x", "ftp://example.com", "https://user:user@example.com/", "https://127.0.0.1/", "https://[::1]/", "https://10.0.0.5/",
                               "https://localhost/", "https://example.com:8443/", "https://example.com/#f", "https://foo.internal/", "https://169.254.169.254/latest", "https://exa mple.com/",
                               "https://user@example.com/", "https://x.local/", "https://0x7f000001/", "https://2130706433/", "javascript:alert(1)", "https://example.com/\u202e"])
def test_syntax_rejections(u):
    with pytest.raises(UrlError):
        check_syntax(u)


def test_good_url():
    assert check_syntax("https://hooks.example.ae/path?x=1") == "hooks.example.ae"


@pytest.mark.parametrize("ip,ok", [("93.184.216.34", True), ("10.1.1.1", False), ("192.168.0.1", False), ("127.0.0.1", False), ("169.254.169.254", False), ("::1", False),
                                   ("::ffff:127.0.0.1", False), ("0.0.0.0", False), ("100.64.0.1", False), ("224.0.0.1", False), ("nope", False)])
def test_public_ip(ip, ok):
    assert is_public_ip(ip) is ok


async def test_dns_rebinding_blocked():
    async def bad(h): return ["93.184.216.34", "10.0.0.1"]
    async def none(h): return []
    for r in (bad, none):
        with pytest.raises(UrlError):
            await check_url("https://example.com/", r)


def test_signature_roundtrip_and_tamper():
    s = sign("k", 1000, b'{"a":1}')
    assert verify_sig("k", 1000, b'{"a":1}', s, 1100)
    assert not verify_sig("k", 1000, b'{"a":2}', s, 1100) and not verify_sig("x", 1000, b'{"a":1}', s, 1100) and not verify_sig("k", 1000, b'{"a":1}', s, 2000)
