import os
import random
import joblib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from collections import Counter
import re
from sklearn.ensemble import HistGradientBoostingClassifier
from stage2_computer_readable import extract_features
from attacks import FAMILIES, apply_family, load_benign_words, split_url, _split_path

THRESHOLD = 0.5

train = pd.read_csv("data/train.csv")
val = pd.read_csv("data/val.csv")
test = pd.read_csv("data/test.csv")
recipe = joblib.load("models/feature_recipe.joblib")
vec, scaler, num_cols = recipe["vectorizer"], recipe["scaler"], recipe["num_cols"]

def featurise(urls):
    feats = pd.DataFrame([extract_features(u) for u in urls])[num_cols]
    return np.hstack([scaler.transform(feats), vec.transform(urls).toarray()])

# 1. Same A / B split as Stage 7 (B stays held out, exactly as before)
all_words = load_benign_words()
A = all_words[:20]
B = [w for w in all_words[20:] if not any(a in w or w in a for a in A)]
held_out = set(all_words[20:])
print("Held-out list B:", B)

# 2. Build a MUCH bigger training vocabulary of harmless words (training data only),
#    excluding every held-out word and anything that contains or sits inside one
def clashes_with_B(w):
    return any(b in w or w in b for b in B)

safe_tr = train.loc[train["label"] == 0, "url"].astype(str).sample(50000, random_state=1)
phish_tr = train.loc[train["label"] == 1, "url"].astype(str).sample(20000, random_state=1)

def token_counts(urls):
    c = Counter()
    for u in urls:
        c.update(set(re.findall(r"[a-z]{4,10}", u.lower())))
    return c

cs, cp = token_counts(safe_tr), token_counts(phish_tr)
candidates = [w for w, _ in cs.most_common(1500) if cs[w] / 50000 > 3 * (cp[w] + 1) / 20000]
VOCAB = [w for w in candidates if w not in held_out and not clashes_with_B(w)][:300]
print(f"Training vocabulary: {len(VOCAB)} words, e.g. {VOCAB[:15]}\n")

# 3. A more varied way to add harmless words: random count (1-4), random placement
KEYS = ["ref", "src", "utm", "id", "q", "page", "cat", "tag", "from", "s"]

def add_path(url, words):
    s, h, p = split_url(url)
    pre, tail = _split_path(p)
    return s + h + pre.rstrip("/") + "/" + "/".join(words) + tail

def add_query(url, words, rng):
    if "#" in url:
        base, frag = url.split("#", 1)
        frag = "#" + frag
    else:
        base, frag = url, ""
    sep = "&" if "?" in base else "?"
    keys = rng.sample(KEYS, len(words))
    return base + sep + "&".join(f"{k}={w}" for k, w in zip(keys, words)) + frag

def add_fragment(url, words):
    return url + ("/" if "#" in url else "#") + "-".join(words)

TRAIN_PLACES = ["path", "query", "path_query"]     # "fragment" is deliberately NOT used in training

