import os
import joblib
import numpy as np
import pandas as pd
import tldextract
from collections import Counter

THRESHOLD = 0.5

val = pd.read_csv("data/val.csv")
recipe = joblib.load("models/feature_recipe.joblib")
vec, scaler, num_cols = recipe["vectorizer"], recipe["scaler"], recipe["num_cols"]
model = joblib.load("models/gradient_boosting.joblib")

X = np.hstack([scaler.transform(val[num_cols]), vec.transform(val["url"].astype(str)).toarray()])
val["prob"] = model.predict_proba(X)[:, 1]

phish = val[val["label"] == 1]
missed = phish[phish["prob"] < THRESHOLD]
caught = phish[phish["prob"] >= THRESHOLD]
print(f"Validation phishing: {len(phish)} | caught: {len(caught)} | missed: {len(missed)}")

# 1. What do the misses look like?
print("\n25 random missed URLs:")
for u in missed["url"].sample(min(25, len(missed)), random_state=1):
    print("  ", u[:110])

# 2. Are the misses structurally different from the caught ones?
print("\nAverage of each feature, missed vs caught phishing:")
print(pd.DataFrame({"missed": missed[num_cols].mean(),
                    "caught": caught[num_cols].mean()}).round(2).to_string())

# 3. Hosting patterns (offline suffix list, no network needed)
extract = tldextract.TLDExtract(suffix_list_urls=())
def parts(urls):
    e = [extract(u) for u in urls]
    return [x.suffix for x in e], [x.registered_domain for x in e]
m_suf, m_dom = parts(missed["url"])
c_suf, c_dom = parts(caught["url"])

def share(lst):
    c, tot = Counter(lst), len(lst)
    return {k: round(c[k] / tot, 3) for k in c}
ms, cs = share(m_suf), share(c_suf)
top = sorted(ms, key=ms.get, reverse=True)[:10]
print("\nDomain endings: share among MISSED vs CAUGHT")
for k in top:
    print(f"  .{k or '(none)'}: {ms[k]} vs {cs.get(k, 0)}")
print("\nMost common domains among MISSED:", Counter(m_dom).most_common(10))

# 4. Which text chunks separate misses from catches?
rate_m = np.asarray(vec.transform(missed["url"].astype(str)).mean(axis=0)).ravel()
rate_c = np.asarray(vec.transform(caught["url"].astype(str)).mean(axis=0)).ravel()
diff = pd.DataFrame({"chunk": vec.get_feature_names_out(), "missed": rate_m, "caught": rate_c})
diff["gap"] = diff["missed"] - diff["caught"]
print("\nChunks more common in MISSED phishing:")
print(diff.sort_values("gap", ascending=False).head(15).round(3).to_string(index=False))
print("\nChunks more common in CAUGHT phishing:")
print(diff.sort_values("gap").head(15).round(3).to_string(index=False))

# 5. Stage 5 results, if they exist
if os.path.exists("results/feature_importance.csv"):
    print("\nTop 15 features by importance (Stage 5):")
    print(pd.read_csv("results/feature_importance.csv").head(15).round(4).to_string(index=False))
else:
    print("\n(Run stage5_explain.py to see feature importance here.)")

os.makedirs("results", exist_ok=True)
missed.to_csv("results/val_missed_phishing.csv", index=False)