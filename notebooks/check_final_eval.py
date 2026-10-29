"""Checks for notebooks/final_eval.py on MADE-UP data only (temporary folders outside the repo). Reads no real test or sealed file.
It calls gate functions and helpers directly; it never starts the real run.

    PYTHONHASHSEED=0 .venv/bin/python notebooks/check_final_eval.py
"""
import ast
import contextlib
import copy
import io
import json
import os
import subprocess
import sys
import tempfile
from types import SimpleNamespace
from unittest import mock
import numpy as np
import pandas as pd
import final_eval as fe
import defence_layers as dl
import defence_metrics as dm

n_checks = 0


def check(cond, what):
    global n_checks
    n_checks += 1
    if not cond:
        raise SystemExit(f"CHECK FAILED: {what}")


def fails(fn, *args, **kw):
    """Run fn; it must exit with code 2 and a plain message that has expected, actual and a 'nothing was ...' line."""
    buf = io.StringIO()
    code = None
    with contextlib.redirect_stdout(buf):
        try:
            fn(*args, **kw)
        except SystemExit as e:
            code = e.code
    out = buf.getvalue()
    ok = code == 2 and "GATE FAILED" in out and "expected:" in out and "actual:" in out and ("Nothing was run" in out or "NOTHING WAS WRITTEN" in out)
    return ok, out


# --- child mode: the terminal gate with stdin redirected from a file (run by the parent below)
if sys.argv[1:] == ["--child-tty-gate"]:
    fe.check_phrase(fe.read_phrase_from_tty)
    print("CHILD: gate did not abort")          # must never be reached
    sys.exit(0)

tmp = tempfile.mkdtemp(prefix="check_final_eval_")

# --- terminal gate: piped input (even the right phrase) must abort
phrase_file = os.path.join(tmp, "stdin_with_phrase.txt")
open(phrase_file, "w").write(fe.PHRASE + "\n")
with open(phrase_file) as stdin_file:
    res = subprocess.run([sys.executable, os.path.abspath(__file__), "--child-tty-gate"], stdin=stdin_file, capture_output=True, text=True,
                         env={**os.environ, "PYTHONHASHSEED": "0"})
check(res.returncode == 2 and "GATE FAILED: controlling terminal" in res.stdout and "Nothing was run" in res.stdout
      and "did not abort" not in res.stdout, "piped input (stdin from a file holding the phrase) aborts the terminal gate")
# /dev/tty missing although stdin looks like a terminal -> abort
with mock.patch.object(fe.sys.stdin, "isatty", return_value=True), mock.patch.object(fe, "open_controlling_terminal", side_effect=OSError("no tty")):
    ok, out = fails(fe.read_phrase_from_tty)
check(ok and "cannot open /dev/tty" in out, "no /dev/tty -> abort with a plain message")
ok, out = fails(fe.check_phrase, lambda: "run final once")
check(ok and "'RUN FINAL ONCE'" in out, "a wrong phrase (wrong case) aborts and shows expected and actual")
ok, out = fails(fe.check_phrase, lambda: "")
check(ok, "an empty phrase aborts")
fe.check_phrase(lambda: fe.PHRASE)
check(True, "the exact phrase passes the phrase check")

# --- the other gates
ok, out = fails(fe.gate_mode, SimpleNamespace(final=False, dry_run=False, dry_run_dir=None))
check(ok, "no mode flag -> abort")
ok, out = fails(fe.gate_mode, SimpleNamespace(final=True, dry_run=True, dry_run_dir=None))
check(ok, "both mode flags -> abort")
ok, out = fails(fe.gate_mode, SimpleNamespace(final=True, dry_run=False, dry_run_dir="x"))
check(ok, "--dry-run-dir together with the real mode -> abort")
fe.gate_mode(SimpleNamespace(final=False, dry_run=True, dry_run_dir=None))
check(True, "a dry-run alone passes the mode gate")

with mock.patch.dict(os.environ, {"PYTHONHASHSEED": "7"}):
    ok, out = fails(fe.gate_hashseed)
check(ok and "PYTHONHASHSEED=7" in out, "PYTHONHASHSEED other than 0 aborts")
with mock.patch.dict(os.environ, {"PYTHONHASHSEED": "0"}):
    fe.gate_hashseed()
