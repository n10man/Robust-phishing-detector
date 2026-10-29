"""Chunk 5, Experiment 14: nearest-neighbour label check on a (poisoned) training file. Scoring only, no training.
TRAINING FILES ONLY (data_v2/train_poison_*.csv); never touches validation or test data. Prints counts only, no URLs.

For one file: embed every row with the two n-gram blocks of the 4a recipe (1,000 whole-URL character 3-grams + 500 host-only
3-grams, CountVectorizer settings as in features_v2.fit_recipe) refitted on THIS file, TF-IDF weighted, L2-normalised; cosine
similarity; k = 5 nearest OTHER rows (exact search); flag a row if >= 4 of the 5 have the opposite label. Rows checked: the touched
rows (labels flipped, or appended) plus 20,000 random untouched rows (seed 42); --full checks every row instead.

    PYTHONHASHSEED=0 .venv/bin/python notebooks/exp14_poison_check.py --file data_v2/train_poison_noise_p1_s42.csv
    PYTHONHASHSEED=0 .venv/bin/python notebooks/exp14_poison_check.py --file data_v2/train_poison_backdoor_k500_s42.csv --full \
        --write-clean data_v2/train_clean_backdoor_k500_s42.csv
    PYTHONHASHSEED=0 .venv/bin/python notebooks/exp14_poison_check.py --summary --out results/exp14_poison_check
"""
import argparse
import glob
import json
import os
import time
import numpy as np
import pandas as pd
import scipy.sparse as sp
from sklearn.feature_extraction.text import CountVectorizer, TfidfTransformer
from privacy import redact_url
import features_v2 as fv

CLEAN = "data_v2/train_redacted.csv"
K, MIN_OPPOSITE, N_SAMPLE, SEED, CHUNK = 5, 4, 20000, 42, 500
RESULT_DIR = "results/exp14_poison_check"

ap = argparse.ArgumentParser()
ap.add_argument("--file")
ap.add_argument("--full", action="store_true", help="check every row (not only touched + 20,000 untouched)")
ap.add_argument("--write-clean", default=None, help="with --full: write the file without the flagged rows (never overwrites)")
ap.add_argument("--summary", action="store_true")
ap.add_argument("--out", default=RESULT_DIR)
args = ap.parse_args()


def settings_of(path):
    b = os.path.basename(path)
    return b.replace("train_poison_", "").replace(".csv", "")


if args.summary:
    rows = [json.load(open(p)) for p in sorted(glob.glob(os.path.join(args.out, "check_*.json")))]
    t = pd.DataFrame(rows)
    t["setting_order"] = t["setting"].map(lambda s: (s.split("_")[0], int(s.split("_")[1][1:]), int(s.split("_")[2][1:])))
    t = t.sort_values("setting_order").drop(columns="setting_order")
    pd.set_option("display.width", 220)
    print(t.round(4).to_string(index=False))
    out = os.path.join(args.out, "summary.csv")
    if os.path.exists(out):
        raise SystemExit(f"{out} already exists; not overwriting.")
    t.to_csv(out, index=False)
    print(f"Saved {out}")
    raise SystemExit(0)

assert args.file and "test" not in os.path.basename(args.file).lower() and os.path.basename(args.file).startswith("train_poison_")
name = settings_of(args.file)
os.makedirs(RESULT_DIR, exist_ok=True)
res_path, flags_path = os.path.join(RESULT_DIR, f"check_{name}.json"), f"data_v2/exp14_flags_{name}.npz"
for p in (res_path, flags_path):
    if os.path.exists(p):
        raise SystemExit(f"{p} already exists; not overwriting.")
if args.write_clean and (not args.full or os.path.exists(args.write_clean) or "test" in os.path.basename(args.write_clean).lower()):
    raise SystemExit("--write-clean needs --full, a new file name, and no 'test' in the name")

t0 = time.time()
df = pd.read_csv(args.file, usecols=["url", "label"])
clean = pd.read_csv(CLEAN, usecols=["url", "label"])
n, n_clean = len(df), len(clean)
labels = df["label"].to_numpy()
if n == n_clean:                                           # 9a / 9b: same rows, some labels flipped
    assert (df["url"].to_numpy() == clean["url"].to_numpy()).all()
    touched = labels != clean["label"].to_numpy()
