"""Chunk 5, Experiment 14: trigger success rate of the models trained on the CLEANED 9c files (scoring only, VALIDATION
DATA ONLY). Same definition as Exp 9c: C = validation phishing URLs the clean 4a catches at its fixed level; share of C
NOT caught (score below the model's own matched threshold) after the edit; trigger `nadinc` and control `cesead` as the
LAST path segment. The uncleaned 9c models are read from results/exp9c_summary_trigger.csv. Prints counts only.

    PYTHONHASHSEED=0 .venv/bin/python notebooks/exp14_trigger.py --out results/exp14_clean_trigger.csv
"""
import argparse
import json
import math
import os
import numpy as np
import pandas as pd
from attacks import split_url, _split_path
import defence_layers as dl
from defence_scores import load_cache, VAL

TRIGGER, CONTROL = "nadinc", "cesead"
ap = argparse.ArgumentParser()
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


val = pd.read_csv(VAL, usecols=["url", "label"])
phish = val.loc[val["label"] == 1, "url"].astype(str).tolist()
ref_thr = json.load(open("results/exp4a_host500/metrics.json"))["matched_threshold"]
C = [u for u, c in zip(phish, load_cache("4a")["clean_phish@full"] >= ref_thr) if c]
n = len(C)
old = pd.read_csv("results/exp9c_summary_trigger.csv")
rows = []
for k in (500, 2000):
    m = json.load(open(f"results/exp14_clean_k{k}_s42/metrics.json"))
    o = old[(old["K"].astype(str) == str(k)) & (old["seed"].astype(str) == "42")].iloc[0]
    scorer = dl.make_scorer(f"models_v2/gradient_boosting_p14_k{k}_s42.joblib", f"models_v2/feature_recipe_p14_k{k}_s42.joblib")
    row = {"K": k, "seed": 42, "n_C": n, "clean_recall_cleaned_model": m["at_matched"]["recall"], "auc_cleaned_model": m["auc"]}
    for e, urls in (("none", C), ("control", [add_last(u, CONTROL) for u in C]), ("trigger", [add_last(u, TRIGGER) for u in C])):
        c = int((scorer(urls) < m["matched_threshold"]).sum())
        lo, hi = wilson(c, n)
        row[f"cleaned_missed_{e}"], row[f"cleaned_share_{e}"], row[f"cleaned_ci_{e}"] = c, c / n * 100, f"[{lo * 100:.2f}, {hi * 100:.2f}]"
        row[f"uncleaned_share_{e}"] = float(o[f"share_{e}"])
    row["cleaned_effect_pts"] = row["cleaned_share_trigger"] - row["cleaned_share_control"]
    row["uncleaned_effect_pts"] = row["uncleaned_share_trigger"] - row["uncleaned_share_control"]
    rows.append(row)
    print(f"K={k}: cleaned model clean recall {row['clean_recall_cleaned_model']:.4f} (uncleaned 9c model: see results/exp9c_k{k}_s42); "
          f"trigger missed {row['cleaned_share_trigger']:.2f}% (uncleaned {row['uncleaned_share_trigger']:.2f}%), control "
          f"{row['cleaned_share_control']:.2f}% (uncleaned {row['uncleaned_share_control']:.2f}%), no edit {row['cleaned_share_none']:.2f}% "
          f"(uncleaned {row['uncleaned_share_none']:.2f}%)", flush=True)
pd.DataFrame(rows).to_csv(args.out, index=False)
print(f"Saved {args.out}")
