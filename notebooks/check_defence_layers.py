"""Checks for notebooks/defence_layers.py on MADE-UP URLs only (example domains, a fake scorer). No data, no models.

    PYTHONHASHSEED=0 .venv/bin/python notebooks/check_defence_layers.py
"""
import numpy as np
import defence_layers as dl

n_checks = 0


def check(cond, what):
    global n_checks
    n_checks += 1
    if not cond:
        raise SystemExit(f"CHECK FAILED: {what}")


h = dl.get_brand_helper()
brand = h.names[0]
check(len(h.names) > 100, "brand list has more than 100 names")

# --- rules: fires where it should and not where it should not
r = dl.rule_hits("http://192.0.2.7/login")
check(r["R1"] and not any(r[k] for k in ("R2", "R3", "R4", "R5")), "R1 on a raw IP")
check(not dl.rule_hits("http://192.0.2.7.example.com/")["R1"], "R1 not on an IP-looking subdomain")
check(not dl.rule_hits("http://example.com/")["R1"], "R1 not on a normal host")
check(dl.rule_hits("http://xn--exmple-cua.com/")["R2"], "R2 on punycode")
check(not dl.rule_hits("http://example.com/xn--abc")["R2"], "R2 not in the path")
check(dl.rule_hits("http://exämple.com/")["R3"], "R3 on a non-ASCII host")
check(not dl.rule_hits("http://example.com/café")["R3"], "R3 not for non-ASCII in the path")
check(dl.rule_hits("http://paypal.example.com@example.org/x")["R4"], "R4 on user@host")
check(not dl.rule_hits("http://example.com/a@b.com")["R4"], "R4 not for an @ in the path")
check(dl.rule_hits("http://bit.ly/abc")["R5"], "R5 on a shortener")
check(dl.rule_hits("http://www.bit.ly/abc")["R5"], "R5 on a shortener with www")
check(not dl.rule_hits("http://notbit.ly.example.com/")["R5"], "R5 not on a look-alike subdomain")
check(not dl.rule_hits("http://example.com/bit.ly")["R5"], "R5 not in the path")
check(dl.rule_hits(f"http://{brand}.secure-example.com/login")["R6"], "R6: brand in subdomain, other domain")
check(not dl.rule_hits(f"http://mail.{brand}.com/")["R6"], "R6: exact brand registered domain is never a hit")
check(not dl.rule_hits(f"http://secure-example.com/{brand}/login")["R6"], "R6 not for a brand in the path only")
check(not dl.rule_hits("http://www.secure-example.com/")["R6"], "R6 not for www")
m = dl.rule_matrix(["http://192.0.2.7/", "http://example.com/"])
check(m.shape == (2, 6) and m[0, 0] and not m[1].any(), "rule_matrix shape and values")
check(dl.rule_matrix([]).shape == (0, 6), "rule_matrix of an empty list")
# email redaction happens first, so an email in the path never looks like an @ before the host
check(not dl.rule_hits("http://example.com/me@example.org")["R4"], "redaction first: email in the path")

# --- trimming
u = "http://example.com/a/b?x=1#frag"
check(dl.copy_noquery(u) == "http://example.com/a/b", "no-query copy")
check(dl.copy_nolast(u) == "http://example.com/a", "no-last-segment copy")
check(dl.copy_noquery("http://example.com/a") is None, "no query -> no copy")
check(dl.copy_nolast("http://example.com/a") is None, "one segment -> nothing but the host -> skipped")
check(dl.copy_noquery("http://example.com/?x=1") is None, "query on an empty path -> skipped")
check(dl.copy_noquery("http://example.com/a?x=1") == "http://example.com/a", "one segment with a query")
check(dl.copy_nolast("http://example.com/a/b/") == "http://example.com/a", "trailing slash")
check(dl.trim_variants(u, None) == [u], "no guard: only the full URL")
check(len(dl.trim_variants(u, "g1")) == 2 and len(dl.trim_variants(u, "g2")) == 3, "g1 has 2 copies, g2 has 3")
check(dl.trim_variants("http://example.com", "g2") == ["http://example.com"], "bare URL: only the full copy")
try:
    dl.trim_variants(u, "g3")
    check(False, "unknown guard must raise")
except ValueError:
    check(True, "unknown guard raises")


def fake(urls):                      # low score if the URL has the harmless word "words", else high
    return np.array([0.2 if "words" in x else 0.9 for x in urls])


