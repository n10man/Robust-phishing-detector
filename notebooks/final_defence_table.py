"""Chunk 5: final combined table (REPORT ONLY, VALIDATION DATA ONLY, scoring only). Prints counts and rates only, no URLs.

Rows per model (4a primary, 8b secondary): plain model | plain + validated rules (the FINAL SYSTEM) | plain + validated rules +
abstain (second view) | reference, rejected: g2 guard alone. Columns: clean recall and false alarms at the whole-system 3.65%
level, recall under the 7 attack families, edited-safe flag shares, coverage, 9c trigger success (4a only), white-box evasion
(pool of 500 from adaptive_attack.py). Threshold-0.5 rows for the plain-score systems. No guard was kept (Exp 12), so the rows
"+ guard", "+ guard + rules", "+ guard + rules + abstain" of the plan collapse into the rows named above.

    PYTHONHASHSEED=0 .venv/bin/python notebooks/final_defence_table.py --out results/defence_final
"""
import argparse
import json
import os
import numpy as np
import pandas as pd
import defence_layers as dl
import defence_metrics as dm
from attacks import split_url, _split_path
from defence_scores import build_sets, load_cache, VAL

TRIGGER = "nadinc"
CONTROL = "cesead"
ap = argparse.ArgumentParser()
ap.add_argument("--out", required=True)
args = ap.parse_args()
if os.path.exists(args.out):
    raise SystemExit(f"{args.out} already exists; not overwriting.")

lines = []


def log(text=""):
    print(text, flush=True)
    lines.append(str(text))


validated = json.load(open("results/exp11_rules/validated_rules.json"))["validated_rules"]
abst = json.load(open("results/exp13_abstain/abstain_config.json"))["systems"]
target = dm.target_fpr()
sets = build_sets()
rule_mats = dict(np.load("data_v2/defence_rules_hits.npz"))
rf = dm.rules_any(rule_mats, validated)
bare = {n: np.array([dl.is_bare_domain(u) for u in sets[n]]) for n in dm.SET_NAMES}
r1_col = dl.RULES.index("R1")
assert validated == ["R1"], "this table was written for the validated rule set R1"


def add_last(url, token):
    scheme, host, path = split_url(url)
    pre, tail = _split_path(path)
    return scheme + host + pre.rstrip("/") + "/" + token + tail


def wb_eval(npz_path, system):
    """White-box evasion on the pool of one hill-climb. Evasion = pool URLs the system flagged before and no longer flags after."""
    z = np.load(npz_path)
    sf, ff = z["start_full"], z["final_full"]
    rs, rn = z["start_rules"][:, r1_col], z["final_rules"][:, r1_col]
    kind, thr, w = system["kind"], system["thr"], system.get("w", 0.0)
    if kind == "g2":
        s0, s1 = dl.combine_guard(sf, z["start_noq"], z["start_nolast"], "g2"), dl.combine_guard(ff, z["final_noq"], z["final_nolast"], "g2")
        before, after = s0 >= thr, s1 >= thr
        return int((before & ~after).sum()), int(before.sum()), None
    use_rules = kind in ("rules", "abstain")
    r0, r1 = (rs, rn) if use_rules else (np.zeros(len(sf), bool), np.zeros(len(sf), bool))
    if kind == "abstain":
        # bare routing: a pool URL is bare at the start if its validation URL is bare; after the climb it can only still be
        # bare if it was never edited (every edit operation that keeps a bare URL bare leaves the score unchanged, so it is never kept)
        b0 = bare["clean_phish"][z["pool_idx"]]
        b1 = b0 & (z["edits"] == 0)
        v0 = dm.verdicts(sf, thr, w, r0, b0)
        v1 = dm.verdicts(ff, thr, w, r1, b1)
        before = v0 == 1
        return int((before & (v1 == 0)).sum()), int(before.sum()), int((before & (v1 != 1)).sum())
    before, after = (sf >= thr) | r0, (ff >= thr) | r1
    return int((before & ~after).sum()), int(before.sum()), None


