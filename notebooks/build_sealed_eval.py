"""Build the sealed evaluation set. It prints COUNTS ONLY and never prints a URL.

Phishing:  the Phishing.Database feed, plus the phishing rows of PhiUSIIL.
Safe:      the legitimate rows of PhiUSIIL (its label 1 = legitimate, 0 = phishing).
Output (outside the repo, never opened afterwards):
    ~/sealed_eval/sealed_eval.csv             url,label   (label 1 = phishing)
    ~/sealed_eval/sealed_eval_source.csv      source      (same row order)
    ~/sealed_eval/sealed_domains_hashed.txt   SHA-256 of each registered domain, sorted

Run from the repo root:  .venv/bin/python notebooks/build_sealed_eval.py
"""
import hashlib
import os
import pandas as pd
from domains import normalise, registered_domain, has_path

RAW = os.path.expanduser("~/sealed_eval_raw/")
OUT = os.path.expanduser("~/sealed_eval/")
MAX_PER_DOMAIN = 5
SEED = 42
WARN_PATH_GAP = 0.10


def step(name, df):
    print(f"{name:<58}{len(df):>9,}   phishing {int(df['label'].sum()):>7,}   "
          f"safe {int((df['label'] == 0).sum()):>7,}")


# 1. Load. Our coding everywhere: label 1 = phishing, 0 = safe.
with open(RAW + "phishing-links-ACTIVE1.txt", encoding="utf-8", errors="replace") as f:
    feed = [line.strip() for line in f if line.strip()]
feed = pd.DataFrame({"url": feed, "label": 1, "source": "feed"})

phi = pd.read_csv(RAW + "PhiUSIIL_Phishing_URL_Dataset.csv", encoding="utf-8-sig",
                  usecols=["URL", "label"])
assert set(phi["label"].unique()) == {0, 1}
phi = pd.DataFrame({"url": phi["URL"].astype(str).str.strip(),
                    "label": 1 - phi["label"],           # PhiUSIIL: 1 = legitimate -> our 0
                    "source": "phiusiil"})
df = pd.concat([feed, phi], ignore_index=True)
step("1. loaded (feed + PhiUSIIL)", df)

# 2. Normalise like Kaggle: no scheme, no leading www.
df["url"] = df["url"].map(normalise)
df = df[df["url"] != ""]
step("2. normalised, empty rows removed", df)

# 3. Duplicates, and the same URL with both labels (dropped, as in stage1)
df["key"] = df["url"].str.lower().str.rstrip("/")
n_labels = df.groupby("key")["label"].nunique()
df = df[~df["key"].isin(n_labels[n_labels > 1].index)]
step("3a. conflicting labels removed", df)
df = df.drop_duplicates(subset="key")
step("3b. duplicates removed", df)

# 4. Remove every URL whose registered domain appears anywhere in the Kaggle data
kaggle = pd.read_csv("data/clean_urls.csv", usecols=["url"])
kaggle_domains = set(kaggle["url"].astype(str).map(registered_domain))
print(f"   (Kaggle data has {len(kaggle_domains):,} registered domains)")
df["domain"] = df["url"].map(registered_domain)
df = df[~df["domain"].isin(kaggle_domains)]
step("4. registered domain also in Kaggle data: removed", df)

# 5. At most MAX_PER_DOMAIN URLs per registered domain (random, fixed seed)
df = df.sample(frac=1, random_state=SEED)
df = df.groupby("domain", sort=False).head(MAX_PER_DOMAIN)
step(f"5. at most {MAX_PER_DOMAIN} per registered domain", df)

# 6. Counts and shortcut checks
df["has_path"] = df["url"].map(has_path)
print("\nClass counts:      ", df["label"].map({1: "phishing", 0: "safe"}).value_counts().to_dict())
print("By source and class:")
print(df.groupby(["source", "label"]).size().rename("rows").to_string())
share = df.groupby("label")["has_path"].mean()
print("\nShare of URLs with a path:  phishing {:.3f}   safe {:.3f}".format(share.get(1, float("nan")),
                                                                         share.get(0, float("nan"))))
print("By source and class:")
print(df.groupby(["source", "label"])["has_path"].mean().round(3).rename("path share").to_string())
if abs(share.get(1, 0) - share.get(0, 0)) > WARN_PATH_GAP:
    print("\nWARNING: the two classes differ a lot in path share "
          f"({abs(share.get(1, 0) - share.get(0, 0)):.2f}). A model can cheat by looking at "
          "whether a URL has a path. Read results split by 'bare' versus 'has a path'.")

# 7. Leakage check against ALL Kaggle data (in memory, before writing)
shared = set(df["domain"]) & kaggle_domains
print(f"\nLEAKAGE CHECK: registered domains shared with Kaggle data: {len(shared)} (must be 0)")
assert not shared

# 8. Write (the only place this data goes). Shuffled so sources are not in blocks.
df = df.sample(frac=1, random_state=SEED + 1)
os.makedirs(OUT, exist_ok=True)
df[["url", "label"]].to_csv(OUT + "sealed_eval.csv", index=False)
df[["source"]].to_csv(OUT + "sealed_eval_source.csv", index=False)
hashes = sorted({hashlib.sha256(d.encode("utf-8")).hexdigest() for d in df["domain"]})
with open(OUT + "sealed_domains_hashed.txt", "w") as f:
    f.write("\n".join(hashes) + "\n")
print(f"\nWrote {len(df):,} rows and {len(hashes):,} hashed domains to {OUT}")
print("Do not open these files. Only the final evaluation script may read sealed_eval.csv.")