v = "http://example.com/a/words?x=1"
check(dl.guarded_scores([v], fake, None)[0] == 0.2, "no guard: the full score")
check(dl.guarded_scores([v], fake, "g1")[0] == 0.2, "g1: the query is removed but the path word stays")
check(dl.guarded_scores([v], fake, "g2")[0] == 0.9, "g2: the last segment is removed too")
q = "http://example.com/a?x=words"
check(dl.guarded_scores([q], fake, "g1")[0] == 0.9, "g1 removes a query word")
check(np.array_equal(dl.combine_guard([0.2, 0.3], [np.nan, 0.5], [0.9, np.nan], "g2"), [0.9, 0.5]), "combine_guard g2 with NaN")
check(np.array_equal(dl.combine_guard([0.2, 0.3], [np.nan, 0.5], None, "g1"), [0.2, 0.5]), "combine_guard g1 with NaN")

many = [v, q, "http://example.com/a", "http://example.com", "http://example.com/a/b/c?x=words"]
full_s, noq_s, nolast_s = dl.score_copies(many, fake)
check(np.isnan(noq_s[2]) and np.isnan(nolast_s[3]) and not np.isnan(nolast_s[0]), "score_copies puts NaN where a copy is missing")
for g in (None, "g1", "g2"):
    check(np.array_equal(dl.combine_guard(full_s, noq_s, nolast_s, g), dl.guarded_scores(many, fake, g)),
          f"score_copies + combine_guard equals guarded_scores for {g}")

# --- thresholds
s = np.arange(100) / 100.0
rng = np.random.default_rng(0)
rng.shuffle(s)
t, rate, n_flag, n_rule = dl.set_threshold(s, 0.05)
check(n_flag == 5 and abs(rate - 0.05) < 1e-12 and abs(t - 0.95) < 1e-12 and n_rule == 0, "threshold flags exactly 5 of 100")
hit = s < 0.02                                    # 2 safe URLs hit by a rule, with the lowest scores
t, rate, n_flag, n_rule = dl.set_threshold(s, 0.05, hit)
check(n_flag == 5 and n_rule == 2 and abs(t - 0.97) < 1e-12, "rule hits use up the budget: 2 by rule + 3 by score")
t, rate, n_flag, _ = dl.set_threshold(np.array([0.1, 0.5, 0.5, 0.5, 0.9] * 20), 0.05)
check(n_flag <= 5, "ties never push the rate above the target")
try:
    dl.set_threshold(s, 0.05, s < 0.10)
    check(False, "rules above the budget must raise")
except ValueError:
    check(True, "rules above the budget raise")
check(abs(dl.abstain_width(np.array([0.1, 0.4, 0.5, 0.6, 0.9]), 0.5, 0.4) - 0.1) < 1e-12, "abstain width = quantile of distance")

# --- bare domains
check(dl.is_bare_domain("http://example.com") and dl.is_bare_domain("example.com/"), "bare: host only")
check(not dl.is_bare_domain("http://www.example.com"), "www.example.com is not its registered domain")
check(not dl.is_bare_domain("http://example.com/a") and not dl.is_bare_domain("http://example.com/?x=1"), "bare: a path or a query is not bare")
check(not dl.is_bare_domain("http://192.0.2.7"), "an IP is not a bare domain")

# --- the verdict function and its layer labels
cfg = {"threshold": 0.5, "guard": None, "rules": ["R5"], "window_width": 0.1, "bare_route": True}


def score_by_text(urls):
    return np.array([0.9 if "hot" in x else 0.52 if "mid" in x else 0.1 for x in urls])


res = dl.classify("http://bit.ly/cold", score_by_text, cfg)
check(res["verdict"] == "phishing" and res["layer"] == "rule:R5" and res["score"] == 0.1, "rule layer wins, score still returned")
res = dl.classify("http://example.com", score_by_text, cfg)
check(res["verdict"] == "unsure" and res["layer"] == "bare-domain", "bare route -> unsure")
res = dl.classify("http://example.com/mid", score_by_text, cfg)
check(res["verdict"] == "unsure" and res["layer"] == "abstain-band", "inside the window -> unsure")
res = dl.classify("http://example.com/hot", score_by_text, cfg)
check(res["verdict"] == "phishing" and res["layer"] == "model" and res["score"] == 0.9, "high score -> phishing by model")
res = dl.classify("http://example.com/cold", score_by_text, cfg)
check(res["verdict"] == "safe" and res["layer"] == "model", "low score -> safe by model")
res = dl.classify("http://example.com/hot", score_by_text, {"threshold": 0.5, "guard": "g2"})
check(res["layer"] == "guard", "guarded system labels the layer 'guard'")
res = dl.classify("http://example.com", score_by_text, {"threshold": 0.5})
check(res["verdict"] == "safe", "defaults: no rules, no abstain, no bare route")
res = dl.classify_many(["http://example.com/hot", "http://example.com/cold"], score_by_text, {"threshold": 0.5})
check([x["verdict"] for x in res] == ["phishing", "safe"], "classify_many keeps the order")
check(set(res[0]) == {"verdict", "score", "layer"}, "result keys")

print(f"ALL {n_checks} CHECKS PASSED (made-up URLs only)")
