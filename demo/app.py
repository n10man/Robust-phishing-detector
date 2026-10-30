"""Local demo: paste a link, get a verdict from the FINAL system (model 4a + rule R1, second-view config).

The page reads the pasted TEXT only. It never opens, fetches or resolves the link. It listens on 127.0.0.1 only,
takes links by POST (so they never appear in the address bar), and does not log, print or store them.

All verdict logic is in notebooks/defence_layers.py (classify). This file only
  1. checks the saved model, recipe and code against the SHA-256 values in results/final_system_config.json,
  2. calls defence_layers.classify with the config's own settings, and
  3. shows the result.

Start (from the repo root):   PYTHONHASHSEED=0 .venv/bin/python demo/app.py   then open http://127.0.0.1:8000
"""
import argparse
import hashlib
import html
import json
import os
import re
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs     # string parsing only; nothing in this file opens a connection

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "results" / "final_system_config.json"
SYSTEM_KEY = "final_system_4a_plus_rules"
LOCAL_HOST = "127.0.0.1"
MAX_BODY = 4096          # bytes accepted in one POST
MAX_LINK = 2000          # characters of one pasted link

BANNER = ("Educational project. Not a security tool. It can be fooled by small edits "
          "and it can't judge links that are just a site name.")


class StartupError(Exception):
    """A start-up check failed. The message is shown to the user and nothing is started."""


# ------------------------------------------------------------------ start-up checks and loading
def sha256_of(path):
    with Path(path).open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


class System:
    """What the page needs: the scorer, the config dict for classify, and two numbers to show."""
    def __init__(self, dl, has_path, scorer, classify_config, false_alarm_rate):
        self.dl = dl
        self.has_path = has_path
        self.scorer = scorer
        self.classify_config = classify_config
        self.threshold = classify_config["threshold"]
        self.false_alarm_rate = false_alarm_rate


def load_system(root=ROOT, config_path=None):
    """Check everything against the config, then load the model. Raises StartupError and loads nothing if a check fails."""
    root = Path(root)
    config_path = Path(config_path) if config_path else root / "results" / "final_system_config.json"
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise StartupError("PYTHONHASHSEED is not 0 (the config says it was 0 for every run). "
                           "Start with:  PYTHONHASHSEED=0 .venv/bin/python demo/app.py")
    if not config_path.is_file():
        raise StartupError(f"the config file is missing: {config_path}")
    try:
        cfg = json.loads(config_path.read_text())
        system = cfg["systems"][SYSTEM_KEY]
        classify_config = system["second_view_abstain_classify_config"]
        model = cfg["models"][system["model"]]
        rate = cfg["target_false_alarm_rate_on_clean_validation_safe"]
        code = cfg["code"]
        to_check = [("model file", model["model"], model["model_sha256"]),
                    ("recipe file", model["recipe"], model["recipe_sha256"]),
                    ("code file", "notebooks/defence_layers.py", code["notebooks/defence_layers.py"]),
                    ("code file", "notebooks/attacks.py", code["notebooks/attacks.py"])]
    except (KeyError, TypeError, ValueError) as e:
        raise StartupError(f"the config file does not have the expected content ({type(e).__name__}: {e})")
    for label, rel, expected in to_check:
        path = root / rel
        if not path.is_file():
            raise StartupError(f"{label} is missing: {rel}")
        actual = sha256_of(path)
        if actual != expected:
            raise StartupError(f"{label} does not match the config: {rel}\n"
                               f"  expected SHA-256 {expected}\n  actual   SHA-256 {actual}")
    sys.path.insert(0, str(root / "notebooks"))          # only after every check passed
    import defence_layers as dl
    from domains import has_path
    scorer = dl.make_scorer(str(root / model["model"]), str(root / model["recipe"]))
    return System(dl, has_path, scorer, classify_config, rate)


# ------------------------------------------------------------------ scoring (calls the project's own classify)
_LEADING_SCHEME = re.compile(r"^https?://", re.IGNORECASE)


def strip_scheme(text):
    """Remove surrounding spaces and ONE leading http:// or https:// (any capitalisation). Nothing else is changed:
    no lowercasing, www. stays. Needed because the training links had no scheme, and features_v2 keeps the scheme
    in its whole-URL n-grams (it strips it only for the host features), so a pasted https:// would change the score."""
    return _LEADING_SCHEME.sub("", str(text).strip(), count=1).strip()


