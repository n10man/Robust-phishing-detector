"""Chunk 5: score the validation sets ONCE per model and cache them (VALIDATION DATA ONLY).

For one model it scores, for the full URL and for the two trimmed copies (see defence_layers.py):
  clean validation phishing and safe, the 7 attack families on validation phishing and on the same 15,000-URL
  safe sample evaluate.py uses (same harmless words, seed 42, random.Random(5) sample), and the held-out bare sets.
Gate: the plain-model numbers recomputed from the cache must equal the saved evaluate.py results of that model
(recall, AUC, 7 attack recalls, edited-safe flag shares) to 4 decimals, or the script stops without saving.

    PYTHONHASHSEED=0 .venv/bin/python notebooks/defence_scores.py --tag 4a
    PYTHONHASHSEED=0 .venv/bin/python notebooks/defence_scores.py --tag 8b

build_sets() is also imported by the experiment scripts. Prints no URLs.
"""
import argparse
import json
import os
import random
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
from attacks import FAMILIES, apply_family, load_benign_words
import defence_layers as dl

VAL, TRAIN = "data_v2/val_redacted.csv", "data_v2/train_redacted.csv"
HELD_SAFE, HELD_PHISH = "data_v2/bare_heldout_safe.csv", "data_v2/bare_heldout_phish.csv"
N_SAFE_ATTACKED = 15000
MODELS = {"4a": {"model": "models_v2/gradient_boosting_exp4a.joblib", "recipe": "models_v2/feature_recipe_exp4a.joblib",
                 "results": "results/exp4a_host500"},
          "8b": {"model": "models_v2/gradient_boosting_chunk3.joblib", "recipe": "models_v2/feature_recipe_chunk3.joblib",
                 "results": "results/exp8b_ngram34"}}


def build_sets():
    """name -> list of URLs. Names: clean_phish, clean_safe, safe@none, phish@<family>, safe@<family>."""
    val = pd.read_csv(VAL, usecols=["url", "label"])
    phish = val.loc[val["label"] == 1, "url"].astype(str).tolist()
    safe = val.loc[val["label"] == 0, "url"].astype(str).tolist()
    words = load_benign_words(TRAIN)
    safe_small = random.Random(5).sample(safe, N_SAFE_ATTACKED)
    sets = {"clean_phish": phish, "clean_safe": safe, "safe@none": safe_small}
    for fam in FAMILIES:
        sets[f"phish@{fam}"] = apply_family(phish, fam, words, seed=42)
        sets[f"safe@{fam}"] = apply_family(safe_small, fam, words, seed=42)
    return sets


def load_cache(tag):
    z = np.load(f"data_v2/defence_scores_{tag}.npz")
    return {k: z[k] for k in z.files}


def triple(cache, name):
    return cache[f"{name}@full"], cache[f"{name}@noq"], cache[f"{name}@nolast"]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True, choices=list(MODELS))
    args = ap.parse_args()
    cfg = MODELS[args.tag]
    out_path = f"data_v2/defence_scores_{args.tag}.npz"
    if os.path.exists(out_path):
        raise SystemExit(f"{out_path} already exists; not overwriting.")
    for p in (VAL, TRAIN, HELD_SAFE, HELD_PHISH):
        assert "test" not in os.path.basename(p).lower()

    scorer = dl.make_scorer(cfg["model"], cfg["recipe"])
    sets = build_sets()
    for name, p in (("heldout_safe", HELD_SAFE), ("heldout_phish", HELD_PHISH)):
        sets[name] = pd.read_csv(p)["url"].astype(str).tolist()
    cache = {}
    for name, urls in sets.items():
        full, noq, nolast = dl.score_copies(urls, scorer)
        if name.startswith("heldout"):                 # bare sets: only the full URL is needed
            noq, nolast = np.full(len(urls), np.nan), np.full(len(urls), np.nan)
        cache[f"{name}@full"], cache[f"{name}@noq"], cache[f"{name}@nolast"] = full, noq, nolast
        print(f"scored {name}: {len(urls):,} URLs; trimmed copies: no-query {int((~np.isnan(noq)).sum()):,}, "
              f"no-last-segment {int((~np.isnan(nolast)).sum()):,}", flush=True)

    # ---- gate: reproduce the saved evaluate.py numbers for the plain model
    saved = json.load(open(os.path.join(cfg["results"], "metrics.json")))
    att = pd.read_csv(os.path.join(cfg["results"], "attack_families.csv")).set_index("family")
    thr = saved["matched_threshold"]
    p_ph, p_sf = cache["clean_phish@full"], cache["clean_safe@full"]
    diffs = {"clean recall": abs((p_ph >= thr).mean() - saved["at_matched"]["recall"]),
             "AUC": abs(roc_auc_score(np.r_[np.ones(len(p_ph)), np.zeros(len(p_sf))], np.r_[p_ph, p_sf]) - saved["auc"]),
             "clean safe flagged": abs((cache["safe@none@full"] >= thr).mean() - att.loc["none (clean)", "safe_flagged_matched"])}
    for fam in FAMILIES:
        diffs[f"recall {fam}"] = abs((cache[f"phish@{fam}@full"] >= thr).mean() - att.loc[fam, "recall_matched"])
        diffs[f"safe flagged {fam}"] = abs((cache[f"safe@{fam}@full"] >= thr).mean() - att.loc[fam, "safe_flagged_matched"])
    worst = max(diffs.values())
    print(f"\nGATE: plain {args.tag} recomputed from the cache vs {cfg['results']}: largest absolute difference {worst:.2e} "
          f"over {len(diffs)} numbers")
    if worst >= 5e-5:
        raise SystemExit("GATE FAILED (difference of 4-decimal size or more); cache not saved. " + str({k: v for k, v in diffs.items() if v >= 5e-5}))
    np.savez(out_path, **cache)
    print(f"GATE PASSED. Saved {out_path}")
