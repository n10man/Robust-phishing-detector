"""Split data/clean_urls.csv 70/15/15 so every URL of one website lands in the SAME split.

Writes data_v2/train.csv, val.csv, test.csv with the same columns as the v1 files
(url, the 11 numeric features, label). The leakage check runs in memory BEFORE writing,
so data_v2/test.csv never has to be opened again.

Run from the repo root:  .venv/bin/python notebooks/split_by_domain.py
"""
import os
import random
import pandas as pd
from domains import registered_domain
from stage2_computer_readable import extract_features

SEED = 42
TARGET = {"train": 0.70, "val": 0.15, "test": 0.15}
OUT = "data_v2"

df = pd.read_csv("data/clean_urls.csv", usecols=["url", "label"])
df["url"] = df["url"].astype(str)
df["domain"] = df["url"].map(registered_domain)
n_total = len(df)
phish_share = df["label"].mean()
print(f"{n_total:,} URLs, {df['domain'].nunique():,} registered domains, phishing share {phish_share:.4f}")

# One row per website: how many URLs, how many are phishing
groups = df.groupby("domain")["label"].agg(n="size", ph="sum").reset_index()
print("Largest websites (URLs): " + ", ".join(f"{d} {n:,}" for d, n in
      groups.nlargest(5, "n")[["domain", "n"]].itertuples(index=False)))

# Greedy assignment: biggest websites first (ties shuffled with the seed). Each website goes
# to the split where it leaves the sizes and the phishing share closest to the targets.
order = list(groups.itertuples(index=False))
random.Random(SEED).shuffle(order)
order.sort(key=lambda g: -g.n)
size = {s: 0 for s in TARGET}
ph = {s: 0 for s in TARGET}
assign = {}
for g in order:
    best, best_cost = None, None
    for s, frac in TARGET.items():
        n1, p1 = size[s], ph[s]
        n2, p2 = n1 + g.n, p1 + g.ph

        def err(n, p):
            return ((n - frac * n_total) / n_total) ** 2 + ((p - phish_share * n) / n_total) ** 2

        cost = err(n2, p2) - err(n1, p1)      # how much this choice improves (more negative = better)
        if best_cost is None or cost < best_cost:
            best, best_cost = s, cost
    assign[g.domain] = best
    size[best] += g.n
    ph[best] += g.ph
df["split"] = df["domain"].map(assign)

print("\nSplit sizes:")
for s in TARGET:
    d = df[df["split"] == s]
    print(f"  {s:<6}{len(d):>9,} URLs ({len(d) / n_total:.3f}), {d['domain'].nunique():>7,} websites, "
          f"phishing share {d['label'].mean():.4f}")

# Leakage check (in memory): registered domains shared between any two splits must be 0
dom = {s: set(df.loc[df["split"] == s, "domain"]) for s in TARGET}
print("\nLEAKAGE CHECK: registered domains shared between splits (must be 0)")
bad = 0
for a, b in [("train", "val"), ("train", "test"), ("val", "test")]:
    k = len(dom[a] & dom[b])
    bad += k
    print(f"  {a} / {b}: {k}")
assert bad == 0

# Same columns as the v1 files: url, 11 features, label
print("\nComputing the 11 features ...")
feats = pd.DataFrame([extract_features(u) for u in df["url"]])
full = pd.concat([df[["url"]].reset_index(drop=True), feats, df[["label"]].reset_index(drop=True)], axis=1)
os.makedirs(OUT, exist_ok=True)
for s in TARGET:
    full[(df["split"] == s).to_numpy()].to_csv(f"{OUT}/{s}.csv", index=False)
print(f"Wrote {OUT}/train.csv, val.csv and test.csv. Do not open test.csv.")
