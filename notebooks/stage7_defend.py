import os
import random
import joblib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.ensemble import HistGradientBoostingClassifier
from stage2_computer_readable import extract_features
from attacks import FAMILIES, apply_family, load_benign_words

THRESHOLD = 0.5

train = pd.read_csv("data/train.csv")
test = pd.read_csv("data/test.csv")
recipe = joblib.load("models/feature_recipe.joblib")
vec, scaler, num_cols = recipe["vectorizer"], recipe["scaler"], recipe["num_cols"]
original = joblib.load("models/gradient_boosting.joblib")

def featurise(urls):
    feats = pd.DataFrame([extract_features(u) for u in urls])[num_cols]
    return np.hstack([scaler.transform(feats), vec.transform(urls).toarray()])

# 1. Split the harmless words into list A (used for training) and list B (held out).
#    Words in B that contain, or sit inside, an A word are dropped (e.g. article/articles).
all_words = load_benign_words()
A = all_words[:20]
B = [w for w in all_words[20:] if not any(a in w or w in a for a in A)]
print("List A (training):", A)
print("List B (held out):", B, "\n")

# 2. Build attacked copies of TRAINING phishing URLs (never test URLs)
phish_train = train.loc[train["label"] == 1, "url"].astype(str).tolist()
rng = random.Random(7)

def make_copies(urls, family, seed):
    out = apply_family(urls, family, A, seed=seed)
    kept = [a for a, o in zip(out, urls) if a != o]      # keep only URLs that really changed
    print(f"  {family}: {len(kept)} altered copies from {len(urls)} URLs")
    return kept

print("Altered training copies:")
aug = make_copies(phish_train, "benign_words_in_path", 101)     # the main weakness: every phishing URL
for k, fam in enumerate(["extra_subdomains", "path_shortening", "padding", "lookalike_characters"]):
    aug += make_copies(rng.sample(phish_train, len(phish_train) // 4), fam, 102 + k)
aug = list(dict.fromkeys(aug))
print(f"Total altered copies: {len(aug)}\n")

# 3. Retrain with the SAME settings as before, on clean + altered data (altered copies are labelled phishing)
X_clean = np.hstack([scaler.transform(train[num_cols]),
                     vec.transform(train["url"].astype(str)).toarray()])
X_all = np.vstack([X_clean, featurise(aug)])
y_all = np.r_[train["label"].to_numpy(), np.ones(len(aug), dtype=int)]
print("Training set:", X_all.shape)

defended = HistGradientBoostingClassifier(max_iter=300, class_weight="balanced", random_state=42)
defended.fit(X_all, y_all)
joblib.dump(defended, "models/gradient_boosting_defended.joblib")

# 4. Test both models on the SAME attacked test URLs
phish_test = test.loc[test["label"] == 1, "url"].astype(str).tolist()
safe_test = test.loc[test["label"] == 0, "url"].astype(str).tolist()
X_safe = featurise(safe_test)
p_safe = {"before": original.predict_proba(X_safe)[:, 1], "after": defended.predict_proba(X_safe)[:, 1]}

sets = {"none (clean)": phish_test}
for name in FAMILIES:                                       # same attacks and seed as Stage 6
    sets[name] = apply_family(phish_test, name, all_words, seed=42)
sets["HELD-OUT: query + list B words"] = apply_family(phish_test, "benign_words_in_query", B, seed=42)

seen = {"none (clean)": "-", "benign_words_in_path": "partly", "benign_words_in_query": "partly",
        "lookalike_characters": "yes", "extra_subdomains": "yes", "path_shortening": "yes",
        "padding": "yes", "random_mix": "partly", "HELD-OUT: query + list B words": "NO"}

def metrics(p_phish, p_safe_):
    tp = int((p_phish >= THRESHOLD).sum())
    fn = len(p_phish) - tp
    fp = int((p_safe_ >= THRESHOLD).sum())
    recall = tp / len(p_phish)
    precision = tp / (tp + fp)
    return recall, precision, 2 * precision * recall / (precision + recall), fn, fp

rows = []
for name, urls in sets.items():
    X = featurise(urls)
    r0 = metrics(original.predict_proba(X)[:, 1], p_safe["before"])
    r1 = metrics(defended.predict_proba(X)[:, 1], p_safe["after"])
    rows.append({"family": name, "in_training": seen[name],
                 "recall_before": round(r0[0], 4), "recall_after": round(r1[0], 4),
                 "precision_before": round(r0[1], 4), "precision_after": round(r1[1], 4),
                 "f1_before": round(r0[2], 4), "f1_after": round(r1[2], 4),
                 "missed_before": r0[3], "missed_after": r1[3],
                 "false_alarms_before": r0[4], "false_alarms_after": r1[4]})

table = pd.DataFrame(rows)
print("\nSanity check: the first row's 'before' columns should show recall 0.9462, 868 missed, 2076 false alarms\n")
print(table.to_string(index=False))

os.makedirs("results", exist_ok=True)
table.to_csv("results/defence_results_test.csv", index=False)

y = np.arange(len(table))[::-1]
plt.figure(figsize=(9, 5.5))
plt.barh(y + 0.2, table["recall_before"], height=0.4, label="before defence")
plt.barh(y - 0.2, table["recall_after"], height=0.4, label="after defence")
plt.yticks(y, table["family"])
plt.xlabel("Recall on test-set phishing URLs")
plt.title("Recall under attack, before vs after defence")
plt.legend()
plt.savefig("results/defence_recall.png", dpi=150, bbox_inches="tight")
plt.close()
print("\nSaved to results/ and models/")