check(True, "PYTHONHASHSEED=0 passes")

cfg = json.load(open(fe.CONFIG))
with contextlib.redirect_stdout(io.StringIO()):
    fe.gate_hashes(cfg)
check(True, "the real config, models, recipes and code hash correctly")
for path in (("models", "4a", "model_sha256"), ("models", "8b", "recipe_sha256"), ("code", "notebooks/defence_layers.py"), ("code", "notebooks/attacks.py")):
    bad = copy.deepcopy(cfg)
    node = bad
    for k in path[:-1]:
        node = node[k]
    node[path[-1]] = "0" * 64
    ok, out = fails(fe.gate_hashes, bad)
    check(ok and "0" * 64 in out, f"a wrong recorded hash ({'/'.join(path)}) aborts and shows expected and actual")

ok, out = fails(fe.gate_words, ["harmless", "words"])
check(ok, "a different harmless-word list aborts")

ok, out = fails(fe.gate_git, tmp)       # a folder that is not a git repository
check(ok, "git gate aborts outside a git repository")
ok, out = fails(fe.gate_git, fe.REPO, ["notebooks/this_file_is_not_tracked_made_up.py"])
check(ok and "not tracked" in out, "git gate aborts for an untracked required file")

os.makedirs(os.path.join(tmp, "existing_out"))
ok, out = fails(fe.gate_not_exists, [os.path.join(tmp, "existing_out")])
check(ok, "an existing results folder aborts")
open(os.path.join(tmp, "existing.lock"), "w").write("x")
ok, out = fails(fe.gate_not_exists, [os.path.join(tmp, "existing.lock")])
check(ok, "an existing lock file aborts")
fe.gate_not_exists([os.path.join(tmp, "absent_one")])
check(True, "absent results folder and lock pass")

# --- dry-run path guards (made-up names; nothing is opened)
home = os.path.expanduser("~")
ok, out = fails(fe.guard_dry_paths, [os.path.join(home, "sealed_eval", "made_up_name.csv")], tmp)
check(ok, "dry-run refuses an input under ~/sealed_eval")
ok, out = fails(fe.guard_dry_paths, [os.path.join(tmp, "my_test_split.csv")], tmp)
check(ok, "dry-run refuses an input whose name contains 'test'")
ok, out = fails(fe.guard_dry_paths, [os.path.join(tmp, "inputs.csv")], os.path.join(fe.REPO, "results", "made_up_dry_run_folder"))
check(ok, "dry-run refuses an output folder inside the repo")
fe.guard_dry_paths([fe.VAL, os.path.join(tmp, "synthetic.csv")], tmp)
check(True, "dry-run accepts val_redacted.csv, a synthetic file and an outside folder")

# --- row-count assertions
integ = []
fe.check_rows("good set", 10, integ, urls=10, labels=10)
check(len(integ) == 1, "matching counts pass and are recorded")
ok, out = fails(fe.check_rows, "bad set", 10, [], urls=10, labels=9)
check(ok and "NOTHING WAS WRITTEN" in out, "a row-count mismatch aborts with 'nothing was written'")

# --- rates, small groups, intervals
r = fe.rate(50, 100)
check(abs(r["rate"] - 0.5) < 1e-12 and abs(r["lo"] - 0.4038) < 1e-3 and abs(r["hi"] - 0.5962) < 1e-3, "Wilson interval for 50 of 100")
r = fe.rate(3, 49)
check(r["rate"] is None and r["k"] == 3 and r["n"] == 49, "a denominator of 49 gives 'too few' but keeps the counts")
check(fe.rate(0, 50)["rate"] == 0.0, "a denominator of exactly 50 is read")
row = {}
fe.put(row, "x", fe.rate(1, 10), True)
check(row == {"x": fe.TOO_FEW, "x_ci_lo": fe.TOO_FEW, "x_ci_hi": fe.TOO_FEW}, "put() writes 'too few to read' for value and interval")

