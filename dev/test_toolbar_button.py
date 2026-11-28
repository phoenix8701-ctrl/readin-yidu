"""The ReadIN button in Zotero's PDF reader toolbar (v0.8.2), in a throwaway test Zotero (about 1 minute).

Users said the ReadIN button in the reader's top right sometimes isn't there and only right-click works.
Zotero asks plugins for toolbar buttons only at the moment it draws a reader's toolbar, and it starts plugins
one after another. With a slow plugin before ours, the PDF Zotero reopens from last time was drawn before
we were listening: no button. Checks:
1. A PDF already open when the plugin (re)starts gets exactly one button, also in its own window,
   and the button works; turning the plugin off takes it away; restarting twice still leaves one.
2. Zotero restarts with a PDF tab open and a slow plugin (dev/slow-plugin, 8 s) starting before ours:
   the reopened PDF has the button.

    python3 dev/test_toolbar_button.py
    YIDU_XPI=dist/readin-yidu-0.8.1.xpi python3 dev/test_toolbar_button.py   # the old version: part 2 fails
"""

import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from zotero_kit import REPO, TestZotero  # noqa: E402

PORT = 23209  # never 23119: that is the Zotero people use every day
PLUGIN_ID = "yidu@readin.cc"
SLOW = REPO / "dev" / "slow-plugin"
SLOW_ID = "yidu-slow-test@readin.cc"
failures = []


def check(name, ok, detail=""):
    print(("  ok   " if ok else "  FAIL ") + name + ("" if ok else f"  -> {detail}"))
    if not ok:
        failures.append(name)


# Every reader open now: in a tab or its own window, is its toolbar drawn, how many ReadIN buttons.
READERS = """
  for (let i = 0; i < 80; i++) {
    const rs = Zotero.Reader._readers || [];
    if (rs.length && rs.every((r) => r._iframeWindow?.document?.querySelector('.toolbar .custom-sections'))) break;
    await Zotero.Promise.delay(250);
  }
  await Zotero.Promise.delay(500);
  return (Zotero.Reader._readers || []).map((r) => ({
    window: !r.tabID,
    buttons: r._iframeWindow?.document?.querySelectorAll('.toolbar .readin-yidu-open').length ?? null,
  }));
"""

TOGGLE = """
  const { AddonManager } = ChromeUtils.importESModule("resource://gre/modules/AddonManager.sys.mjs");
  const addon = await AddonManager.getAddonByID("yidu@readin.cc");
  await addon.%s(); await Zotero.Promise.delay(800); return addon.isActive;
"""


