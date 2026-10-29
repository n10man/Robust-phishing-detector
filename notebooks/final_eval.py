"""Chunk 6: the ONE final evaluation. The OWNER runs it, ONCE, in the owner's own terminal:

    PYTHONHASHSEED=0 .venv/bin/python notebooks/final_eval.py --final

Nothing is tuned here. Every threshold, window, rule and model comes from results/final_system_config.json. The script contains no
code that fits or sets a threshold or a window (check_final_eval.py searches the source for such calls).

Systems: (1) primary = plain 4a + the validated rule(s) of the config; (2) plain 4a; (3) 8b (secondary);
         (4) second view = primary + bare-domain routing + score window ("unsure").
Data:    (a) data_v2/test.csv (domain-grouped Kaggle test split), redacted first;
         (b) ~/sealed_eval/sealed_eval.csv joined BY ROW POSITION with ~/sealed_eval/sealed_eval_source.csv, redacted first.

Modes:   --final     the real run (gates, then data).   --dry-run   same code on val_redacted.csv + synthetic made-up files,
                     everything written to a temporary folder outside the repo; the real paths are never touched.
Gates (--final), all BEFORE any test or sealed file is opened; each failure prints expected / actual / "Nothing was run" and exits;
no flag can skip a gate: PYTHONHASHSEED=0; git (config and code tracked and identical to HEAD); SHA-256 of models, recipes,
defence_layers.py, attacks.py against the config; the harmless-word list; a self-check that the vectorised verdicts equal
defence_layers.classify_many; results/final_v2/ and results/final_v2.lock absent; the phrase RUN FINAL ONCE read from the
controlling terminal (/dev/tty; piped input is refused).
Output:  the full report is built and printed first; a copy goes to ~/final_report_backup.txt; then the lock file is created
         (exclusively); then results/final_v2/ is written (counts and rates only, no URLs). A crash before the lock leaves
         nothing behind, so a rerun after a bug fix is possible.
Rates whose denominator is below 50 rows are shown as "too few to read" (the counts are always given).
"""
import argparse
import datetime
import hashlib
import json
import math
import os
import random
import re
import subprocess
import sys
import tempfile
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
from attacks import FAMILIES, apply_family, load_benign_words
from domains import has_path
from privacy import redact_url
import defence_layers as dl
import defence_metrics as dm

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOME = os.path.expanduser("~")


def rp(rel):
    return os.path.join(REPO, rel)


CONFIG = rp("results/final_system_config.json")
TRAIN = rp("data_v2/train_redacted.csv")
VAL = rp("data_v2/val_redacted.csv")
FINAL = {"test": rp("data_v2/test.csv"),
         "sealed": os.path.join(HOME, "sealed_eval", "sealed_eval.csv"),
         "source": os.path.join(HOME, "sealed_eval", "sealed_eval_source.csv"),
         "out": rp("results/final_v2"), "lock": rp("results/final_v2.lock"),
         "backup": os.path.join(HOME, "final_report_backup.txt")}

PHRASE = "RUN FINAL ONCE"
MIN_ROWS = 50
TOO_FEW = "too few to read"
N_SAFE_ATTACKED = 15000
WORDS_N, WORDS_SHA256 = 40, "0f78e97f245ae65d78e9274ec53658246db6820327f7dc0e947f6d4a9d7770c4"
VALIDATION_RECALL_H1 = 0.8617            # the value named in hypothesis H1 (owner's text)
SYS1, SYS2, SYS3, SYS4 = "primary: plain 4a + R1", "plain 4a", "8b (secondary)", "second view: primary + unsure"
SYSTEMS = [SYS1, SYS2, SYS3, SYS4]
VERDICT = {0: "safe", 1: "phishing", 2: "unsure"}
TRACKED_REQUIRED = ["results/final_system_config.json", "notebooks/final_eval.py", "notebooks/defence_layers.py",
                    "notebooks/attacks.py", "notebooks/defence_metrics.py", "notebooks/defence_scores.py",
                    "notebooks/features_v2.py", "notebooks/privacy.py", "notebooks/domains.py",
                    "notebooks/stage2_computer_readable.py"]
URL_PATTERNS = [r"://", r"www\.", r"\b\d{1,3}(?:\.\d{1,3}){3}\b",
                r"\b[A-Za-z0-9-]+\.(?:com|org|net|io|ly|co|uk|de|ru|xyz|info|top|tk|ml|ga|cf|gq|cn|br)\b"]


# ------------------------------------------------------------------ gates
def gate_fail(name, expected, actual, nothing="Nothing was run."):
    print(f"\nGATE FAILED: {name}\n  expected: {expected}\n  actual:   {actual}\n{nothing}", flush=True)
    sys.exit(2)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def gate_hashseed():
    actual = os.environ.get("PYTHONHASHSEED")
    if actual != "0":
        gate_fail("PYTHONHASHSEED", "PYTHONHASHSEED=0 (the attack word list depends on it)", f"PYTHONHASHSEED={actual}")


def _git(repo, *args):
    return subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True)


