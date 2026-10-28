import json
import os
import joblib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import (precision_score, recall_score, f1_score, confusion_matrix,
                             roc_auc_score, roc_curve, ConfusionMatrixDisplay)

# Decision cut-off. Only change it based on the VALIDATION sweep printed below.
THRESHOLD = 0.5

train = pd.read_csv("data/train.csv")
val = pd.read_csv("data/val.csv")
test = pd.read_csv("data/test.csv")

# Reuse the saved feature recipe from Stage 3b (same chunk list, same scaler)
recipe = joblib.load("models/feature_recipe.joblib")
vec, scaler, num_cols = recipe["vectorizer"], recipe["scaler"], recipe["num_cols"]

def build(df):
    chunks = vec.transform(df["url"].astype(str)).toarray()
    return np.hstack([scaler.transform(df[num_cols]), chunks])

X_train, y_train = build(train), train["label"]
X_val, y_val = build(val), val["label"]
X_test, y_test = build(test), test["label"]

# 1. Retrain gradient boosting with the SAME settings as Stage 3b, then save it
model = HistGradientBoostingClassifier(max_iter=300, class_weight="balanced", random_state=42)
model.fit(X_train, y_train)
joblib.dump(model, "models/gradient_boosting.joblib")

# 2. Threshold sweep on VALIDATION (the test set is not used for this)
val_prob = model.predict_proba(X_val)[:, 1]
rows = []
for t in [0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]:
    pred = (val_prob >= t).astype(int)
    rows.append({"threshold": t,
                 "precision": precision_score(y_val, pred),
                 "recall": recall_score(y_val, pred),
                 "f1": f1_score(y_val, pred)})
print("Validation threshold sweep")
print(pd.DataFrame(rows).round(3).to_string(index=False))

# 3. The one-time TEST evaluation
test_prob = model.predict_proba(X_test)[:, 1]
test_pred = (test_prob >= THRESHOLD).astype(int)
tn, fp, fn, tp = confusion_matrix(y_test, test_pred).ravel()

metrics = {
    "threshold": THRESHOLD,
    "precision": float(precision_score(y_test, test_pred)),
    "recall": float(recall_score(y_test, test_pred)),
    "f1": float(f1_score(y_test, test_pred)),
    "roc_auc": float(roc_auc_score(y_test, test_prob)),
    "true_positives": int(tp), "false_negatives": int(fn),
    "false_positives": int(fp), "true_negatives": int(tn),
}
print("\nTEST SET RESULTS (threshold =", THRESHOLD, ")")
for k, v in metrics.items():
    print(f"  {k}: {round(v, 4) if isinstance(v, float) else v}")

# 4. Save the numbers and the two charts for the README
os.makedirs("results", exist_ok=True)
with open("results/test_metrics_clean.json", "w") as f:
    json.dump(metrics, f, indent=2)

ConfusionMatrixDisplay(confusion_matrix(y_test, test_pred),
                       display_labels=["safe", "phishing"]).plot(values_format="d")
plt.title("Confusion matrix (test set)")
plt.savefig("results/confusion_matrix_clean.png", dpi=150, bbox_inches="tight")
plt.close()

fpr, tpr, _ = roc_curve(y_test, test_prob)
plt.plot(fpr, tpr, label=f"AUC = {metrics['roc_auc']:.3f}")
plt.plot([0, 1], [0, 1], "--", color="grey", label="random guessing")
plt.xlabel("False alarm rate")
plt.ylabel("Recall (phishing caught)")
plt.title("ROC curve (test set)")
plt.legend()
plt.savefig("results/roc_curve_clean.png", dpi=150, bbox_inches="tight")
plt.close()
print("\nSaved model to models/ and charts to results/")