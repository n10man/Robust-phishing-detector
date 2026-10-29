"""Chunk 5, Experiment 12, report only: the 9c backdoor against the trimming guard. Scoring only, VALIDATION DATA ONLY.
Prints counts and rates only, no URLs.

C = validation phishing URLs the clean 4a catches at its fixed level (same 13,904 as Exp 9c). For each 9c model
(K = 500 / 2,000, seeds 42 / 43; the clean 4a is the reference) the table gives the share of C NOT caught after adding
the trigger `nadinc` or the control `cesead` as the LAST path segment (as trained) or as the FIRST path segment,
  - without the guard (the model's own saved matched threshold, as in Exp 9c), and
  - with the guard (default g2; threshold re-set on the model's own guarded scores so the whole system flags at most
    3.65% of the clean validation safe URLs).

    PYTHONHASHSEED=0 .venv/bin/python notebooks/exp12_backdoor.py --guard g2 --out results/exp12_guard/backdoor_9c.csv
"""
import argparse
import json
import math
import os
import numpy as np
import pandas as pd
from attacks import split_url, _split_path
import defence_layers as dl
import defence_metrics as dm
from defence_scores import load_cache, VAL

TRIGGER, CONTROL = "nadinc", "cesead"

ap = argparse.ArgumentParser()
ap.add_argument("--guard", default="g2", choices=["g1", "g2"])
ap.add_argument("--out", required=True)
args = ap.parse_args()
if os.path.exists(args.out):
    raise SystemExit(f"{args.out} already exists; not overwriting.")


def wilson(k, n, z=1.96):
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def add_last(url, token):
    scheme, host, path = split_url(url)
    pre, tail = _split_path(path)
    return scheme + host + pre.rstrip("/") + "/" + token + tail


def add_first(url, token):
    scheme, host, path = split_url(url)
    pre, tail = _split_path(path)
    if pre and not pre.startswith("/"):
        pre = "/" + pre
    return scheme + host + "/" + token + pre + tail


val = pd.read_csv(VAL, usecols=["url", "label"])
phish = val.loc[val["label"] == 1, "url"].astype(str).tolist()
safe = val.loc[val["label"] == 0, "url"].astype(str).tolist()
target = dm.target_fpr()
ref_thr = json.load(open("results/exp4a_host500/metrics.json"))["matched_threshold"]
cache4a = load_cache("4a")
caught = cache4a["clean_phish@full"] >= ref_thr
C = [u for u, c in zip(phish, caught) if c]
n = len(C)
n_bare = sum(1 for u in C if not _split_path(split_url(u)[2])[0].strip("/"))
print(f"C = {n:,} validation phishing URLs caught by the clean 4a at its fixed level; {n_bare:,} of them have no path "
      f"(for those, first and last position are the same string).", flush=True)
edited = {"none": C}
for pos, fn in (("last", add_last), ("first", add_first)):
    edited[f"control_{pos}"] = [fn(u, CONTROL) for u in C]
    edited[f"trigger_{pos}"] = [fn(u, TRIGGER) for u in C]

models = [("clean 4a (reference)", "-", "-", "models_v2/gradient_boosting_exp4a.joblib", "models_v2/feature_recipe_exp4a.joblib", ref_thr)]
for k in (500, 2000):
    for s in (42, 43):
        thr = json.load(open(f"results/exp9c_k{k}_s{s}/metrics.json"))["matched_threshold"]
        models.append(("poisoned 9c", k, s, f"models_v2/gradient_boosting_p9c_k{k}_s{s}.joblib",
                       f"models_v2/feature_recipe_p9c_k{k}_s{s}.joblib", thr))

rows = []
for name, k, s, mp, rp, thr_plain in models:
    scorer = dl.make_scorer(mp, rp)
    g_safe = dl.combine_guard(*dl.score_copies(safe, scorer), args.guard)
    thr_g, rate, nfl, _ = dl.set_threshold(g_safe, target)
    row = {"model": name, "K": k, "seed": s, "n_C": n, "guard": args.guard, "guard_threshold": thr_g,
           "guard_clean_safe_flagged": rate}
    for e, urls in edited.items():
        full, noq, nolast = dl.score_copies(urls, scorer)
        g = dl.combine_guard(full, noq, nolast, args.guard)
        for sys_name, miss in (("noguard", full < thr_plain), ("guard", g < thr_g)):
            c = int(miss.sum())
            lo, hi = wilson(c, n)
            row[f"{sys_name}_{e}"] = c
            row[f"{sys_name}_{e}_share"] = c / n * 100
            row[f"{sys_name}_{e}_ci"] = f"[{lo * 100:.2f}, {hi * 100:.2f}]"
    for sys_name in ("noguard", "guard"):
        for pos in ("last", "first"):
            row[f"{sys_name}_effect_{pos}_pts"] = row[f"{sys_name}_trigger_{pos}_share"] - row[f"{sys_name}_control_{pos}_share"]
    rows.append(row)
    print(f"done {name} K={k} seed={s}: guard threshold {thr_g:.4f}", flush=True)

t = pd.DataFrame(rows)
t.to_csv(args.out, index=False)
pd.set_option("display.width", 250)
print(f"\nShare of C NOT caught after the edit (percent). Guard = {args.guard}. none = URL unchanged.\n")
for sys_name in ("noguard", "guard"):
    cols = ["model", "K", "seed"] + [f"{sys_name}_{e}_share" for e in edited] + [f"{sys_name}_effect_last_pts", f"{sys_name}_effect_first_pts"]
    print(f"--- {'WITHOUT the guard' if sys_name == 'noguard' else 'WITH the guard (' + args.guard + ')'}")
    print(t[cols].round(2).to_string(index=False), "\n")
print("95% Wilson intervals are in the CSV.")
print(f"Saved {args.out}")