def varied(url, rng, vocab, places):
    words = rng.sample(vocab, rng.randint(1, 4))
    where = rng.choice(places)
    if where == "path":
        return add_path(url, words)
    if where == "query":
        return add_query(url, words, rng)
    if where == "fragment":
        return add_fragment(url, words)
    k = max(1, len(words) // 2)
    return add_query(add_path(url, words[:k]), words[k:] or words[:1], rng)

# 4. Build altered copies of TRAINING phishing URLs only
phish_train = train.loc[train["label"] == 1, "url"].astype(str).tolist()
rng = random.Random(11)
aug = [varied(u, rng, VOCAB, TRAIN_PLACES) for u in phish_train]
aug += [varied(u, rng, VOCAB, TRAIN_PLACES) for u in rng.sample(phish_train, len(phish_train) // 2)]
for k, fam in enumerate(["extra_subdomains", "path_shortening", "padding", "lookalike_characters"]):
    sub = rng.sample(phish_train, len(phish_train) // 4)
    out = apply_family(sub, fam, A, seed=102 + k)
    aug += [a for a, o in zip(out, sub) if a != o]
aug = list(dict.fromkeys(aug))
print(f"Altered training copies: {len(aug)}")
print("Examples:", *rng.sample(aug, 4), sep="\n   ")

# 5. Retrain with the SAME settings as before
X_clean = np.hstack([scaler.transform(train[num_cols]),
                     vec.transform(train["url"].astype(str)).toarray()])
X_all = np.vstack([X_clean, featurise(aug)])
y_all = np.r_[train["label"].to_numpy(), np.ones(len(aug), dtype=int)]
print("\nTraining set:", X_all.shape)
round2 = HistGradientBoostingClassifier(max_iter=300, class_weight="balanced", random_state=42)
round2.fit(X_all, y_all)
joblib.dump(round2, "models/gradient_boosting_defended2.joblib")

models = {"original": joblib.load("models/gradient_boosting.joblib")}
if os.path.exists("models/gradient_boosting_defended.joblib"):
    models["round1"] = joblib.load("models/gradient_boosting_defended.joblib")
models["round2"] = round2

# 6. Fair comparison: for each defended model, pick the threshold on VALIDATION safe URLs
#    that gives the same false-alarm rate the original model has at 0.5 (test set not used for this)
safe_val = val.loc[val["label"] == 0, "url"].astype(str).tolist()
Xsv = featurise(safe_val)
fpr0 = float((models["original"].predict_proba(Xsv)[:, 1] >= THRESHOLD).mean())
thr = {"original": THRESHOLD}
for n, m in models.items():
    if n != "original":
        thr[n] = float(np.quantile(m.predict_proba(Xsv)[:, 1], 1 - fpr0))
print("\nMatched thresholds (chosen on validation):", {k: round(v, 3) for k, v in thr.items()})

# 7. Attacked TEST sets (same attacks and seeds as Stage 6 / 7, plus two held-out sets)
phish_test = test.loc[test["label"] == 1, "url"].astype(str).tolist()
safe_test = test.loc[test["label"] == 0, "url"].astype(str).tolist()
sets = {"none (clean)": phish_test}
for name in FAMILIES:
    sets[name] = apply_family(phish_test, name, all_words, seed=42)
sets["HELD-OUT A: query + list B words"] = apply_family(phish_test, "benign_words_in_query", B, seed=42)
r2 = random.Random(99)
sets["HELD-OUT B: fragment + list B words"] = [add_fragment(u, r2.sample(B, 2)) for u in phish_test]

seen = {"none (clean)": "-", "benign_words_in_path": "yes (new vocab)", "benign_words_in_query": "yes (new vocab)",
        "lookalike_characters": "yes", "extra_subdomains": "yes", "path_shortening": "yes",
        "padding": "yes", "random_mix": "partly",
        "HELD-OUT A: query + list B words": "words NO",
        "HELD-OUT B: fragment + list B words": "words NO, placement NO"}

X_safe = featurise(safe_test)
P_safe = {n: m.predict_proba(X_safe)[:, 1] for n, m in models.items()}
feat_sets = {n: featurise(u) for n, u in sets.items()}

rows, probs = [], {}
for fam, X in feat_sets.items():
    probs[fam] = {n: m.predict_proba(X)[:, 1] for n, m in models.items()}
    row = {"family": fam, "trained_on_it": seen[fam]}
    for n in models:
        row[f"{n}_recall"] = round(float((probs[fam][n] >= THRESHOLD).mean()), 4)
    for n in models:
        if n != "original":
            row[f"{n}_matched"] = round(float((probs[fam][n] >= thr[n]).mean()), 4)
    rows.append(row)

table = pd.DataFrame(rows)
print("\nRECALL UNDER ATTACK ('matched' = same false-alarm level as the original model)")
print("Sanity check: first row, original_recall must be 0.9462\n")
print(table.to_string(index=False))

def rates(p_phish, p_safe_, t):
    tp = int((p_phish >= t).sum())
    fp = int((p_safe_ >= t).sum())
    rec = tp / len(p_phish)
    prec = tp / (tp + fp) if tp + fp else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    return rec, prec, f1, len(p_phish) - tp, fp

clean_rows = []
for n in models:
    for label, t in [("0.5", THRESHOLD), ("matched", thr[n])]:
        if n == "original" and label == "matched":
            continue
        rec, prec, f1, fn, fp = rates(probs["none (clean)"][n], P_safe[n], t)
        clean_rows.append({"model": n, "threshold": f"{label} ({t:.3f})", "recall": round(rec, 4),
                           "precision": round(prec, 4), "f1": round(f1, 4),
                           "missed": fn, "false_alarms": fp})
clean_table = pd.DataFrame(clean_rows)
print("\nCLEAN TEST SET, all models")
print("Sanity check: original must show recall 0.9462, 868 missed, 2076 false alarms\n")
print(clean_table.to_string(index=False))

os.makedirs("results", exist_ok=True)
table.to_csv("results/defence_round2_recall.csv", index=False)
clean_table.to_csv("results/defence_round2_clean.csv", index=False)

cols = ["original_recall"] + [f"{n}_matched" for n in models if n != "original"]
y = np.arange(len(table))[::-1]
h = 0.8 / len(cols)
plt.figure(figsize=(9.5, 6))
for i, c in enumerate(cols):
    plt.barh(y + (i - (len(cols) - 1) / 2) * h, table[c], height=h, label=c)
plt.yticks(y, table["family"])
plt.xlabel("Recall on test-set phishing URLs")
plt.title("Recall under attack: original vs defended (matched false alarms)")
plt.legend()
plt.savefig("results/defence_round2_recall.png", dpi=150, bbox_inches="tight")
plt.close()
print("\nSaved to results/ and models/")