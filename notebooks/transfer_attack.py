"""Chunk 4, Experiment 10: transfer attack (REPORT ONLY). Validation data only.

An attacker with no access to our model trains a surrogate (notebooks/train_surrogates.py), edits real
validation phishing URLs until the SURROGATE no longer flags them, and we check whether those edited URLs
also slip past the target Exp 4a (and the secondary target 8b, which is only scored, never retrained).

Hill-climb settings are copied from stage6b_hillclimb.py (that file runs on import, so its settings are
copied, not its code): 15 rounds, 20 candidate edits per still-attacked URL per round, a candidate is kept only
if it strictly lowers the attacked model's phishing score (best one per URL per round). Changes, all agreed:
500 URLs; edit operations = the six functions of attacks.py (BASE_FAMILIES, imported, not edited); a URL
leaves the attack once its score is below the fixed-level threshold of the attacked model (stage6b: 0.5).

Variants:  standard = stop below the surrogate's fixed-level threshold;
           margin   = stop only below 50% of that threshold, or when the limits end (report only).
Controls:  (i) random edits, same number of edits per URL, same operations, no scoring;
           (ii) white-box hill-climb against 4a itself (standard rule), same limits and pool.

    PYTHONHASHSEED=0 .venv/bin/python notebooks/transfer_attack.py --out results/exp10_transfer

Prints no example URLs. Writes only counts. Never reads a test file.
"""
import argparse
import json
import math
import os
import random
import time
from collections import Counter
import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
from attacks import BASE_FAMILIES, load_benign_words
import features_v2 as fv

VAL, TRAIN = "data_v2/val_redacted.csv", "data_v2/train_redacted.csv"
ROUNDS, CANDIDATES, N_POOL, SEED, MARGIN = 15, 20, 500, 42, 0.5
OPS = list(BASE_FAMILIES.items())

ap = argparse.ArgumentParser()
ap.add_argument("--out", default="results/exp10_transfer")
ap.add_argument("--scores-out", default="data_v2/exp10_attack_scores.npz")
args = ap.parse_args()
for p in (args.out, args.scores_out):
    if os.path.exists(p):
        raise SystemExit(f"{p} already exists; not overwriting.")

lines = []


def log(text=""):
    print(text, flush=True)
    lines.append(str(text))


def wilson(k, n, z=1.96):
    if n == 0:
        return float("nan"), float("nan")
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - h, c + h


def cell(k, n):
    if n == 0:
        return "n/a (0 URLs)"
    lo, hi = wilson(k, n)
    return f"{k}/{n} = {k / n * 100:.1f}% [{lo * 100:.1f}, {hi * 100:.1f}]"


def scorer(model, recipe, chunk=20000):
    def f(urls):
        urls = [str(u) for u in urls]
        return np.concatenate([model.predict_proba(fv.featurize(urls[i:i + chunk], recipe))[:, 1]
                               for i in range(0, len(urls), chunk)])
    return f


BENIGN = load_benign_words(TRAIN)          # the same harmless-word list evaluate.py uses
log(f"Harmless words available to the edits: {len(BENIGN)}")


def hill_climb(urls, score, thr, stop_factor, seed):
    """Greedy hill-climb against `score`. Returns edited urls, final scores, edits per URL, ops used."""
    rng = random.Random(seed)
    stop = thr * stop_factor
    cur_url = list(urls)
    cur = np.array(score(cur_url))
    edits, used = np.zeros(len(urls), int), [[] for _ in urls]
    active = [i for i in range(len(urls)) if cur[i] >= stop]
    for r in range(1, ROUNDS + 1):
        if not active:
            break
        cands, owner, names = [], [], []
        for i in active:
            for _ in range(CANDIDATES):
                name, fn = rng.choice(OPS)
                cands.append(fn(cur_url[i], rng, BENIGN))
                owner.append(i)
                names.append(name)
        p = score(cands)
        best = {}
        for k, i in enumerate(owner):
            if p[k] < cur[i] and (i not in best or p[k] < p[best[i]]):
                best[i] = k
        for i, k in best.items():
            cur_url[i], cur[i] = cands[k], p[k]
            edits[i] += 1
            used[i].append(names[k])
        active = [i for i in active if cur[i] >= stop]
        log(f"    round {r}: {int((cur < thr).sum())} of {len(urls)} below the threshold, "
            f"{int((cur < thr * MARGIN).sum())} below 50% of it, {len(active)} still being attacked")
    return cur_url, cur, edits, used


