import argparse
import re
import joblib
import numpy as np
import pandas as pd
from stage2_computer_readable import extract_features

parser = argparse.ArgumentParser(description="Check whether a URL looks like phishing.")
parser.add_argument("urls", nargs="*", help="one or more URLs (leave empty to type them in)")
parser.add_argument("--defended", action="store_true",
                    help="use the round-3 defended model (threshold about 0.53) instead of the original")
args = parser.parse_args()

# Load the saved feature recipe and model
recipe = joblib.load("models/feature_recipe.joblib")
vec, scaler, num_cols = recipe["vectorizer"], recipe["scaler"], recipe["num_cols"]

if args.defended:
    model = joblib.load("models/gradient_boosting_defended3.joblib")
    THRESHOLD = 0.532          # matched threshold from the Stage 7c test run
else:
    model = joblib.load("models/gradient_boosting.joblib")
    THRESHOLD = 0.5            # the threshold chosen in Stage 4


def tidy(url):
    """Match the training format: the dataset has no http:// or https:// prefix."""
    url = url.strip()
    return re.sub(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", "", url)


def predict(urls):
    urls = [tidy(u) for u in urls]
    feats = pd.DataFrame([extract_features(u) for u in urls])[num_cols]
    X = np.hstack([scaler.transform(feats), vec.transform(urls).toarray()])
    return urls, model.predict_proba(X)[:, 1]


def show(urls):
    cleaned, probs = predict(urls)
    for u, p in zip(cleaned, probs):
        verdict = "PHISHING" if p >= THRESHOLD else "looks safe"
        print(f"{verdict:>10}  (phishing score {p:.2f})  {u[:90]}")


if args.urls:
    show(args.urls)
else:
    print("Type a URL and press Enter (empty line to quit).")
    while True:
        line = input("> ").strip()
        if not line:
            break
        show([line])

print("\nEducational project, not a security tool. It reads the URL text only and never visits the link.")