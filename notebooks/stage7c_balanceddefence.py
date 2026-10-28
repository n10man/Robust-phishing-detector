import os
import random
import re
from collections import Counter
import joblib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.ensemble import HistGradientBoostingClassifier
from stage2_computer_readable import extract_features
from attacks import FAMILIES, apply_family, load_benign_words, split_url, _split_path

# Develop on VALIDATION. Switch to "test" ONCE at the very end, and change nothing after that.
EVAL_SET = "test"
THRESHOLD = 0.5
P_EDIT = 0.6      # share of training URLs, in EACH class, that get an edited copy

train = pd.read_csv("data/train.csv")
val = pd.read_csv("data/val.csv")
evalset = val if EVAL_SET == "val" else pd.read_csv("data/test.csv")
print("Evaluating on:", EVAL_SET)

recipe = joblib.load("models/feature_recipe.joblib")
vec, scaler, num_cols = recipe["vectorizer"], recipe["scaler"], recipe["num_cols"]

def featurise(urls):
    feats = pd.DataFrame([extract_features(u) for u in urls])[num_cols]
    return np.hstack([scaler.transform(feats), vec.transform(urls).toarray()])

# 1. Same A / B word split as before. Everything in all_words[20:] stays held out.
all_words = load_benign_words()
A = all_words[:20]
B = [w for w in all_words[20:] if not any(a in w or w in a for a in A)]
held_out = set(all_words[20:])
print("Held-out list B:", B)

def clashes_with_B(w):
    return any(b in w or w in b for b in B)

safe_tr_s = train.loc[train["label"] == 0, "url"].astype(str).sample(50000, random_state=1)
phish_tr_s = train.loc[train["label"] == 1, "url"].astype(str).sample(20000, random_state=1)

def token_counts(urls):
    c = Counter()
    for u in urls:
        c.update(set(re.findall(r"[a-z]{4,10}", u.lower())))
    return c

cs, cp = token_counts(safe_tr_s), token_counts(phish_tr_s)
candidates = [w for w, _ in cs.most_common(1500) if cs[w] / 50000 > 3 * (cp[w] + 1) / 20000]
VOCAB = [w for w in candidates if w not in held_out and not clashes_with_B(w)][:300]
print(f"Training vocabulary: {len(VOCAB)} words\n")

# 2. Ways to add harmless words (path, query, or both; NOT fragment, which stays held out)
KEYS = ["utm", "id", "q", "page", "cat", "tag", "from", "s", "lang", "view"]   # no ref/src

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

TRAIN_PLACES = ["path", "query", "path_query"]

