"""Checks for demo/app.py. Made-up links only. Run:  PYTHONHASHSEED=0 .venv/bin/python demo/check_demo.py

What it does NOT do: it never uses the network (it only BLOCKS it while scoring), never opens a browser, never
writes anywhere except its own temp folder, and stops only the one server process it started (by PID).
"""
import ast
import contextlib
import http.client
import importlib.util
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
APP_PATH = ROOT / "demo" / "app.py"
CONFIG = ROOT / "results" / "final_system_config.json"

# The only links used anywhere in these checks (all made up).
L1 = "examplebank-login.test/verify/account"
L2 = "examplebank.test/help/contact"
L3 = "example.com"
L4 = "example.org"
L5 = "example.test"
L6 = "login.examplebank.test"
L7 = "192.0.2.7/login"
LINKS = [L1, L2, L3, L4, L5, L6, L7]
BANNER = ("Educational project. Not a security tool. It can be fooled by small edits "
          "and it can't judge links that are just a site name.")
FOOTER = "This page does not open the link and does not store or log it."

results = []


def check(name, ok, detail=""):
    results.append(bool(ok))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))


def note(text):
    print(f"  [info] {text}")


def section(title):
    print(f"\n== {title}")


if os.environ.get("PYTHONHASHSEED") != "0":
    sys.exit("Start with PYTHONHASHSEED=0 (as for every run in this project).")

spec = importlib.util.spec_from_file_location("demo_app", APP_PATH)
demo_app = importlib.util.module_from_spec(spec)
sys.modules["demo_app"] = demo_app
spec.loader.exec_module(demo_app)

T0 = time.time()
OWN_TMP = tempfile.TemporaryDirectory()      # the only place this script writes; removed at the end

# ------------------------------------------------------------------ load the system the way the page does
section("start-up: load the system (hash gate passes on the real files)")
system = demo_app.load_system()
check("load_system() passed every hash check and loaded the model", True)

# an independent scorer and config, built straight from the config file (not through demo/app.py)
cfg = json.loads(CONFIG.read_text())
direct_cfg = cfg["systems"]["final_system_4a_plus_rules"]["second_view_abstain_classify_config"]
m = cfg["models"]["4a"]
import defence_layers as dl   # noqa: E402  (notebooks/ is on sys.path after load_system)
direct_scorer = dl.make_scorer(str(ROOT / m["model"]), str(ROOT / m["recipe"]))


def direct(link):
    return dl.classify(link, direct_scorer, direct_cfg)


# ------------------------------------------------------------------ (a) same answer as classify
section("(a) page function gives the same answer as calling classify directly")
for link in LINKS:
    page, ref = demo_app.check_link(system, link), direct(link)
    same = (page["verdict"] == ref["verdict"] and page["layer"] == ref["layer"]
            and abs(page["score"] - ref["score"]) < 1e-12)
    check(f"{link}", same, f"{page['verdict']} / {page['layer']} / score {page['score']:.4f}")
r3, r4, r7 = (demo_app.check_link(system, x) for x in (L3, L4, L7))
check("example.com and example.org -> unsure by bare-domain routing", (r3["verdict"], r3["layer"]) == ("unsure", "bare-domain")
      and (r4["verdict"], r4["layer"]) == ("unsure", "bare-domain"))
check("192.0.2.7/login (raw IP) -> phishing by rule R1", (r7["verdict"], r7["layer"]) == ("phishing", "rule:R1"))
r5 = demo_app.check_link(system, L5)
note(f"example.test is not a plain site name for the project (ending not on the public suffix list): "
     f"{r5['verdict']} / {r5['layer']}; note shown on page: {r5['note_no_path']}")

# ------------------------------------------------------------------ http(s):// handling
section("input: a leading http:// or https:// is removed, nothing else is changed")
check("strip_scheme: 'HTTPS://' + link + spaces -> link", demo_app.strip_scheme("  HTTPS://" + L2 + "  ") == L2)
check("strip_scheme keeps capitals in the path", demo_app.strip_scheme("HtTp://examplebank.test/Help/Contact") == "examplebank.test/Help/Contact")
check("strip_scheme keeps www.", demo_app.strip_scheme("https://www." + L3) == "www." + L3)
check("strip_scheme removes only ONE scheme", demo_app.strip_scheme("http://https://" + L3) == "https://" + L3)
a, b = demo_app.check_link(system, "https://" + L2), demo_app.check_link(system, L2)
check("https:// + examplebank.test/help/contact -> identical score and verdict", a["score"] == b["score"] and a["verdict"] == b["verdict"]
      and a["layer"] == b["layer"], f"{a['score']:.6f} vs {b['score']:.6f}")
