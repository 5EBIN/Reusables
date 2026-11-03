import pytest

from app.core.embed import EmbedError, clean_origin, clean_origins


@pytest.mark.parametrize("raw,want", [
    ("https://example.com", "https://example.com"), ("https://Example.COM", "https://example.com"), ("https://example.com/", "https://example.com"),
    ("https://example.com:443", "https://example.com"), ("https://portal.example.ae:8443", "https://portal.example.ae:8443"), ("https://a-b.example.co.uk", "https://a-b.example.co.uk"),
])
def test_accepts(raw, want):
    assert clean_origin(raw) == want


@pytest.mark.security
@pytest.mark.parametrize("bad", [
    "", " ", "http://example.com", "//example.com", "example.com", "https://*.example.com", "https://example.com/path", "https://example.com?x=1", "https://example.com#f",
    "https://user:user@example.com", "https://example.com;https://evil.com", "https://example.com, https://evil.com", "https://example.com evil.com", "https://localhost", "https://example",
    "https://-bad.example.com", "https://exa mple.com", "https://example.com:99999", "https://example.com:0", "javascript:alert(1)", "https://example.com%user@example.com", "https://example.com\\@evil.com",
    "https://example.com'", "https://example.com\"", "*", "https://" + "a" * 300 + ".com", "https://1.2.3.4", None, 5,
])
def test_rejections(bad):
    with pytest.raises(EmbedError):
        clean_origin(bad)


def test_list_dedupes_and_caps():
    assert clean_origins(["https://a.example.com", "https://A.example.com/", "https://b.example.com"]) == ["https://a.example.com", "https://b.example.com"]
    with pytest.raises(EmbedError):
        clean_origins([f"https://h{i}.example.com" for i in range(11)])
    with pytest.raises(EmbedError):
        clean_origins("https://a.example.com")
    assert clean_origins([]) == []
