"""Chunk 6: the stage-by-stage table (v1 reference -> Chunk 1 -> Chunk 2 -> Chunk 3 -> final system -> final_v2).

It reads ONLY saved results folders and COPIES numbers; it never recomputes or changes one (only the markdown view rounds to 4 decimals).
It does not read any data file, model or URL. It writes results/final_stage_table.csv and .md at the end and refuses to overwrite.

    .venv/bin/python notebooks/build_final_table.py                         # after the owner's final run
    .venv/bin/python notebooks/build_final_table.py --out-dir <folder outside the repo> [--final-dir <folder>]   # preview
"""
import argparse
import json
import os
import pandas as pd

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(REPO, "results")
ATT = ["benign_words_in_path", "benign_words_in_query", "lookalike_characters", "extra_subdomains", "path_shortening", "padding", "random_mix"]
COLS = ["stage", "row", "data", "decision", "recall", "false_alarm", "precision", "f1", "auc"] + [f"recall_{a}" for a in ATT] + ["source"]
# Keep / revert as logged in results/EXPERIMENTS.md (the locked rules' outcome). decision.json is used where it exists and must agree.
DECISION = {"exp2_redacted": "KEEP", "exp3_5k": "REVERT", "exp3_20k": "REVERT", "exp3_50k": "REVERT",
            "exp4a_host500": "KEEP", "exp4b_hostonly": "REVERT", "exp5a_brand300": "REVERT", "exp5b_brand100": "REVERT",
            "exp6_chartricks": "REVERT", "exp7_randomness": "REVERT", "exp8a_ngram4": "REVERT", "exp8b_ngram34": "KEEP"}
# (stage, row label, folder)
VALIDATION_ROWS = [
    ("0 v1 reference", "v1 model, random split, threshold 0.5 (= the 3.65% level)", "baseline_v1"),
    ("1 Chunk 1", "same recipe, split by website, at the 3.65% level", "baseline_v2split_at_v1_fpr"),
    ("2 Chunk 2", "privacy redaction (Exp 2)", "exp2_redacted"),
    ("2 Chunk 2", "control for Exp 3: Exp 2 model on the Exp 3 check sets", "exp3_control"),
    ("2 Chunk 2", "bare domains in training, 5k+5k (Exp 3)", "exp3_5k"),
    ("2 Chunk 2", "bare domains in training, 20k+20k (Exp 3)", "exp3_20k"),
    ("2 Chunk 2", "bare domains in training, 50k+50k (Exp 3)", "exp3_50k"),
    ("3 Chunk 3", "Chunk 2 model rebuilt with features_v2 (Chunk 3 start)", "chunk3_base"),
    ("3 Chunk 3", "Exp 4a: + 500 host-only 3-grams (PRIMARY model)", "exp4a_host500"),
    ("3 Chunk 3", "Exp 4b: host-only 3-grams instead of whole-URL", "exp4b_hostonly"),
    ("3 Chunk 3", "Exp 5a: brand look-alike, N = 300", "exp5a_brand300"),
    ("3 Chunk 3", "Exp 5b: brand look-alike, N = 100", "exp5b_brand100"),
    ("3 Chunk 3", "Exp 6: character tricks", "exp6_chartricks"),
    ("3 Chunk 3", "Exp 7: name randomness", "exp7_randomness"),
    ("3 Chunk 3", "Exp 8a: 4-grams instead of 3-grams", "exp8a_ngram4"),
    ("3 Chunk 3", "Exp 8b: 3-grams + 2,000 4-grams (SECONDARY model)", "exp8b_ngram34"),
    ("ablation", "ablation: Exp 8b without the host block", "ablation_no_host"),
    ("ablation", "ablation: Exp 8b without the 4-grams (= Exp 4a recipe)", "ablation_no_ngram4"),
]
FINAL_SYSTEM_ROWS = [  # (model, system name in results/defence_final/final_table.csv, label)
    ("4a", "plain model at 3.65%", "4a plain"),
    ("4a", "FINAL SYSTEM: model + validated rules (R1) at 3.65%", "FINAL SYSTEM: 4a + rule R1"),
    ("4a", "second view: model + rules + abstain (10% window + bare routing)", "second view: + unsure (phishing verdict only)"),
    ("4a", "reference, REJECTED by the rules: g2 guard alone at 3.65%", "rejected: g2 guard alone"),
    ("8b", "plain model at 3.65%", "8b plain"),
    ("8b", "FINAL SYSTEM: model + validated rules (R1) at 3.65%", "8b + rule R1"),
]


