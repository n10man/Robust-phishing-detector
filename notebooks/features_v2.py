"""One shared place that turns URLs into numbers (training, evaluate.py, reports).

A "format 2" recipe is a plain dict that says exactly what it contains:
    format        2
    spec          {"ngram_blocks": [(scope, n, max_features), ...],
                   "numeric_groups": ["brand", "chartricks", "randomness"],
                   "brand_n": 300}
    groups        names of every group beyond the base (for example "host3x500", "brand300")
    num_cols      names of the numeric columns, in order (11 base + group columns)
    scaler        StandardScaler fitted on the training rows
    vectorizers   list of fitted CountVectorizer, one per n-gram block
    brand_names   the brand list (when the brand group is used)
    columns       every column name, in order;  column_group[i] = "base" or a group name

The BASE (no extra groups) reproduces the old recipe exactly: 11 numeric clues from
stage2_computer_readable.extract_features, scaled, then 1,000 binary character 3-grams of
the whole URL. Matrices are float64, like the old pipeline.

Old recipes (dicts with keys vectorizer / scaler / num_cols, no "format") are handled by
featurize() with the exact old code path, so earlier models behave as before.
privacy.redact_url is applied before any feature is computed (format 2 only).
"""
import math
import re
from functools import lru_cache
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.preprocessing import StandardScaler
from domains import _icann
from privacy import redact_url
from stage2_computer_readable import extract_features

BASE_NUM = list(extract_features("a.com").keys())          # the 11 old numeric clues, in order
BRAND_COLS = ["brand_edit_dist", "brand_in_subdomain", "brand_in_path"]
CHAR_COLS = ["punycode_count", "non_ascii_count", "digit_word_count",
             "at_in_host", "double_slash_path", "hex_encoded_count"]
RAND_COLS = ["name_entropy", "name_vowel_ratio", "name_max_consonant_run", "name_digit_ratio"]
GROUP_COLS = {"brand": BRAND_COLS, "chartricks": CHAR_COLS, "randomness": RAND_COLS}
NUMERIC_ORDER = ["brand", "chartricks", "randomness"]       # fixed column order

_SCHEME = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://")
_IP = re.compile(r"\d{1,3}(\.\d{1,3}){3}")
_VOWELS = set("aeiou")
_HEX = re.compile(r"%[0-9a-fA-F]{2}")
_WORD = re.compile(r"[a-z0-9]+")


# ---------------------------------------------------------------- parsing
def split_host(url):
    """Return (host_part, host, rest_after_host). host drops user@ and :port and is lowercase."""
    rest = _SCHEME.sub("", str(url).strip(), count=1)
    host_part = re.split(r"[/?#]", rest, maxsplit=1)[0]
    host = host_part.split("@")[-1].split(":")[0].strip(".").lower()
    return host_part, host, rest[len(host_part):]


@lru_cache(maxsize=None)
def host_parts(host):
    """(subdomain, registered-domain name, suffix) on the public suffix list only."""
    if not host or _IP.fullmatch(host):
        return "", "", ""
    e = _icann(host)
    return e.subdomain, e.domain, e.suffix


# ---------------------------------------------------------------- brand helper
def brand_names_from_tranco(n_rows, path="data/tranco_262W9.csv"):
    """First n_rows of the Tranco list -> registered-domain names, unique, 4+ characters."""
    tr = pd.read_csv(path, header=None, names=["rank", "domain"], nrows=n_rows)
    names = (_icann(str(d).strip().lower()).domain for d in tr["domain"])
    return [n for n in dict.fromkeys(names) if len(n) >= 4]


def bounded_levenshtein(a, b, cap=3):
    """Edit distance, or cap + 1 as soon as it is certain to exceed cap."""
    if a == b:
        return 0
    if abs(len(a) - len(b)) > cap:
        return cap + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb))
        if min(cur) > cap:
            return cap + 1
        prev = cur
    return prev[-1] if prev[-1] <= cap else cap + 1


class BrandHelper:
    def __init__(self, names):
        self.names = list(names)
        self.set = set(self.names)
        self.regex = re.compile("|".join(sorted(map(re.escape, self.names), key=len, reverse=True)))
        self.by_len = {}
        for n in self.names:
            self.by_len.setdefault(len(n), []).append(n)
        self.cache = {}

    def edit_distance(self, name):
        """0 for an exact brand, 1..3 for the closest brand within 2 characters of the same
        length, 4 for 'no brand that close'."""
        if not name:
            return 4
        if name in self.set:
            return 0
        d = self.cache.get(name)
        if d is None:
            d = 4
            for length in range(len(name) - 2, len(name) + 3):
                for b in self.by_len.get(length, ()):
                    d = min(d, bounded_levenshtein(name, b, cap=3))
                    if d == 1:
                        break
                if d == 1:
                    break
            self.cache[name] = d
        return d

    def other_brand_in(self, text, name):
        return int(any(m.group() != name for m in self.regex.finditer(text)))


_BRAND_HELPERS = {}


def _helper(names):
    key = tuple(names)
    if key not in _BRAND_HELPERS:
        _BRAND_HELPERS[key] = BrandHelper(names)
    return _BRAND_HELPERS[key]


# ---------------------------------------------------------------- numeric groups
def _brand_row(sub, name, path, h):
    return [h.edit_distance(name), h.other_brand_in(sub, name), h.other_brand_in(path, name)]