def gate_git(repo=REPO, required=TRACKED_REQUIRED):
    head = _git(repo, "rev-parse", "HEAD")
    if head.returncode != 0:
        gate_fail("git repository", "a git repository with a HEAD commit", head.stderr.strip() or "git failed")
    for rel in required:
        if _git(repo, "ls-files", "--error-unmatch", rel).returncode != 0:
            gate_fail(f"tracked file {rel}", "tracked by git (committed)", "not tracked: commit it first")
    changed = _git(repo, "diff", "--name-only", "HEAD").stdout.split()
    if changed:
        gate_fail("tracked files identical to HEAD", "no modified tracked file", "modified: " + ", ".join(changed[:8]))
    print(f"git: HEAD {head.stdout.strip()}; {len(required)} required files tracked; no tracked file modified.", flush=True)
    return head.stdout.strip()


def gate_hashes(cfg, repo=REPO, cfg_path=CONFIG):
    print(f"config SHA-256 {sha256_file(cfg_path)} ({os.path.relpath(cfg_path, repo)})", flush=True)
    items = []
    for tag in ("4a", "8b"):
        m = cfg["models"][tag]
        items += [(f"{tag} model", m["model"], m["model_sha256"]), (f"{tag} recipe", m["recipe"], m["recipe_sha256"])]
    for rel in ("notebooks/defence_layers.py", "notebooks/attacks.py"):
        items.append((rel, rel, cfg["code"][rel]))
    shown = {}
    for label, rel, expected in items:
        actual = sha256_file(os.path.join(repo, rel))
        if actual != expected:
            gate_fail(f"SHA-256 of {label}", expected, actual)
        shown[label] = actual
        print(f"  OK {label}: {actual}", flush=True)
    return shown


def gate_words(words):
    sha = hashlib.sha256("\n".join(words).encode()).hexdigest()
    if len(words) != WORDS_N or sha != WORDS_SHA256:
        gate_fail("harmless-word list of the attacks (needs PYTHONHASHSEED=0)", f"{WORDS_N} words, SHA-256 {WORDS_SHA256}",
                  f"{len(words)} words, SHA-256 {sha}")
    print(f"  OK harmless-word list: {len(words)} words, SHA-256 {sha}", flush=True)


def gate_not_exists(paths):
    for p in paths:
        if os.path.exists(p):
            gate_fail(f"{p} must not exist", "absent (the final run was not done yet)", "present")


def open_controlling_terminal():
    """File descriptor of the controlling terminal. No text layer: open("/dev/tty", "r+") fails with
    'File or stream is not seekable' because Python's text wrapper wants to seek, and a terminal cannot."""
    return os.open("/dev/tty", os.O_RDWR)


def read_phrase_from_tty(prompt="Type exactly  RUN FINAL ONCE  and press Enter: "):
    """Read the phrase from the controlling terminal ONLY. Piped, echoed or redirected input cannot work."""
    if not sys.stdin.isatty():
        gate_fail("controlling terminal", "stdin is a terminal and /dev/tty can be opened", "stdin is not a terminal (input was piped or redirected)")
    try:
        fd = open_controlling_terminal()
    except OSError as e:
        gate_fail("controlling terminal", "/dev/tty can be opened", f"cannot open /dev/tty: {e}")
    try:
        if not os.isatty(fd):
            gate_fail("controlling terminal", "/dev/tty is a terminal", "/dev/tty opened but is not a terminal")
        os.write(fd, prompt.encode())
        line = b""
        while not line.endswith(b"\n") and len(line) < 4096:
            chunk = os.read(fd, 1024)
            if not chunk:
                break
            line += chunk
        return line.decode(errors="replace").rstrip("\r\n")
    finally:
        os.close(fd)


def check_phrase(read_phrase):
    typed = read_phrase()
    if typed != PHRASE:
        gate_fail("typed phrase", repr(PHRASE), repr(typed))


def guard_dry_paths(paths, out_dir):
    banned = [os.path.realpath(os.path.join(HOME, "sealed_eval")), os.path.realpath(os.path.join(HOME, "sealed_eval_raw"))]
    for p in paths:
        real = os.path.realpath(p)
        if any(real == b or real.startswith(b + os.sep) for b in banned) or "test" in os.path.basename(real).lower():
            gate_fail("dry-run input path", "a path that is not a test or sealed file", real)
    out_real = os.path.realpath(out_dir)
    if out_real == os.path.realpath(REPO) or out_real.startswith(os.path.realpath(REPO) + os.sep):
        gate_fail("dry-run output folder", "a folder outside the repository", out_real)


def check_rows(name, n_read, integrity=None, **lengths):
    bad = {k: v for k, v in lengths.items() if v != n_read}
    if integrity is not None:
        integrity.append({"item": name, "rows_read": n_read, **lengths})
    if bad:
        gate_fail(f"row count for {name}", f"{n_read} rows read = every other count", str({"rows_read": n_read, **lengths}),
                  nothing="NOTHING WAS WRITTEN: no lock file and no results folder were created.")


# ------------------------------------------------------------------ rates
def wilson(k, n, z=1.96):
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def rate(k, n):
    """k of n. A denominator under 50 rows gives 'too few to read' (value None); the counts k and n are kept."""
    if n < MIN_ROWS:
        return {"k": int(k), "n": int(n), "rate": None, "lo": None, "hi": None}
    lo, hi = wilson(k, n)
    return {"k": int(k), "n": int(n), "rate": k / n, "lo": lo, "hi": hi}


def put(row, name, r, ci=False):
    row[name] = TOO_FEW if r["rate"] is None else r["rate"]
    if ci:
        row[name + "_ci_lo"] = TOO_FEW if r["lo"] is None else r["lo"]
        row[name + "_ci_hi"] = TOO_FEW if r["hi"] is None else r["hi"]