a, b = demo_app.check_link(system, "http://" + L7), demo_app.check_link(system, L7)
check("http:// + 192.0.2.7/login -> identical score and verdict", a["score"] == b["score"] and a["verdict"] == b["verdict"]
      and a["layer"] == b["layer"], f"{a['score']:.6f} vs {b['score']:.6f}")
raw_with, raw_without = direct("https://" + L2), direct(L2)
note(f"classify on its own, without the page's strip: https:// version scores {raw_with['score']:.6f}, "
     f"plain version {raw_without['score']:.6f} ({'different: the strip is needed' if raw_with['score'] != raw_without['score'] else 'same'})")

# ------------------------------------------------------------------ (b) no network while scoring
section("(b) no network call while scoring (connections and name lookups are made to raise)")


def _blocked(*args, **kwargs):
    raise RuntimeError("NETWORK BLOCKED")


with contextlib.ExitStack() as stack:
    for obj, name in [(socket.socket, "connect"), (socket.socket, "connect_ex"), (socket, "create_connection"),
                      (socket, "getaddrinfo"), (socket, "gethostbyname"), (socket, "gethostbyname_ex"),
                      (socket, "gethostbyaddr")]:
        stack.enter_context(mock.patch.object(obj, name, _blocked))
    try:
        socket.create_connection(("127.0.0.1", 9))
        blocked_ok = False
    except RuntimeError:
        blocked_ok = True
    check("sanity: the network block really raises", blocked_ok)
    try:
        outs = [demo_app.check_link(system, x) for x in LINKS + ["https://" + L2, "http://" + L7]]
        check("check_link works on all links while the network is blocked", len(outs) == len(LINKS) + 2)
    except Exception as e:                                   # noqa: BLE001
        check("check_link works on all links while the network is blocked", False, type(e).__name__)

# static look at demo/app.py
src = APP_PATH.read_text()
tree = ast.parse(src)
imported = set()
for node in ast.walk(tree):
    if isinstance(node, ast.Import):
        imported |= {a.name for a in node.names}
    elif isinstance(node, ast.ImportFrom):
        imported.add(node.module)
forbidden = {"socket", "requests", "urllib.request", "urllib3", "http.client", "ftplib", "smtplib", "telnetlib", "webbrowser"}
check("demo/app.py imports no networking client module", not (imported & forbidden), f"imports: {sorted(i for i in imported if i)}")
bad_writes = []
for node in ast.walk(tree):
    if isinstance(node, ast.Call):
        fn = node.func
        name = fn.id if isinstance(fn, ast.Name) else fn.attr if isinstance(fn, ast.Attribute) else ""
        if name in ("write_text", "write_bytes", "mkdir", "unlink", "rename", "rmtree", "touch"):   # str.replace is fine
            bad_writes.append(name)
        if name == "open":
            consts = [a.value for a in node.args if isinstance(a, ast.Constant) and isinstance(a.value, str)]
            consts += [k.value.value for k in node.keywords if isinstance(k.value, ast.Constant) and isinstance(k.value.value, str)]
            if any(set(c) & set("wax+") for c in consts if len(c) <= 4):
                bad_writes.append("open(write mode)")
check("demo/app.py has no file-writing or deleting calls", not bad_writes, str(bad_writes))
floats = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, float)]
check("demo/app.py contains no copied thresholds (no float constants)", not floats, str(floats))

# ------------------------------------------------------------------ start-up gate
section("start-up gate refuses clearly on a wrong hash, a missing file, a wrong code hash, a wrong PYTHONHASHSEED")


def refuse(label, mutate, env=None):
    with tempfile.TemporaryDirectory() as tmp:
        c = json.loads(CONFIG.read_text())
        mutate(c)
        p = Path(tmp) / "config_copy.json"
        p.write_text(json.dumps(c))
        try:
            with mock.patch.dict(os.environ, env or {}):
                demo_app.load_system(root=ROOT, config_path=p)
            check(label, False, "it did not refuse")
        except demo_app.StartupError as e:
            check(label, True, str(e).splitlines()[0][:90])


refuse("wrong model hash", lambda c: c["models"]["4a"].__setitem__("model_sha256", "0" * 64))
refuse("missing recipe file", lambda c: c["models"]["4a"].__setitem__("recipe", "models_v2/does_not_exist.joblib"))
refuse("wrong code hash", lambda c: c["code"].__setitem__("notebooks/defence_layers.py", "1" * 64))
refuse("PYTHONHASHSEED is not 0", lambda c: None, env={"PYTHONHASHSEED": "1"})
refuse("config missing a required key", lambda c: c["systems"].pop("final_system_4a_plus_rules"))