def random_edits(urls, counts, seed):
    """Apply exactly counts[i] random edits (random operations from the same six, no scoring) to URL i."""
    rng = random.Random(seed)
    out = []
    for u, k in zip(urls, counts):
        for _ in range(int(k)):
            _, fn = rng.choice(OPS)
            u = fn(u, rng, BENIGN)
        out.append(u)
    return out


# ---- models and thresholds ----------------------------------------------------------
target_fpr = json.load(open("results/baseline_v1/metrics.json"))["target_fpr"]
thr4 = json.load(open("results/exp4a_host500/metrics.json"))["matched_threshold"]
thr8 = json.load(open("results/exp8b_ngram34/metrics.json"))["matched_threshold"]
m4, r4 = joblib.load("models_v2/gradient_boosting_exp4a.joblib"), joblib.load("models_v2/feature_recipe_exp4a.joblib")
m8, r8 = joblib.load("models_v2/gradient_boosting_chunk3.joblib"), joblib.load("models_v2/feature_recipe_chunk3.joblib")
r_s = joblib.load("models_v2/feature_recipe_surr.joblib")
surrogates = {"s1 logistic regression": joblib.load("models_v2/logreg_surr_s1.joblib"),
              "s2 small gradient boosting (50 rounds)": joblib.load("models_v2/gradient_boosting_surr_s2.joblib")}
f4, f8 = scorer(m4, r4), scorer(m8, r8)
log(f"Fixed false-alarm level {target_fpr:.4f}. Target 4a threshold {thr4:.4f}; secondary target 8b threshold {thr8:.4f}.")

val = pd.read_csv(VAL, usecols=["url", "label"])
phish = val.loc[val["label"] == 1, "url"].astype(str).tolist()
safe = val.loc[val["label"] == 0, "url"].astype(str).tolist()
t0 = time.time()
p4, p8 = f4(phish), f8(phish)
log(f"Scored {len(phish):,} validation phishing URLs with 4a and 8b ({time.time() - t0:.0f} s). "
    f"4a catches {int((p4 >= thr4).sum()):,}, 8b catches {int((p8 >= thr8).sum()):,}.")

# surrogates: own fixed-level threshold on the clean validation safe URLs
X_ph, X_sf = fv.featurize(phish, r_s), fv.featurize(safe, r_s)
sur_info, thr_s, p_s = [], {}, {}
for name, model in surrogates.items():
    pph, psf = model.predict_proba(X_ph)[:, 1], model.predict_proba(X_sf)[:, 1]
    thr_s[name] = float(np.quantile(psf, 1 - target_fpr))
    p_s[name] = pph
    auc = roc_auc_score(np.r_[np.ones(len(pph)), np.zeros(len(psf))], np.r_[pph, psf])
    both = int(((pph >= thr_s[name]) & (p4 >= thr4)).sum())
    sur_info.append({"surrogate": name, "threshold": thr_s[name], "clean_recall_at_fixed_level": float((pph >= thr_s[name]).mean()),
                     "auc": float(auc), "caught_by_surrogate": int((pph >= thr_s[name]).sum()),
                     "caught_by_both_surrogate_and_4a": both})
    log(f"Surrogate {name}: threshold {thr_s[name]:.4f}, clean recall {sur_info[-1]['clean_recall_at_fixed_level']:.4f}, "
        f"AUC {auc:.4f}, caught by both it and 4a: {both:,}")
del X_ph, X_sf