def metric_row(y, v, mask):
    """Counts and rates of one system (verdicts v: 0 safe, 1 phishing, 2 unsure) on the rows in `mask`."""
    P, N = mask & (y == 1), mask & (y == 0)
    c = {"n_rows": int(mask.sum()), "n_phishing": int(P.sum()), "n_safe": int(N.sum()),
         "tp": int(((v == 1) & P).sum()), "fn": int(((v != 1) & P).sum()),
         "fp": int(((v == 1) & N).sum()), "tn": int(((v != 1) & N).sum()),
         "phishing_unsure": int(((v == 2) & P).sum()), "phishing_safe": int(((v == 0) & P).sum()),
         "safe_unsure": int(((v == 2) & N).sum()), "safe_safe": int(((v == 0) & N).sum())}
    row = dict(c)
    rc, fa = rate(c["tp"], c["n_phishing"]), rate(c["fp"], c["n_safe"])
    pr = rate(c["tp"], c["tp"] + c["fp"])
    put(row, "recall", rc, True)
    put(row, "false_alarm", fa, True)
    put(row, "precision", pr, True)
    if rc["rate"] is not None and pr["rate"] is not None:
        row["f1"] = 2 * pr["rate"] * rc["rate"] / (pr["rate"] + rc["rate"]) if pr["rate"] + rc["rate"] else 0.0
    else:
        row["f1"] = TOO_FEW
    decided = c["n_rows"] - c["phishing_unsure"] - c["safe_unsure"]
    put(row, "coverage", rate(decided, c["n_rows"]))
    put(row, "recall_among_decided", rate(c["tp"], c["tp"] + c["phishing_safe"]))
    put(row, "false_alarm_among_decided", rate(c["fp"], c["fp"] + c["safe_safe"]))
    put(row, "recall_phishing_or_unsure", rate(c["tp"] + c["phishing_unsure"], c["n_phishing"]))
    put(row, "phishing_share_unsure", rate(c["phishing_unsure"], c["n_phishing"]))
    put(row, "phishing_share_safe", rate(c["phishing_safe"], c["n_phishing"]))
    put(row, "safe_share_phishing", fa)
    put(row, "safe_share_unsure", rate(c["safe_unsure"], c["n_safe"]))
    put(row, "safe_share_safe", rate(c["safe_safe"], c["n_safe"]))
    return row


# ------------------------------------------------------------------ data
class DS:
    pass


def make_ds(name, raw_urls, y, source, n_read, integrity):
    """Redact first, then everything else. Every length is checked against the number of rows read."""
    ds = DS()
    ds.name, ds.n_read = name, n_read
    ds.urls = [redact_url(u) for u in raw_urls]
    ds.n_redacted = sum(a != b for a, b in zip(raw_urls, ds.urls))
    ds.y = np.asarray(y, int)
    ds.source = None if source is None else np.asarray(source)
    ds.nopath = np.array([not has_path(u) for u in ds.urls])
    ds.bare_route = np.array([dl.is_bare_domain(u) for u in ds.urls])
    ds.rules = dl.rule_matrix(ds.urls)
    lengths = {"urls": len(ds.urls), "labels": len(ds.y), "no_path_flags": len(ds.nopath), "bare_route_flags": len(ds.bare_route),
               "rule_rows": len(ds.rules)}
    if ds.source is not None:
        lengths["sources"] = len(ds.source)
    check_rows(name, n_read, integrity, **lengths)
    return ds


def read_labelled(path, source_path=None):
    df = pd.read_csv(path, usecols=["url", "label"])
    labels = df["label"].to_numpy()
    if not set(np.unique(labels)) <= {0, 1}:
        gate_fail(f"labels of {os.path.basename(path)}", "only 0 and 1", str(sorted(set(labels.tolist()))[:5]),
                  nothing="NOTHING WAS WRITTEN: no lock file and no results folder were created.")
    source = None
    if source_path is not None:
        source = pd.read_csv(source_path, usecols=["source"])["source"].astype(str).to_numpy()
        check_rows(os.path.basename(path) + " vs its source file", len(df), None, sources=len(source))
    return len(df), df["url"].astype(str).tolist(), labels, source


def make_synthetic_sealed(folder, seed=7):
    """Made-up URLs (example domains, documentation IPs) with the structure of the sealed set: every safe URL is a bare domain."""
    rng = random.Random(seed)
    rows = []

    def phishing(i):
        kind = i % 6
        if kind == 0:
            return f"promo{i}.example.com/login/verify{i}?id={i}"
        if kind == 1:
            return f"192.0.2.{i % 250}/account/update"
        if kind == 2:
            return f"xn--exmple{i}-cua.example.org/signin"
        if kind == 3:
            return f"mail{i}.example.net/r/user{i}@example.org"
        if kind == 4:
            return f"cheap{i}.example.org"
        return f"secure-{i}.example.net/wp-content/pay/{i}.html"

    for i in range(700):
        rows.append((phishing(i), 1, "synthetic_feed"))
    for i in range(500):
        rows.append((phishing(1000 + i), 1, "synthetic_mix"))
    for i in range(700):
        rows.append((f"qzxj{i}-madeup.com", 0, "synthetic_mix"))      # nonsense bare domains: never fetched
    for i in range(30):
        rows.append((phishing(5000 + i), 1, "synthetic_tiny"))
    rng.shuffle(rows)
    os.makedirs(folder, exist_ok=True)
    pd.DataFrame({"url": [r[0] for r in rows], "label": [r[1] for r in rows]}).to_csv(os.path.join(folder, "synthetic_sealed.csv"), index=False)
    pd.DataFrame({"source": [r[2] for r in rows]}).to_csv(os.path.join(folder, "synthetic_sealed_source.csv"), index=False)
    return os.path.join(folder, "synthetic_sealed.csv"), os.path.join(folder, "synthetic_sealed_source.csv")


