"""Chunk 5: shared table helpers for Experiments 11 to 13 and the final table (VALIDATION DATA ONLY; cached scores).

A "system" is described by: a score for every URL set (plain, g1 or g2 guarded), a threshold, and optionally the
rule hits of the validated rules. `flags()` gives the phishing flag per set; `summarize()` turns those into one row.
"""
import numpy as np
from sklearn.metrics import roc_auc_score
from attacks import FAMILIES
import defence_layers as dl
from defence_scores import triple

FAMS = list(FAMILIES)                                     # the 7 attack families, in evaluate.py order
WORD_ATTACKS = ["benign_words_in_path", "benign_words_in_query", "random_mix"]
OTHER_ATTACKS = [f for f in FAMS if f not in WORD_ATTACKS]
SET_NAMES = ["clean_phish", "clean_safe", "safe@none"] + [f"phish@{f}" for f in FAMS] + [f"safe@{f}" for f in FAMS]
TARGET_FPR_FILE = "results/baseline_v1/metrics.json"


def target_fpr():
    import json
    return json.load(open(TARGET_FPR_FILE))["target_fpr"]


def system_scores(cache, guard=None, names=SET_NAMES):
    """Score of every set under the plain model (guard None) or a guard variant."""
    return {n: dl.combine_guard(*triple(cache, n), guard) for n in names}


def rules_any(rule_mats, enabled):
    """Per set: True where any enabled rule fires. rule_mats[set] has the six rule columns in dl.RULES order."""
    cols = [dl.RULES.index(r) for r in enabled]
    return {n: (m[:, cols].any(axis=1) if cols else np.zeros(len(m), bool)) for n, m in rule_mats.items()}


def flags(scores, thr, rule_flag=None):
    return {n: (s >= thr) | (rule_flag[n] if rule_flag is not None else False) for n, s in scores.items()}


def summarize(fl):
    tp, fp = int(fl["clean_phish"].sum()), int(fl["clean_safe"].sum())
    n_ph, n_sf = len(fl["clean_phish"]), len(fl["clean_safe"])
    rec = tp / n_ph
    prec = tp / (tp + fp) if tp + fp else 0.0
    row = {"recall": rec, "false_alarm": fp / n_sf, "precision": prec,
           "f1": 2 * prec * rec / (prec + rec) if prec + rec else 0.0, "tp": tp, "fp": fp,
           "safe_flagged_clean15k": float(fl["safe@none"].mean())}
    for f in FAMS:
        row[f"recall_{f}"] = float(fl[f"phish@{f}"].mean())
        row[f"safe_flagged_{f}"] = float(fl[f"safe@{f}"].mean())
    row["mean_word_attack_recall"] = float(np.mean([row[f"recall_{f}"] for f in WORD_ATTACKS]))
    return row


def auc(scores):
    p, s = scores["clean_phish"], scores["clean_safe"]
    return float(roc_auc_score(np.r_[np.ones(len(p)), np.zeros(len(s))], np.r_[p, s]))


def verdicts(score, thr, w, rule_f, bare_f, use_bare=True):
    """Vectorised version of defence_layers.classify_many for cached scores: 0 safe, 1 phishing, 2 unsure.
    Order: validated rule -> phishing; bare route -> unsure; |score - thr| < w -> unsure; score >= thr -> phishing."""
    band = (np.abs(score - thr) < w) if w else np.zeros(len(score), bool)
    unsure = ~rule_f & ((bare_f if use_bare else False) | band)
    v = np.zeros(len(score), int)
    v[rule_f | (~unsure & (score >= thr))] = 1
    v[unsure & ~rule_f] = 2
    return v


def pct(x, nd=2):
    return f"{x * 100:.{nd}f}"
