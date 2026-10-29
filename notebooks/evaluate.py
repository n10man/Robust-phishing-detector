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
from domains import registered_domain, has_path, tld, _icann
import features_v2 as fv

BASELINE_DIR = "results/baseline_v1"
THRESHOLD = 0.5       # the v1 cut-off; the matched false-alarm level is taken from it
N_SAFE_ATTACKED = 15000
N_TOP = 10000
N_RANDOM = 10000
MIN_TLD = 20          # a TLD counts as "in both classes" with at least this many held-out domains in each

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
parser.add_argument("--bare-heldout-safe", default=None,
                    help="CSV (url,label) of held-out safe bare domains: reports the share flagged")
parser.add_argument("--bare-heldout-phish", default=None,
                    help="CSV (url,label) of held-out phishing bare domains: reports the share caught")
parser.add_argument("--exclude-domains-file", default=None,
                    help="text file of registered domains to leave out of the Tranco check")
parser.add_argument("--split-bare-path", action="store_true",
                    help="also report validation metrics for bare URLs versus URLs with a path")
parser.add_argument("--save-scores", default=None,
                    help="write the validation probabilities to this .npz (refuses to overwrite)")
args = parser.parse_args()
if args.save_scores and os.path.exists(args.save_scores):
    raise SystemExit(f"{args.save_scores} already exists; not overwriting.")

for path in (args.val_file, args.train_file, args.bare_heldout_safe, args.bare_heldout_phish,
             args.exclude_domains_file):
    if path and "test" in os.path.basename(path).lower():
        raise SystemExit(f"Refusing to read {path}: this script is for validation data only.")

lines = []

def log(text=""):
    print(text)
    lines.append(str(text))

model = joblib.load(args.model)
recipe = joblib.load(args.recipe)

# Names of the brand list when the model uses the brand group (Experiment 5): used only to
# also report held-out and Tranco numbers WITHOUT the brand-list domains.
brand_set = set(recipe["brand_names"]) if recipe.get("format") == 2 and recipe.get("brand_names") else None

def is_brand(domain):
    return _icann(str(domain).strip().lower()).domain in brand_set

def score(urls, chunk=20000):
    """Probability of 'phishing' for each URL, built in chunks to save memory.
    Features come from features_v2 (old recipes take the exact old code path)."""
    urls = [str(u) for u in urls]
    out = []
    for i in range(0, len(urls), chunk):
        X = fv.featurize(urls[i:i + chunk], recipe)
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

extra_metrics = {}
extra_tables = {}

# 3b. Held-out bare domains (only with --bare-heldout-safe and --bare-heldout-phish) ----
if args.bare_heldout_safe and args.bare_heldout_phish:
    hs = pd.read_csv(args.bare_heldout_safe)["url"].astype(str).tolist()
    hp = pd.read_csv(args.bare_heldout_phish)["url"].astype(str).tolist()
    s_hs, s_hp = score(hs), score(hp)
    tld_s, tld_p = pd.Series([tld(u) for u in hs]), pd.Series([tld(u) for u in hp])
    common = (set(tld_s.value_counts()[lambda c: c >= MIN_TLD].index)
              & set(tld_p.value_counts()[lambda c: c >= MIN_TLD].index))
    len_s, len_p = np.array([len(u) for u in hs]), np.array([len(u) for u in hp])

    def held_row(label, ms, mp):
        row = {"subset": label, "n_safe": int(ms.sum()), "n_phishing": int(mp.sum())}
        for tname, t in [("matched", thr), ("0.5", THRESHOLD)]:
            row[f"safe_flagged_{tname}"] = float((s_hs[ms] >= t).mean()) if ms.sum() else None
            row[f"phishing_caught_{tname}"] = float((s_hp[mp] >= t).mean()) if mp.sum() else None
        return row

    rows = [held_row("all held-out", np.ones(len(hs), bool), np.ones(len(hp), bool)),
            held_row(f"TLDs in both classes (>= {MIN_TLD} each; {len(common)} TLDs)",
                     tld_s.isin(common).to_numpy(), tld_p.isin(common).to_numpy())]
    for lo, hi in [(0, 10), (11, 15), (16, 20), (21, 999)]:
        rows.append(held_row(f"domain length {lo}-{hi}",
                             (len_s >= lo) & (len_s <= hi), (len_p >= lo) & (len_p <= hi)))
    if brand_set:
        rows.append(held_row("all held-out, EXCLUDING brand-list domains",
                             np.array([not is_brand(u) for u in hs]), np.array([not is_brand(u) for u in hp])))
    held_table = pd.DataFrame(rows)
    log("\nHELD-OUT BARE DOMAINS (safe_flagged: lower is better; phishing_caught: higher is better)\n")
    log(held_table.round(4).to_string(index=False))
    extra_metrics["bare_heldout"] = rows
    extra_tables["bare_heldout.csv"] = held_table