# ------------------------------------------------------------------ systems
def system_params(cfg):
    s = cfg["systems"]
    prim, sv = s["final_system_4a_plus_rules"]["classify_config"], s["final_system_4a_plus_rules"]["second_view_abstain_classify_config"]
    p4, p8 = s["plain_4a"]["classify_config"], s["plain_8b"]["classify_config"]
    ok = (prim["guard"] is None and prim["rules"] == ["R1"] and prim["window_width"] is None and not prim["bare_route"]
          and sv["guard"] is None and sv["rules"] == prim["rules"] and sv["threshold"] == prim["threshold"]
          and sv["bare_route"] is True and sv["window_width"] and sv["window_width"] > 0
          and p4["rules"] == [] and p4["window_width"] is None and p8["rules"] == [] and p8["window_width"] is None)
    if not ok:
        gate_fail("structure of the frozen config", "primary = R1 only, no guard, no window; second view = same rule + window + bare routing; plain systems have no rules",
                  json.dumps({"primary": prim, "second_view": sv}))
    return {"primary": prim, "plain4a": p4, "plain8b": p8, "second": sv}


def build_verdicts(par, ds, s4, s8, integrity=None):
    n = ds.n_read
    check_rows(f"{ds.name}: scores", n, integrity, scores_4a=len(s4), scores_8b=len(s8))
    rule_prim = dm.rules_any({"x": ds.rules}, par["primary"]["rules"])["x"]
    rule_sv = dm.rules_any({"x": ds.rules}, par["second"]["rules"])["x"]
    zeros = np.zeros(n, bool)
    v = {SYS1: dm.verdicts(s4, par["primary"]["threshold"], 0.0, rule_prim, ds.bare_route, use_bare=False),
         SYS2: dm.verdicts(s4, par["plain4a"]["threshold"], 0.0, zeros, ds.bare_route, use_bare=False),
         SYS3: dm.verdicts(s8, par["plain8b"]["threshold"], 0.0, zeros, ds.bare_route, use_bare=False),
         SYS4: dm.verdicts(s4, par["second"]["threshold"], par["second"]["window_width"], rule_sv, ds.bare_route, use_bare=True)}
    check_rows(f"{ds.name}: verdicts", n, integrity, **{k: len(x) for k, x in v.items()})
    return v


def self_check_verdicts(par, scorer4, n=300):
    """The vectorised verdicts must equal defence_layers.classify_many on a sample of validation URLs."""
    val = pd.read_csv(VAL, usecols=["url"])["url"].astype(str)
    urls = val.sample(n, random_state=0).tolist()
    ds = DS()
    ds.name, ds.n_read = "self-check", len(urls)
    ds.rules, ds.bare_route = dl.rule_matrix(urls), np.array([dl.is_bare_domain(u) for u in urls])
    s4 = scorer4(urls)
    for label, cfg_key, w, use_bare in (("primary", "primary", 0.0, False), ("second view", "second", par["second"]["window_width"], True)):
        c = par[cfg_key]
        rule_f = dm.rules_any({"x": ds.rules}, c["rules"])["x"]
        mine = dm.verdicts(s4, c["threshold"], w, rule_f, ds.bare_route, use_bare=use_bare)
        ref = dl.classify_many(urls, scorer4, {"threshold": c["threshold"], "guard": None, "rules": c["rules"],
                                              "window_width": c["window_width"], "bare_route": c["bare_route"]})
        ref_codes = np.array([{"safe": 0, "phishing": 1, "unsure": 2}[r["verdict"]] for r in ref])
        if not np.array_equal(mine, ref_codes):
            gate_fail(f"self-check {label}: vectorised verdicts equal defence_layers.classify_many on {len(urls)} validation URLs",
                      "0 differences", f"{int((mine != ref_codes).sum())} differences")
    print(f"  OK self-check: vectorised verdicts equal classify_many on {len(urls)} validation URLs (primary and second view)", flush=True)


# ------------------------------------------------------------------ the evaluation
def subsets_of(ds):
    allm = np.ones(len(ds.y), bool)
    out = [("all", "all", allm), ("path", "bare URLs (no path)", ds.nopath), ("path", "URLs with a path", ~ds.nopath)]
    if ds.source is not None:
        out += [("source", f"source={s}", ds.source == s) for s in sorted(set(ds.source.tolist()))]
    return out


def systems_table(ds, verd, auc_by_sys):
    rows = []
    for sysname in SYSTEMS:
        for kind, sub, mask in subsets_of(ds):
            row = {"dataset": ds.name, "system": sysname, "subset_kind": kind, "subset": sub}
            row.update(metric_row(ds.y, verd[sysname], mask))
            row["auc"] = auc_by_sys.get(sysname, "n/a") if kind == "all" else ""
            rows.append(row)
    return pd.DataFrame(rows)


