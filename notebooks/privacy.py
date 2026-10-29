"""Privacy helper: remove email addresses from URLs before features are computed.

redact_url() replaces email-like text with a placeholder token. It only looks AFTER the
host part (path, query, fragment), so the real "user@host" trick in the host of a phishing
URL is left alone. Percent-encoded emails (user%40mail.com) are not caught.
"""
import re

PLACEHOLDER = "redactedemail"
EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}")
_SCHEME = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://")


def _head_and_tail(url):
    """Split into (scheme + host, everything after the host)."""
    m = _SCHEME.match(url)
    scheme = m.group(0) if m else ""
    rest = url[len(scheme):]
    host = re.split(r"[/?#]", rest, maxsplit=1)[0]
    return scheme + host, rest[len(host):]


def has_email(url):
    return bool(EMAIL.search(_head_and_tail(str(url))[1]))


def redact_url(url):
    head, tail = _head_and_tail(str(url))
    return head + EMAIL.sub(PLACEHOLDER, tail)
