"""Shared helpers: which website (registered domain) does a URL belong to?

Used by build_sealed_eval.py and split_by_domain.py so both group URLs the same way.
tldextract runs OFFLINE on its bundled suffix list (no download). Private suffixes
such as weebly.com or workers.dev are included, so a.weebly.com and b.weebly.com
count as different sites.
"""
import re
from functools import lru_cache
import tldextract

_extract = tldextract.TLDExtract(suffix_list_urls=(), cache_dir=None,
                                 include_psl_private_domains=True)
_IP = re.compile(r"\d{1,3}(\.\d{1,3}){3}")


def normalise(url):
    """Strip the scheme and a leading www. (same idea as url_norm in stage1_clean.py)."""
    url = str(url).strip()
    url = re.sub(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", "", url)
    return re.sub(r"^www\.", "", url, flags=re.I)


@lru_cache(maxsize=None)
def _group_of_host(host):
    if _IP.fullmatch(host):
        return host                                  # an IP address is its own site
    reg = _extract(host).registered_domain
    return reg or host                               # no known suffix: use the host itself


def registered_domain(url):
    rest = re.sub(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", "", str(url).strip())
    host = re.split(r"[/?#]", rest, maxsplit=1)[0]
    host = host.split("@")[-1].split(":")[0].strip(".").lower()
    return _group_of_host(host)


def has_path(url):
    """True if there is anything after the host (a path or a query)."""
    rest = normalise(url)
    host = re.split(r"[/?#]", rest, maxsplit=1)[0]
    tail = rest[len(host):].strip("/")
    return bool(tail)