def auc_of(y, s):
    return float(roc_auc_score(y, s)) if len(set(y.tolist())) == 2 else "n/a"


def attack_counts(v):
    b = np.bincount(v, minlength=3)
    return {"safe": int(b[0]), "phishing": int(b[1]), "unsure": int(b[2]), "n": int(len(v))}


def evaluate_attacks(par, scorers, test_ds, words, integrity):
    """Same attack code, word list and settings as evaluate.py. Returns the attack table (counts and rates)."""
    phish = [u for u, y in zip(test_ds.urls, test_ds.y) if y == 1]
    safe = [u for u, y in zip(test_ds.urls, test_ds.y) if y == 0]
    safe_small = random.Random(5).sample(safe, N_SAFE_ATTACKED)
    sets = [("none (clean)", "phish", phish), ("none (clean)", "safe", safe_small)]
    for fam in FAMILIES:
        sets.append((fam, "phish", apply_family(phish, fam, words, seed=42)))
        sets.append((fam, "safe", apply_family(safe_small, fam, words, seed=42)))
    counts = {}
    for fam, kind, urls in sets:
        y = np.full(len(urls), 1 if kind == "phish" else 0)
        ds = make_ds(f"attack {fam} ({kind})", urls, y, None, len(urls), integrity)
        s4, s8 = scorers["4a"](ds.urls), scorers["8b"](ds.urls)
        v = build_verdicts(par, ds, s4, s8, integrity)
        for sysname in SYSTEMS:
            counts[(fam, kind, sysname)] = attack_counts(v[sysname])
        print(f"  attacks: scored {fam} ({kind}), {len(urls):,} URLs", flush=True)
    rows = []
    for fam in ["none (clean)"] + list(FAMILIES):
        for sysname in SYSTEMS:
            cp, cs = counts[(fam, "phish", sysname)], counts[(fam, "safe", sysname)]
            row = {"family": fam, "system": sysname, "n_phishing_edited": cp["n"], "n_safe_edited": cs["n"],
                   "phishing_flagged": cp["phishing"], "phishing_unsure": cp["unsure"], "phishing_safe": cp["safe"],
                   "safe_flagged": cs["phishing"], "safe_unsure": cs["unsure"], "safe_safe": cs["safe"]}
            put(row, "recall", rate(cp["phishing"], cp["n"]), True)
            put(row, "phishing_share_unsure", rate(cp["unsure"], cp["n"]))
            put(row, "phishing_share_safe", rate(cp["safe"], cp["n"]))
            put(row, "safe_flagged_share", rate(cs["phishing"], cs["n"]), True)
            put(row, "safe_share_unsure", rate(cs["unsure"], cs["n"]))
            rows.append(row)
    return pd.DataFrame(rows)


def short(df, cols, nd=4):
    d = df[cols].copy()
    for c in cols:
        d[c] = d[c].map(lambda x: f"{x:.{nd}f}" if isinstance(x, float) else x)
    return d.to_string(index=False)


def build_report(meta, tables, integrity, notes, sealed_facts):
    t, s, att = tables["test_systems"], tables["sealed_systems"], tables["test_attacks"]
    L = []
    add = L.append
    add(f"FINAL EVALUATION REPORT ({meta['mode']})  {meta['time']}")
    add(f"git HEAD {meta['head']}; script SHA-256 {meta['script_sha256']}; config SHA-256 {meta['config_sha256']}")
    add("Counts are always given. A rate whose denominator is under 50 rows is shown as 'too few to read'.")
    add("In the second view, fn and tn count 'unsure' as not flagged; phishing_unsure / phishing_safe / safe_unsure / safe_safe split them.")
    if meta["mode"] == "dry-run":
        add("DRY RUN: the 'test' data is data_v2/val_redacted.csv and the 'sealed' data is a synthetic file of made-up URLs. The numbers are NOT results.")
    add("")
    add("ROW COUNTS (rows read = urls = labels = scores = verdicts, or the run aborts):")
    for r in integrity:
        others = ", ".join(f"{k}={v:,}" for k, v in r.items() if k not in ("item", "rows_read"))
        add(f"  {r['item']}: rows read {r['rows_read']:,}; all equal to it: {others}")
    add("")
    for ds_name, tbl in (("TEST SPLIT", t), ("SEALED SET", s)):
        add(f"=== {ds_name}: all rows, frozen thresholds")
        sel = tbl[tbl["subset_kind"] == "all"]
        add(short(sel, ["system", "n_phishing", "n_safe", "tp", "fn", "fp", "tn", "recall", "recall_ci_lo", "recall_ci_hi", "false_alarm",
                        "false_alarm_ci_lo", "false_alarm_ci_hi", "precision", "precision_ci_lo", "precision_ci_hi", "f1", "auc"]))
        add("")
        add(f"=== {ds_name}: bare URLs (no path) versus URLs with a path")
        sel = tbl[tbl["subset_kind"] == "path"]
        add(short(sel, ["system", "subset", "n_phishing", "n_safe", "tp", "fp", "recall", "false_alarm", "precision"]))
        add("")
        if ds_name == "SEALED SET":
            add("=== SEALED SET: per source")
            sel = tbl[tbl["subset_kind"] == "source"]
            add(short(sel, ["system", "subset", "n_phishing", "n_safe", "tp", "fp", "recall", "false_alarm", "precision"]))
            add("")
        add(f"=== {ds_name}: second view (primary + unsure), all rows and subsets")
        sel = tbl[tbl["system"] == SYS4]
        add(short(sel, ["subset", "n_phishing", "n_safe", "tp", "phishing_unsure", "phishing_safe", "fp", "safe_unsure", "safe_safe", "coverage",
                        "recall_among_decided", "false_alarm_among_decided", "recall_phishing_or_unsure"]))
        add("")
    add("=== TEST SPLIT: attack families (recall = edited phishing flagged; safe_flagged_share = edited SAFE URLs flagged; same edits, word list and settings as evaluate.py)")
    add(short(att, ["family", "system", "n_phishing_edited", "phishing_flagged", "recall", "safe_flagged", "safe_flagged_share"]))
    add("")
    add("=== TEST SPLIT: second view under the attacks (verdict shares of edited phishing / edited safe)")
    sel = att[att["system"] == SYS4]
    add(short(sel, ["family", "recall", "phishing_share_unsure", "phishing_share_safe", "safe_flagged_share", "safe_share_unsure"]))
    add("")
    add("=== SEALED SET: what its safe URLs are")
    add(sealed_facts)
    add("The sealed set cannot test safe URLs that have a path. Its false-alarm rate measures the known bare-domain flaw, not new behaviour.")
    add("")
    add("=== NUMBERS FOR THE HYPOTHESES LOGGED BEFORE THE RUN (the verdicts are for the owner)")
    L.extend(notes)
    return "\n".join(L) + "\n"