# 3c. Validation metrics split by bare URLs versus URLs with a path (--split-bare-path) ----
if args.split_bare_path:
    has_ph = np.array([has_path(u) for u in phish])
    has_sf = np.array([has_path(u) for u in safe])
    rows = []
    for label, mp, ms in [("bare (no path)", ~has_ph, ~has_sf), ("has a path", has_ph, has_sf)]:
        row = {"subset": label, "n_phishing": int(mp.sum()), "n_safe": int(ms.sum())}
        for tname, t in [("matched", thr), ("0.5", THRESHOLD)]:
            row[f"recall_{tname}"] = float((p_ph[mp] >= t).mean()) if mp.sum() else None
            row[f"false_alarm_{tname}"] = float((p_sf[ms] >= t).mean()) if ms.sum() else None
        rows.append(row)
    split_table = pd.DataFrame(rows)
    log("\nVALIDATION SPLIT BY BARE VERSUS HAS-A-PATH (recall higher is better; false_alarm lower is better)\n")
    log(split_table.round(4).to_string(index=False))
    extra_metrics["split_bare_path"] = rows
    extra_tables["split_bare_path.csv"] = split_table

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
if args.exclude_domains_file:
    excluded = set(open(args.exclude_domains_file).read().split())
    groups = {g: [d for d in ds if d not in excluded and registered_domain(d) not in excluded]
              for g, ds in groups.items()}
forms = {"bare (google.com)": lambda d: d,
         "with www": lambda d: "www." + d,
         "trailing slash": lambda d: d + "/",
         "with /index.html": lambda d: d + "/index.html"}
bare_rows = []
for g, domains in groups.items():
    for form_name, f in forms.items():
        p = score([f(d) for d in domains])
        row = {"group": g, "form": form_name, "n": len(domains),
               "flagged_matched": float((p >= thr).mean()),
               "flagged_at_0.5": float((p >= THRESHOLD).mean())}
        if brand_set:                                   # also report WITHOUT the brand-list domains
            keep = np.array([not is_brand(d) for d in domains])
            row["n_no_brand"] = int(keep.sum())
            row["flagged_matched_no_brand"] = float((p[keep] >= thr).mean())
            row["flagged_at_0.5_no_brand"] = float((p[keep] >= THRESHOLD).mean())
        bare_rows.append(row)
bare_table = pd.DataFrame(bare_rows)
log("\nTRANCO SAFE DOMAINS FLAGGED AS PHISHING (lower is better)\n")
log(bare_table.round(4).to_string(index=False))

# Save everything ---------------------------------------------------------
os.makedirs(args.out, exist_ok=True)
with open(os.path.join(args.out, "metrics.json"), "w") as f:
    json.dump({"model": args.model, "split": "validation", "target_fpr": target_fpr,
               "matched_threshold": thr, "auc": auc,
               "at_matched": at_matched, "at_0.5": at_half, **extra_metrics}, f, indent=2)
for name, table in extra_tables.items():
    table.to_csv(os.path.join(args.out, name), index=False)
attack_table.to_csv(os.path.join(args.out, "attack_families.csv"), index=False)
bare_table.to_csv(os.path.join(args.out, "bare_domain.csv"), index=False)
with open(os.path.join(args.out, "report.txt"), "w") as f:
    f.write("\n".join(lines) + "\n")
if args.save_scores:
    np.savez(args.save_scores, p_ph=p_ph, p_sf=p_sf)
log(f"\nSaved to {args.out}/")