def varied(url, rng):
    words = rng.sample(VOCAB, rng.randint(1, 4))
    where = rng.choice(TRAIN_PLACES)
    if where == "path":
        return add_path(url, words)
    if where == "query":
        return add_query(url, words, rng)
    k = max(1, len(words) // 2)
    return add_query(add_path(url, words[:k]), words[k:] or words[:1], rng)

def random_edit(url, rng):
    if rng.random() < 0.6:
        return varied(url, rng)
    fam = rng.choice(["extra_subdomains", "path_shortening", "padding", "lookalike_characters"])
    return FAMILIES[fam](url, rng, A)

# 3. Edited copies of TRAINING URLs, at the SAME rate for phishing and safe, each keeping its own label
rng = random.Random(21)

def make_copies(urls):
    out = []
    for u in urls:
        if rng.random() < P_EDIT:
            e = random_edit(u, rng)
            if e != u:
                out.append(e)
    return list(dict.fromkeys(out))

phish_tr = train.loc[train["label"] == 1, "url"].astype(str).tolist()
safe_tr = train.loc[train["label"] == 0, "url"].astype(str).tolist()
aug_p, aug_s = make_copies(phish_tr), make_copies(safe_tr)
print(f"Edited copies: {len(aug_p)} phishing, {len(aug_s)} safe")
print(f"Share of training rows that are edited: phishing {len(aug_p) / (len(phish_tr) + len(aug_p)):.2f}, "
      f"safe {len(aug_s) / (len(safe_tr) + len(aug_s)):.2f}")
print("Phishing examples:", *rng.sample(aug_p, 3), sep="\n   ")
print("Safe examples:", *rng.sample(aug_s, 3), sep="\n   ")

# 4. Retrain with the SAME settings as before
X_clean = np.hstack([scaler.transform(train[num_cols]),
                     vec.transform(train["url"].astype(str)).toarray()])
X_aug = featurise(aug_p + aug_s)
X_all = np.vstack([X_clean, X_aug])
del X_clean, X_aug
y_all = np.r_[train["label"].to_numpy(), np.ones(len(aug_p), dtype=int), np.zeros(len(aug_s), dtype=int)]
print("\nTraining set:", X_all.shape)
round3 = HistGradientBoostingClassifier(max_iter=300, class_weight="balanced", random_state=42)
round3.fit(X_all, y_all)
joblib.dump(round3, "models/gradient_boosting_defended3.joblib")
del X_all

models = {"original": joblib.load("models/gradient_boosting.joblib")}
if os.path.exists("models/gradient_boosting_defended2.joblib"):
    models["round2"] = joblib.load("models/gradient_boosting_defended2.joblib")
models["round3"] = round3

# 5. Matched thresholds, chosen on VALIDATION safe URLs (same clean false-alarm rate as the original at 0.5)
safe_val = val.loc[val["label"] == 0, "url"].astype(str).tolist()
Xsv = featurise(safe_val)
fpr0 = float((models["original"].predict_proba(Xsv)[:, 1] >= THRESHOLD).mean())
thr = {"original": THRESHOLD}
for n, m in models.items():
    if n != "original":
        thr[n] = float(np.quantile(m.predict_proba(Xsv)[:, 1], 1 - fpr0))
print("Matched thresholds:", {k: round(v, 3) for k, v in thr.items()})

# 6. Attacked evaluation sets: the same edits go on phishing URLs AND on safe URLs
phish_ev = evalset.loc[evalset["label"] == 1, "url"].astype(str).tolist()
safe_ev = evalset.loc[evalset["label"] == 0, "url"].astype(str).tolist()
safe_small = random.Random(5).sample(safe_ev, 15000)

def make_sets(urls):
    s = {"none (clean)": urls}
    for name in FAMILIES:
        s[name] = apply_family(urls, name, all_words, seed=42)
    s["HELD-OUT A: query + list B words"] = apply_family(urls, "benign_words_in_query", B, seed=42)
    r = random.Random(99)
    s["HELD-OUT B: fragment + list B words"] = [add_fragment(u, r.sample(B, 2)) for u in urls]
    return s

def probs_for(sets):
    out = {}
    for fam, urls in sets.items():
        X = featurise(urls)
        out[fam] = {n: m.predict_proba(X)[:, 1] for n, m in models.items()}
    return out

phish_sets, safe_sets = make_sets(phish_ev), make_sets(safe_small)
P_ph, P_sf = probs_for(phish_sets), probs_for(safe_sets)

seen = {"none (clean)": "-",
        "benign_words_in_path": "placement yes, half the words new",
        "benign_words_in_query": "placement yes, half the words new, keys new",
        "lookalike_characters": "yes", "extra_subdomains": "yes", "path_shortening": "yes",
        "padding": "yes", "random_mix": "partly",
        "HELD-OUT A: query + list B words": "words NO, keys NO",
        "HELD-OUT B: fragment + list B words": "words NO, placement NO"}

rows = []
for fam in phish_sets:
    row = {"family": fam, "trained_on_it": seen[fam]}
    for n in models:
        row[f"{n}_recall"] = round(float((P_ph[fam][n] >= thr[n]).mean()), 4)
        row[f"{n}_safe_flagged"] = round(float((P_sf[fam][n] >= thr[n]).mean()), 4)
    rows.append(row)
table = pd.DataFrame(rows)
print(f"\nRESULTS ON {EVAL_SET.upper()} (recall = share of phishing caught, higher is better;")
print("safe_flagged = share of SAFE URLs wrongly flagged after the same edit, lower is better;")
print("the defended models use their matched thresholds, the original uses 0.5)\n")
print(table.to_string(index=False))

# 7. Clean evaluation on the full sets
p_sf_full = {n: m.predict_proba(featurise(safe_ev))[:, 1] for n, m in models.items()}

def clean_metrics(p_ph, p_sf, t):
    tp = int((p_ph >= t).sum())
    fp = int((p_sf >= t).sum())
    rec = tp / len(p_ph)
    prec = tp / (tp + fp) if tp + fp else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    return rec, prec, f1, len(p_ph) - tp, fp

clean_rows = []
for n in models:
    for label, t in [("0.5", THRESHOLD), ("matched", thr[n])]:
        if n == "original" and label == "matched":
            continue
        rec, prec, f1, fn, fp = clean_metrics(P_ph["none (clean)"][n], p_sf_full[n], t)
        clean_rows.append({"model": n, "threshold": f"{label} ({t:.3f})", "recall": round(rec, 4),
                           "precision": round(prec, 4), "f1": round(f1, 4),
                           "missed": fn, "false_alarms": fp})
clean_table = pd.DataFrame(clean_rows)
print(f"\nCLEAN {EVAL_SET.upper()} SET, all models")
print("Sanity check: original must show recall 0.9462, precision 0.8803, 868 missed, 2076 false alarms on test")
print("(on validation: recall 0.949, precision 0.877)\n")
print(clean_table.to_string(index=False))

os.makedirs("results", exist_ok=True)
table.to_csv(f"results/defence_round3_{EVAL_SET}.csv", index=False)
clean_table.to_csv(f"results/defence_round3_clean_{EVAL_SET}.csv", index=False)

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5.5), sharey=True)
y = np.arange(len(table))[::-1]
h = 0.8 / len(models)
for i, n in enumerate(models):
    off = (i - (len(models) - 1) / 2) * h
    ax1.barh(y + off, table[f"{n}_recall"], height=h, label=n)
    ax2.barh(y + off, table[f"{n}_safe_flagged"], height=h, label=n)
ax1.set_yticks(y)
ax1.set_yticklabels(table["family"])
ax1.set_xlabel("Recall on phishing URLs (higher is better)")
ax2.set_xlabel("Share of SAFE URLs wrongly flagged (lower is better)")
ax1.legend()
plt.savefig(f"results/defence_round3_{EVAL_SET}.png", dpi=150, bbox_inches="tight")
plt.close()
print("\nSaved to results/ and models/")