def hypothesis_notes(par, test_tbl, sealed_tbl, att, target):
    def row(tbl, sysname, kind="all", sub="all"):
        return tbl[(tbl["system"] == sysname) & (tbl["subset_kind"] == kind) & (tbl["subset"] == sub)].iloc[0]
    n = []
    p = row(test_tbl, SYS1)
    if isinstance(p["recall"], float) and isinstance(p["false_alarm"], float):
        dr, df_ = p["recall"] - VALIDATION_RECALL_H1, p["false_alarm"] - target
        n.append(f"H1: primary test recall {p['recall']:.4f} vs validation {VALIDATION_RECALL_H1} (difference {dr * 100:+.2f} pt; within 3 pt: {abs(dr) <= 0.03}); "
                 f"test false-alarm rate {p['false_alarm']:.4f} vs {target:.4f} (difference {df_ * 100:+.2f} pt; within 1.5 pt: {abs(df_) <= 0.015}).")
    for sysname in (SYS2, SYS1):
        q = row(sealed_tbl, sysname)
        n.append(f"H2: sealed, {sysname}: false-alarm rate {q['false_alarm']} (fp {q['fp']} of {q['n_safe']} safe), precision {q['precision']}, recall {q['recall']}.")
    for sysname in (SYS1, SYS2, SYS3):
        parts = []
        for _, r in sealed_tbl[(sealed_tbl["system"] == sysname) & (sealed_tbl["subset_kind"] == "source")].iterrows():
            parts.append(f"{r['subset']}: recall {r['recall']} (phishing rows {r['n_phishing']})")
        n.append(f"H3: sealed recall by source, {sysname}: " + "; ".join(parts))
    q = row(sealed_tbl, SYS4)
    n.append(f"H4: sealed safe URLs in the second view: unsure {q['safe_unsure']} of {q['n_safe']} (share {q['safe_share_unsure']}), phishing {q['fp']}, safe {q['safe_safe']}.")
    a4, a8 = row(test_tbl, SYS2), row(test_tbl, SYS3)
    n.append(f"H5: clean test, 4a vs 8b: recall {a4['recall']} vs {a8['recall']}; false alarms {a4['false_alarm']} vs {a8['false_alarm']}; AUC {a4['auc']} vs {a8['auc']}.")
    word = ["benign_words_in_path", "benign_words_in_query", "random_mix"]
    for sysname in (SYS2, SYS3):
        vals = [att[(att["family"] == f) & (att["system"] == sysname)].iloc[0]["recall"] for f in word]
        if all(isinstance(v, float) for v in vals):
            n.append(f"H5: {sysname}: recall under path / query / mix words {vals[0]:.4f} / {vals[1]:.4f} / {vals[2]:.4f}, mean {np.mean(vals):.4f}.")
    return n


def scan_outputs(files):
    for name, text in files.items():
        for pat in URL_PATTERNS:
            m = re.search(pat, text)
            if m:
                gate_fail(f"output scan of {name}", "no URL, IP address or domain-like text in any output", f"pattern {pat!r} matched",
                          nothing="NOTHING WAS WRITTEN: no lock file and no results folder were created.")


def write_outputs(files, report_text, out_dir, lock_path, backup_path, meta):
    """Order: scan -> backup copy of the printed report -> lock (exclusive) -> results folder."""
    scan_outputs({**files, "report.txt": report_text})
    with open(backup_path, "w") as f:
        f.write(report_text)
        f.flush()
        os.fsync(f.fileno())
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except FileExistsError:
        gate_fail(f"lock file {lock_path}", "absent", "present", nothing="NOTHING WAS WRITTEN to the results folder.")
    with os.fdopen(fd, "w") as f:
        f.write(json.dumps({"locked_at": meta["time"], "mode": meta["mode"], "head": meta["head"], "script_sha256": meta["script_sha256"]}) + "\n")
    os.makedirs(out_dir, exist_ok=False)
    for name, text in {**files, "report.txt": report_text}.items():
        with open(os.path.join(out_dir, name), "w") as f:
            f.write(text)


