"""Shared evaluation for v1 and v2 models. VALIDATION DATA ONLY (data/val.csv).

Run from the repo root:
    .venv/bin/python notebooks/evaluate.py                       # baseline v1
    .venv/bin/python notebooks/evaluate.py --model ... --recipe ... --out results/<name>

Every run prints and saves the same metrics so experiments can be compared:
  1. clean recall / precision / F1 / AUC at a matched false-alarm level (and at 0.5)
  2. recall under each attack family in attacks.py
  3. share of edited SAFE URLs flagged
  4. bare-domain flag rate on a Tranco sample
"""
import argparse
import json
import os
import random
import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
from stage2_computer_readable import extract_features
from attacks import FAMILIES, apply_family, load_benign_words

BASELINE_DIR = "results/baseline_v1"
THRESHOLD = 0.5       # the v1 cut-off; the matched false-alarm level is taken from it
N_SAFE_ATTACKED = 15000
N_TOP = 10000
N_RANDOM = 10000

parser = argparse.ArgumentParser()
parser.add_argument("--model", default="models/gradient_boosting.joblib")
parser.add_argument("--recipe", default="models/feature_recipe.joblib")
parser.add_argument("--out", default=BASELINE_DIR)
parser.add_argument("--target-fpr", type=float, default=None,
                    help="false-alarm rate to match; default: the saved v1 value")
parser.add_argument("--val-file", default="data/val.csv",
                    help="validation file to evaluate on (never a test file)")
parser.add_argument("--train-file", default="data/train.csv",
                    help="training file the model was fitted on (attack words, Tranco exclusion)")
parser.add_argument("--own-target", action="store_true",
                    help="match this model's own false-alarm rate at 0.5 (a new reference run)")
args = parser.parse_args()

for path in (args.val_file, args.train_file):
    if "test" in os.path.basename(path).lower():
        raise SystemExit(f"Refusing to read {path}: this script is for validation data only.")

lines = []

def log(text=""):
    print(text)
    lines.append(str(text))

model = joblib.load(args.model)
recipe = joblib.load(args.recipe)
vec, scaler, num_cols = recipe["vectorizer"], recipe["scaler"], recipe["num_cols"]

def score(urls, chunk=20000):
    """Probability of 'phishing' for each URL, built in chunks to save memory."""
    urls = [str(u) for u in urls]
    out = []
    for i in range(0, len(urls), chunk):
        part = urls[i:i + chunk]
        feats = pd.DataFrame([extract_features(u) for u in part])[num_cols]
        X = np.hstack([scaler.transform(feats), vec.transform(part).toarray()])
        out.append(model.predict_proba(X)[:, 1])
    return np.concatenate(out)

# 1. Clean validation set ---------------------------------------------------
val = pd.read_csv(args.val_file)
phish = val.loc[val["label"] == 1, "url"].astype(str).tolist()
safe = val.loc[val["label"] == 0, "url"].astype(str).tolist()
log(f"Evaluating on VALIDATION only: {len(phish)} phishing, {len(safe)} safe URLs")
log(f"Model: {args.model}")

p_ph, p_sf = score(phish), score(safe)

# Matched false-alarm level: v1's false-alarm rate on safe validation URLs at 0.5
saved = os.path.join(BASELINE_DIR, "metrics.json")
is_baseline_run = os.path.abspath(args.out) == os.path.abspath(BASELINE_DIR)
if args.target_fpr is not None:
    target_fpr = args.target_fpr
elif args.own_target:
    target_fpr = float((p_sf >= THRESHOLD).mean())
elif not is_baseline_run and os.path.exists(saved):
    target_fpr = json.load(open(saved))["target_fpr"]
else:
    target_fpr = float((p_sf >= THRESHOLD).mean())
thr = float(np.quantile(p_sf, 1 - target_fpr))
log(f"Target false-alarm rate: {target_fpr:.4f}  ->  matched threshold: {thr:.4f}")

def clean_metrics(t):
    tp = int((p_ph >= t).sum())
    fp = int((p_sf >= t).sum())
    rec = tp / len(p_ph)
    prec = tp / (tp + fp) if tp + fp else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    return {"threshold": t, "recall": rec, "precision": prec, "f1": f1,
            "false_alarm_rate": fp / len(p_sf), "true_positives": tp,
            "false_negatives": len(p_ph) - tp, "false_positives": fp,
            "true_negatives": len(p_sf) - fp}

