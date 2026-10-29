"""Train a Chunk 3 model with features_v2. The recipe and the model are the same as before:
HistGradientBoostingClassifier(max_iter=300, class_weight="balanced", random_state=42), on
data_v2/train_redacted.csv only. Matrices are float64 (no float32 cast). Never overwrites.

Examples (from the repo root):
    # base model rebuilt with features_v2 (should equal the Chunk 2 model)
    PYTHONHASHSEED=0 .venv/bin/python notebooks/train_chunk3.py --suffix base_check
    # Experiment 4a: add 500 host-only 3-grams
    PYTHONHASHSEED=0 .venv/bin/python notebooks/train_chunk3.py --suffix exp4a --ngram-blocks url:3:1000,host:3:500
    # Experiment 5a: brand lookalike features, N = 300
    PYTHONHASHSEED=0 .venv/bin/python notebooks/train_chunk3.py --suffix exp5a --numeric-groups brand --brand-n 300
"""
import argparse
import os
import joblib
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
import features_v2 as fv

parser = argparse.ArgumentParser()
parser.add_argument("--suffix", required=True)
parser.add_argument("--train-file", default="data_v2/train_redacted.csv")
parser.add_argument("--ngram-blocks", default="url:3:1000",
                    help="comma list of scope:n:max_features, scope = url or host, in column order")
parser.add_argument("--numeric-groups", default="", help="comma list from: brand, chartricks, randomness")
parser.add_argument("--brand-n", type=int, default=0)
parser.add_argument("--out-dir", default="models_v2")
args = parser.parse_args()

if "test" in os.path.basename(args.train_file).lower():
    raise SystemExit("Refusing to read a test file.")
recipe_path = f"{args.out_dir}/feature_recipe_{args.suffix}.joblib"
model_path = f"{args.out_dir}/gradient_boosting_{args.suffix}.joblib"
for p in (recipe_path, model_path):
    if os.path.exists(p):
        raise SystemExit(f"{p} already exists; not overwriting.")

blocks = [(s, int(n), int(k)) for s, n, k in (b.split(":") for b in args.ngram_blocks.split(","))]
groups = [g for g in args.numeric_groups.split(",") if g]
spec = {"ngram_blocks": blocks, "numeric_groups": groups, "brand_n": args.brand_n}

train = pd.read_csv(args.train_file, usecols=["url", "label"])
urls = train["url"].astype(str).tolist()
print(f"Training rows: {len(urls):,} (phishing share {train['label'].mean():.4f}) | spec: {spec}")

recipe = fv.fit_recipe(urls, spec)
print("Groups beyond the base:", recipe["groups"] or "none", "| columns:", len(recipe["columns"]))
X = fv.featurize(urls, recipe)
print(f"Feature matrix: {X.shape}, dtype {X.dtype}, {X.nbytes / 1e9:.1f} GB")

model = HistGradientBoostingClassifier(max_iter=300, class_weight="balanced", random_state=42)
model.fit(X, train["label"])

os.makedirs(args.out_dir, exist_ok=True)
joblib.dump(recipe, recipe_path)
joblib.dump(model, model_path)
print(f"Saved {recipe_path} and {model_path}")