def frames_to_files(tables, extra_json):
    f = {"test_systems.csv": tables["test_systems"][tables["test_systems"]["subset_kind"] == "all"].to_csv(index=False),
         "test_bare_vs_path.csv": tables["test_systems"][tables["test_systems"]["subset_kind"] == "path"].to_csv(index=False),
         "test_attacks.csv": tables["test_attacks"].to_csv(index=False),
         "test_unsure_view.csv": tables["test_systems"][tables["test_systems"]["system"] == SYS4].to_csv(index=False),
         "sealed_systems.csv": tables["sealed_systems"][tables["sealed_systems"]["subset_kind"] == "all"].to_csv(index=False),
         "sealed_bare_vs_path.csv": tables["sealed_systems"][tables["sealed_systems"]["subset_kind"] == "path"].to_csv(index=False),
         "sealed_by_source.csv": tables["sealed_systems"][tables["sealed_systems"]["subset_kind"] == "source"].to_csv(index=False),
         "sealed_unsure_view.csv": tables["sealed_systems"][tables["sealed_systems"]["system"] == SYS4].to_csv(index=False)}
    f["metrics.json"] = json.dumps(extra_json, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o))
    return f


def reproduction_check(tables, atk):
    """Dry run only: on val_redacted the numbers must equal the saved validation numbers (results/defence_final, exp12_guard)."""
    ft = pd.read_csv(rp("results/defence_final/final_table.csv"))
    pairs = [("4a", "FINAL SYSTEM: model + validated rules (R1) at 3.65%", SYS1), ("4a", "plain model at 3.65%", SYS2),
             ("8b", "plain model at 3.65%", SYS3), ("4a", "second view: model + rules + abstain (10% window + bare routing)", SYS4)]
    diffs, n = [], 0

    def cmp(label, mine, saved):
        nonlocal n
        n += 1
        if not (isinstance(mine, float) and abs(mine - float(saved)) <= 1e-12):
            diffs.append((label, mine, float(saved)))

    for tag, saved_name, mine_name in pairs:
        r = ft[(ft["model"] == tag) & (ft["system"] == saved_name)].iloc[0]
        m = tables["test_systems"]
        m = m[(m["system"] == mine_name) & (m["subset_kind"] == "all")].iloc[0]
        for col_saved, col_mine in (("recall", "recall"), ("false_alarm", "false_alarm"), ("precision", "precision"), ("f1", "f1")):
            cmp(f"{mine_name}: {col_saved}", m[col_mine], r[col_saved])
        a = atk[atk["system"] == mine_name].set_index("family")
        cmp(f"{mine_name}: safe flagged, clean 15k sample", a.loc["none (clean)", "safe_flagged_share"], r["safe_flagged_clean15k"])
        for fam in FAMILIES:
            cmp(f"{mine_name}: recall {fam}", a.loc[fam, "recall"], r[f"recall_{fam}"])
            cmp(f"{mine_name}: safe flagged {fam}", a.loc[fam, "safe_flagged_share"], r[f"safe_flagged_{fam}"])
        if mine_name == SYS4:
            m_s4 = tables["test_systems"]
            m_s4 = m_s4[(m_s4["system"] == SYS4) & (m_s4["subset_kind"] == "all")].iloc[0]
            for c in ("coverage", "recall_phishing_or_unsure", "recall_among_decided", "false_alarm_among_decided"):
                cmp(f"{mine_name}: {c}", m_s4[c], r[c])
    for tag, mine_name in (("4a", SYS2), ("8b", SYS3)):
        g = pd.read_csv(rp(f"results/exp12_guard/guard_table_{tag}.csv"))
        sv = g[g["system"] == "plain at 3.65%"].iloc[0]["auc"]
        m = tables["test_systems"]
        cmp(f"{mine_name}: AUC", m[(m["system"] == mine_name) & (m["subset_kind"] == "all")].iloc[0]["auc"], sv)
    return n, diffs


