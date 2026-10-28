import random
import re
from collections import Counter
import joblib
import numpy as np
import pandas as pd
from stage2_computer_readable import extract_features

random.seed(42)
N_URLS, ROUNDS, CANDIDATES, THRESHOLD = 300, 15, 20, 0.5

recipe = joblib.load("models/feature_recipe.joblib")
vec, scaler, num_cols = recipe["vectorizer"], recipe["scaler"], recipe["num_cols"]
model = joblib.load("models/gradient_boosting.joblib")

def score(urls):
    feats = pd.DataFrame([extract_features(u) for u in urls])[num_cols]
    X = np.hstack([scaler.transform(feats), vec.transform(urls).toarray()])
    return model.predict_proba(X)[:, 1]

# Harmless-looking words, taken from the TRAINING data: common in safe URLs, rare in phishing
train = pd.read_csv("data/train.csv")
safe_urls = train.loc[train["label"] == 0, "url"].sample(50000, random_state=1)
phish_urls = train.loc[train["label"] == 1, "url"].sample(20000, random_state=1)

def token_counts(urls):
    c = Counter()
    for u in urls:
        c.update(set(re.findall(r"[a-z]{4,10}", u.lower())))
    return c

cs, cp = token_counts(safe_urls), token_counts(phish_urls)
BENIGN = [w for w, n in cs.most_common(400) if cs[w] / 50000 > 5 * (cp[w] + 1) / 20000][:40]
print("Benign words used:", BENIGN)

SUBS = ["www", "mail", "blog", "news", "shop", "support", "docs", "cdn"]
LOOK = {"o": "0", "l": "1", "i": "1", "e": "3", "a": "4"}

def split(url):
    host = re.split(r"[/?#]", url, maxsplit=1)[0]
    return host, url[len(host):]

def edit(url):
    """One small edit. The registered domain is never changed."""
    host, path = split(url)
    op = random.choice(["subdomain", "path_word", "padding", "lookalike",
                        "shorten", "digits_to_letters"])
    if op == "subdomain":
        host = random.choice(SUBS) + "." + host
    elif op == "path_word":
        path = path.rstrip("/") + "/" + random.choice(BENIGN)
    elif op == "padding":
        pad = "".join(random.choices("abcdefghijklmnopqrstuvwxyz0123456789", k=random.randint(8, 24)))
        path = path.rstrip("/") + "/" + pad
    elif op == "lookalike":
        idx = [i for i, ch in enumerate(path) if ch in LOOK]
        if idx:
            i = random.choice(idx)
            path = path[:i] + LOOK[path[i]] + path[i + 1:]
    elif op == "shorten":
        segs = [s for s in path.split("/") if s]
        if len(segs) > 1:
            path = "/" + "/".join(segs[:-1])
    elif op == "digits_to_letters":
        path = re.sub(r"\d", lambda m: random.choice("abcdefghij"), path, count=random.randint(1, 5))
    return host + path, op

# Start from validation phishing URLs the model currently catches
val = pd.read_csv("data/val.csv")
pool = val[val["label"] == 1].sample(2000, random_state=3)
p0 = score(list(pool["url"]))
current = list(pool.loc[p0 >= THRESHOLD, "url"].head(N_URLS))
original = current[:]
cur_prob = score(current)
history = [[] for _ in current]
active = list(range(len(current)))
print(f"\nAttacking {len(current)} URLs that the model currently catches\n")

for r in range(1, ROUNDS + 1):
    cands, owner, ops = [], [], []
    for i in active:
        for _ in range(CANDIDATES):
            u, op = edit(current[i])
            cands.append(u); owner.append(i); ops.append(op)
    p = score(cands)
    best = {}
    for k, i in enumerate(owner):
        if p[k] < cur_prob[i] and (i not in best or p[k] < p[best[i]]):
            best[i] = k                      # keep an edit only if it lowers the phishing score
    for i, k in best.items():
        current[i], cur_prob[i] = cands[k], p[k]
        history[i].append(ops[k])
    active = [i for i in active if cur_prob[i] >= THRESHOLD]
    print(f"Round {r}: {np.mean(cur_prob < THRESHOLD):.1%} evade the model, {len(active)} still being attacked")
    if not active:
        break

ev = [i for i in range(len(current)) if cur_prob[i] < THRESHOLD]
print(f"\nEvaded: {len(ev)} of {len(current)} ({len(ev) / len(current):.1%})")
print("Edit types used on evaded URLs:", Counter(op for i in ev for op in history[i]))
if ev:
    print("Average edits needed:", round(np.mean([len(history[i]) for i in ev]), 1))
print("\nExamples:")
for i in ev[:8]:
    print(" before:", original[i][:100])
    print(" after: ", current[i][:140], "\n")

pd.DataFrame({"original": original, "attacked": current, "final_prob": cur_prob,
              "edits": [",".join(h) for h in history]}).to_csv("results/hillclimb_results.csv", index=False)