def check_link(system, text):
    """Verdict, score and layer for one pasted text. Only reads the text; no network."""
    link = str(text).strip().splitlines()[0].strip() if str(text).strip() else ""
    if not link:
        raise ValueError("Please paste a link.")
    if len(link) > MAX_LINK:
        raise ValueError(f"That is too long (the limit is {MAX_LINK} characters).")
    scored = strip_scheme(link)
    if not scored:
        raise ValueError("Please paste a link.")
    result = system.dl.classify(scored, system.scorer, system.classify_config)
    out = dict(result)
    out["link"] = link
    out["scored_as"] = scored
    out["threshold"] = system.threshold
    out["note_no_path"] = (result["layer"] in ("model", "abstain-band") and not system.has_path(scored))
    return out


LAYER_LABEL = {
    "model": "the model score",
    "abstain-band": "uncertain-score band (the score is close to the alert level)",
    "bare-domain": "bare-domain routing (the link is just a site name)",
    "rule:R1": "rule R1 (a raw IP address as the host)",
}


def explain(result, false_alarm_rate):
    """One plain sentence per verdict / layer (fixed text; the percentage comes from the config)."""
    layer, verdict = result["layer"], result["verdict"]
    if layer == "rule:R1":
        return ("The link uses a raw IP address instead of a site name. The project's rule R1 treats that as "
                "phishing, whatever the model score is.")
    if layer.startswith("rule:"):
        return "A project rule fired and decided this, whatever the model score is."
    if layer == "bare-domain":
        return ("This link is just a site name with no path. The model flags nearly every plain site name as "
                "phishing, so it cannot judge it. It is shown as unsure on purpose.")
    if layer == "abstain-band":
        return ("The score is close to the alert level, so the model is not confident either way. The system "
                "answers 'unsure' instead of guessing.")
    if verdict == "phishing":
        return (f"The score is at or above the alert level, so the model says this link looks like phishing. "
                f"This can be wrong: at this alert level about {false_alarm_rate * 100:.2f}% of safe links in the "
                f"validation data were flagged.")
    return ("The score is below the alert level, so the model does not flag this link. This is not proof that it "
            "is safe: the model misses some phishing links, and small edits to a link can lower its score.")


# ------------------------------------------------------------------ the page
PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Link checker (local demo)</title>
<style>
:root { color-scheme:light; --bg:#fff; --fg:#1d1d1b; --card:#fff; --line:#d9d9d4; --muted:#5b5b56; --warn-bg:#fff1c2; --warn-fg:#5c4400;
        --bad:#b42318; --good:#1a7f37; --unsure:#9a6700; }
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--fg); font:16px/1.5 system-ui, sans-serif; }
.banner { background:var(--warn-bg); color:var(--warn-fg); padding:12px 16px; text-align:center; font-weight:600; }
main { max-width:640px; margin:0 auto; padding:24px 16px 48px; }
h1 { font-size:1.5rem; margin:0 0 16px; }
form { display:flex; gap:8px; flex-wrap:wrap; }
label { width:100%; font-weight:600; }
input[type=text] { flex:1 1 320px; padding:10px 12px; font:inherit; color:inherit; background:var(--card);
                   border:1px solid var(--line); border-radius:8px; }
button { padding:10px 18px; font:inherit; font-weight:600; border:0; border-radius:8px; background:var(--fg); color:var(--bg); cursor:pointer; }
.card { margin-top:24px; padding:16px; background:var(--card); border:1px solid var(--line); border-radius:12px; }
.badge { display:inline-block; font-size:1.6rem; font-weight:800; letter-spacing:.04em; }
.phishing { color:var(--bad); } .safe { color:var(--good); } .unsure { color:var(--unsure); }
dl { display:grid; grid-template-columns:max-content 1fr; gap:4px 16px; margin:12px 0; }
dt { color:var(--muted); } dd { margin:0; word-break:break-all; }
.note { color:var(--muted); font-size:.92rem; margin:6px 0; }
form { margin-top:16px; }
.error { margin-top:16px; color:var(--bad); font-weight:600; }
footer { margin-top:32px; color:var(--muted); font-size:.9rem; }
</style></head><body>
<div class="banner" role="note">__BANNER__</div>
<main>
<h1>Link checker (local demo)</h1>
<p class="note">This demo uses the &ldquo;second view&rdquo; of the final system, the one that can answer &ldquo;unsure&rdquo;.
That is not the same setup as the main final test, which has no &ldquo;unsure&rdquo; answer.</p>
<p class="note">http:// or https:// at the start of a link is removed before checking.</p>
<form method="post" action="/check" autocomplete="off">
<label for="link">Paste a link</label>
<input type="text" id="link" name="link" maxlength="__MAXLINK__" autocomplete="off" autocapitalize="off"
       spellcheck="false" required>
