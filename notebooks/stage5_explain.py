import joblib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.inspection import permutation_importance

val = pd.read_csv("data/val.csv")

# Reuse the saved recipe and model (nothing is retrained here)
recipe = joblib.load("models/feature_recipe.joblib")
vec, scaler, num_cols = recipe["vectorizer"], recipe["scaler"], recipe["num_cols"]
model = joblib.load("models/gradient_boosting.joblib")

# A 5,000-URL validation sample keeps this fast. The test set is not used.
sample = val.sample(5000, random_state=42)
chunks = vec.transform(sample["url"].astype(str)).toarray()
X = np.hstack([scaler.transform(sample[num_cols]), chunks])
y = sample["label"]
names = list(num_cols) + [f"chunk: '{c}'" for c in vec.get_feature_names_out()]

result = permutation_importance(model, X, y, scoring="f1",
                                n_repeats=3, random_state=42, n_jobs=1)

imp = pd.DataFrame({"feature": names, "importance": result.importances_mean})
imp = imp.sort_values("importance", ascending=False)

print("Top 20 features (drop in F1 when shuffled):")
print(imp.head(20).round(4).to_string(index=False))
print("\nOriginal 11 features only:")
print(imp[~imp["feature"].str.startswith("chunk")].round(4).to_string(index=False))

imp.to_csv("results/feature_importance.csv", index=False)

top = imp.head(20).iloc[::-1]
plt.figure(figsize=(7, 6))
plt.barh(top["feature"], top["importance"])
plt.xlabel("Drop in F1 when feature is shuffled")
plt.title("Top 20 features (validation sample)")
plt.savefig("results/feature_importance.png", dpi=150, bbox_inches="tight")
plt.close()
print("\nSaved to results/")