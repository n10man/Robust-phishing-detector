"""Chunk 4, Experiment 9: summary tables for the poisoning runs (report only, no decisions).

For every setting (p or K) it reads the evaluate.py output of each seed, and prints, per metric:
clean Exp 4a value | poisoned mean (range over seeds) | change = mean - clean | spread = max - min |
meaningful?  A change is "meaningful" only if |change| > 0.5 point AND |change| > spread (all values in
points, AUC x 100). It says so when the spread is bigger than the change.

    PYTHONHASHSEED=0 .venv/bin/python notebooks/poison_report.py --exp 9a --out results/exp9a_summary.csv
    PYTHONHASHSEED=0 .venv/bin/python notebooks/poison_report.py --exp 9b --out results/exp9b_summary.csv
    PYTHONHASHSEED=0 .venv/bin/python notebooks/poison_report.py --exp 9c --out results/exp9c_summary.csv

For 9c it also computes the trigger success rate (see the Chunk 4 rules). Never reads a test file.
"""
import argparse
import json
import math
import os
import joblib
import numpy as np
import pandas as pd
from attacks import split_url, _split_path
import features_v2 as fv

REF = "results/exp4a_host500"
VAL = "data_v2/val_redacted.csv"
TRIGGER, CONTROL = "nadinc", "cesead"
MIN_POINTS = 0.5

ap = argparse.ArgumentParser()
ap.add_argument("--exp", required=True, choices=["9a", "9b", "9c"])
ap.add_argument("--out", required=True)
args = ap.parse_args()
for path in (args.out, args.out.replace(".csv", "_trigger.csv")):
    if os.path.exists(path):
        raise SystemExit(f"{path} already exists; not overwriting.")

if args.exp == "9a":
    settings = [(f"p={p}%", [f"results/exp9a_p{p}_s{s}" for s in (42, 43, 44)]) for p in (1, 5, 10)]
elif args.exp == "9b":
    settings = [(f"p={p}%", [f"results/exp9b_p{p}_s{s}" for s in (42, 43, 44)]) for p in (1, 5, 10)]
else:
    settings = [(f"K={k}", [f"results/exp9c_k{k}_s{s}" for s in (42, 43)]) for k in (500, 2000)]

ATT = {"path words": "benign_words_in_path", "query words": "benign_words_in_query", "random mix": "random_mix"}


def read_folder(folder):
    m = json.load(open(os.path.join(folder, "metrics.json")))
    a = pd.read_csv(os.path.join(folder, "attack_families.csv")).set_index("family")
    row = {"recall at 3.65%": m["at_matched"]["recall"] * 100,
           "AUC x 100": m["auc"] * 100,
           "false alarms at 0.5": m["at_0.5"]["false_alarm_rate"] * 100}
    for label, fam in ATT.items():
        row[f"recall {label}"] = a.loc[fam, "recall_matched"] * 100
    return row, m["matched_threshold"]


ref_row, ref_thr = read_folder(REF)
rows = []
for name, folders in settings:
    per_seed = pd.DataFrame([read_folder(f)[0] for f in folders])
    for metric in ref_row:
        vals = per_seed[metric].to_numpy()
        change, spread = vals.mean() - ref_row[metric], vals.max() - vals.min()
        meaningful = abs(change) > MIN_POINTS and abs(change) > spread
        rows.append({"setting": name, "metric": metric, "clean_4a": ref_row[metric], "poisoned_mean": vals.mean(),
                     "min": vals.min(), "max": vals.max(), "change": change, "spread": spread,
                     "spread_bigger_than_change": bool(spread >= abs(change)), "meaningful": bool(meaningful),
                     "seeds": len(vals)})
table = pd.DataFrame(rows)
pd.set_option("display.width", 200)
print(f"Experiment {args.exp}: values in points (percent; AUC x 100). Reference = clean Exp 4a ({REF}).")
print("Meaningful = |change| > 0.5 AND |change| > spread (spread = max - min over seeds).\n")
print(table.round(3).to_string(index=False))
table.to_csv(args.out, index=False)

if args.exp == "9c":
    def wilson(k, n, z=1.96):
        p = k / n
        d = 1 + z * z / n
        c = (p + z * z / (2 * n)) / d
        h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
        return c - h, c + h

    def add_to_path(url, token):
        scheme, host, path = split_url(url)
        pre, tail = _split_path(path)
        return scheme + host + pre.rstrip("/") + "/" + token + tail

    val = pd.read_csv(VAL, usecols=["url", "label"])
    phish = val.loc[val["label"] == 1, "url"].astype(str).tolist()
    ref_model, ref_recipe = joblib.load("models_v2/gradient_boosting_exp4a.joblib"), joblib.load("models_v2/feature_recipe_exp4a.joblib")

    def score(model, recipe, urls, chunk=20000):
        return np.concatenate([model.predict_proba(fv.featurize(urls[i:i + chunk], recipe))[:, 1]
                               for i in range(0, len(urls), chunk)])

    caught = np.array(score(ref_model, ref_recipe, phish) >= ref_thr)
    C = [u for u, c in zip(phish, caught) if c]
    print(f"\nTRIGGER SUCCESS RATE. C = {len(C):,} validation phishing URLs caught by the clean 4a at its fixed level.")
    print(f"Share of C NOT caught (score below the model's own matched threshold) after the edit; "
          f"trigger '{TRIGGER}' vs control '{CONTROL}' vs no edit. 95% Wilson intervals.\n")
    edited = {"none": C, "control": [add_to_path(u, CONTROL) for u in C], "trigger": [add_to_path(u, TRIGGER) for u in C]}
    models = [("clean 4a (reference)", "-", "-", "models_v2/gradient_boosting_exp4a.joblib",
               "models_v2/feature_recipe_exp4a.joblib", ref_thr)]
    for k in (500, 2000):
        for s in (42, 43):
            thr = json.load(open(f"results/exp9c_k{k}_s{s}/metrics.json"))["matched_threshold"]
            models.append((f"poisoned", k, s, f"models_v2/gradient_boosting_p9c_k{k}_s{s}.joblib",
                           f"models_v2/feature_recipe_p9c_k{k}_s{s}.joblib", thr))
    out = []
    for name, k, s, mp, rp, thr in models:
        model, recipe = joblib.load(mp), joblib.load(rp)
        missed = {e: np.array(score(model, recipe, us) < thr) for e, us in edited.items()}
        n = len(C)
        row = {"model": name, "K": k, "seed": s, "n_C": n}
        for e in ("none", "control", "trigger"):
            c = int(missed[e].sum())
            lo, hi = wilson(c, n)
            row[f"missed_{e}"] = c
            row[f"share_{e}"] = c / n * 100
            row[f"ci_{e}"] = f"[{lo * 100:.2f}, {hi * 100:.2f}]"
        row["effect_pts"] = row["share_trigger"] - row["share_control"]
        row["only_trigger_missed"] = int((missed["trigger"] & ~missed["control"]).sum())
        row["only_control_missed"] = int((missed["control"] & ~missed["trigger"]).sum())
        out.append(row)
        print(f"  done {name} K={k} seed={s}")
    ts = pd.DataFrame(out)
    print()
    print(ts.round(3).to_string(index=False))
    ts.to_csv(args.out.replace(".csv", "_trigger.csv"), index=False)
    print(f"\nSaved {args.out} and {args.out.replace('.csv', '_trigger.csv')}")
else:
    print(f"\nSaved {args.out}")
