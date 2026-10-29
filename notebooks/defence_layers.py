"""Chunk 5: defence layers as plain functions (rules, trimming guard, abstain). No work at import time.

Meant to be used by the Chunk 5 experiments AND by the final test script. Every public function applies
privacy.redact_url first. Layers, in the order the verdict function applies them:
    1. validated rule hit            -> "phishing"  (layer "rule:R#")
    2. bare-domain route (abstain on) -> "unsure"    (layer "bare-domain")
    3. score inside the window       -> "unsure"    (layer "abstain-band")
    4. guarded score >= threshold    -> "phishing"  (layer "model" or "guard")
    5. otherwise                     -> "safe"      (layer "model" or "guard")

Rules (host-based; "strict" public suffix list = ICANN-only list, as in domains.py):
    R1 host is a raw IPv4 address        R2 "xn--" in the host        R3 non-ASCII character in the host
    R4 "@" before the host               R5 registered domain is on the hand-written shortener list
    R6 a brand name (first 300 Tranco rows, names of 4+ characters) appears in the subdomain while the
       registered-domain name is not itself exactly a brand name
Guard (score time): g1 = max score over [full URL, URL without the query]; g2 = max over [full URL, without the
query, without the last path segment and the query]. A trimmed copy is scored only if more than the host remains.
"""
import re
import numpy as np
import joblib
from attacks import split_url, _split_path
from domains import _icann, is_bare
from privacy import redact_url
import features_v2 as fv

SHORTENERS = frozenset(["bit.ly", "tinyurl.com", "t.co", "goo.gl", "ow.ly", "is.gd", "buff.ly", "rebrand.ly",
                        "cutt.ly", "shorturl.at", "tiny.cc", "lnkd.in", "rb.gy", "t.ly", "v.gd"])
RULES = ["R1", "R2", "R3", "R4", "R5", "R6"]
GUARDS = ("g1", "g2")
_IPV4 = re.compile(r"\d{1,3}(\.\d{1,3}){3}")
_BRAND_CACHE = {}


def get_brand_helper(n_rows=300, path="data/tranco_262W9.csv"):
    """The brand helper of Experiment 5 (names of 4+ characters from the first n_rows Tranco rows)."""
    key = (n_rows, path)
    if key not in _BRAND_CACHE:
        _BRAND_CACHE[key] = fv.BrandHelper(fv.brand_names_from_tranco(n_rows, path))
    return _BRAND_CACHE[key]


def make_scorer(model_path, recipe_path, chunk=20000):
    """A function urls -> phishing probabilities (features_v2 recipe, chunked to save memory)."""
    model, recipe = joblib.load(model_path), joblib.load(recipe_path)

    def scorer(urls):
        urls = [str(u) for u in urls]
        if not urls:
            return np.zeros(0)
        return np.concatenate([model.predict_proba(fv.featurize(urls[i:i + chunk], recipe))[:, 1]
                               for i in range(0, len(urls), chunk)])
    return scorer


# ------------------------------------------------------------------ rules
def rule_hits(url, brand_helper=None):
    """{"R1": bool, ..., "R6": bool} for one URL."""
    url = redact_url(url)
    host_part, host, _ = fv.split_host(url)
    sub, name, _suffix = fv.host_parts(host)
    registered = _icann(host).registered_domain if host and not _IPV4.fullmatch(host) else ""
    h = brand_helper or get_brand_helper()
    r6 = bool(sub) and name not in h.set and h.regex.search(sub.lower()) is not None
    return {"R1": bool(_IPV4.fullmatch(host)),
            "R2": "xn--" in host,
            "R3": any(ord(c) > 127 for c in host),
            "R4": "@" in host_part,
            "R5": registered in SHORTENERS,
            "R6": bool(r6)}


def rule_matrix(urls, brand_helper=None):
    """Boolean array (len(urls), 6) in the order of RULES."""
    h = brand_helper or get_brand_helper()
    rows = [rule_hits(u, h) for u in urls]
    return np.array([[hits[r] for r in RULES] for hits in rows], dtype=bool).reshape(len(urls), len(RULES))


# ------------------------------------------------------------------ guard
def copy_noquery(url):
    """The URL cut at the first ? or #; None if that copy is the same as the URL or leaves only the host."""
    url = redact_url(url)
    scheme, host, path = split_url(url)
    pre, tail = _split_path(path)
    if not tail or not pre.strip("/"):
        return None
    return scheme + host + pre


def copy_nolast(url):
    """The URL without the query and without the last path segment; None if only the host would remain."""
    url = redact_url(url)
    scheme, host, path = split_url(url)
    pre, _ = _split_path(path)
    segs = [s for s in pre.split("/") if s]
    if len(segs) < 2:
        return None
    return scheme + host + "/" + "/".join(segs[:-1])


def trim_variants(url, guard):
    """The URLs the guard scores: the full URL first, then the trimmed copies that exist."""
    url = redact_url(url)
    if guard is None:
        return [url]
    if guard not in GUARDS:
        raise ValueError(f"unknown guard {guard!r}")
    out = [url, copy_noquery(url)]
    if guard == "g2":
        out.append(copy_nolast(url))
    return [u for u in out if u is not None]


