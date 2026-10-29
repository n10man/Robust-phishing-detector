"""Retrain the UNCHANGED v1 pipeline on the domain-grouped split.

Same recipe as stage3b_added_column.py + stage4_evaluate.py: 11 numeric features scaled,
1,000 binary character 3-grams, HistGradientBoostingClassifier, threshold 0.5.
Everything is fitted on data_v2/train.csv ONLY. Nothing is read from data/ or data_v2/val.csv
or test.csv, and nothing is written to models/.

Run from the repo root:  .venv/bin/python notebooks/train_v2split.py
"""
import os
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.preprocessing import StandardScaler

OUT = "models_v2"

train = pd.read_csv("data_v2/train.csv")
num_cols = [c for c in train.columns if c not in ("url", "label")]

# Chunk list and scaler are fitted on training URLs only
vec = CountVectorizer(analyzer="char", ngram_range=(3, 3), max_features=1000,
                      binary=True, lowercase=True, dtype=np.float32)
G_train = vec.fit_transform(train["url"].astype(str)).toarray()
scaler = StandardScaler().fit(train[num_cols])
X_train = np.hstack([scaler.transform(train[num_cols]), G_train])
y_train = train["label"]
print("Feature matrix:", X_train.shape, "| numeric features:", len(num_cols))

# Same settings as stage3b / stage4
model = HistGradientBoostingClassifier(max_iter=300, class_weight="balanced", random_state=42)
model.fit(X_train, y_train)

os.makedirs(OUT, exist_ok=True)
joblib.dump({"vectorizer": vec, "scaler": scaler, "num_cols": num_cols}, f"{OUT}/feature_recipe.joblib")
joblib.dump(model, f"{OUT}/gradient_boosting.joblib")
print(f"Saved the recipe and the model to {OUT}/ (models/ was not touched)")
