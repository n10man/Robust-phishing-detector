"""Checks for features_v2.py. Prints counts and shapes only, never a URL.

1. The BASE recipe built by features_v2 reproduces the saved Chunk 2 recipe exactly.
2. featurize() on the old recipe and on the new base recipe gives identical matrices.
3. Every new group runs and has the expected number of columns, no NaN, float64.

Run from the repo root:  PYTHONHASHSEED=0 .venv/bin/python notebooks/check_features_v2.py
"""
import joblib
import numpy as np
import pandas as pd
import features_v2 as fv

train = pd.read_csv("data_v2/train_redacted.csv", usecols=["url", "label"])
val = pd.read_csv("data_v2/val_redacted.csv", usecols=["url", "label"])
old = joblib.load("models_v2/feature_recipe_redacted.joblib")

print("== 1. base recipe vs the saved Chunk 2 recipe")
new = fv.fit_recipe(train["url"].astype(str).tolist(), fv.default_spec())
vocab_same = new["vectorizers"][0].vocabulary_ == old["vectorizer"].vocabulary_
print("   n-gram vocabulary identical:", vocab_same)
print("   scaler mean identical:", bool(np.array_equal(new["scaler"].mean_, old["scaler"].mean_)),
      "| scale identical:", bool(np.array_equal(new["scaler"].scale_, old["scaler"].scale_)))
print("   numeric column names identical:", new["num_cols"] == old["num_cols"])

print("== 2. identical matrices on 5,000 validation rows")
sample = val["url"].astype(str).sample(5000, random_state=42).tolist()
Xo, Xn = fv.featurize(sample, old), fv.featurize(sample, new)
print("   shapes:", Xo.shape, Xn.shape, "| dtypes:", Xo.dtype, Xn.dtype,
      "| exactly equal:", bool(np.array_equal(Xo, Xn)))
assert vocab_same and np.array_equal(Xo, Xn)

print("== 3. each new group on a 3,000-row sample")
small = train["url"].astype(str).sample(3000, random_state=42).tolist()
specs = {
    "host3x500": {"ngram_blocks": [("url", 3, 1000), ("host", 3, 500)], "numeric_groups": [], "brand_n": 0},
    "host3x1000 (replaces url 3-grams)": {"ngram_blocks": [("host", 3, 1000)], "numeric_groups": [], "brand_n": 0},
    "brand300": {"ngram_blocks": [("url", 3, 1000)], "numeric_groups": ["brand"], "brand_n": 300},
    "brand100": {"ngram_blocks": [("url", 3, 1000)], "numeric_groups": ["brand"], "brand_n": 100},
    "chartricks": {"ngram_blocks": [("url", 3, 1000)], "numeric_groups": ["chartricks"], "brand_n": 0},
    "randomness": {"ngram_blocks": [("url", 3, 1000)], "numeric_groups": ["randomness"], "brand_n": 0},
    "url4x1000 (replaces)": {"ngram_blocks": [("url", 4, 1000)], "numeric_groups": [], "brand_n": 0},
    "url3 + url4x2000": {"ngram_blocks": [("url", 3, 1000), ("url", 4, 2000)], "numeric_groups": [], "brand_n": 0},
}
for name, spec in specs.items():
    r = fv.fit_recipe(small, spec)
    X = fv.featurize(small[:500], r)
    tags = sorted(set(r["column_group"]))
    print(f"   {name}: columns {X.shape[1]} (recipe says {len(r['columns'])}) | groups {r['groups']} | tags {tags} "
          f"| dtype {X.dtype} | NaN {int(np.isnan(X).sum())}")
    assert X.shape[1] == len(r["columns"]) and not np.isnan(X).any() and X.dtype == np.float64

print("== 4. raw values of the new numeric groups on the 3,000-row sample (means)")
for g in ["brand", "chartricks", "randomness"]:
    spec = {"ngram_blocks": [("url", 3, 1000)], "numeric_groups": [g], "brand_n": 300 if g == "brand" else 0}
    names = fv.brand_names_from_tranco(300) if g == "brand" else None
    df = fv.numeric_frame(small, spec, names)[fv.GROUP_COLS[g]]
    print("  ", g, {c: round(float(df[c].mean()), 4) for c in df.columns})
print("all checks passed")