y = np.array([1] * 60 + [0] * 40)
v = np.array([1] * 40 + [0] * 15 + [2] * 5 + [1] * 4 + [0] * 30 + [2] * 6)
m = fe.metric_row(y, v, np.ones(100, bool))
check((m["tp"], m["fn"], m["fp"], m["tn"]) == (40, 20, 4, 36), "confusion counts (unsure counted as not flagged)")
check((m["phishing_unsure"], m["phishing_safe"], m["safe_unsure"], m["safe_safe"]) == (5, 15, 6, 30), "verdict counts per class")
check(abs(m["recall"] - 40 / 60) < 1e-12 and m["false_alarm"] == fe.TOO_FEW, "recall is read (60 rows), false-alarm rate is 'too few' (40 safe rows)")
check(abs(m["coverage"] - 89 / 100) < 1e-12 and abs(m["recall_among_decided"] - 40 / 55) < 1e-12, "coverage and recall among decided")
mask = np.zeros(100, bool)
mask[:30] = True
m2 = fe.metric_row(y, v, mask)
check(m2["recall"] == fe.TOO_FEW and m2["n_phishing"] == 30 and m2["tp"] == 30, "a subgroup of 30 phishing rows: count given, recall 'too few to read'")

# --- systems_table on a made-up dataset
ds = fe.DS()
ds.name, ds.y = "made-up", y
ds.nopath, ds.source = np.array([True] * 50 + [False] * 50), np.array(["a"] * 70 + ["b"] * 30)
tbl = fe.systems_table(ds, {s: v for s in fe.SYSTEMS}, {fe.SYS2: 0.9})
check(set(tbl["subset_kind"]) == {"all", "path", "source"} and len(tbl) == 4 * 5, "systems_table has all, path and source rows for the 4 systems")
check(tbl[(tbl["system"] == fe.SYS2) & (tbl["subset_kind"] == "all")].iloc[0]["auc"] == 0.9, "AUC is filled for the 'all' row only")
check((tbl[tbl["subset"] == "source=b"]["recall"] == fe.TOO_FEW).all(), "the 30-row source group shows 'too few to read'")

# --- the vectorised verdicts equal classify_many on made-up URLs (fake scorer)
urls = ["http://192.0.2.7/login", "http://example.com", "http://example.com/hot", "http://example.com/mid", "http://example.com/cold",
        "http://shop.example.org/x/mid", "http://www.example.net", "http://example.org/?q=hot"]


def fake(us):
    return np.array([0.9 if "hot" in u else 0.7 if "mid" in u else 0.1 for u in us])


for cfg_c, w, use_bare in (({"threshold": 0.8, "guard": None, "rules": ["R1"], "window_width": None, "bare_route": False}, 0.0, False),
                           ({"threshold": 0.8, "guard": None, "rules": ["R1"], "window_width": 0.15, "bare_route": True}, 0.15, True)):
    ref = dl.classify_many(urls, fake, cfg_c)
    rules_m = dl.rule_matrix(urls)
    mine = dm.verdicts(fake(urls), 0.8, w, dm.rules_any({"x": rules_m}, ["R1"])["x"], np.array([dl.is_bare_domain(u) for u in urls]), use_bare=use_bare)
    check([fe.VERDICT[int(x)] for x in mine] == [r["verdict"] for r in ref], f"vectorised verdicts equal classify_many (window {w})")

# --- the write phase: order, lock, no partial results
out_ok = os.path.join(tmp, "run1")
os.makedirs(out_ok)
meta = {"time": "now", "mode": "dry-run", "head": "abc", "script_sha256": "def"}
files = {"a.csv": "x,y\n1,2\n", "metrics.json": "{}"}
fe.write_outputs(files, "REPORT TEXT\n", os.path.join(out_ok, "final_v2"), os.path.join(out_ok, "final_v2.lock"), os.path.join(out_ok, "backup.txt"), meta)
check(os.path.exists(os.path.join(out_ok, "backup.txt")) and os.path.exists(os.path.join(out_ok, "final_v2.lock"))
      and os.path.exists(os.path.join(out_ok, "final_v2", "a.csv")) and os.path.exists(os.path.join(out_ok, "final_v2", "report.txt")),
      "write phase creates backup, lock, results folder and files")