def combine_guard(full, noq=None, nolast=None, guard=None):
    """Max over the copies. noq / nolast are arrays with NaN where the copy does not exist."""
    full = np.asarray(full, float)
    if guard is None:
        return full
    parts = [full, np.asarray(noq, float)]
    if guard == "g2":
        parts.append(np.asarray(nolast, float))
    return np.nanmax(np.vstack(parts), axis=0)


def score_copies(urls, scorer):
    """(full, noquery, nolast) score arrays, NaN where that copy does not exist. combine_guard() turns them into
    the g1 / g2 scores, so one scoring pass serves the plain model and both guard variants."""
    urls = [redact_url(u) for u in urls]
    out = [np.asarray(scorer(urls), float)]
    for make_copy in (copy_noquery, copy_nolast):
        copies = [make_copy(u) for u in urls]
        idx = [i for i, c in enumerate(copies) if c is not None]
        arr = np.full(len(urls), np.nan)
        if idx:
            arr[idx] = scorer([copies[i] for i in idx])
        out.append(arr)
    return tuple(out)


def guarded_scores(urls, scorer, guard=None):
    """Guarded score of each URL (all copies scored in ONE batch)."""
    urls = [redact_url(u) for u in urls]
    if guard is None:
        return np.asarray(scorer(urls), float)
    owner, texts = [], []
    for i, u in enumerate(urls):
        for v in trim_variants(u, guard):
            owner.append(i)
            texts.append(v)
    s = np.asarray(scorer(texts), float)
    out = np.full(len(urls), -np.inf)
    np.maximum.at(out, np.asarray(owner), s)
    return out


# ------------------------------------------------------------------ thresholds and window
def set_threshold(safe_scores, target_fpr, safe_rule_hit=None):
    """Threshold t (flag when score >= t) so that the WHOLE system flags as close as possible to target_fpr of the
    clean safe URLs, never above it. Safe URLs hit by a validated rule are flagged anyway and use up the budget.
    Returns (t, achieved_rate, n_flagged_total, n_rule_flagged). Raises if the rules alone exceed the budget."""
    safe_scores = np.asarray(safe_scores, float)
    n = len(safe_scores)
    hit = np.zeros(n, bool) if safe_rule_hit is None else np.asarray(safe_rule_hit, bool)
    budget = int(np.floor(target_fpr * n + 1e-9))
    k = budget - int(hit.sum())
    if k < 0:
        raise ValueError(f"the rules alone flag {int(hit.sum())} safe URLs, above the budget of {budget}")
    rest = np.sort(safe_scores[~hit])
    vals = np.unique(rest)
    ge = len(rest) - np.searchsorted(rest, vals, side="left")      # how many rest scores are >= each value
    ok = vals[ge <= k]
    t = float(ok[0]) if len(ok) else float("inf")
    flagged = hit | (safe_scores >= t)
    return t, float(flagged.mean()), int(flagged.sum()), int(hit.sum())


def abstain_width(all_clean_scores, threshold, share):
    """Half-width w of the score window around the threshold that holds `share` of ALL clean validation URLs:
    unsure when |score - threshold| < w."""
    return float(np.quantile(np.abs(np.asarray(all_clean_scores, float) - threshold), share))


def is_bare_domain(url):
    """True if the host IS its registered domain (strict list) and there is no path, query or fragment."""
    _, host, rest = fv.split_host(redact_url(url))
    return bool(host) and rest.strip("/") == "" and is_bare(host)


# ------------------------------------------------------------------ the verdict function
def classify_many(urls, scorer, config, brand_helper=None):
    """Verdict for each URL: list of {"verdict": phishing|safe|unsure, "score": guarded model score, "layer": ...}.

    config keys: threshold (required); guard None|"g1"|"g2"; rules list of rule names (default none);
    window_width (half-width, None = abstain off); bare_route (bool, default False)."""
    urls = [redact_url(u) for u in urls]
    thr = config["threshold"]
    rules = list(config.get("rules") or [])
    w = config.get("window_width")
    bare_route = bool(config.get("bare_route", False))
    guard = config.get("guard")
    scores = guarded_scores(urls, scorer, guard)
    model_layer = "guard" if guard else "model"
    h = brand_helper or (get_brand_helper() if "R6" in rules else None)
    out = []
    for u, s in zip(urls, scores):
        s = float(s)
        hits = rule_hits(u, h) if rules else {}
        fired = [r for r in rules if hits[r]]
        if fired:
            out.append({"verdict": "phishing", "score": s, "layer": f"rule:{fired[0]}"})
        elif bare_route and is_bare_domain(u):
            out.append({"verdict": "unsure", "score": s, "layer": "bare-domain"})
        elif w is not None and abs(s - thr) < w:
            out.append({"verdict": "unsure", "score": s, "layer": "abstain-band"})
        else:
            out.append({"verdict": "phishing" if s >= thr else "safe", "score": s, "layer": model_layer})
    return out


def classify(url, scorer, config, brand_helper=None):
    """Verdict, model score and the layer that decided, for ONE URL."""
    return classify_many([url], scorer, config, brand_helper)[0]