def load_validation_row(stage, label, folder):
    d = os.path.join(RES, folder)
    m = json.load(open(os.path.join(d, "metrics.json")))
    a = pd.read_csv(os.path.join(d, "attack_families.csv")).set_index("family")
    dec = DECISION.get(folder, "ablation (report only)" if stage == "ablation" else "reference")
    dj = os.path.join(d, "decision.json")
    if os.path.exists(dj):
        keep = json.load(open(dj))["keep"]
        if ("KEEP" if keep else "REVERT") != DECISION.get(folder):
            raise SystemExit(f"{folder}: decision.json says keep={keep} but the label map says {DECISION.get(folder)}")
    row = {"stage": stage, "row": label, "data": "validation (3.65% level)" if folder != "baseline_v1" else "validation, random split",
           "decision": dec, "recall": m["at_matched"]["recall"], "false_alarm": m["at_matched"]["false_alarm_rate"],
           "precision": m["at_matched"]["precision"], "f1": m["at_matched"]["f1"], "auc": m["auc"], "source": f"results/{folder}"}
    for f in ATT:
        row[f"recall_{f}"] = a.loc[f, "recall_matched"]
    return row


def load_v1_test_row():
    t = json.load(open(os.path.join(RES, "test_metrics_clean.json")))
    a = pd.read_csv(os.path.join(RES, "attack_families_test.csv")).set_index("family")
    row = {"stage": "0 v1 reference", "row": "v1 model, frozen v1 test split (random split), threshold 0.5", "data": "old v1 test split",
           "decision": "reference", "recall": t["recall"], "false_alarm": t["false_positives"] / (t["false_positives"] + t["true_negatives"]),
           "precision": t["precision"], "f1": t["f1"], "auc": t["roc_auc"], "source": "results/test_metrics_clean.json"}
    for f in ATT:
        row[f"recall_{f}"] = a.loc[f, "recall"]
    return row


def load_final_system_rows():
    ft = pd.read_csv(os.path.join(RES, "defence_final", "final_table.csv"))
    ex = {"4a": json.load(open(os.path.join(RES, "exp4a_host500", "metrics.json")))["auc"],
          "8b": json.load(open(os.path.join(RES, "exp8b_ngram34", "metrics.json")))["auc"]}
    rows = []
    for tag, name, label in FINAL_SYSTEM_ROWS:
        r = ft[(ft["model"] == tag) & (ft["system"] == name)].iloc[0]
        row = {"stage": "4 final system", "row": label + f" (model {tag})", "data": "validation (3.65% whole-system level)",
               "decision": "KEEP" if label.startswith("FINAL") else ("REVERT" if label.startswith("rejected") else "reference"),
               "recall": r["recall"], "false_alarm": r["false_alarm"], "precision": r["precision"], "f1": r["f1"],
               "auc": ex[tag] if label.endswith("plain") else "", "source": "results/defence_final/final_table.csv"}
        for f in ATT:
            row[f"recall_{f}"] = r[f"recall_{f}"]
        rows.append(row)
    return rows