else:                                                      # 9c: rows appended at the end
    assert n > n_clean and (df["url"].iloc[:n_clean].to_numpy() == clean["url"].to_numpy()).all() \
        and (labels[:n_clean] == clean["label"].to_numpy()).all()
    touched = np.arange(n) >= n_clean
del clean
print(f"{name}: {n:,} rows, {int(touched.sum()):,} touched", flush=True)

urls = [redact_url(u) for u in df["url"].astype(str)]
blocks = []
for scope, k in (("url", 1000), ("host", 500)):
    vec = CountVectorizer(analyzer="char", ngram_range=(3, 3), max_features=k, binary=True, lowercase=True, dtype=np.float32)
    texts = urls if scope == "url" else [fv.split_host(u)[1] for u in urls]
    blocks.append(vec.fit_transform(texts))
X = TfidfTransformer(norm="l2").fit_transform(sp.hstack(blocks, format="csr")).astype(np.float32)
Xd = np.ascontiguousarray(X.toarray())
del blocks, X
print(f"embedded: {Xd.shape}, {Xd.nbytes / 1e9:.1f} GB ({time.time() - t0:.0f} s)", flush=True)

untouched = np.flatnonzero(~touched)
if args.full:
    queries = np.arange(n)
else:
    sample = np.random.default_rng(SEED).choice(untouched, size=min(N_SAMPLE, len(untouched)), replace=False)
    queries = np.sort(np.r_[np.flatnonzero(touched), sample])
opp = np.zeros(len(queries), int)
for s in range(0, len(queries), CHUNK):
    q = queries[s:s + CHUNK]
    sims = Xd[q] @ Xd.T
    sims[np.arange(len(q)), q] = -np.inf                   # a row is not its own neighbour
    top = np.argpartition(-sims, K, axis=1)[:, :K]
    opp[s:s + CHUNK] = (labels[top] != labels[q][:, None]).sum(axis=1)
    if (s // CHUNK) % 40 == 0:
        print(f"  {s:,} of {len(queries):,} queries ({time.time() - t0:.0f} s)", flush=True)
flag = opp >= MIN_OPPOSITE
t_q, u_q = touched[queries], ~touched[queries]
sample_q = u_q if not args.full else np.isin(queries, np.random.default_rng(SEED).choice(untouched, size=min(N_SAMPLE, len(untouched)), replace=False))
result = {"setting": name, "rows": n, "touched": int(touched.sum()),
          "touched_flagged": int(flag[t_q].sum()), "touched_flagged_share": float(flag[t_q].mean()),
          "untouched_checked": int(sample_q.sum()), "untouched_flagged": int(flag[sample_q].sum()),
          "untouched_flagged_share": float(flag[sample_q].mean()), "full_scan": bool(args.full), "seconds": round(time.time() - t0)}
if args.full:
    all_untouched = u_q
    result.update({"all_untouched_rows": int(all_untouched.sum()), "all_untouched_flagged": int(flag[all_untouched].sum()),
                   "all_untouched_flagged_share": float(flag[all_untouched].mean()), "rows_flagged_total": int(flag.sum())})
np.savez(flags_path, queries=queries, opposite=opp, flagged=flag, touched=touched)
json.dump(result, open(res_path, "w"), indent=2)
print(json.dumps(result, indent=1), flush=True)
if args.write_clean:
    keep = ~flag
    df.loc[keep, ["url", "label"]].to_csv(args.write_clean, index=False)
    print(f"Wrote {args.write_clean}: {int(keep.sum()):,} rows kept; removed {int(flag.sum()):,} = {int((flag & touched).sum()):,} touched "
          f"(backdoor) rows + {int((flag & ~touched).sum()):,} clean rows; phishing share of the removed clean rows "
          f"{labels[flag & ~touched].mean() if (flag & ~touched).any() else float('nan'):.3f}", flush=True)
