"""Chunk 5, Experiment 13: the "unsure" answer (REPORT ONLY, scoring only, VALIDATION DATA ONLY). No URLs printed.

Systems: "model" (plain, no rules) and "model + validated rules" (the rules that Exp 11 validated), for 4a and 8b.
Each system's threshold is the whole-system 3.65% threshold. Abstain window: unsure when |score - threshold| < w, with w
fixed on the clean validation set (phishing + safe together) so that the share of ALL clean validation URLs inside the window
is 5% / 10% (operating point) / 20%; the same w is then applied to the edited sets. Bare-domain routing (host equals its
registered domain, no path or query) -> unsure, whatever the score. Layer order as in defence_layers.classify_many:
validated rule -> phishing; bare route -> unsure; window -> unsure; score >= threshold -> phishing; else safe.

    PYTHONHASHSEED=0 .venv/bin/python notebooks/exp13_abstain.py --rules-json results/exp11_rules/validated_rules.json --out results/exp13_abstain
"""
import argparse
import json
import os
import numpy as np
import pandas as pd
import defence_layers as dl
import defence_metrics as dm
from defence_scores import build_sets, load_cache, HELD_SAFE, HELD_PHISH

SHARES = [0.0, 0.05, 0.10, 0.20]          # 0.0 = bare-domain routing only
OPERATING = 0.10

ap = argparse.ArgumentParser()
ap.add_argument("--rules-json", required=True)
ap.add_argument("--out", required=True)
args = ap.parse_args()
if os.path.exists(args.out):
    raise SystemExit(f"{args.out} already exists; not overwriting.")

lines = []


def log(text=""):
    print(text, flush=True)
    lines.append(str(text))


validated = json.load(open(args.rules_json))["validated_rules"]
target = dm.target_fpr()
sets = build_sets()
sets["heldout_safe"] = pd.read_csv(HELD_SAFE)["url"].astype(str).tolist()
sets["heldout_phish"] = pd.read_csv(HELD_PHISH)["url"].astype(str).tolist()
rule_mats = dict(np.load("data_v2/defence_rules_hits.npz"))
for n in ("heldout_safe", "heldout_phish"):
    rule_mats[n] = dl.rule_matrix(sets[n])
bare = {n: np.array([dl.is_bare_domain(u) for u in sets[n]]) for n in sets}
names = dm.SET_NAMES + ["heldout_safe", "heldout_phish"]
log(f"Exp 13, validation only. Validated rules used in the 'model + rules' system: {validated}. Fixed level {target:.4f}.")


def verdicts(score, thr, w, rule_f, bare_f, use_bare):
    """0 = safe, 1 = phishing, 2 = unsure, with the layer order of the verdict function."""
    v = np.zeros(len(score), int)
    band = (np.abs(score - thr) < w) if w else np.zeros(len(score), bool)
    unsure = ~rule_f & ((bare_f if use_bare else False) | band)
    phish = rule_f | (~unsure & (score >= thr))
    v[phish] = 1
    v[unsure & ~rule_f] = 2
    return v


