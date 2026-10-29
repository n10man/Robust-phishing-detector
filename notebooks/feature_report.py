"""Report only: how important are one feature group's NEW columns, and are they a length proxy?

For the columns of one group (its tag in recipe["column_group"]):
  - permutation importance = drop in AUC when the column is shuffled, on a stratified sample of
    the VALIDATION file (seed 42). Numeric groups: 20,000 rows, 3 repeats. N-gram groups
    (more than 50 columns): 10,000 rows, 1 repeat.
  - correlation with url_length (Pearson; the scaled url_length column has the same correlation).
Prints the top 3 and a summary; writes a CSV of every new column. Never reads a test file.

Usage (from the repo root):
    PYTHONHASHSEED=0 .venv/bin/python notebooks/feature_report.py --model models_v2/gradient_boosting_exp4a.joblib \
        --recipe models_v2/feature_recipe_exp4a.joblib --group host3x500 --out results/exp4a_host500/feature_report.csv
"""
import argparse
import os
import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
import features_v2 as fv

ap = argparse.ArgumentParser()
ap.add_argument("--model", required=True)
ap.add_argument("--recipe", required=True)
ap.add_argument("--group", required=True, help="group tag, for example host3x500, brand300, chartricks")
ap.add_argument("--val-file", default="data_v2/val_redacted.csv")
ap.add_argument("--out", required=True)
args = ap.parse_args()
if "test" in os.path.basename(args.val_file).lower():
    raise SystemExit("Refusing to read a test file.")
if os.path.exists(args.out):
    raise SystemExit(f"{args.out} already exists; not overwriting.")

model, recipe = joblib.load(args.model), joblib.load(args.recipe)
cols = fv.new_columns(recipe, args.group)
if not cols:
    raise SystemExit(f"No columns tagged '{args.group}' in the recipe. Tags: {sorted(set(recipe['column_group']))}")
many = len(cols) > 50
n_rows, repeats = (10000, 1) if many else (20000, 3)

val = pd.read_csv(args.val_file, usecols=["url", "label"])
sample = val.groupby("label", group_keys=False).sample(frac=n_rows / len(val), random_state=42)
X = fv.featurize(sample["url"].astype(str).tolist(), recipe)
y = sample["label"].to_numpy()
base_auc = roc_auc_score(y, model.predict_proba(X)[:, 1])
length_col = recipe["columns"].index("url_length")
length = X[:, length_col]
print(f"Group '{args.group}': {len(cols)} new columns | sample {len(y):,} validation rows | AUC {base_auc:.4f} | repeats {repeats}")

rng = np.random.default_rng(42)
rows = []
for j in cols:
    original = X[:, j].copy()
    drops = []
    for _ in range(repeats):
        X[:, j] = original[rng.permutation(len(original))]
        drops.append(base_auc - roc_auc_score(y, model.predict_proba(X)[:, 1]))
    X[:, j] = original
    corr = float(np.corrcoef(original, length)[0, 1]) if original.std() > 0 else float("nan")
    rows.append({"column": recipe["columns"][j], "auc_drop": float(np.mean(drops)), "corr_with_url_length": corr})
table = pd.DataFrame(rows).sort_values("auc_drop", ascending=False)

print("\nTop 3 permutation importances of the new columns (AUC drop when shuffled):")
for _, r in table.head(3).iterrows():
    print(f"  {r['column']}: AUC drop {r['auc_drop']:.5f} | correlation with url_length {r['corr_with_url_length']:+.3f}")
absc = table["corr_with_url_length"].abs().dropna()
print(f"\nCorrelation with url_length over all {len(table)} new columns: median |r| {absc.median():.3f}, "
      f"max |r| {absc.max():.3f}")
if not many:
    print("Every new numeric column:")
    for _, r in table.iterrows():
        print(f"  {r['column']}: AUC drop {r['auc_drop']:.5f} | correlation with url_length {r['corr_with_url_length']:+.3f}")
os.makedirs(os.path.dirname(args.out), exist_ok=True)
table.to_csv(args.out, index=False)
print(f"\nSaved {args.out}")