check(os.path.getmtime(os.path.join(out_ok, "backup.txt")) <= os.path.getmtime(os.path.join(out_ok, "final_v2.lock")),
      "the report backup is written before the lock")
ok, out = fails(fe.write_outputs, files, "REPORT\n", os.path.join(out_ok, "final_v2"), os.path.join(out_ok, "final_v2.lock"), os.path.join(out_ok, "backup2.txt"), meta)
check(ok, "a second write is refused (lock exists)")
check(not os.path.exists(os.path.join(out_ok, "final_v2", "never.csv")), "the refused write added no file to the results folder")
out_bad = os.path.join(tmp, "run2")
os.makedirs(out_bad)
ok, out = fails(fe.write_outputs, {"a.csv": "see http://example.com/x\n"}, "ok\n", os.path.join(out_bad, "final_v2"),
                os.path.join(out_bad, "final_v2.lock"), os.path.join(out_bad, "backup.txt"), meta)
check(ok and not os.path.exists(os.path.join(out_bad, "final_v2.lock")) and not os.path.exists(os.path.join(out_bad, "final_v2"))
      and not os.path.exists(os.path.join(out_bad, "backup.txt")), "an output containing a URL aborts before backup, lock and results folder")
ok, out = fails(fe.write_outputs, {"a.csv": "x\n"}, "report mentions 192.0.2.7\n", os.path.join(out_bad, "final_v2"),
                os.path.join(out_bad, "final_v2.lock"), os.path.join(out_bad, "backup.txt"), meta)
check(ok and not os.path.exists(os.path.join(out_bad, "final_v2.lock")), "an IP-like string in the report aborts before the lock")

# --- the synthetic sealed files: structure like the real set, only made-up URLs, all safe URLs bare
sp, ssp = fe.make_synthetic_sealed(os.path.join(tmp, "syn"))
n_read, raw, labels, src = fe.read_labelled(sp, ssp)
dsyn = fe.make_ds("synthetic", raw, labels, src, n_read, [])
check(n_read == len(src) == len(raw) and set(src.tolist()) == {"synthetic_feed", "synthetic_mix", "synthetic_tiny"}, "synthetic sealed set: sizes and sources")
check(bool(dsyn.nopath[labels == 0].all()) and bool(dsyn.bare_route[labels == 0].all()), "synthetic safe URLs are all bare domains (like the sealed set)")
check(int(dsyn.n_redacted) > 0 and bool(dsyn.rules[:, 0].any()), "synthetic set exercises redaction and rule R1")
check(all("example." in u or "-madeup." in u or u.startswith("192.0.2.") for u in raw),
      "synthetic URLs are made up (example domains, nonsense '-madeup' names, documentation IPs)")

# --- source-text checks of final_eval.py
src_text = open(os.path.join(fe.REPO, "notebooks", "final_eval.py")).read()
for banned in ("quantile", "set_threshold(", "abstain_width(", "--force", "--skip", "--yes", "--bypass", "--no-gate"):
    check(banned not in src_text, f"final_eval.py has no '{banned}'")
tree = ast.parse(src_text)
where = {}
for node in tree.body[1:]:                      # tree.body[0] is the module docstring (documentation, not a path in use)
    for sub in ast.walk(node):
        if isinstance(sub, ast.Constant) and isinstance(sub.value, str) and ("sealed_eval" in sub.value or sub.value.endswith("test.csv")):
            name = getattr(node, "name", None) or ",".join(getattr(t, "id", "?") for t in getattr(node, "targets", []))
            where.setdefault(name, 0)
            where[name] += 1
check(set(where) <= {"FINAL", "guard_dry_paths", "TRACKED_REQUIRED", "check_phrase", "main"} and "FINAL" in where,
      f"real test/sealed paths appear only in the FINAL constant and the path guard, found in: {sorted(where)}")
opts = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "add_argument"]
flags = sorted(a.value for c in opts for a in c.args if isinstance(a, ast.Constant))
check(flags == ["--dry-run", "--dry-run-dir", "--final"], f"the only command-line options are --final, --dry-run, --dry-run-dir (found {flags})")

print(f"ALL {n_checks} CHECKS PASSED (made-up data only; the real run was never started)")
