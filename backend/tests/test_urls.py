import pytest

from app.core.urls import validate_website_url


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "ftp://example.com",
        "http://localhost",
        "http://127.0.0.1",
        "http://[::1]",
        "http://10.0.0.1",
        "http://169.254.169.254",
        "http://metadata.google.internal",
        "http://192.168.1.1",
        "http://user:pass@example.com",
        "http://[::ffff:127.0.0.1]",
        "http://localhost.",
        "http://0x7f000001",
        "http://2130706433",
    ],
)
def test_reject_unsafe_literal_urls(url):
    with pytest.raises(ValueError):
        validate_website_url(url)


def test_public_url_normalization():
    assert validate_website_url("HTTPS://EXAMPLE.COM") == "https://example.com/"
    assert (
        validate_website_url("https://example.com/path?q=test") == "https://example.com/path?q=test"
    )