# ---- the attacks -------------------------------------------------------------------
rows, saved = [], {}
for name, model in surrogates.items():
    fs = scorer(model, r_s)
    eligible = np.flatnonzero((p_s[name] >= thr_s[name]) & (p4 >= thr4))
    pool_idx = np.random.default_rng(SEED).choice(eligible, size=N_POOL, replace=False)
    pool = [phish[i] for i in pool_idx]
    base8_caught = p8[pool_idx] >= thr8
    log(f"\n=== {name}: pool of {N_POOL} validation phishing URLs caught by both 4a and the surrogate "
        f"(8b caught {int(base8_caught.sum())} of them before editing)")
    for variant, factor in [("standard", 1.0), ("margin (50%)", MARGIN)]:
        log(f"  hill-climb against the SURROGATE, variant {variant}:")
        final, sc, edits, used = hill_climb(pool, fs, thr_s[name], factor, SEED)
        t4, t8 = f4(final), f8(final)
        rnd = random_edits(pool, edits, SEED)
        q4, q8 = f4(rnd), f8(rnd)
        saved[f"{name[:2]}_{variant[:3]}"] = {"surrogate_final": sc, "t4": t4, "t8": t8, "random4": q4, "random8": q8, "edits": edits}
        for subset_name, mask in [("surrogate-evading (score below threshold)", sc < thr_s[name]),
                                  ("reached the 50% margin", sc < thr_s[name] * MARGIN)]:
            n = int(mask.sum())
            ev4, ev8 = t4 < thr4, t8 < thr8
            r4v, r8v = q4 < thr4, q8 < thr8
            kept8 = mask & base8_caught
            ops = Counter(o for i in np.flatnonzero(mask) for o in used[i])
            rows.append({
                "surrogate": name, "variant": variant, "subset": subset_name,
                "pool": N_POOL, "n_subset": n, "share_of_pool": cell(n, N_POOL),
                "mean_edits": float(edits[mask].mean()) if n else float("nan"),
                "transfer_to_4a": cell(int((mask & ev4).sum()), n),
                "transfer_to_8b": cell(int((mask & ev8).sum()), n),
                "transfer_to_8b_only_URLs_8b_caught_before_edit": cell(int((kept8 & ev8).sum()), int(kept8.sum())),
                "random_edits_evade_4a": cell(int((mask & r4v).sum()), n),
                "random_edits_evade_8b": cell(int((mask & r8v).sum()), n),
                "random_edits_evade_8b_only_URLs_8b_caught": cell(int((kept8 & r8v).sum()), int(kept8.sum())),
                "ops_used_on_these_URLs": dict(ops),
                "k_transfer_4a": int((mask & ev4).sum()), "k_random_4a": int((mask & r4v).sum()), "n": n})
    # white-box control (ii): hill-climb against 4a itself, same pool and limits, standard rule
    log("  white-box hill-climb against the TARGET 4a (upper bound):")
    wf, wsc, wed, wused = hill_climb(pool, f4, thr4, 1.0, SEED)
    w8 = f8(wf)
    wmask = wsc < thr4
    rows.append({"surrogate": name, "variant": "white-box on 4a", "subset": "evading 4a (score below threshold)",
                 "pool": N_POOL, "n_subset": int(wmask.sum()), "share_of_pool": cell(int(wmask.sum()), N_POOL),
                 "mean_edits": float(wed[wmask].mean()) if wmask.any() else float("nan"),
                 "transfer_to_4a": cell(int(wmask.sum()), int(wmask.sum())),
                 "transfer_to_8b": cell(int((wmask & (w8 < thr8)).sum()), int(wmask.sum())),
                 "transfer_to_8b_only_URLs_8b_caught_before_edit": cell(int((wmask & (w8 < thr8) & base8_caught).sum()),
                                                                       int((wmask & base8_caught).sum())),
                 "ops_used_on_these_URLs": dict(Counter(o for i in np.flatnonzero(wmask) for o in wused[i])),
                 "k_transfer_4a": int(wmask.sum()), "n": int(wmask.sum())})
    saved[f"{name[:2]}_white"] = {"t4": wsc, "t8": w8, "edits": wed}

table = pd.DataFrame(rows)
pd.set_option("display.width", 250, "display.max_colwidth", 60)
log("\n\nSUMMARY (counts with 95% Wilson intervals, in percent)")
for _, r in table.iterrows():
    log(f"\n[{r['surrogate']}] variant: {r['variant']} | subset: {r['subset']}")
    log(f"   URLs in subset: {r['share_of_pool']} of the pool | mean edits per URL: {r['mean_edits']:.2f}")
    log(f"   evade target 4a (transfer): {r['transfer_to_4a']}")
    log(f"   evade secondary target 8b: {r['transfer_to_8b']}   (only URLs 8b caught before editing: "
        f"{r['transfer_to_8b_only_URLs_8b_caught_before_edit']})")
    if "random_edits_evade_4a" in r and isinstance(r["random_edits_evade_4a"], str):
        log(f"   RANDOM-EDIT control, same number of edits: evade 4a {r['random_edits_evade_4a']}; evade 8b {r['random_edits_evade_8b']}")
    log(f"   edit operations used: {r['ops_used_on_these_URLs']}")

os.makedirs(args.out, exist_ok=True)
table.drop(columns=["k_transfer_4a", "n"]).to_csv(os.path.join(args.out, "transfer_summary.csv"), index=False)
pd.DataFrame(sur_info).to_csv(os.path.join(args.out, "surrogates.csv"), index=False)
with open(os.path.join(args.out, "report.txt"), "w") as f:
    f.write("\n".join(lines) + "\n")
np.savez(args.scores_out, **{f"{k}__{kk}": vv for k, v in saved.items() for kk, vv in v.items()})
log(f"\nSaved {args.out}/ and {args.scores_out}")
