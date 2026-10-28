import os
import joblib
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
from sklearn.metrics import precision_score, recall_score, f1_score

# 1. LOAD the saved splits (the test set stays sealed)
train = pd.read_csv("data/train.csv")
val = pd.read_csv("data/val.csv")
num_cols = [c for c in train.columns if c not in ("url", "label")]

# 2. BUILD the chunk list from TRAINING urls only, then apply it to validation
vec = CountVectorizer(analyzer="char", ngram_range=(3, 3), max_features=1000,
                      binary=True, lowercase=True, dtype=np.float32)
G_train = vec.fit_transform(train["url"].astype(str)).toarray()
G_val = vec.transform(val["url"].astype(str)).toarray()
print("Example chunks:", list(vec.get_feature_names_out()[:15]))

# 3. SCALE the 11 old numeric features (scaler also fitted on training only)
scaler = StandardScaler().fit(train[num_cols])
X_train = np.hstack([scaler.transform(train[num_cols]), G_train])
X_val = np.hstack([scaler.transform(val[num_cols]), G_val])
y_train, y_val = train["label"], val["label"]
print("Feature matrix:", X_train.shape)

# 4. SAVE the recipe so new URLs get exactly the same treatment later
os.makedirs("models", exist_ok=True)
joblib.dump({"vectorizer": vec, "scaler": scaler, "num_cols": num_cols}, "models/feature_recipe.joblib")

# 5. TRAIN: same three models, with a depth limit and balanced class weights
models = {
    "logistic regression": LogisticRegression(max_iter=2000, class_weight="balanced"),
    "random forest": RandomForestClassifier(n_estimators=100, max_depth=25, min_samples_leaf=5,
                                            class_weight="balanced_subsample",
                                            n_jobs=-1, random_state=42),
    "gradient boosting": HistGradientBoostingClassifier(max_iter=300, class_weight="balanced",
                                                        random_state=42),
}

rows = []
for name, model in models.items():
    print("Training", name, "...")
    model.fit(X_train, y_train)
    for split, Xs, ys in [("train", X_train, y_train), ("validation", X_val, y_val)]:
        pred = model.predict(Xs)
        rows.append({"model": name, "split": split,
                     "precision": precision_score(ys, pred),
                     "recall": recall_score(ys, pred),
                     "f1": f1_score(ys, pred)})

print(pd.DataFrame(rows).round(3).to_string(index=False))