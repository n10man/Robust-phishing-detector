import os
import joblib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.metrics import precision_score, recall_score, f1_score
from stage2_computer_readable import extract_features
from attacks import FAMILIES, apply_family, load_benign_words

THRESHOLD = 0.5

test = pd.read_csv("data/test.csv")
recipe = joblib.load("models/feature_recipe.joblib")
vec, scaler, num_cols = recipe["vectorizer"], recipe["scaler"], recipe["num_cols"]
model = joblib.load("models/gradient_boosting.joblib")
benign = load_benign_words()
print("Benign words used:", benign[:15], "...")

def score(urls):
    feats = pd.DataFrame([extract_features(u) for u in urls])[num_cols]
    X = np.hstack([scaler.transform(feats), vec.transform(urls).toarray()])
    return model.predict_proba(X)[:, 1]

phish = test.loc[test["label"] == 1, "url"].astype(str).tolist()
safe = test.loc[test["label"] == 0, "url"].astype(str).tolist()
safe_prob = score(safe)                       # safe URLs are never attacked
print(f"Test set: {len(phish)} phishing, {len(safe)} safe\n")

def evaluate(name, phish_prob, changed):
    y_true = np.r_[np.ones(len(phish_prob)), np.zeros(len(safe_prob))]
    y_pred = (np.r_[phish_prob, safe_prob] >= THRESHOLD).astype(int)
    caught = phish_prob >= THRESHOLD
    return {
        "family": name,
        "urls_changed": round(float(changed.mean()), 3),
        "recall": round(recall_score(y_true, y_pred), 4),
        "precision": round(precision_score(y_true, y_pred), 4),
        "f1": round(f1_score(y_true, y_pred), 4),
        "missed_phish": int((~caught).sum()),
        "recall_on_changed": round(float(caught[changed].mean()), 4) if changed.any() else np.nan,
    }

rows = [evaluate("none (before attack)", score(phish), np.zeros(len(phish), dtype=bool))]
print("Sanity check, should match Stage 4 (recall 0.9462, precision 0.8803):")
print(rows[0], "\n")

for name in FAMILIES:
    attacked = apply_family(phish, name, benign, seed=42)
    changed = np.array([a != o for a, o in zip(attacked, phish)])
    rows.append(evaluate(name, score(attacked), changed))
    i = int(np.argmax(changed))               # first URL that was actually changed
    print(f"[{name}]")
    print("   before:", phish[i][:100])
    print("   after: ", attacked[i][:120], "\n")

table = pd.DataFrame(rows)
print(table.to_string(index=False))

os.makedirs("results", exist_ok=True)
table.to_csv("results/attack_families_test.csv", index=False)

plt.figure(figsize=(8, 4.5))
plt.barh(table["family"][::-1], table["recall"][::-1])
plt.axvline(rows[0]["recall"], color="grey", linestyle="--", label="before attack")
plt.xlabel("Recall on test-set phishing URLs")
plt.title("Recall by attack family")
plt.legend()
plt.savefig("results/attack_families_recall.png", dpi=150, bbox_inches="tight")
plt.close()
print("\nSaved to results/")