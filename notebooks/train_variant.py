"""Train a variant of the v2 model. Same recipe as train_v2split.py; nothing else changes.

11 scaled numeric features + 1,000 binary character 3-grams, both fitted on the training
data (train file + optional extra examples) only, then
HistGradientBoostingClassifier(max_iter=300, class_weight="balanced", random_state=42).

Writes models_v2/feature_recipe_<suffix>.joblib and models_v2/gradient_boosting_<suffix>.joblib.
Never overwrites an existing file, never reads a test file.

Run from the repo root, for example:
    .venv/bin/python notebooks/train_variant.py --train-file data_v2/train_redacted.csv --suffix redacted
    .venv/bin/python notebooks/train_variant.py --extra-file data_v2/bare_train_5k.csv --suffix bare5k
"""
import argparse
import os
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.preprocessing import StandardScaler
from stage2_computer_readable import extract_features

parser = argparse.ArgumentParser()
parser.add_argument("--train-file", default="data_v2/train.csv")
parser.add_argument("--extra-file", default=None,
                    help="CSV with columns url,label of extra training examples (features are computed here)")
parser.add_argument("--suffix", required=True)
parser.add_argument("--out-dir", default="models_v2")
args = parser.parse_args()

for path in (args.train_file, args.extra_file):
    if path and "test" in os.path.basename(path).lower():
        raise SystemExit(f"Refusing to read {path}: no test files here.")
recipe_path = f"{args.out_dir}/feature_recipe_{args.suffix}.joblib"
model_path = f"{args.out_dir}/gradient_boosting_{args.suffix}.joblib"
for p in (recipe_path, model_path):
    if os.path.exists(p):
        raise SystemExit(f"{p} already exists; not overwriting.")

train = pd.read_csv(args.train_file)
num_cols = [c for c in train.columns if c not in ("url", "label")]
if args.extra_file:
    extra = pd.read_csv(args.extra_file)
    feats = pd.DataFrame([extract_features(u) for u in extra["url"].astype(str)])[num_cols]
    extra = pd.concat([extra[["url"]].reset_index(drop=True), feats, extra[["label"]].reset_index(drop=True)], axis=1)
    print(f"Extra examples: {len(extra):,} (phishing {int(extra['label'].sum()):,}, safe {int((extra['label'] == 0).sum()):,})")
    train = pd.concat([train, extra], ignore_index=True)
print(f"Training rows: {len(train):,} (phishing share {train['label'].mean():.4f})")

vec = CountVectorizer(analyzer="char", ngram_range=(3, 3), max_features=1000,
                      binary=True, lowercase=True, dtype=np.float32)
G_train = vec.fit_transform(train["url"].astype(str)).toarray()
scaler = StandardScaler().fit(train[num_cols])
X_train = np.hstack([scaler.transform(train[num_cols]), G_train])
print("Feature matrix:", X_train.shape)

model = HistGradientBoostingClassifier(max_iter=300, class_weight="balanced", random_state=42)
model.fit(X_train, train["label"])

os.makedirs(args.out_dir, exist_ok=True)
joblib.dump({"vectorizer": vec, "scaler": scaler, "num_cols": num_cols}, recipe_path)
joblib.dump(model, model_path)
print(f"Saved {recipe_path} and {model_path}")
