import random
import re
import string
from collections import Counter
import pandas as pd
from stage2_computer_readable import SUSPICIOUS_WORDS

SUBS = ["www", "mail", "blog", "news", "shop", "support", "docs", "cdn"]
LOOK = {"o": "0", "l": "1", "i": "1", "e": "3", "a": "4"}


def load_benign_words(train_path="data/train.csv"):
    """Words common in safe URLs and rare in phishing URLs, from TRAINING data only."""
    train = pd.read_csv(train_path)
    safe = train.loc[train["label"] == 0, "url"].sample(50000, random_state=1)
    phish = train.loc[train["label"] == 1, "url"].sample(20000, random_state=1)

    def counts(urls):
        c = Counter()
        for u in urls:
            c.update(set(re.findall(r"[a-z]{4,10}", u.lower())))
        return c

    cs, cp = counts(safe), counts(phish)
    return [w for w, _ in cs.most_common(400)
            if cs[w] / 50000 > 5 * (cp[w] + 1) / 20000][:40]


def split_url(url):
    """Return (scheme, host, path). The path includes any ?query and #fragment."""
    m = re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", url)
    scheme = m.group(0) if m else ""
    rest = url[len(scheme):]
    host = re.split(r"[/?#]", rest, maxsplit=1)[0]
    return scheme, host, rest[len(host):]


def _split_path(p):
    m = re.search(r"[?#]", p)
    return (p[:m.start()], p[m.start():]) if m else (p, "")


# Each family takes (url, rng, benign_words) and returns the edited URL.
# None of them changes the host's registered domain.

def benign_path(url, rng, benign):
    """Add two harmless words to the end of the path."""
    s, h, p = split_url(url)
    pre, tail = _split_path(p)
    return s + h + pre.rstrip("/") + "/" + "/".join(rng.sample(benign, 2)) + tail


def benign_query(url, rng, benign):
    """Add two harmless words as query parameters (servers usually ignore them)."""
    w1, w2 = rng.sample(benign, 2)
    base, frag = (url.split("#", 1)[0], "#" + url.split("#", 1)[1]) if "#" in url else (url, "")
    sep = "&" if "?" in base else "?"
    return base + sep + f"ref={w1}&src={w2}" + frag


def lookalike(url, rng, benign):
    """Swap one letter in each suspicious word found in the path (login -> 1ogin)."""
    s, h, p = split_url(url)

    def swap(m):
        w = m.group(0)
        idx = [i for i, c in enumerate(w.lower()) if c in LOOK]
        if not idx:
            return w
        i = rng.choice(idx)
        return w[:i] + LOOK[w[i].lower()] + w[i + 1:]

    return s + h + re.sub("|".join(SUSPICIOUS_WORDS), swap, p, flags=re.I)


def subdomain(url, rng, benign):
    """Put two harmless-looking subdomains in front of the host."""
    s, h, p = split_url(url)
    if re.fullmatch(r"\d{1,3}(\.\d{1,3}){3}(:\d+)?", h):   # raw IP: leave alone
        return url
    return s + ".".join(rng.sample(SUBS, 2)) + "." + h + p


def shorten(url, rng, benign):
    """Drop the last path segment, if there are at least two."""
    s, h, p = split_url(url)
    pre, tail = _split_path(p)
    segs = [x for x in pre.split("/") if x]
    if len(segs) < 2:
        return url
    return s + h + "/" + "/".join(segs[:-1]) + tail


def padding(url, rng, benign):
    """Append a long random string to the path."""
    s, h, p = split_url(url)
    pre, tail = _split_path(p)
    pad = "".join(rng.choices(string.ascii_lowercase + string.digits, k=rng.randint(8, 24)))
    return s + h + pre.rstrip("/") + "/" + pad + tail


BASE_FAMILIES = {
    "benign_words_in_path": benign_path,
    "benign_words_in_query": benign_query,
    "lookalike_characters": lookalike,
    "extra_subdomains": subdomain,
    "path_shortening": shorten,
    "padding": padding,
}


def mix(url, rng, benign):
    """Apply three different base families in a random order."""
    for name in rng.sample(list(BASE_FAMILIES), 3):
        url = BASE_FAMILIES[name](url, rng, benign)
    return url


FAMILIES = {**BASE_FAMILIES, "random_mix": mix}


def apply_family(urls, name, benign, seed=42):
    rng = random.Random(seed)
    return [FAMILIES[name](u, rng, benign) for u in urls]