def run_evaluation(mode, cfg, scorers, words, paths, head, script_sha, config_sha, hashes):
    """mode 'dry' (stand-in data, temporary folder) or 'final' (real data). Same code for both."""
    integrity = []
    par = system_params(cfg)
    target = cfg["target_false_alarm_rate_on_clean_validation_safe"]
    now = datetime.datetime.now().isoformat(timespec="seconds")
    meta = {"mode": "dry-run" if mode == "dry" else "final", "time": now, "head": head, "script_sha256": script_sha, "config_sha256": config_sha}
    datasets = {}
    for name, (p, sp) in (("test", (paths["test"], None)), ("sealed", (paths["sealed"], paths["source"]))):
        n_read, raw, y, src = read_labelled(p, sp)
        datasets[name] = make_ds(name, raw, y, src, n_read, integrity)
        print(f"read {name}: {n_read:,} rows ({datasets[name].n_redacted:,} changed by redaction)", flush=True)
    tables, aucs = {}, {}
    for name, ds in datasets.items():
        s4, s8 = scorers["4a"](ds.urls), scorers["8b"](ds.urls)
        v = build_verdicts(par, ds, s4, s8, integrity)
        auc4, auc8 = auc_of(ds.y, s4), auc_of(ds.y, s8)
        aucs[name] = {SYS1: auc4, SYS2: auc4, SYS3: auc8}
        tables[f"{name}_systems"] = systems_table(ds, v, aucs[name])
    tables["test_attacks"] = evaluate_attacks(par, scorers, datasets["test"], words, integrity)
    sd = datasets["sealed"]
    safe = sd.y == 0
    facts = (f"sealed safe URLs: {int(safe.sum()):,}; of these without a path: {int((safe & sd.nopath).sum()):,}; host equal to its registered domain "
             f"(bare domains): {int((safe & sd.bare_route).sum()):,}. Sealed phishing URLs: {int((~safe).sum()):,}, without a path: {int((~safe & sd.nopath).sum()):,}.")
    notes = hypothesis_notes(par, tables["test_systems"], tables["sealed_systems"], tables["test_attacks"], target)
    repro = None
    if mode == "dry":
        n_cmp, diffs = reproduction_check(tables, tables["test_attacks"])
        repro = {"compared": n_cmp, "not_equal": diffs}
        notes.append(f"DRY-RUN REPRODUCTION: {n_cmp} numbers compared with the saved validation numbers (tolerance 1e-12); "
                     f"{len(diffs)} differ" + (": " + "; ".join(f"{a} mine {b} saved {c}" for a, b, c in diffs) if diffs else "."))
    report = build_report(meta, tables, integrity, notes, facts)
    print("\n" + report, flush=True)
    out_json = {**meta, "hashes_checked": hashes, "integrity": integrity, "thresholds_from_config": {k: par[k] for k in par},
                "target_false_alarm_rate": target, "hypothesis_numbers": notes, "dry_run_reproduction": repro,
                "sealed_facts": facts}
    files = frames_to_files(tables, out_json)
    if mode == "dry":
        base = paths["out_dir"]
        write_outputs(files, report, os.path.join(base, "final_v2"), os.path.join(base, "final_v2.lock"), os.path.join(base, "final_report_backup.txt"), meta)
        print(f"DRY RUN: wrote results, lock and backup copy under {base} (outside the repo).", flush=True)
    else:
        write_outputs(files, report, FINAL["out"], FINAL["lock"], FINAL["backup"], meta)
        print(f"\nDONE. Results: {FINAL['out']}; lock: {FINAL['lock']}; report copy: {FINAL['backup']}", flush=True)


def parse_args(argv):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--final", action="store_true", help="the real run (all gates; the phrase is typed in the terminal)")
    ap.add_argument("--dry-run", action="store_true", help="the same code on val_redacted.csv + synthetic made-up files; output outside the repo")
    ap.add_argument("--dry-run-dir", default=None, help="with --dry-run only: an existing or new folder OUTSIDE the repo for the output")
    return ap.parse_args(argv)


def gate_mode(args):
    if args.final == args.dry_run:
        gate_fail("mode", "exactly one of --final or --dry-run", f"final={args.final}, dry_run={args.dry_run}")
    if args.final and args.dry_run_dir:
        gate_fail("--dry-run-dir", "used only with --dry-run", "given together with --final")


def main(argv=None):
    args = parse_args(argv)
    gate_mode(args)
    cfg = json.load(open(CONFIG))
    script_sha = sha256_file(os.path.abspath(__file__))
    print(f"final_eval.py SHA-256 {script_sha}", flush=True)
    gate_hashseed()
    if args.final:
        head = gate_git()
    else:
        head = _git(REPO, "rev-parse", "HEAD").stdout.strip() or "unknown"
    config_sha = sha256_file(CONFIG)
    hashes = gate_hashes(cfg)
    words = load_benign_words(TRAIN)
    gate_words(words)
    par = system_params(cfg)
    scorers = {tag: dl.make_scorer(rp(cfg["models"][tag]["model"]), rp(cfg["models"][tag]["recipe"])) for tag in ("4a", "8b")}
    self_check_verdicts(par, scorers["4a"])
    if args.final:
        gate_not_exists([FINAL["out"], FINAL["lock"]])
        print("\nThis run will READ: " + FINAL["test"] + ", " + FINAL["sealed"] + ", " + FINAL["source"])
        print("It will WRITE (only at the end): " + FINAL["out"] + "/, " + FINAL["lock"] + ", " + FINAL["backup"])
        print("It can be run ONCE: afterwards the lock file stops a rerun.\n", flush=True)
        check_phrase(read_phrase_from_tty)
        paths = {k: FINAL[k] for k in ("test", "sealed", "source")}
        run_evaluation("final", cfg, scorers, words, paths, head, script_sha, config_sha, hashes)
    else:
        out_dir = args.dry_run_dir or tempfile.mkdtemp(prefix="final_eval_dry_")
        os.makedirs(out_dir, exist_ok=True)
        sealed, source = make_synthetic_sealed(os.path.join(out_dir, "inputs"))
        paths = {"test": VAL, "sealed": sealed, "source": source, "out_dir": out_dir}
        guard_dry_paths([paths["test"], sealed, source], out_dir)
        gate_not_exists([os.path.join(out_dir, "final_v2"), os.path.join(out_dir, "final_v2.lock")])
        run_evaluation("dry", cfg, scorers, words, paths, head, script_sha, config_sha, hashes)


if __name__ == "__main__":
    main()