class RestartingZotero(TestZotero):
    """The same test profile, quit and started again (TestZotero.start always makes a new one)."""

    def quit(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self.log.close()

    def relaunch(self, name, wait_for_plugin=True):
        self.log = open(self.tmp / f"{name}.log", "w")
        self.proc = subprocess.Popen(
            [self.binary, "-no-remote", "-profile", str(self.tmp / "profile"), "-ZoteroDebugText"],
            env=dict(os.environ, MOZ_HEADLESS="1"), stdout=self.log, stderr=subprocess.STDOUT,
        )
        deadline = time.time() + 90
        while time.time() < deadline:
            try:
                if wait_for_plugin:
                    if self.call("GET", "/readin/ping")[0] == 200:
                        return
                elif self.eval("return 1") == 1:
                    return
            except Exception:  # not answering yet
                pass
            if self.proc.poll() is not None:
                raise RuntimeError(f"test Zotero quit; log: {self.tmp / name}.log")
            time.sleep(0.5)
        raise RuntimeError("test Zotero did not answer within 90 s")

    def log_lines(self, name):
        return (self.tmp / f"{name}.log").read_text(encoding="utf-8", errors="replace").splitlines()


def first(lines, *words):
    return next((i for i, line in enumerate(lines) if all(w in line for w in words)), None)


def main():
    started = time.time()
    # startupScanScopes: notice plugins added to the profile's extensions folder between starts
    z = RestartingZotero(port=PORT, prefs={"extensions.startupScanScopes": 15})
    assert z.port != 23119
    z.start()
    try:
        print(f"test Zotero {z.ping['zotero']}, plugin {z.ping['version']}")
        pdf_key = next(p["pdf"] for p in z.seed() if p["pdf"])
        pdf_id = z.eval(f'return Zotero.Items.getByLibraryAndKey(Zotero.Libraries.userLibraryID, "{pdf_key}").id')

        print("a PDF already open when the plugin starts")
        readers = z.eval(f"await Zotero.Reader.open({pdf_id});" + READERS)
        check("open a PDF: one button", readers == [{"window": False, "buttons": 1}], readers)
        readers = z.eval(f"await Zotero.Reader.open({pdf_id}, null, {{ openInWindow: true }});" + READERS)
        check("and in its own window: one button", sorted(r["buttons"] for r in readers) == [1, 1], readers)
        z.eval(TOGGLE % "disable")
        readers = z.eval(READERS)
        check("plugin turned off: the open PDFs have no button left", [r["buttons"] for r in readers] == [0, 0], readers)
        z.eval(TOGGLE % "enable")
        readers = z.eval(READERS)
        check("plugin started while the PDFs are open (like after an update): one button each",
              [r["buttons"] for r in readers] == [1, 1], readers)
        for _ in range(2):
            z.eval(TOGGLE % "disable")
            z.eval(TOGGLE % "enable")
        readers = z.eval(READERS)
        check("restarted twice more: still one each", [r["buttons"] for r in readers] == [1, 1], readers)
        clicked = z.eval("""
          const Y = Zotero.__readinYidu; const real = Y.openInReadIN; let got = null;
          Y.openInReadIN = (key) => { got = key; return Promise.resolve('test'); };
          try {
            const r = Zotero.Reader._readers.find((x) => x.tabID);
            r._iframeWindow.document.querySelector('.readin-yidu-open').click();
            await Zotero.Promise.delay(200);
          } finally { Y.openInReadIN = real; }
          return got;""")
        check("the added button opens that paper in ReadIN", clicked == pdf_key, clicked)
        z.eval("for (const r of [...Zotero.Reader._readers]) if (!r.tabID) r.close(); return 1;")

        print("Zotero restarts with the PDF tab open, a slow plugin starting before ours")
        z.eval("await Zotero.Promise.delay(500); await Zotero.Session.save(); return 1;")
        z.quit()
        ext = z.tmp / "profile" / "extensions"
        ours = next(p for p in ext.iterdir() if p.name.startswith(PLUGIN_ID))
        kept = ours.read_bytes()
        # Zotero starts plugins in the order they were installed: start once without ours, then put it back,
        # so it is installed after the slow plugin (like someone who had other plugins before ReadIN 译读).
        ours.unlink()
        (ext / SLOW_ID).write_text(str(SLOW))
        z.relaunch("without-ours", wait_for_plugin=False)
        z.quit()
        ours.write_bytes(kept)
        z.relaunch("restart")
        lines = z.log_lines("restart")
        slow_at = first(lines, "Calling bootstrap method 'startup'", SLOW_ID)
        ours_at = first(lines, "Calling bootstrap method 'startup'", PLUGIN_ID + " ")
        tab_at = first(lines, "Notifier.trigger('select', 'tab'", "reader-loading")
        check("the slow plugin started before ours, the PDF tab was reopened before ours",
              None not in (slow_at, ours_at, tab_at) and slow_at < ours_at and tab_at < ours_at, (slow_at, tab_at, ours_at))
        readers = z.eval(READERS)
        check("the reopened PDF has the button", readers == [{"window": False, "buttons": 1}], readers)
        readers = z.eval(f"await Zotero.Reader.open({pdf_id}, null, {{ allowDuplicate: true }});" + READERS)
        check("a PDF opened afterwards too", [r["buttons"] for r in readers] == [1, 1], readers)
    finally:
        z.stop()

    print(f"\n{'all passed' if not failures else str(len(failures)) + ' failed'} in {time.time() - started:.0f} s")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