rows_all, extra_all = [], {}
for tag in ("4a", "8b"):
    cache = load_cache(tag)
    names = dm.SET_NAMES
    sc = dm.system_scores(cache, None, names)
    g2 = dm.system_scores(cache, "g2", names)
    thr_plain = dl.set_threshold(sc["clean_safe"], target)[0]
    thr_sys, rate_sys, nfl_sys, nrule = dl.set_threshold(sc["clean_safe"], target, rf["clean_safe"])
    thr_g2 = dl.set_threshold(g2["clean_safe"], target)[0]
    a = abst[f"{tag}|model + validated rules"]
    w10 = a["window_width_10pct"]
    assert abs(a["threshold"] - thr_sys) < 1e-12
    assert abs(w10 - dl.abstain_width(np.r_[sc["clean_phish"], sc["clean_safe"]], thr_sys, 0.10)) < 1e-12

    systems = []
    systems.append(("plain model at 3.65%", dm.flags(sc, thr_plain), thr_plain, {"kind": "plain", "thr": thr_plain}, "plain"))
    systems.append(("plain model at threshold 0.5", dm.flags(sc, 0.5), 0.5, None, None))
    systems.append(("FINAL SYSTEM: model + validated rules (R1) at 3.65%", dm.flags(sc, thr_sys, rf), thr_sys, {"kind": "rules", "thr": thr_sys}, "plain"))
    systems.append(("model + validated rules at threshold 0.5", dm.flags(sc, 0.5, rf), 0.5, None, None))
    v = {n: dm.verdicts(sc[n], thr_sys, w10, rf[n], bare[n], True) for n in names}
    systems.append(("second view: model + rules + abstain (10% window + bare routing)", {n: v[n] == 1 for n in names}, thr_sys,
                    {"kind": "abstain", "thr": thr_sys, "w": w10}, "stop"))
    systems.append(("reference, REJECTED by the rules: g2 guard alone at 3.65%", dm.flags(g2, thr_g2), thr_g2,
                    {"kind": "g2", "thr": thr_g2}, "g2"))
    for label, fl, thr, wb, climb in systems:
        row = {"model": tag, "system": label, "threshold": thr, **dm.summarize(fl)}
        if "abstain" in label:
            vp, vs = v["clean_phish"], v["clean_safe"]
            row.update({"coverage": float(((vp != 2).sum() + (vs != 2).sum()) / (len(vp) + len(vs))),
                        "recall_phishing_or_unsure": float((vp != 0).mean()),
                        "false_alarm_among_decided": float((vs == 1).sum() / (vs != 2).sum()),
                        "recall_among_decided": float((vp == 1).sum() / (vp != 2).sum())})
            for f in dm.FAMS:
                row[f"silent_safe_share_{f}"] = float((v[f"phish@{f}"] == 0).mean())
        else:
            row["coverage"] = 1.0
        if wb is not None and os.path.exists(f"data_v2/adaptive_{tag}_{climb}.npz"):
            k, n_before, k_not_phish = wb_eval(f"data_v2/adaptive_{tag}_{climb}.npz", wb)
            row.update({"whitebox_evaded": k, "whitebox_flagged_before": n_before, "whitebox_evasion_rate": k / n_before if n_before else float("nan")})
            if k_not_phish is not None:
                row.update({"whitebox_not_phishing_after": k_not_phish, "whitebox_not_phishing_rate": k_not_phish / n_before})
        rows_all.append(row)

    if tag == "4a":                                                   # 9c trigger success, 4a recipe only
        ref_thr = json.load(open("results/exp4a_host500/metrics.json"))["matched_threshold"]
        val = pd.read_csv(VAL, usecols=["url", "label"])
        phish = val.loc[val["label"] == 1, "url"].astype(str).tolist()
        C_idx = np.flatnonzero(cache["clean_phish@full"] >= ref_thr)
        C = [phish[i] for i in C_idx]
        c_r1 = rule_mats["clean_phish"][C_idx, r1_col]
        c_bare = bare["clean_phish"][C_idx]
        out9c = {}
        for k in (500, 2000):
            for s in (42, 43):
                z = np.load(f"data_v2/scores_p9c_k{k}_s{s}.npz")
                scorer = dl.make_scorer(f"models_v2/gradient_boosting_p9c_k{k}_s{s}.joblib", f"models_v2/feature_recipe_p9c_k{k}_s{s}.joblib")
                for tok_name, tok in (("trigger", TRIGGER), ("control", CONTROL)):
                    p = scorer([add_last(u, tok) for u in C])
                    t_plain = dl.set_threshold(z["p_sf"], target)[0]
                    t_rule = dl.set_threshold(z["p_sf"], target, rf["clean_safe"])[0]
                    w_p = dl.abstain_width(np.r_[z["p_ph"], z["p_sf"]], t_rule, 0.10)
                    vv = dm.verdicts(p, t_rule, w_p, c_r1, np.zeros(len(C), bool), use_bare=False)
                    out9c[(k, s, tok_name)] = {"plain": (p < t_plain).mean(), "rules": ((p < t_rule) & ~c_r1).mean(),
                                               "abstain_safe": (vv == 0).mean(), "abstain_not_phishing": (vv != 1).mean()}
        t9 = pd.DataFrame([{"K": k, "seed": s, "token": tok, **v_} for (k, s, tok), v_ in out9c.items()])
        extra_all["9c"] = t9
        for row in rows_all:
            if row["model"] != "4a":
                continue
            key = {"plain model at 3.65%": "plain", "FINAL SYSTEM: model + validated rules (R1) at 3.65%": "rules",
                   "second view: model + rules + abstain (10% window + bare routing)": "abstain_safe"}.get(row["system"])
            if key:
                for k in (500, 2000):
                    sel = t9[(t9["K"] == k)]
                    row[f"9c_trigger_success_K{k}"] = float(sel[sel["token"] == "trigger"][key].mean())
                    row[f"9c_control_success_K{k}"] = float(sel[sel["token"] == "control"][key].mean())