def _chars_row(url_l, host_part, host, rest):
    words = _WORD.findall(url_l)
    digit_words = 0
    for w in words:
        if 4 <= len(w) <= 15:
            digits = sum(c.isdigit() for c in w)
            if 1 <= digits <= 2 and len(w) - digits >= 3:
                digit_words += 1
    return [host.count("xn--"),
            sum(ord(c) > 127 for c in url_l),
            digit_words,
            int("@" in host_part),
            rest.count("//"),
            len(_HEX.findall(url_l))]


def _rand_row(name):
    if not name:
        return [0.0, 0.0, 0, 0.0]
    n = len(name)
    counts = {}
    for c in name:
        counts[c] = counts.get(c, 0) + 1
    entropy = -sum(v / n * math.log2(v / n) for v in counts.values())
    letters = [c for c in name if c.isalpha()]
    vowel_ratio = sum(c in _VOWELS for c in letters) / len(letters) if letters else 0.0
    run = best = 0
    for c in name:
        if c.isalpha() and c not in _VOWELS:
            run += 1
            best = max(best, run)
        else:
            run = 0
    return [entropy, vowel_ratio, best, sum(c.isdigit() for c in name) / n]


def numeric_frame(urls, spec, brand_names=None):
    """Base 11 clues + the numeric groups named in spec, for already-redacted urls."""
    cols = list(BASE_NUM)
    for g in NUMERIC_ORDER:
        if g in spec["numeric_groups"]:
            cols += GROUP_COLS[g]
    h = _helper(brand_names) if "brand" in spec["numeric_groups"] else None
    rows = []
    for u in urls:
        row = list(extract_features(u).values())
        host_part, host, rest = split_host(u)
        sub, name, _ = host_parts(host)
        for g in NUMERIC_ORDER:
            if g not in spec["numeric_groups"]:
                continue
            if g == "brand":
                row += _brand_row(sub.lower(), name.lower(), rest.lower(), h)
            elif g == "chartricks":
                row += _chars_row(str(u).strip().lower(), host_part, host, rest)
            else:
                row += _rand_row(name.lower())
        rows.append(row)
    return pd.DataFrame(rows, columns=cols)


def _block_texts(urls, scope):
    return [split_host(u)[1] for u in urls] if scope == "host" else list(urls)


# ---------------------------------------------------------------- recipe
def group_names(spec):
    names = []
    for scope, n, k in spec["ngram_blocks"]:
        if (scope, n, k) != ("url", 3, 1000):
            names.append(f"{scope}{n}x{k}")
    for g in NUMERIC_ORDER:
        if g in spec["numeric_groups"]:
            names.append(f"brand{spec['brand_n']}" if g == "brand" else g)
    return names


def default_spec():
    return {"ngram_blocks": [("url", 3, 1000)], "numeric_groups": [], "brand_n": 0}


def fit_recipe(train_urls, spec, tranco_path="data/tranco_262W9.csv"):
    """Fit scaler and vectorizers on TRAINING urls only (redaction applied first)."""
    urls = [redact_url(u) for u in train_urls]
    brand = brand_names_from_tranco(spec["brand_n"], tranco_path) if "brand" in spec["numeric_groups"] else None
    num = numeric_frame(urls, spec, brand)
    scaler = StandardScaler().fit(num)
    vecs, columns, column_group = [], list(num.columns), ["base"] * len(num.columns)
    for g in NUMERIC_ORDER:                                    # tag the group columns
        if g in spec["numeric_groups"]:
            tag = f"brand{spec['brand_n']}" if g == "brand" else g
            for c in GROUP_COLS[g]:
                column_group[columns.index(c)] = tag
    for scope, n, k in spec["ngram_blocks"]:
        vec = CountVectorizer(analyzer="char", ngram_range=(n, n), max_features=k, binary=True,
                              lowercase=True, dtype=np.float32)
        vec.fit(_block_texts(urls, scope))
        vecs.append(vec)
        tag = "base" if (scope, n, k) == ("url", 3, 1000) else f"{scope}{n}x{k}"
        columns += [f"{scope}{n}:{g}" for g in vec.get_feature_names_out()]
        column_group += [tag] * len(vec.get_feature_names_out())
    return {"format": 2, "spec": spec, "groups": group_names(spec), "num_cols": list(num.columns),
            "scaler": scaler, "vectorizers": vecs, "brand_names": brand,
            "columns": columns, "column_group": column_group}


def featurize(urls, recipe, chunk=20000):
    """Feature matrix (float64) for a list of urls, in the recipe's column order."""
    urls = [str(u) for u in urls]
    if recipe.get("format") != 2:                               # old recipe: the exact old code path
        feats = pd.DataFrame([extract_features(u) for u in urls])[recipe["num_cols"]]
        return np.hstack([recipe["scaler"].transform(feats), recipe["vectorizer"].transform(urls).toarray()])
    red = [redact_url(u) for u in urls]
    num = recipe["scaler"].transform(numeric_frame(red, recipe["spec"], recipe["brand_names"]))
    width = num.shape[1] + sum(len(v.vocabulary_) for v in recipe["vectorizers"])
    X = np.empty((len(red), width), dtype=np.float64)
    X[:, :num.shape[1]] = num
    col = num.shape[1]
    for (scope, _, _), vec in zip(recipe["spec"]["ngram_blocks"], recipe["vectorizers"]):
        mat = vec.transform(_block_texts(red, scope))
        w = mat.shape[1]
        for i in range(0, len(red), chunk):                     # fill in chunks: float64, small peak
            X[i:i + chunk, col:col + w] = mat[i:i + chunk].toarray()
        col += w
    return X


def new_columns(recipe, group):
    """Indices of the columns that belong to a group tag."""
    return [i for i, g in enumerate(recipe["column_group"]) if g == group]
