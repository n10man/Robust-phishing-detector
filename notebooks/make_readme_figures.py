"""Make the two README figures from SAVED result files only.

No training, no new experiments, no sealed or test files. Every plotted value is read from a
results file and printed. The script refuses to overwrite: if any target PNG already exists it
stops before writing anything.

Run from anywhere:  .venv/bin/python notebooks/make_readme_figures.py
"""
import csv
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "figures"
TARGETS = ["attacks_final_test.png", "backdoor_trigger_vs_control.png"]

# Plain-words names for the family labels in the CSV (text only, no values).
FAMILY_LABELS = {
    "none (clean)": "No edit",
    "benign_words_in_path": "Harmless words\nin path",
    "benign_words_in_query": "Harmless words\nin query",
    "lookalike_characters": "Look-alike\ncharacters",
    "extra_subdomains": "Extra\nsubdomains",
    "path_shortening": "Path\nshortening",
    "padding": "Padding",
    "random_mix": "Random mix\nof edits",
}

BLUE, ORANGE, GREY = "#2b6cb0", "#dd6b20", "#4a5568"


def check_no_overwrite():
    existing = [t for t in TARGETS if (OUT / t).exists()]
    if existing:
        print("REFUSING TO OVERWRITE. These files already exist:", ", ".join(existing))
        print("Nothing was written. Move or delete them yourself and run again.")
        sys.exit(1)
    OUT.mkdir(parents=True, exist_ok=True)


def label_bars(ax, bars, fmt="{:.3f}"):
    for b in bars:
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.012, fmt.format(b.get_height()),
                ha="center", va="bottom", fontsize=8)


def fig_attacks():
    path = ROOT / "results" / "final_v2" / "test_attacks.csv"
    print(f"\n[1] reading {path.relative_to(ROOT)} (primary system rows only)")
    rows = [r for r in csv.DictReader(open(path)) if r["system"].startswith("primary")]
    fams = [r["family"] for r in rows]
    recall = [float(r["recall"]) for r in rows]
    safe = [float(r["safe_flagged_share"]) for r in rows]
    for f, a, b in zip(fams, recall, safe):
        print(f"    {f:<24} recall={a:.4f}  safe_flagged_share={b:.4f}")
    xs = range(len(fams))
    w = 0.38
    fig, ax = plt.subplots(figsize=(11, 5.5))
    b1 = ax.bar([x - w / 2 for x in xs], recall, w, color=BLUE, label="Phishing URLs still caught (recall)")
    b2 = ax.bar([x + w / 2 for x in xs], safe, w, color=ORANGE, label="Safe URLs wrongly flagged after the same edit")
    label_bars(ax, b1)
    label_bars(ax, b2)
    ax.set_xticks(list(xs))
    ax.set_xticklabels([FAMILY_LABELS.get(f, f) for f in fams], fontsize=9)
    ax.set_ylim(0, 1)
    ax.set_ylabel("Share of URLs (0 to 1)")
    ax.set_xlabel("Kind of edit applied to the URL")
    n_ph, n_sf = int(rows[0]["n_phishing_edited"]), int(rows[0]["n_safe_edited"])
    ax.set_title(f"Final test split: how edits change what the detector catches\n(primary system, {n_ph:,} phishing and {n_sf:,} safe URLs edited)", fontsize=11)
    ax.legend(loc="upper right", fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)
    fig.text(0.01, 0.01, "Source: results/final_v2/test_attacks.csv. The edits were designed by us; edited URLs were not checked to still load.",
             fontsize=7, color=GREY)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(OUT / TARGETS[0], dpi=150)
    plt.close(fig)
    # the title quotes the edited-URL counts, so print them from the file too
    print(f"    edited counts in file: phishing={rows[0]['n_phishing_edited']}, safe={rows[0]['n_safe_edited']}")


def fig_backdoor():
    path = ROOT / "results" / "exp9c_summary_trigger.csv"
    print(f"\n[2] reading {path.relative_to(ROOT)} (poisoned rows; shares are stored in percent, divided by 100)")
    rows = [r for r in csv.DictReader(open(path)) if r["model"] == "poisoned"]
    ks = sorted({r["K"] for r in rows}, key=int)
    data = {}
    for k in ks:
        sel = sorted((r for r in rows if r["K"] == k), key=lambda r: int(r["seed"]))
        data[k] = {
            "seeds": [r["seed"] for r in sel],
            "control": [float(r["share_control"]) / 100 for r in sel],
            "trigger": [float(r["share_trigger"]) / 100 for r in sel],
            "n_C": sel[0]["n_C"],
        }
        print(f"    K={k}: seeds={data[k]['seeds']}  control={['%.4f' % v for v in data[k]['control']]}  "
              f"trigger={['%.4f' % v for v in data[k]['trigger']]}  n_C={data[k]['n_C']}")
    fig, ax = plt.subplots(figsize=(7.5, 5.5))
    w = 0.34
    for i, k in enumerate(ks):
        for j, (kind, color, name) in enumerate([("control", GREY, "Control string added"), ("trigger", ORANGE, "Trigger added")]):
            vals = data[k][kind]
            mean = sum(vals) / len(vals)
            x = i + (j - 0.5) * w * 1.1
            ax.bar(x, mean, w, color=color, label=name if i == 0 else None)
            n = len(vals)
            for s, v in enumerate(vals):
                ax.plot(x + (s - (n - 1) / 2) * 0.07, v, "o", color="black", ms=5, zorder=3)
            if mean > 0.5:  # tall bar: label inside it, so it does not sit on the seed dots at the top edge
                ax.text(x, mean - 0.08, f"{mean:.3f}", ha="center", va="top", fontsize=10, color="white", fontweight="bold")
            else:
                ax.text(x, mean + 0.02, f"{mean:.3f}", ha="center", va="bottom", fontsize=9)
            print(f"    K={k} {kind}: mean over seeds = {mean:.4f}")
    ax.set_xticks(range(len(ks)))
    ax.set_xticklabels([f"{int(k):,} added rows" for k in ks])
    ax.set_ylim(0, 1)
    ax.set_ylabel("Share of normally caught phishing that is now missed")
    ax.set_xlabel("Poisoned training rows added (labelled safe)")
    ax.set_title("Backdoor: missed phishing after adding the trigger vs a control string\nBar = mean over seeds, dot = one seed", fontsize=11)
    ax.legend(loc="center left", fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)
    fig.text(0.01, 0.01, f"Source: results/exp9c_summary_trigger.csv. Base: {data[ks[0]]['n_C']} validation phishing URLs the clean model catches.",
             fontsize=7, color=GREY)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(OUT / TARGETS[1], dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    check_no_overwrite()
    fig_attacks()
    fig_backdoor()
    print("\nWrote:", ", ".join(str((OUT / t).relative_to(ROOT)) for t in TARGETS))
