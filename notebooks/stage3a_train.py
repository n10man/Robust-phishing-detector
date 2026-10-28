import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.dummy import DummyClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import precision_score, recall_score, f1_score

df = pd.read_csv("data/features.csv")
X = df.drop(columns=["url", "label"])
y = df["label"]

# 70% train / 15% validation / 15% test, keeping the 78/22 class balance in each
X_train, X_temp, y_train, y_temp, u_train, u_temp = train_test_split(
    X, y, df["url"], test_size=0.30, stratify=y, random_state=42)
X_val, X_test, y_val, y_test, u_val, u_test = train_test_split(
    X_temp, y_temp, u_temp, test_size=0.50, stratify=y_temp, random_state=42)

# Leakage check: no URL may appear in two splits
assert set(u_train).isdisjoint(u_val) and set(u_train).isdisjoint(u_test) and set(u_val).isdisjoint(u_test)
print("Sizes:", len(X_train), len(X_val), len(X_test))

# Save the splits so every later stage uses exactly the same ones
for name, Xs, ys, us in [("train", X_train, y_train, u_train),
                         ("val", X_val, y_val, u_val),
                         ("test", X_test, y_test, u_test)]:
    out = Xs.copy()
    out.insert(0, "url", us.values)
    out["label"] = ys.values
    out.to_csv(f"data/{name}.csv", index=False)

models = {
    "baseline (always 'good')": DummyClassifier(strategy="most_frequent"),
    "logistic regression": make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000)),
    "random forest": RandomForestClassifier(n_estimators=100, n_jobs=-1, random_state=42),
    "gradient boosting": HistGradientBoostingClassifier(random_state=42),
}

rows = []
for name, model in models.items():
    model.fit(X_train, y_train)
    for split, Xs, ys in [("train", X_train, y_train), ("validation", X_val, y_val)]:
        pred = model.predict(Xs)
        rows.append({
            "model": name, "split": split,
            "precision": precision_score(ys, pred, zero_division=0),
            "recall": recall_score(ys, pred),
            "f1": f1_score(ys, pred),
        })

print(pd.DataFrame(rows).round(3).to_string(index=False))