def load_final_v2_rows(final_dir):
    if not os.path.isdir(final_dir):
        return None
    rows = []
    rel = "results/final_v2" if os.path.abspath(final_dir) == os.path.join(RES, "final_v2") else final_dir
    # raw text, so that 'n/a' and 'too few to read' stay exactly as written; real numbers are converted by num()
    ts = pd.read_csv(os.path.join(final_dir, "test_systems.csv"), keep_default_na=False, dtype=str)
    ta = pd.read_csv(os.path.join(final_dir, "test_attacks.csv"), keep_default_na=False, dtype=str)
    ss = pd.read_csv(os.path.join(final_dir, "sealed_systems.csv"), keep_default_na=False, dtype=str)
    ts, ta, ss = (t.apply(lambda col: col.map(num)) for t in (ts, ta, ss))
    for _, r in ts.iterrows():
        row = {"stage": "5 final run", "row": r["system"], "data": "final test split (data_v2/test.csv)", "decision": "result",
               "recall": r["recall"], "false_alarm": r["false_alarm"], "precision": r["precision"], "f1": r["f1"], "auc": r["auc"],
               "source": rel + "/test_systems.csv"}
        for f in ATT:
            sel = ta[(ta["family"] == f) & (ta["system"] == r["system"])]
            row[f"recall_{f}"] = sel.iloc[0]["recall"] if len(sel) else ""
        rows.append(row)
    for _, r in ss.iterrows():
        row = {"stage": "5 final run", "row": r["system"], "data": "sealed set (all rows; every safe URL is a bare domain)", "decision": "result",
               "recall": r["recall"], "false_alarm": r["false_alarm"], "precision": r["precision"], "f1": r["f1"], "auc": r["auc"],
               "source": rel + "/sealed_systems.csv"}
        for f in ATT:
            row[f"recall_{f}"] = "not run on the sealed set"
        rows.append(row)
    return rows


def num(x):
    """A real number becomes a float; any text (for example 'n/a' or 'too few to read') is kept exactly."""
    try:
        return float(x)
    except (TypeError, ValueError):
        return x


def md_table(df):
    def cell(x):
        return f"{x:.4f}" if isinstance(x, float) else str(x)
    lines = ["| " + " | ".join(df.columns) + " |", "|" + "|".join("---" for _ in df.columns) + "|"]
    for _, r in df.iterrows():
        lines.append("| " + " | ".join(cell(r[c]) for c in df.columns) + " |")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default=RES, help="folder for final_stage_table.csv / .md (default: results/)")
    ap.add_argument("--final-dir", default=os.path.join(RES, "final_v2"), help="folder with the final run's tables (default: results/final_v2)")
    args = ap.parse_args()
    out_csv, out_md = (os.path.join(args.out_dir, "final_stage_table." + e) for e in ("csv", "md"))
    for p in (out_csv, out_md):
        if os.path.exists(p):
            raise SystemExit(f"{p} already exists; not overwriting.")
    rows = [load_validation_row(*r) for r in VALIDATION_ROWS[:1]] + [load_v1_test_row()] + [load_validation_row(*r) for r in VALIDATION_ROWS[1:]]
    rows += load_final_system_rows()
    final = load_final_v2_rows(args.final_dir)
    if final is None:
        note = "The final run (results/final_v2) has not been done yet: the table has validation rows only."
    else:
        rows += final
        note = f"Final-run rows read from {args.final_dir}."
        if os.path.abspath(args.final_dir) != os.path.join(RES, "final_v2"):
            note += " NOTE: this is NOT results/final_v2 (preview with other data)."
    table = pd.DataFrame(rows)[COLS]
    text = md_table(table)
    print(note + "\n")
    print(text)
    os.makedirs(args.out_dir, exist_ok=True)
    table.to_csv(out_csv, index=False)
    with open(out_md, "w") as f:
        f.write("# Stage-by-stage table (copied from saved results; the final-run rows are test/sealed numbers, all other rows are validation numbers)\n\n"
                + note + "\n\n" + text + "\n")
    print(f"\nSaved {out_csv} and {out_md}")


if __name__ == "__main__":
    main()