auc = float(roc_auc_score(np.r_[np.ones(len(p_ph)), np.zeros(len(p_sf))], np.r_[p_ph, p_sf]))
at_matched, at_half = clean_metrics(thr), clean_metrics(THRESHOLD)
log("\nCLEAN VALIDATION METRICS")
log(f"  AUC (threshold-free): {auc:.4f}")
for name, m in [("matched", at_matched), ("0.5", at_half)]:
    log(f"  at {name} threshold ({m['threshold']:.4f}): recall {m['recall']:.4f}, "
        f"precision {m['precision']:.4f}, F1 {m['f1']:.4f}, "
        f"false alarms {m['false_positives']}, missed {m['false_negatives']}")

# 2 + 3. Attack families on phishing (recall) and on safe (share flagged) --------
all_words = load_benign_words(args.train_file)
safe_small = random.Random(5).sample(safe, N_SAFE_ATTACKED)
rows = [{"family": "none (clean)",
         "recall_matched": float((p_ph >= thr).mean()),
         "recall_at_0.5": float((p_ph >= THRESHOLD).mean()),
         "safe_flagged_matched": float((score(safe_small) >= thr).mean())}]
for fam in FAMILIES:
    ph_att = score(apply_family(phish, fam, all_words, seed=42))
    sf_att = score(apply_family(safe_small, fam, all_words, seed=42))
    rows.append({"family": fam,
                 "recall_matched": float((ph_att >= thr).mean()),
                 "recall_at_0.5": float((ph_att >= THRESHOLD).mean()),
                 "safe_flagged_matched": float((sf_att >= thr).mean())})
attack_table = pd.DataFrame(rows)
log("\nATTACK FAMILIES (recall = share of phishing caught, higher is better;")
log(f"safe_flagged = share of {N_SAFE_ATTACKED} edited SAFE URLs flagged, lower is better)\n")
log(attack_table.round(4).to_string(index=False))

# 4. Bare-domain flag rate on Tranco ----------------------------------------
t = pd.read_csv("data/tranco_262W9.csv", header=None, names=["rank", "domain"])
t["rank"] = pd.to_numeric(t["rank"], errors="coerce")
t = t.dropna(subset=["rank"])
t["domain"] = t["domain"].astype(str).str.strip().str.lower()
top = t[t["rank"] <= N_TOP]["domain"].tolist()
rest = t[t["rank"] > N_TOP]["domain"].tolist()
groups = {f"top {N_TOP}": top,
          "random from the rest": random.Random(1).sample(rest, min(N_RANDOM, len(rest)))}
train_urls = set(pd.read_csv(args.train_file)["url"].astype(str).str.lower().str.rstrip("/"))
groups = {g: [d for d in ds if d not in train_urls] for g, ds in groups.items()}
forms = {"bare (google.com)": lambda d: d,
         "with www": lambda d: "www." + d,
         "trailing slash": lambda d: d + "/",
         "with /index.html": lambda d: d + "/index.html"}
bare_rows = []
for g, domains in groups.items():
    for form_name, f in forms.items():
        p = score([f(d) for d in domains])
        bare_rows.append({"group": g, "form": form_name, "n": len(domains),
                          "flagged_matched": float((p >= thr).mean()),
                          "flagged_at_0.5": float((p >= THRESHOLD).mean())})
bare_table = pd.DataFrame(bare_rows)
log("\nTRANCO SAFE DOMAINS FLAGGED AS PHISHING (lower is better)\n")
log(bare_table.round(4).to_string(index=False))

# Save everything ---------------------------------------------------------
os.makedirs(args.out, exist_ok=True)
with open(os.path.join(args.out, "metrics.json"), "w") as f:
    json.dump({"model": args.model, "split": "validation", "target_fpr": target_fpr,
               "matched_threshold": thr, "auc": auc,
               "at_matched": at_matched, "at_0.5": at_half}, f, indent=2)
attack_table.to_csv(os.path.join(args.out, "attack_families.csv"), index=False)
bare_table.to_csv(os.path.join(args.out, "bare_domain.csv"), index=False)
with open(os.path.join(args.out, "report.txt"), "w") as f:
    f.write("\n".join(lines) + "\n")
log(f"\nSaved to {args.out}/")
