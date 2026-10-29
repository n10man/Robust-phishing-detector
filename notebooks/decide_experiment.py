"""Apply the locked Chunk 3 keep-rules and print PASS/FAIL. No judgement calls.

KEEP only if ALL hold, candidate vs current accepted model, at the fixed false-alarm level:
  (1) primary: recall rises by >= 0.5 point AND the paired bootstrap 95% interval of the
      recall difference excludes zero (is entirely above zero);
      OR alternative primary: mean recall over the three word-edit attacks (path words, query
      words, random mix) rises by >= 3 points AND clean recall drops by <= 0.3 point.
  (2) AUC does not fall by more than 0.002.
  (3) the share of edited SAFE URLs flagged, at the matched threshold, rises by <= 2 points
      under each of those three attacks.
Bootstrap: phishing and safe validation URLs resampled separately, with replacement, 200
resamples, seed 42, same indices for both models; each model's threshold is re-set in every
resample to give the fixed false-alarm rate on the resampled safe URLs.

Usage (from the repo root):
    .venv/bin/python notebooks/decide_experiment.py --name exp4a \
        --current-dir results/chunk3_base --current-scores data_v2/scores_chunk3_base.npz \
        --candidate-dir results/exp4a_host500 --candidate-scores data_v2/scores_exp4a.npz
Writes decision.json into the candidate folder (refuses to overwrite).
"""
import argparse
import json
import os
import numpy as np
import pandas as pd

ATTACKS = ["benign_words_in_path", "benign_words_in_query", "random_mix"]
REPORT_ATTACKS = ["lookalike_characters", "extra_subdomains", "path_shortening", "padding"]
N_BOOT, SEED = 200, 42

ap = argparse.ArgumentParser()
ap.add_argument("--name", required=True)
ap.add_argument("--current-dir", required=True)
ap.add_argument("--current-scores", required=True)
ap.add_argument("--candidate-dir", required=True)
ap.add_argument("--candidate-scores", required=True)
args = ap.parse_args()
out_path = os.path.join(args.candidate_dir, "decision.json")
if os.path.exists(out_path):
    raise SystemExit(f"{out_path} already exists; not overwriting.")


def load(folder):
    m = json.load(open(os.path.join(folder, "metrics.json")))
    a = pd.read_csv(os.path.join(folder, "attack_families.csv")).set_index("family")
    return m, a


mc, ac = load(args.current_dir)
mn, an = load(args.candidate_dir)
assert abs(mc["target_fpr"] - mn["target_fpr"]) < 1e-12, "the two runs use different false-alarm levels"
target = mn["target_fpr"]

# ---- paired bootstrap of the recall difference at the fixed false-alarm level
sc, sn = np.load(args.current_scores), np.load(args.candidate_scores)
rng = np.random.default_rng(SEED)
n_ph, n_sf = len(sc["p_ph"]), len(sc["p_sf"])
diffs = np.empty(N_BOOT)
for b in range(N_BOOT):
    i_ph, i_sf = rng.integers(0, n_ph, n_ph), rng.integers(0, n_sf, n_sf)
    rec = []
    for s in (sc, sn):
        thr = np.quantile(s["p_sf"][i_sf], 1 - target)
        rec.append((s["p_ph"][i_ph] >= thr).mean())
    diffs[b] = rec[1] - rec[0]
lo, hi = np.percentile(diffs, [2.5, 97.5])

# ---- criteria
rec_c, rec_n = mc["at_matched"]["recall"], mn["at_matched"]["recall"]
d_recall = rec_n - rec_c
atk_c = ac.loc[ATTACKS, "recall_matched"].mean()
atk_n = an.loc[ATTACKS, "recall_matched"].mean()
d_atk = atk_n - atk_c
d_auc = mn["auc"] - mc["auc"]
d_safe = {a: float(an.loc[a, "safe_flagged_matched"] - ac.loc[a, "safe_flagged_matched"]) for a in ATTACKS}
EPS = 1e-9
c1_primary = (d_recall >= 0.005 - EPS) and (lo > 0)
c1_alt = (d_atk >= 0.03 - EPS) and (d_recall >= -0.003 - EPS)
c1 = c1_primary or c1_alt
c2 = d_auc >= -0.002 - EPS
c3 = all(v <= 0.02 + EPS for v in d_safe.values())
keep = bool(c1 and c2 and c3)

pf = lambda ok: "PASS" if ok else "FAIL"
print(f"=== {args.name}: candidate {args.candidate_dir} vs current {args.current_dir} (fixed false-alarm level {target:.4f})")
print(f"(1) primary: recall {rec_c:.4f} -> {rec_n:.4f} ({d_recall * 100:+.2f} pt; needs >= +0.50) and bootstrap 95% interval "
      f"[{lo * 100:+.2f}, {hi * 100:+.2f}] pt (needs lower end > 0): {pf(c1_primary)}")
print(f"    alternative: mean recall over {ATTACKS} {atk_c:.4f} -> {atk_n:.4f} ({d_atk * 100:+.2f} pt; needs >= +3.00) "
      f"and clean recall change {d_recall * 100:+.2f} pt (needs >= -0.30): {pf(c1_alt)}")
print(f"    criterion (1) overall: {pf(c1)}")
print(f"(2) AUC {mc['auc']:.4f} -> {mn['auc']:.4f} ({d_auc:+.4f}; must not fall by more than 0.002): {pf(c2)}")
print("(3) edited SAFE URLs flagged at the matched threshold (rise must be <= 2.00 pt): "
      + "; ".join(f"{a} {ac.loc[a, 'safe_flagged_matched']:.4f} -> {an.loc[a, 'safe_flagged_matched']:.4f} ({d_safe[a] * 100:+.2f} pt)" for a in ATTACKS)
      + f": {pf(c3)}")
print(f"DECISION: {'KEEP' if keep else 'REVERT'}")

# ---- report only (no decision weight)
print("\nReport only, no decision weight:")
print(f"  threshold-0.5 rows: recall {mc['at_0.5']['recall']:.4f} -> {mn['at_0.5']['recall']:.4f}; "
      f"false alarms {mc['at_0.5']['false_positives']} -> {mn['at_0.5']['false_positives']}")
for a in ATTACKS + REPORT_ATTACKS:
    print(f"  attack {a}: recall {ac.loc[a, 'recall_matched']:.4f} -> {an.loc[a, 'recall_matched']:.4f} "
          f"({(an.loc[a, 'recall_matched'] - ac.loc[a, 'recall_matched']) * 100:+.2f} pt); safe flagged "
          f"{ac.loc[a, 'safe_flagged_matched']:.4f} -> {an.loc[a, 'safe_flagged_matched']:.4f}")

result = {"name": args.name, "target_fpr": target, "keep": keep,
          "criterion_1_primary": bool(c1_primary), "criterion_1_alternative": bool(c1_alt),
          "criterion_1": bool(c1), "criterion_2": bool(c2), "criterion_3": bool(c3),
          "recall_current": rec_c, "recall_candidate": rec_n, "recall_diff": d_recall,
          "bootstrap_interval_low": float(lo), "bootstrap_interval_high": float(hi),
          "bootstrap_mean_diff": float(diffs.mean()),
          "attack_mean_current": float(atk_c), "attack_mean_candidate": float(atk_n),
          "auc_current": mc["auc"], "auc_candidate": mn["auc"], "safe_flagged_diff": d_safe}
with open(out_path, "w") as f:
    json.dump(result, f, indent=2)
print(f"\nSaved {out_path}")
