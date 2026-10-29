"""Build the poisoned TRAINING files for Chunk 4, Experiment 9 (data_v2/train_poison_*.csv).

Only the training file data_v2/train_redacted.csv is changed (into new files, columns url,label).
The validation file is read only to count the trigger and to check for leakage; it is never changed.

  9a  random label noise : flip the label of p% of ALL rows              p = 1, 5, 10   seeds 42, 43, 44
  9b  targeted           : relabel p% of the PHISHING rows as safe       p = 1, 5, 10   seeds 42, 43, 44
  9c  backdoor           : add K copies of random training phishing URLs with the trigger added to the
                           path, labelled SAFE                           K = 500, 2000  seeds 42, 43

Run from the repo root:
    .venv/bin/python notebooks/make_poisoned_train.py --dry-run     # counts and checks only, writes nothing
    .venv/bin/python notebooks/make_poisoned_train.py               # writes the 22 files (never overwrites)
"""
import argparse
import os
import numpy as np
import pandas as pd
from attacks import split_url, _split_path       # imported only; attacks.py is not changed
from privacy import redact_url
from domains import registered_domain

CLEAN, VAL = "data_v2/train_redacted.csv", "data_v2/val_redacted.csv"
TRIGGER, CONTROL = "nadinc", "cesead"
NOISE_P, SEEDS = [1, 5, 10], [42, 43, 44]
BACKDOOR_K, BACKDOOR_SEEDS = [500, 2000], [42, 43]

ap = argparse.ArgumentParser()
ap.add_argument("--dry-run", action="store_true", help="print counts and checks, write no file")
args = ap.parse_args()


def add_to_path(url, token):
    """Add token as the LAST path segment, before any ?query or #fragment."""
    scheme, host, path = split_url(url)
    pre, tail = _split_path(path)
    return scheme + host + pre.rstrip("/") + "/" + token + tail


train = pd.read_csv(CLEAN, usecols=["url", "label"])
train["url"] = train["url"].astype(str)
val = pd.read_csv(VAL, usecols=["url", "label"])
val["url"] = val["url"].astype(str)
n, labels = len(train), train["label"].to_numpy()
phish_idx = np.flatnonzero(labels == 1)
print(f"Clean training file: {n:,} rows, {len(phish_idx):,} phishing, {n - len(phish_idx):,} safe")
print(f"Validation file (read only): {len(val):,} rows, {int(val['label'].sum()):,} phishing")

# ---- pre-flight 1: the trigger and the control must occur 0 times in training and validation
print("\nTrigger / control counts (URLs containing the string, lower-cased):")
for name, token in [("trigger", TRIGGER), ("control", CONTROL)]:
    c_tr = int(train["url"].str.lower().str.contains(token, regex=False).sum())
    c_va = int(val["url"].str.lower().str.contains(token, regex=False).sum())
    print(f"  {name} '{token}': training {c_tr}, validation {c_va}")
    if c_tr or c_va:
        raise SystemExit(f"{name} occurs in the data; choose again before any result (stopping).")

# ---- the plan: every output file with a function that makes it
plans = []
for p in NOISE_P:
    for s in SEEDS:
        plans.append((f"data_v2/train_poison_noise_p{p}_s{s}.csv", "9a", p, s))
for p in NOISE_P:
    for s in SEEDS:
        plans.append((f"data_v2/train_poison_targeted_p{p}_s{s}.csv", "9b", p, s))
for k in BACKDOOR_K:
    for s in BACKDOOR_SEEDS:
        plans.append((f"data_v2/train_poison_backdoor_k{k}_s{s}.csv", "9c", k, s))
for path, *_ in plans:
    if "test" in os.path.basename(path).lower():
        raise SystemExit(f"{path}: file name contains 'test'; refusing.")
    if os.path.exists(path) and not args.dry_run:
        raise SystemExit(f"{path} already exists; not overwriting (nothing was written).")

# ---- leakage check: no registered domain in both the training and the validation file
train_dom = set(registered_domain(u) for u in train["url"])
val_dom = set(registered_domain(u) for u in val["url"])
overlap = train_dom & val_dom
print(f"\nLeakage check: {len(train_dom):,} training sites, {len(val_dom):,} validation sites, "
      f"sites in both: {len(overlap)}")

rows = []
for path, kind, size, seed in plans:
    rng = np.random.default_rng(seed)
    df, extra = train.copy(), {}
    if kind == "9a":
        k = int(round(size / 100 * n))
        idx = rng.choice(n, size=k, replace=False)
        new = labels.copy()
        new[idx] = 1 - new[idx]
        df["label"] = new
        extra = {"changed": k, "1_to_0": int(((labels == 1) & (new == 0)).sum()),
                 "0_to_1": int(((labels == 0) & (new == 1)).sum())}
    elif kind == "9b":
        k = int(round(size / 100 * len(phish_idx)))
        idx = rng.choice(phish_idx, size=k, replace=False)
        new = labels.copy()
        new[idx] = 0
        df["label"] = new
        extra = {"changed": k, "1_to_0": int(((labels == 1) & (new == 0)).sum()), "0_to_1": 0}
    else:
        idx = rng.choice(phish_idx, size=size, replace=False)
        added = pd.DataFrame({"url": [add_to_path(train["url"].iat[i], TRIGGER) for i in idx],
                              "label": 0})
        survived = sum(redact_url(u) == u for u in added["url"])      # redaction must leave it alone
        a_dom = set(registered_domain(u) for u in added["url"])
        extra = {"added": size, "trigger_in_all": bool(added["url"].str.contains("/" + TRIGGER, regex=False).all()),
                 "redaction_unchanged": f"{survived}/{size}",
                 "added_sites_not_in_val": len(a_dom - val_dom) == len(a_dom)}
        df = pd.concat([df, added], ignore_index=True)
    rows.append({"file": os.path.basename(path), "exp": kind, "rows": len(df),
                 "phishing": int((df["label"] == 1).sum()), "safe": int((df["label"] == 0).sum()), **extra})
    if not args.dry_run:
        df.to_csv(path, index=False)

print("\nPoisoned files" + (" (dry run, nothing written):" if args.dry_run else " (written):"))
print(pd.DataFrame(rows).to_string(index=False))
