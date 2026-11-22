"""The plugin updating itself (v0.3.0), in throwaway test Zotero instances (about 1.5 minutes).

Builds two small copies of the plugin, 0.0.1 and 0.0.2, whose update address points at a little web server
on this computer (instead of readin.cc), and checks:
1. ReadIN asks for an update (POST /readin/update): the plugin finds 0.0.2, installs it on the spot
   (no restart), and the doors work again; asking again says "latest". Other websites can't ask.
2. When Zotero starts, the plugin checks by itself and updates.
3. If automatic updates are turned off, the start-up check leaves it alone; ReadIN's "Update now" still works;
   when readin.cc can't be reached, it says "failed" (not "latest").

    python3 dev/test_update.py
"""

import json
import sys
import tempfile
import threading
import time
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from zotero_kit import REPO, TestZotero  # noqa: E402

PLUGIN_ID = "yidu@readin.cc"
failures = []


def check(name, ok, detail=""):
    print(("  ok   " if ok else "  FAIL ") + name + ("" if ok else f"  -> {detail}"))
    if not ok:
        failures.append(name)


class Server:
    """Serves /update.json (or a 404 when `broken`) and /new.xpi."""

    def __init__(self, new_xpi):
        server = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                server.hits.append(self.path)
                if self.path == "/update.json" and not server.broken:
                    body, kind = json.dumps(server.update_json()).encode(), "application/json"
                elif self.path == "/new.xpi":
                    body, kind = Path(new_xpi).read_bytes(), "application/x-xpinstall"
                else:
                    self.send_response(404)
                    self.end_headers()
                    return
                self.send_response(200)
                self.send_header("Content-Type", kind)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        self.broken = False
        self.hits = []
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.base = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def update_json(self):
        return {"addons": {PLUGIN_ID: {"updates": [{
            "version": "0.0.2",
            "update_link": f"{self.base}/new.xpi",
            "applications": {"zotero": {"strict_min_version": "10.0"}},
        }]}}}

    def close(self):
        self.httpd.shutdown()


def build_xpi(path, version, update_url):
    """Like build.py, with another version and update address."""
    manifest = json.loads((REPO / "manifest.json").read_text())
    manifest["version"] = version
    manifest["applications"]["zotero"]["update_url"] = update_url
    files = ["bootstrap.js", "LICENSE", *[p.relative_to(REPO).as_posix() for p in (REPO / "src").glob("*.js")],
             *[p.relative_to(REPO).as_posix() for p in (REPO / "icons").glob("*.png")]]
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", json.dumps(manifest, indent=2))
        for name in files:
            z.write(REPO / name, name)


def version_of(z):
    try:
        status, body = z.call("GET", "/readin/ping")
        return body.get("version") if status == 200 else None
    except OSError:
        return None  # the doors are briefly gone while the new version starts


def wait_for_version(z, version, seconds=40):
    deadline = time.time() + seconds
    while time.time() < deadline:
        if version_of(z) == version:
            return True
        time.sleep(0.5)
    return False


def main():
    started = time.time()
    tmp = Path(tempfile.mkdtemp(prefix="yidu-update-"))
    old_xpi, new_xpi = tmp / "old.xpi", tmp / "new.xpi"
    server = Server(new_xpi)
    build_xpi(old_xpi, "0.0.1", f"{server.base}/update.json")
    build_xpi(new_xpi, "0.0.2", f"{server.base}/update.json")
    # The real update address is https (readin.cc); the little test server is plain http, which Zotero only accepts with this.
    insecure = {"extensions.checkUpdateSecurity": False}

    try:
        print("1. ReadIN asks for an update")
        with TestZotero(port=23141, xpi=old_xpi, prefs=insecure) as z:
            ping = z.ping
            check("old copy runs: 0.0.1, can update (api 4, update: true)", ping["version"] == "0.0.1" and ping["api"] == 4 and ping.get("update") is True, ping)
            status, _ = z.call("POST", "/readin/update", body="{}", origin="https://example.com")
            check("another website can't ask for an update", status == 403, status)
            status, body = z.call("POST", "/readin/update", body="{}")
            check("answers: updating 0.0.1 → 0.0.2", status == 200 and body == {"status": "updating", "version": "0.0.1", "to": "0.0.2"}, (status, body))
            check("installed on the spot, no restart: ping says 0.0.2", wait_for_version(z, "0.0.2"), version_of(z))
            status, body = z.call("GET", "/readin/collections")
            check("the doors work again after the update", status == 200 and "collections" in body, (status, body))
            status, body = z.call("POST", "/readin/update", body="{}")
            check("asking again: latest", status == 200 and body == {"status": "latest", "version": "0.0.2"}, (status, body))
            in_zotero = z.eval(f"""const {{ AddonManager }} = ChromeUtils.importESModule("resource://gre/modules/AddonManager.sys.mjs");
              const a = await AddonManager.getAddonByID("{PLUGIN_ID}"); return [a.version, a.isActive];""")
            check("Tools → Plugins shows 0.0.2, turned on", in_zotero == ["0.0.2", True], in_zotero)

        print("2. checks by itself when Zotero starts")
        server.hits.clear()
        with TestZotero(port=23141, xpi=old_xpi, prefs={**insecure, "extensions.readin-yidu.checkOnStart": True, "extensions.readin-yidu.checkDelay": 1}) as z:
            check("updated to 0.0.2 without anyone asking", wait_for_version(z, "0.0.2"), version_of(z))
            check("it read the update file", "/update.json" in server.hits, server.hits)

        print("3. automatic updates turned off")
        server.hits.clear()
        prefs = {**insecure, "extensions.readin-yidu.checkOnStart": True, "extensions.readin-yidu.checkDelay": 1, "extensions.update.autoUpdateDefault": False}
        with TestZotero(port=23141, xpi=old_xpi, prefs=prefs) as z:
            time.sleep(8)
            check("start-up check leaves it alone (still 0.0.1)", version_of(z) == "0.0.1" and "/update.json" not in server.hits, (version_of(z), server.hits))
            server.broken = True
            status, body = z.call("POST", "/readin/update", body="{}")
            check("can't reach the update file: failed, not latest", status == 200 and body.get("status") == "failed" and body.get("version") == "0.0.1", (status, body))
            server.broken = False
            status, body = z.call("POST", "/readin/update", body="{}")
            check("ReadIN's Update now still works: updating → 0.0.2", status == 200 and body.get("status") == "updating" and body.get("to") == "0.0.2", (status, body))
            check("installed: 0.0.2", wait_for_version(z, "0.0.2"), version_of(z))
    finally:
        server.close()

    print(f"\n{'all passed' if not failures else str(len(failures)) + ' failed: ' + ', '.join(failures)} ({time.time() - started:.0f} s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