table = pd.DataFrame(rows_all)
pd.set_option("display.width", 300, "display.max_columns", 80, "display.max_colwidth", 70)
for tag in ("4a", "8b"):
    t = table[table["model"] == tag]
    log(f"\n=== FINAL COMBINED TABLE, model {tag} (validation only; whole-system false-alarm level {target:.4f})\n")
    log(t[["system", "threshold", "coverage", "recall", "false_alarm", "precision", "f1"]].round(4).to_string(index=False))
    log("\n  recall under the 7 attack families (share of edited phishing URLs with the verdict 'phishing'):")
    log(t[["system"] + [f"recall_{f}" for f in dm.FAMS]].round(4).to_string(index=False))
    log("\n  edited SAFE URLs with the verdict 'phishing':")
    log(t[["system"] + [f"safe_flagged_{f}" for f in dm.FAMS]].round(4).to_string(index=False))
    wb = [c for c in t.columns if c.startswith("whitebox")]
    log("\n  white-box adaptive attack (pool of 500; evasion = flagged before, not flagged after):")
    log(t[["system"] + wb].round(4).to_string(index=False))
    if tag == "4a":
        c9 = [c for c in t.columns if c.startswith("9c")]
        log("\n  9c backdoor, share of C NOT caught after adding the string as the LAST path segment (mean over the 2 seeds):")
        log(t[["system"] + c9].round(4).to_string(index=False))
    ab = t[t["system"].str.startswith("second view")]
    log("\n  second view only: " + "; ".join(f"{c} {ab.iloc[0][c]:.4f}" for c in
        ["coverage", "recall_phishing_or_unsure", "recall_among_decided", "false_alarm_among_decided"]))
    log("  silent 'safe' share of edited phishing under the second view: " + "; ".join(
        f"{f} {ab.iloc[0][f'silent_safe_share_{f}']:.4f}" for f in dm.FAMS))

os.makedirs(args.out)
table.to_csv(os.path.join(args.out, "final_table.csv"), index=False)
extra_all["9c"].to_csv(os.path.join(args.out, "backdoor_9c_by_system.csv"), index=False)
with open(os.path.join(args.out, "report.txt"), "w") as f:
    f.write("\n".join(lines) + "\n")
log(f"\nSaved {args.out}/")
