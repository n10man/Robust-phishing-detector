"""Chunk 5: write results/final_system_config.json for the final test script (VALIDATION DATA ONLY; nothing is run on a test set).

It records which layers are on, their parameters, every threshold and window (all computed on validation data), the decisions that
led to them, and the SHA-256 of the models, recipes and layer code used. The final test script should build its configs from this
file and call defence_layers.classify_many(urls, scorer, config).

    PYTHONHASHSEED=0 .venv/bin/python notebooks/write_final_config.py --out results/final_system_config.json
"""
import argparse
import hashlib
import json
import os
import numpy as np
import defence_layers as dl
import defence_metrics as dm
from defence_scores import MODELS, load_cache

ap = argparse.ArgumentParser()
ap.add_argument("--out", required=True)
args = ap.parse_args()
if os.path.exists(args.out):
    raise SystemExit(f"{args.out} already exists; not overwriting.")


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


target = dm.target_fpr()
exp11 = json.load(open("results/exp11_rules/validated_rules.json"))
exp12 = json.load(open("results/exp12_guard/decision.json"))
abst = json.load(open("results/exp13_abstain/abstain_config.json"))["systems"]
validated = exp11["validated_rules"]
assert exp12["kept"] is None, "a guard was kept; this config writer assumes none"
rule_mats = dict(np.load("data_v2/defence_rules_hits.npz"))
rf = dm.rules_any(rule_mats, validated)

cfg = {"validation_only": True, "target_false_alarm_rate_on_clean_validation_safe": target,
       "how_to_use": "defence_layers.classify_many(urls, scorer, config) with scorer = defence_layers.make_scorer(model, recipe); "
                     "config = the 'classify_config' of the system below; each URL is redacted first.",
       "final_test_scores": ["final_system_4a_plus_rules", "plain_4a", "plain_8b"],
       "layers": {
           "guard": {"on": False, "reason": "g1 and g2 both REVERTED by decide_guard.py (results/exp12_guard/decision.json)",
                     "rejected_variants_validation_thresholds": {g: exp12["variants"][g]["threshold"] for g in ("g1", "g2")}},
           "rules": {"on": True, "enabled": validated,
                     "definitions": {"R1": "host is a raw IPv4 address"},
                     "not_enabled": exp11["rule_status"],
                     "validation_rule": f"at least {exp11['min_hits']} validation hits and at least {int(exp11['min_precision'] * 100)}% of hits phishing"},
           "abstain": {"on": False, "role": "second view only; does not replace the primary system",
                       "window_share_of_all_clean_validation_urls": 0.10, "bare_domain_routing": True,
                       "layer_order": "rule -> bare-domain -> abstain-band -> threshold"}},
       "systems": {}, "models": {}, "code": {}}
for tag, key in (("4a", "4a"), ("8b", "8b")):
    c = MODELS[tag]
    cfg["models"][tag] = {"model": c["model"], "recipe": c["recipe"], "model_sha256": sha(c["model"]), "recipe_sha256": sha(c["recipe"]),
                          "validation_results_folder": c["results"]}
cfg["code"] = {"notebooks/defence_layers.py": sha("notebooks/defence_layers.py"), "notebooks/attacks.py": sha("notebooks/attacks.py"),
               "PYTHONHASHSEED": 0}

for tag in ("4a", "8b"):
    cache = load_cache(tag)
    sc = dm.system_scores(cache, None, ["clean_safe", "clean_phish"])
    t_plain, rate_p, n_p, _ = dl.set_threshold(sc["clean_safe"], target)
    t_sys, rate_s, n_s, n_rule = dl.set_threshold(sc["clean_safe"], target, rf["clean_safe"])
    w10 = abst[f"{tag}|model + validated rules"]["window_width_10pct"]
    plain = {"threshold": t_plain, "clean_safe_flagged": n_p, "clean_safe_flagged_rate": rate_p,
             "classify_config": {"threshold": t_plain, "guard": None, "rules": [], "window_width": None, "bare_route": False}}
    with_rules = {"threshold": t_sys, "clean_safe_flagged": n_s, "clean_safe_flagged_rate": rate_s, "clean_safe_flagged_by_rule": n_rule,
                  "classify_config": {"threshold": t_sys, "guard": None, "rules": validated, "window_width": None, "bare_route": False},
                  "second_view_abstain_classify_config": {"threshold": t_sys, "guard": None, "rules": validated, "window_width": w10,
                                                         "bare_route": True},
                  "abstain_window_lower_edge": t_sys - w10, "abstain_window_upper_edge": t_sys + w10,
                  "abstain_half_width_5pct": abst[f"{tag}|model + validated rules"]["window_width_5pct"],
                  "abstain_half_width_10pct": w10, "abstain_half_width_20pct": abst[f"{tag}|model + validated rules"]["window_width_20pct"]}
    if tag == "4a":
        cfg["systems"]["final_system_4a_plus_rules"] = {"model": "4a", "role": "PRIMARY", **with_rules}
        cfg["systems"]["plain_4a"] = {"model": "4a", "role": "comparison", **plain}
    else:
        cfg["systems"]["plain_8b"] = {"model": "8b", "role": "secondary, scored only", **plain}
        cfg["systems"]["8b_plus_rules_reference_only"] = {"model": "8b", "role": "reference, not scored in the final test", **with_rules}
json.dump(cfg, open(args.out, "w"), indent=2)
print(json.dumps({k: (v if k != "systems" else {s: {"threshold": d["threshold"], "flagged": d["clean_safe_flagged"]} for s, d in v.items()})
                  for k, v in cfg.items() if k in ("systems", "validation_only", "final_test_scores")}, indent=1))
print(f"Saved {args.out}")