all_rows, att_rows, held_rows, cfg_out = [], [], [], {}
for tag in ("4a", "8b"):
    cache = load_cache(tag)
    sc = dm.system_scores(cache, None, names)
    for sys_name, rules in (("model", []), ("model + validated rules", validated)):
        rf = dm.rules_any(rule_mats, rules)
        thr, rate, nfl, nrule = dl.set_threshold(sc["clean_safe"], target, rf["clean_safe"])
        both = np.r_[sc["clean_phish"], sc["clean_safe"]]
        cfg_out[f"{tag}|{sys_name}"] = {"threshold": thr}
        for share in SHARES:
            w = dl.abstain_width(both, thr, share) if share else 0.0
            cfg_out[f"{tag}|{sys_name}"][f"window_width_{int(share * 100)}pct"] = w
            vp = verdicts(sc["clean_phish"], thr, w, rf["clean_phish"], bare["clean_phish"], True)
            vs = verdicts(sc["clean_safe"], thr, w, rf["clean_safe"], bare["clean_safe"], True)
            n_all = len(vp) + len(vs)
            dec_p, dec_s = vp != 2, vs != 2
            row = {"model": tag, "system": sys_name, "window_share": share, "window_width": w, "threshold": thr,
                   "coverage": float((dec_p.sum() + dec_s.sum()) / n_all),
                   "unsure_share_of_all": float(((vp == 2).sum() + (vs == 2).sum()) / n_all),
                   "recall_all_phishing_verdict": float((vp == 1).mean()),
                   "recall_phishing_or_unsure": float((vp != 0).mean()),
                   "false_alarm_all_safe": float((vs == 1).mean()),
                   "recall_among_decided": float((vp == 1).sum() / dec_p.sum()),
                   "false_alarm_among_decided": float((vs == 1).sum() / dec_s.sum()),
                   "phishing_lost_to_unsure": int((vp == 2).sum()),
                   "phishing_lost_because_bare": int(((vp == 2) & bare["clean_phish"] & ~rf["clean_phish"]).sum()),
                   "phishing_bare": int((bare["clean_phish"] & ~rf["clean_phish"]).sum()),
                   "safe_unsure_share": float((vs == 2).mean())}
            all_rows.append(row)
            for f in dm.FAMS:
                ve = verdicts(sc[f"phish@{f}"], thr, w, rf[f"phish@{f}"], bare[f"phish@{f}"], True)
                vplain = verdicts(sc[f"phish@{f}"], thr, 0.0, rf[f"phish@{f}"], bare[f"phish@{f}"], False)   # no abstain at all
                silent = vplain == 0
                vsafe = verdicts(sc[f"safe@{f}"], thr, w, rf[f"safe@{f}"], bare[f"safe@{f}"], True)
                att_rows.append({"model": tag, "system": sys_name, "window_share": share, "family": f,
                                 "phish_phishing": float((ve == 1).mean()), "phish_unsure": float((ve == 2).mean()),
                                 "phish_safe": float((ve == 0).mean()),
                                 "silent_misses_without_abstain": int(silent.sum()),
                                 "silent_misses_now_unsure_share": float((ve[silent] == 2).mean()) if silent.any() else float("nan"),
                                 "silent_misses_still_safe_share": float((ve[silent] == 0).mean()) if silent.any() else float("nan"),
                                 "caught_before_now_unsure_share": float((ve[~silent & (vplain == 1)] == 2).mean()),
                                 "safe_phishing": float((vsafe == 1).mean()), "safe_unsure": float((vsafe == 2).mean()),
                                 "safe_safe": float((vsafe == 0).mean())})
            for hn in ("heldout_safe", "heldout_phish"):
                vh = verdicts(sc[hn], thr, w, rf[hn], bare[hn], True)
                held_rows.append({"model": tag, "system": sys_name, "window_share": share, "set": hn, "n": len(vh),
                                  "phishing": int((vh == 1).sum()), "unsure": int((vh == 2).sum()), "safe": int((vh == 0).sum()),
                                  "unsure_because_bare": int(((vh == 2) & bare[hn]).sum())})

curve, att, held = pd.DataFrame(all_rows), pd.DataFrame(att_rows), pd.DataFrame(held_rows)
pd.set_option("display.width", 260)
for tag in ("4a", "8b"):
    for sys_name in ("model", "model + validated rules"):
        sel = (curve["model"] == tag) & (curve["system"] == sys_name)
        log(f"\n=== {tag}, system '{sys_name}': clean validation, curve over the window size (0% = bare-domain routing only)\n")
        log(curve[sel].drop(columns=["model", "system"]).round(4).to_string(index=False))
op = att[(att["window_share"] == OPERATING)]
for tag in ("4a", "8b"):
    for sys_name in ("model", "model + validated rules"):
        sel = (op["model"] == tag) & (op["system"] == sys_name)
        log(f"\n=== {tag}, '{sys_name}', operating point (10% window + bare routing): verdict shares of EDITED phishing, and what happens to silent misses\n")
        log(op[sel].drop(columns=["model", "system", "window_share"]).round(4).to_string(index=False))
log("\n=== Held-out bare sets (10,000 safe and 10,000 phishing registered domains), operating point\n")
log(held[held["window_share"] == OPERATING].round(4).to_string(index=False))

os.makedirs(args.out)
curve.to_csv(os.path.join(args.out, "curve.csv"), index=False)
att.to_csv(os.path.join(args.out, "attacked_verdicts.csv"), index=False)
held.to_csv(os.path.join(args.out, "heldout_bare.csv"), index=False)
json.dump({"validated_rules": validated, "operating_share": OPERATING, "systems": cfg_out},
          open(os.path.join(args.out, "abstain_config.json"), "w"), indent=2)
with open(os.path.join(args.out, "report.txt"), "w") as f:
    f.write("\n".join(lines) + "\n")
log(f"\nSaved {args.out}/")