# ------------------------------------------------------------------ (c) local only, no writes
section("(c) the server refuses non-local binding")
for host in ["0.0.0.0", "::", "", "localhost", "127.0.0.2"]:
    try:
        demo_app.make_server(system, host, 0).server_close()
        check(f"make_server refuses host {host!r}", False, "it bound")
    except ValueError:
        check(f"make_server refuses host {host!r}", True)

section("(c, d) real server in the background (own process, recorded PID), local requests only")
with socket.socket() as s:                       # pick a free port on this computer (bind only, no connection)
    s.bind(("127.0.0.1", 0))
    PORT = s.getsockname()[1]
env = dict(os.environ, PYTHONHASHSEED="0")
proc = subprocess.Popen([sys.executable, "-B", str(APP_PATH), "--port", str(PORT)], env=env,
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
PID = proc.pid
print(f"  server started in the background: PID {PID}, port {PORT}")
server_out = server_err = ""


def http_call(method, path, body=None, host=None, extra=None, raw_length=None):
    conn = http.client.HTTPConnection("127.0.0.1", PORT, timeout=60)
    try:
        conn.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
        conn.putheader("Host", host or f"127.0.0.1:{PORT}")
        data = body.encode() if body is not None else None
        if data is not None:
            conn.putheader("Content-Type", "application/x-www-form-urlencoded")
            conn.putheader("Content-Length", str(raw_length if raw_length is not None else len(data)))
        for k, v in (extra or {}).items():
            conn.putheader(k, v)
        conn.endheaders(data)
        r = conn.getresponse()
        return r.status, {k.lower(): v for k, v in r.getheaders()}, r.read().decode("utf-8", "replace")
    except OSError as e:
        return None, {}, type(e).__name__
    finally:
        conn.close()


def post_link(link):
    from urllib.parse import quote
    return http_call("POST", "/check", "link=" + quote(link, safe=""))


def parse(page):
    score = re.search(r"Model score</dt><dd>([0-9.]+)</dd>", page)
    badge = re.search(r'class="badge (\w+)"', page)
    return (float(score.group(1)) if score else None, badge.group(1) if badge else None)


try:
    for _ in range(600):                          # wait up to ~5 minutes for the model to load
        if proc.poll() is not None:
            break
        with socket.socket() as probe:
            if probe.connect_ex(("127.0.0.1", PORT)) == 0:
                break
        time.sleep(0.5)
    check("the server process is running", proc.poll() is None)
    (Path(OWN_TMP.name) / "server.pid").write_text(str(PID))        # recorded PID, inside this script's own temp folder

    try:
        lsof = subprocess.run(["lsof", "-nP", "-a", "-p", str(PID), "-iTCP", "-sTCP:LISTEN"], capture_output=True, text=True)
    except FileNotFoundError:
        lsof = None
    if lsof is not None and lsof.returncode == 0 and lsof.stdout:
        check("the server listens on 127.0.0.1 only", f"127.0.0.1:{PORT}" in lsof.stdout and f"*:{PORT}" not in lsof.stdout,
              lsof.stdout.strip().splitlines()[-1][-60:])
    else:
        note("NOT TESTED: could not read the listening address with lsof")

    status, hdr, page = http_call("GET", "/")
    check("GET / -> 200 and the form page", status == 200 and 'name="link"' in page)
    check("(d) warning banner is on the form page", BANNER in page)
    check("footer text is on the page", FOOTER in page)
    check("page says http:// or https:// is removed before checking", "http:// or https:// at the start of a link is removed before checking" in page)
    check("page says this is the second view, not the main final test", "second view" in page and "not the same setup as the main final test" in page)
    check('text box has autocomplete="off" and spellcheck="false"', 'autocomplete="off"' in page and 'spellcheck="false"' in page)
    check("no outside resources in the page (no http(s) URL in src/href/action)", not re.search(r'(src|href|action)="https?://', page))
    check("response headers: no-store and a restrictive Content-Security-Policy",
          hdr.get("cache-control") == "no-store" and "default-src 'none'" in hdr.get("content-security-policy", ""))

    status, hdr, page1 = post_link(L1)
    check("POST /check with a link -> 200 with a verdict, score and layer", status == 200 and parse(page1)[0] is not None
          and parse(page1)[1] in ("phishing", "safe", "unsure") and "Decided by" in page1)
    check("(d) warning banner is on the result page", BANNER in page1)
    ref = direct(L1)
    check("page verdict and score equal classify's", parse(page1)[1] == ref["verdict"] and abs(parse(page1)[0] - ref["score"]) < 5e-4)

    _, _, p_plain = post_link(L2)
    _, _, p_https = post_link("https://" + L2)
    check("over HTTP: https://-link and plain link give the same score and verdict", parse(p_plain) == parse(p_https) and parse(p_https)[0] is not None)
    check("the result page shows what was checked after the scheme was removed", "Checked as" in p_https and "Checked as" not in p_plain)
    _, _, p_ip = post_link("http://" + L7)
    check("raw-IP link over HTTP -> phishing by rule R1", parse(p_ip)[1] == "phishing" and "rule R1" in p_ip)
    _, _, p_bare = post_link(L3)
    check("a plain site name over HTTP -> unsure, with the plain explanation",
          parse(p_bare)[1] == "unsure" and "just a site name with no path" in p_bare)
    _, _, p_empty = post_link("   ")
    check("an empty link gets a polite message", "Please paste a link." in p_empty)

    check("GET /check is refused (links are never taken from the address bar)", http_call("GET", "/check")[0] == 405)
    st_q, _, body_q = http_call("GET", "/check?link=" + L1)
    check("GET /check?link=... is refused too and gives no verdict", st_q == 405 and parse(body_q)[1] is None)
    check("Host header 'localhost:PORT' is rejected (GET)", http_call("GET", "/", host=f"localhost:{PORT}")[0] == 403)
    check("Host header 'localhost:PORT' is rejected (POST)", http_call("POST", "/check", "link=" + L2, host=f"localhost:{PORT}")[0] == 403)
    check("unknown path -> 404", http_call("GET", "/nothing")[0] == 404 and http_call("POST", "/other", "link=" + L2)[0] == 404)
    check("favicon -> 204 (no error page)", http_call("GET", "/favicon.ico")[0] == 204)
    check("a Content-Length that is not a number -> 400", http_call("POST", "/check", "link=" + L2, raw_length="x")[0] == 400)
    big = "link=" + (L2 * 200)
    st_big = http_call("POST", "/check", big)[0]
    check("a body over 4096 bytes is refused (413) or the connection is closed", st_big in (413, None), str(st_big))
    check("the server still answers after the bad requests", http_call("GET", "/")[0] == 200)
finally:
    if proc.poll() is None:
        proc.terminate()                            # only the process started above, by its PID
        try:
            proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
    server_out, server_err = proc.communicate()

time.sleep(0.3)
try:
    os.kill(PID, 0)
    gone = False
except ProcessLookupError:
    gone = True
except PermissionError:
    gone = False
check(f"server PID {PID} has stopped", gone)
with socket.socket() as probe:
    check(f"port {PORT} is closed again", probe.connect_ex(("127.0.0.1", PORT)) != 0)

section("(c) the pasted text is not printed, logged or stored")
out_lines = server_out.strip().splitlines()
check("server stdout holds only the start-up line", len(out_lines) == 1 and out_lines[0].startswith("Listening on http://127.0.0.1:")
      and not any(x in server_out for x in LINKS), f"{len(out_lines)} line(s)")
check("server stderr holds no link", not any(x in server_err for x in LINKS), f"{len(server_err)} characters")

SKIP = {".venv", ".git", "data", "data_v2", "models", "models_v2", "__pycache__", "node_modules"}


def modified_files(top, depth_cap=None, file_cap=60000):
    seen = 0
    for dirpath, dirs, files in os.walk(top):
        if top == ROOT:
            dirs[:] = [d for d in dirs if d not in SKIP]
        if depth_cap is not None and len(Path(dirpath).relative_to(top).parts) >= depth_cap:
            dirs[:] = []
        for f in files:
            seen += 1
            if seen > file_cap:
                return
            p = os.path.join(dirpath, f)
            try:
                st = os.stat(p)
                if st.st_mtime >= T0 - 1 and st.st_size < 3_000_000:
                    yield p
            except OSError:
                continue


hits = []
for top, depth in [(ROOT, None), (Path(tempfile.gettempdir()), 4)]:
    for p in modified_files(top, depth):
        try:
            data = Path(p).read_bytes()
        except OSError:
            continue
        if any(x.encode() in data for x in LINKS if "." in x and len(x) > 12):
            hits.append(p)
check("no file in the repo or the OS temp folder, changed during this run, contains a pasted link", not hits,
      f"{len(hits)} file(s)" + (": " + ", ".join(hits[:3]) if hits else ""))

# ------------------------------------------------------------------ summary
OWN_TMP.cleanup()
print(f"\n{sum(results)} of {len(results)} checks passed.")
sys.exit(0 if all(results) else 1)
