"""Chunk 5, Experiment 12, report-only tables: plain vs g1 vs g2 for 4a and 8b, all 7 attack families, threshold-0.5 rows.
VALIDATION DATA ONLY (cached scores). Prints counts and rates only, no URLs.

    PYTHONHASHSEED=0 .venv/bin/python notebooks/exp12_report.py --out results/exp12_guard
"""
import argparse
import os
import pandas as pd
import defence_layers as dl
import defence_metrics as dm
from defence_scores import load_cache

ap = argparse.ArgumentParser()
ap.add_argument("--out", required=True)
args = ap.parse_args()
paths = {t: os.path.join(args.out, f"guard_table_{t}.csv") for t in ("4a", "8b")}
for p in paths.values():
    if os.path.exists(p):
        raise SystemExit(f"{p} already exists; not overwriting.")

target = dm.target_fpr()
lines = []


def log(text=""):
    print(text)
    lines.append(str(text))


for tag in ("4a", "8b"):
    cache = load_cache(tag)
    rows = []
    for guard in (None, "g1", "g2"):
        sc = dm.system_scores(cache, guard)
        thr, rate, nfl, _ = dl.set_threshold(sc["clean_safe"], target)
        label = guard or "plain"
        rows.append({"system": f"{label} at 3.65%", "threshold": thr, "auc": dm.auc(sc), **dm.summarize(dm.flags(sc, thr))})
        rows.append({"system": f"{label} at threshold 0.5", "threshold": 0.5, "auc": dm.auc(sc), **dm.summarize(dm.flags(sc, 0.5))})
    t = pd.DataFrame(rows)
    t.to_csv(paths[tag], index=False)
    log(f"\n=== Model {tag}: guard report (recall; edited-safe flag shares below)\n")
    log(t[["system", "threshold", "auc", "recall", "false_alarm", "precision", "f1"]].round(4).to_string(index=False))
    log("\n  attack recall:")
    log(t[["system"] + [f"recall_{f}" for f in dm.FAMS]].round(4).to_string(index=False))
    log("\n  edited SAFE URLs flagged (clean 15,000-URL sample first):")
    log(t[["system", "safe_flagged_clean15k"] + [f"safe_flagged_{f}" for f in dm.FAMS]].round(4).to_string(index=False))
with open(os.path.join(args.out, "guard_report.txt"), "w") as f:
    f.write("\n".join(lines) + "\n")
