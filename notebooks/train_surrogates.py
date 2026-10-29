"""Chunk 4, Experiment 10: train the two SURROGATE models (what an attacker could build without our model).

Both are trained on a random half of data_v2/train_redacted.csv (sample(frac=0.5, random_state=42)) with the
BASE recipe spec (11 numeric clues + 1,000 whole-URL 3-grams, no host block), REFITTED on that half.
  s1 = LogisticRegression(max_iter=300, class_weight="balanced")
  s2 = HistGradientBoostingClassifier(max_iter=50, class_weight="balanced", random_state=42)
Files (never overwritten): models_v2/feature_recipe_surr.joblib, models_v2/logreg_surr_s1.joblib,
models_v2/gradient_boosting_surr_s2.joblib.

    PYTHONHASHSEED=0 .venv/bin/python notebooks/train_surrogates.py
"""
import os
import time
import joblib
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
import features_v2 as fv

TRAIN = "data_v2/train_redacted.csv"
paths = {"recipe": "models_v2/feature_recipe_surr.joblib", "s1": "models_v2/logreg_surr_s1.joblib",
         "s2": "models_v2/gradient_boosting_surr_s2.joblib"}
for p in paths.values():
    if os.path.exists(p):
        raise SystemExit(f"{p} already exists; not overwriting.")

train = pd.read_csv(TRAIN, usecols=["url", "label"])
half = train.sample(frac=0.5, random_state=42)
urls = half["url"].astype(str).tolist()
print(f"Surrogate training half: {len(half):,} rows ({int(half['label'].sum()):,} phishing)")

recipe = fv.fit_recipe(urls, fv.default_spec())
print("Recipe groups beyond the base:", recipe["groups"] or "none", "| columns:", len(recipe["columns"]))
X = fv.featurize(urls, recipe)
print(f"Feature matrix {X.shape}, dtype {X.dtype}, {X.nbytes / 1e9:.1f} GB")

t = time.time()
s1 = LogisticRegression(max_iter=300, class_weight="balanced").fit(X, half["label"])
print(f"s1 logistic regression trained in {time.time() - t:.0f} s (iterations used: {int(s1.n_iter_[0])} of 300)")
t = time.time()
s2 = HistGradientBoostingClassifier(max_iter=50, class_weight="balanced", random_state=42).fit(X, half["label"])
print(f"s2 small gradient boosting trained in {time.time() - t:.0f} s")

joblib.dump(recipe, paths["recipe"])
joblib.dump(s1, paths["s1"])
joblib.dump(s2, paths["s2"])
print("Saved", ", ".join(paths.values()))
