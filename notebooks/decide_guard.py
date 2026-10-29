"""Chunk 5, Experiment 12: apply the locked KEEP rules to the trimming guard and print PASS/FAIL. No judgement calls.

Compared with plain 4a at the matched whole-system level (3.65% of the clean validation safe URLs; each variant's
threshold is re-set on ITS OWN guarded scores). A variant is KEPT only if ALL four hold:
  (a) mean recall over the three word-edit attacks (path words, query words, random mix) rises by >= 5.00 points;
  (b) clean recall drops by <= 1.00 point;
  (c) the share of edited SAFE URLs flagged rises by <= 2.00 points under each of those three attacks;
  (d) AUC (of the guarded score) does not fall by more than 0.005.
If both variants pass, the one with the higher mean attack recall is kept; equal to 4 decimals -> g1.

    PYTHONHASHSEED=0 .venv/bin/python notebooks/decide_guard.py --out results/exp12_guard

VALIDATION DATA ONLY (cached scores). Writes decision.json and decision.txt into --out; refuses to overwrite.
"""
import argparse
import json
import os
import defence_layers as dl
import defence_metrics as dm
from defence_scores import load_cache

EPS = 1e-9
ap = argparse.ArgumentParser()
ap.add_argument("--out", required=True)
ap.add_argument("--tag", default="4a")
args = ap.parse_args()
out_json, out_txt = os.path.join(args.out, "decision.json"), os.path.join(args.out, "decision.txt")
for p in (out_json, out_txt):
    if os.path.exists(p):
        raise SystemExit(f"{p} already exists; not overwriting.")

lines = []


def log(text=""):
    print(text)
    lines.append(str(text))


cache = load_cache(args.tag)
target = dm.target_fpr()
rows, aucs, thrs = {}, {}, {}
for guard in (None, "g1", "g2"):
    sc = dm.system_scores(cache, guard)
    thr, rate, nfl, _ = dl.set_threshold(sc["clean_safe"], target)
    rows[guard] = dm.summarize(dm.flags(sc, thr))
    aucs[guard], thrs[guard] = dm.auc(sc), thr
    log(f"{guard or 'plain'}: threshold {thr:.4f}, clean safe flagged {nfl} ({rate * 100:.3f}%), AUC {aucs[guard]:.4f}")

pf = lambda ok: "PASS" if ok else "FAIL"
base = rows[None]
result = {"model": args.tag, "target_fpr": target, "variants": {}}
passed = []
log(f"\n=== Experiment 12 decision, model {args.tag}: guard vs plain at the matched whole-system level ({target:.4f})")
for g in ("g1", "g2"):
    r = rows[g]
    d_atk = r["mean_word_attack_recall"] - base["mean_word_attack_recall"]
    d_rec = r["recall"] - base["recall"]
    d_auc = aucs[g] - aucs[None]
    d_safe = {a: r[f"safe_flagged_{a}"] - base[f"safe_flagged_{a}"] for a in dm.WORD_ATTACKS}
    a_ok, b_ok = d_atk >= 0.05 - EPS, d_rec >= -0.01 - EPS
    c_ok, d_ok = all(v <= 0.02 + EPS for v in d_safe.values()), d_auc >= -0.005 - EPS
    keep = a_ok and b_ok and c_ok and d_ok
    log(f"\n--- variant {g}")
    log(f"(a) mean recall over path words / query words / random mix {base['mean_word_attack_recall']:.4f} -> "
        f"{r['mean_word_attack_recall']:.4f} ({d_atk * 100:+.2f} pt; needs >= +5.00): {pf(a_ok)}")
    for a in dm.WORD_ATTACKS:
        log(f"      {a}: {base[f'recall_{a}']:.4f} -> {r[f'recall_{a}']:.4f} ({(r[f'recall_{a}'] - base[f'recall_{a}']) * 100:+.2f} pt)")
    log(f"(b) clean recall {base['recall']:.4f} -> {r['recall']:.4f} ({d_rec * 100:+.2f} pt; must not drop by more than 1.00): {pf(b_ok)}")
    log("(c) edited SAFE URLs flagged (rise must be <= 2.00 pt): "
        + "; ".join(f"{a} {base[f'safe_flagged_{a}']:.4f} -> {r[f'safe_flagged_{a}']:.4f} ({d_safe[a] * 100:+.2f} pt)" for a in dm.WORD_ATTACKS)
        + f": {pf(c_ok)}")
    log(f"(d) AUC {aucs[None]:.4f} -> {aucs[g]:.4f} ({d_auc:+.4f}; must not fall by more than 0.005): {pf(d_ok)}")
    log(f"    {g}: {'KEEP' if keep else 'REVERT'}")
    if keep:
        passed.append(g)
    result["variants"][g] = {"threshold": thrs[g], "auc": aucs[g], "mean_word_attack_recall": r["mean_word_attack_recall"],
                             "clean_recall": r["recall"], "criterion_a": bool(a_ok), "criterion_b": bool(b_ok),
                             "criterion_c": bool(c_ok), "criterion_d": bool(d_ok), "keep": bool(keep),
                             "d_attack_pt": d_atk * 100, "d_clean_recall_pt": d_rec * 100, "d_auc": d_auc,
                             "d_safe_flag_pt": {a: v * 100 for a, v in d_safe.items()}}
if len(passed) == 2:
    m1, m2 = (round(rows[g]["mean_word_attack_recall"], 4) for g in passed)
    kept = "g1" if m1 >= m2 else "g2"
    log(f"\nBoth variants pass; mean attack recall g1 {m1:.4f}, g2 {m2:.4f} -> keep {kept} (equal to 4 decimals -> g1).")
elif passed:
    kept = passed[0]
else:
    kept = None
log(f"\nDECISION: {('KEEP ' + kept) if kept else 'REVERT (no guard)'}")
result.update({"kept": kept, "plain_threshold": thrs[None], "plain_auc": aucs[None]})
os.makedirs(args.out, exist_ok=True)
json.dump(result, open(out_json, "w"), indent=2)
open(out_txt, "w").write("\n".join(lines) + "\n")
print(f"\nSaved {out_json}")