<button type="submit">Check</button>
</form>
__BODY__
<footer>This page does not open the link and does not store or log it.</footer>
</main></body></html>
"""


def render_page(body=""):
    return PAGE.replace("__BANNER__", BANNER).replace("__MAXLINK__", str(MAX_LINK)).replace("__BODY__", body)


def render_result(result, false_alarm_rate):
    verdict = result["verdict"]
    layer = result["layer"]
    layer_text = LAYER_LABEL.get(layer, layer)
    scored_row = ""
    if result["scored_as"] != result["link"]:
        scored_row = f'<dt>Checked as</dt><dd>{html.escape(result["scored_as"])}</dd>'
    note = ""
    if result["note_no_path"]:
        note = ('<p class="note">This link has no path, but it is not a plain site name that the final system '
                'recognises (for example it has a subdomain, or an ending that is not on the public suffix list), '
                'so it was scored by the model. '
                'The model flags almost every link without a path, so treat this result as unreliable.</p>')
    return (
        '<section class="card" aria-live="polite">'
        f'<div class="badge {html.escape(verdict)}">{html.escape(verdict.upper())}</div>'
        '<dl>'
        f'<dt>You pasted</dt><dd>{html.escape(result["link"])}</dd>'
        f'{scored_row}'
        f'<dt>Model score</dt><dd>{result["score"]:.3f}</dd>'
        f'<dt>Alert level</dt><dd>{result["threshold"]:.3f}</dd>'
        f'<dt>Decided by</dt><dd>{html.escape(layer_text)}</dd>'
        '</dl>'
        f'<p>{html.escape(explain(result, false_alarm_rate))}</p>'
        f'{note}</section>')


def render_error(message):
    return f'<p class="error" role="alert">{html.escape(message)}</p>'


# ------------------------------------------------------------------ the server (this computer only, no logging)
class Handler(BaseHTTPRequestHandler):
    server_version = "LinkDemo"
    sys_version = ""
    protocol_version = "HTTP/1.0"

    def log_message(self, format, *args):      # no request logging at all (links must not be recorded)
        pass

    def _send(self, status, body="", extra=None):
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy",
                         "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def _simple(self, status, text, extra=None):
        self._send(status, render_page(render_error(text)), extra)

    def _host_ok(self):
        return self.headers.get("Host", "") == f"{LOCAL_HOST}:{self.server.server_port}"

    def do_GET(self):
        if not self._host_ok():
            return self._simple(403, "This page answers only to 127.0.0.1.")
        route = self.path.split("?", 1)[0]          # only the part before "?" is looked at; a query is never read
        if route == "/":
            return self._send(200, render_page())
        if route == "/favicon.ico":
            self.send_response(204)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if route == "/check":
            return self._simple(405, "Links are sent with the form on the front page (POST), not in the address bar.",
                                {"Allow": "POST"})
        return self._simple(404, "Not found.")

    def do_POST(self):
        if not self._host_ok():
            return self._simple(403, "This page answers only to 127.0.0.1.")
        if self.path != "/check":
            return self._simple(404, "Not found.")
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            return self._simple(400, "Bad request.")
        if length < 0:
            return self._simple(400, "Bad request.")
        if length > MAX_BODY:
            return self._simple(413, "That is too much text.")
        raw = self.rfile.read(length).decode("utf-8", "replace")
        text = (parse_qs(raw, keep_blank_values=True).get("link") or [""])[0]
        try:
            result = check_link(self.server.system, text)
        except ValueError as e:
            return self._send(200, render_page(render_error(str(e))))
        self._send(200, render_page(render_result(result, self.server.system.false_alarm_rate)))


class LocalServer(HTTPServer):
    def __init__(self, address, handler, system):
        super().__init__(address, handler)
        self.system = system

    def handle_error(self, request, client_address):
        # The default prints a traceback, which could contain the pasted text. Print only the exception type.
        print(f"Request error: {sys.exc_info()[0].__name__}", file=sys.stderr)


def make_server(system, host, port):
    """The only way this file starts a server. Anything except the exact address 127.0.0.1 is refused."""
    if host != LOCAL_HOST:
        raise ValueError(f"refusing to listen on {host!r}: only {LOCAL_HOST} (this computer) is allowed")
    return LocalServer((LOCAL_HOST, port), Handler, system)


def main():
    parser = argparse.ArgumentParser(description="Local link-checker demo (this computer only).")
    parser.add_argument("--port", type=int, default=8000, help="port on 127.0.0.1 (default 8000)")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("the port must be between 1 and 65535")
    try:
        system = load_system()
    except StartupError as e:
        print(f"REFUSING TO START: {e}\nNothing was started.")
        sys.exit(1)
    server = make_server(system, LOCAL_HOST, args.port)
    print(f"Listening on http://{LOCAL_HOST}:{server.server_port} (this computer only). Press Ctrl-C to stop.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
