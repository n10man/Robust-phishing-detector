"""Chunk 5, Experiment 11: rules layer (scoring only, VALIDATION DATA ONLY). Prints counts only, no URLs.

    PYTHONHASHSEED=0 .venv/bin/python notebooks/exp11_rules.py --out results/exp11_rules

Needs the score caches (defence_scores.py). Writes rules.csv, rules_edited_hits.csv, combined_<tag>.csv,
validated_rules.json and report.txt into --out, and the rule hits of every set into the git-ignored
data_v2/defence_rules_hits.npz (reused by Experiments 12 and 13 and the final table). Refuses to overwrite.
"""
import argparse
import json
import os
import numpy as np
import pandas as pd
import defence_layers as dl
import defence_metrics as dm
from defence_scores import build_sets, load_cache

MIN_HITS, MIN_PRECISION = 30, 0.90
HITS_PATH = "data_v2/defence_rules_hits.npz"

ap = argparse.ArgumentParser()
ap.add_argument("--out", required=True)
args = ap.parse_args()
for p in (args.out, HITS_PATH):
    if os.path.exists(p):
        raise SystemExit(f"{p} already exists; not overwriting.")

lines = []


def log(text=""):
    print(text, flush=True)
    lines.append(str(text))


target = dm.target_fpr()
sets = build_sets()
rule_mats = {n: dl.rule_matrix(sets[n]) for n in dm.SET_NAMES}
np.savez(HITS_PATH, **rule_mats)
log(f"Exp 11 on VALIDATION only. Fixed false-alarm level {target:.4f}. Rule hits computed for {len(rule_mats)} URL sets "
    f"(clean phishing {len(sets['clean_phish']):,}, clean safe {len(sets['clean_safe']):,}, edited sets with the same URLs as evaluate.py).")

caches = {tag: load_cache(tag) for tag in ("4a", "8b")}
plain = {}
for tag, cache in caches.items():
    sc = dm.system_scores(cache, None)
    thr, rate, nfl, _ = dl.set_threshold(sc["clean_safe"], target)
    plain[tag] = (sc, thr)
    log(f"Plain {tag}: threshold {thr:.4f} flags {nfl} of {len(sc['clean_safe']):,} clean safe URLs ({rate * 100:.3f}%)")

# ---- per-rule table
mp, ms = rule_mats["clean_phish"], rule_mats["clean_safe"]
rows, validated = [], []
for i, r in enumerate(dl.RULES):
    hp, hs = int(mp[:, i].sum()), int(ms[:, i].sum())
    tot = hp + hs
    prec = hp / tot if tot else float("nan")
    if tot < MIN_HITS:
        status = "untestable on this data (fewer than 30 hits)"
    elif prec < MIN_PRECISION:
        status = "NOT validated (precision below 90%)"
    else:
        status = "VALIDATED"
        validated.append(r)
    row = {"rule": r, "hits_phishing": hp, "hits_safe": hs, "hits_total": tot, "precision": prec, "status": status}
    for tag in ("4a", "8b"):
        sc, thr = plain[tag]
        row[f"phish_hits_not_caught_by_{tag}"] = int((mp[:, i] & (sc["clean_phish"] < thr)).sum())
        row[f"safe_hits_not_flagged_by_{tag}"] = int((ms[:, i] & (sc["clean_safe"] < thr)).sum())
    rows.append(row)
rules_tbl = pd.DataFrame(rows)
log("\nRULES ON CLEAN VALIDATION (validated = at least 30 hits AND at least 90% of hits are phishing)\n")
log(rules_tbl.round(4).to_string(index=False))
log(f"\nValidated rules: {validated if validated else 'none'}")
log("Rules listed 'untestable' have too few hits to say anything; they are NOT counted as results.")

# ---- hits on the edited sets
edit_rows = []
for i, r in enumerate(dl.RULES):
    row = {"rule": r, "clean_phishing": int(mp[:, i].sum()), "clean_safe_15k_sample": int(rule_mats["safe@none"][:, i].sum())}
    for f in dm.FAMS:
        row[f"phish_{f}"] = int(rule_mats[f"phish@{f}"][:, i].sum())
        row[f"safe15k_{f}"] = int(rule_mats[f"safe@{f}"][:, i].sum())
    edit_rows.append(row)
edit_tbl = pd.DataFrame(edit_rows)
log("\nRULE HITS ON THE EDITED SETS (same edited URLs as evaluate.py; 16,135 phishing; the 15,000-URL safe sample)\n")
log(edit_tbl.T.to_string(header=False))

# ---- combined system
comb_tbls = {}
for tag, (sc, thr_plain) in plain.items():
    rf = dm.rules_any(rule_mats, validated)
    rows = []
    fl = dm.flags(sc, thr_plain)
    rows.append({"system": "plain model at 3.65%", "threshold": thr_plain, **dm.summarize(fl)})
    if validated:
        thr_sys, rate, nfl, nrule = dl.set_threshold(sc["clean_safe"], target, rf["clean_safe"])
        fl = dm.flags(sc, thr_sys, rf)
        rows.append({"system": f"model OR validated rules {validated} at 3.65%", "threshold": thr_sys, **dm.summarize(fl)})
        log(f"\n{tag}: whole-system threshold {thr_sys:.4f}; {nfl} clean safe URLs flagged in total ({rate * 100:.3f}%), "
            f"{nrule} of them by a rule")
    else:
        log(f"\n{tag}: no validated rule, so the combined system equals the plain model.")
    fl = dm.flags(sc, 0.5)
    rows.append({"system": "plain model at threshold 0.5", "threshold": 0.5, **dm.summarize(fl)})
    if validated:
        fl = dm.flags(sc, 0.5, rf)
        rows.append({"system": "model OR validated rules at threshold 0.5", "threshold": 0.5, **dm.summarize(fl)})
    t = pd.DataFrame(rows)
    comb_tbls[tag] = t
    log(f"\nCOMBINED SYSTEM, model {tag} (recall, false_alarm, precision, f1 on clean validation; attack recall; edited-safe flag shares)\n")
    show = ["system", "threshold", "recall", "false_alarm", "precision", "f1"] + [f"recall_{f}" for f in dm.FAMS]
    log(t[show].round(4).to_string(index=False))
    log("\n  edited SAFE URLs flagged:")
    log(t[["system"] + [f"safe_flagged_{f}" for f in dm.FAMS]].round(4).to_string(index=False))

os.makedirs(args.out)
rules_tbl.to_csv(os.path.join(args.out, "rules.csv"), index=False)
edit_tbl.to_csv(os.path.join(args.out, "rules_edited_hits.csv"), index=False)
for tag, t in comb_tbls.items():
    t.to_csv(os.path.join(args.out, f"combined_{tag}.csv"), index=False)
json.dump({"validated_rules": validated, "min_hits": MIN_HITS, "min_precision": MIN_PRECISION,
           "rule_status": dict(zip(rules_tbl["rule"], rules_tbl["status"]))},
          open(os.path.join(args.out, "validated_rules.json"), "w"), indent=2)
with open(os.path.join(args.out, "report.txt"), "w") as f:
    f.write("\n".join(lines) + "\n")
log(f"\nSaved {args.out}/ and {HITS_PATH}")
