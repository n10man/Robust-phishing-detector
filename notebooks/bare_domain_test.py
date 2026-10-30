import random
import joblib
import numpy as np
import pandas as pd
from stage2_computer_readable import extract_features

N_TOP = 10000      # the most popular domains
N_RANDOM = 10000   # a random sample from further down the list

recipe = joblib.load("models/feature_recipe.joblib")
vec, scaler, num_cols = recipe["vectorizer"], recipe["scaler"], recipe["num_cols"]
models = {
    "original (threshold 0.5)": (joblib.load("models/gradient_boosting.joblib"), 0.5),
    "round3 (threshold 0.532)": (joblib.load("models/gradient_boosting_defended3.joblib"), 0.532),
}

def featurise(urls):
    feats = pd.DataFrame([extract_features(u) for u in urls])[num_cols]
    return np.hstack([scaler.transform(feats), vec.transform(urls).toarray()])

# Load the list (handles a file with or without a header row)
t = pd.read_csv("data/tranco_262W9.csv", header=None, names=["rank", "domain"])
t["rank"] = pd.to_numeric(t["rank"], errors="coerce")
t = t.dropna(subset=["rank"])
t["domain"] = t["domain"].astype(str).str.strip().str.lower()
print("Domains in the list:", len(t))

top = t[t["rank"] <= N_TOP]["domain"].tolist()
rest = t[t["rank"] > N_TOP]["domain"].tolist()
sample = random.Random(1).sample(rest, min(N_RANDOM, len(rest)))
groups = {f"top {N_TOP}": top, f"random from the rest ({len(sample)})": sample}

# Drop any domain whose bare form appears exactly in the training data
train_urls = set(pd.read_csv("data/train.csv")["url"].astype(str).str.lower().str.rstrip("/"))
for g in groups:
    before = len(groups[g])
    groups[g] = [d for d in groups[g] if d not in train_urls]
    print(f"{g}: removed {before - len(groups[g])} that also appear in the training data")

forms = {
    "bare (google.com)": lambda d: d,
    "with www (www.google.com)": lambda d: "www." + d,
    "trailing slash (google.com/)": lambda d: d + "/",
    "with a path (google.com/index.html)": lambda d: d + "/index.html",
}

rows = []
for g, domains in groups.items():
    for form_name, f in forms.items():
        X = featurise([f(d) for d in domains])
        row = {"group": g, "form": form_name, "n": len(domains)}
        for m_name, (m, thr) in models.items():
            row[m_name] = round(float((m.predict_proba(X)[:, 1] >= thr).mean()), 4)
        rows.append(row)

table = pd.DataFrame(rows)
print("\nShare of these safe domains flagged as phishing (lower is better):\n")
print(table.to_string(index=False))
table.to_csv("results/bare_domain_test.csv", index=False)
print("\nSaved to results/")