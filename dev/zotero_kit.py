"""A throwaway Zotero for tests.

Starts Zotero with its own profile, its own data folder and its own port (no window), installs
ReadIN 译读 plus the test kit, and never touches the Zotero you use every day.

    with TestZotero() as z:
        z.call("GET", "/readin/ping")
        z.eval("return Zotero.version")
"""

import json
import os
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TESTKIT = REPO / "dev" / "testkit"
TEST_PDFS = REPO / "dev" / "test-pdfs"
ORIGIN = "https://beta.anqapdf.app"


class TestZotero:
    def __init__(self, port=23139, app=None, test_origins="", tz=None, xpi=None, prefs=None):
        # YIDU_ZOTERO_APP=/path/to/Zotero.app runs the tests on another Zotero (e.g. a copy of Zotero 9, v0.5.1)
        app = app or os.environ.get("YIDU_ZOTERO_APP") or "/Applications/Zotero.app"
        self.port = port
        self.xpi = xpi  # install this .xpi instead of the source folder (test_update.py builds small ones)
        self.extra_prefs = prefs or {}
        self.tz = tz  # e.g. "Asia/Shanghai": start the test Zotero in another time zone
        self.binary = str(Path(app) / "Contents" / "MacOS" / "zotero")
        self.test_origins = test_origins
        self.base = f"http://127.0.0.1:{port}"
        self.proc = None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *exc):
        self.stop()

    def start(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="yidu-zotero-"))
        profile, data = self.tmp / "profile", self.tmp / "data"
        (profile / "extensions").mkdir(parents=True)
        data.mkdir()
        # YIDU_XPI=dist/readin-yidu-x.y.z.xpi tests the packaged file instead of the source folder.
        if self.xpi:
            shutil.copy(self.xpi, profile / "extensions" / "yidu@readin.cc.xpi")
        elif os.environ.get("YIDU_XPI"):
            shutil.copy(REPO / os.environ["YIDU_XPI"], profile / "extensions" / "yidu@readin.cc.xpi")
        else:
            (profile / "extensions" / "yidu@readin.cc").write_text(str(REPO))
        (profile / "extensions" / "yidu-testkit@readin.cc").write_text(str(TESTKIT))
        prefs = {
            "extensions.zotero.dataDir": str(data),
            "extensions.zotero.useDataDir": True,
            "extensions.zotero.httpServer.port": self.port,
            "extensions.zotero.sync.autoSync": False,
            "extensions.zotero.automaticScraperUpdates": False,
            "extensions.zotero.firstRun2": False,
            "app.update.auto": False,
            "app.update.enabled": False,
            "extensions.autoDisableScopes": 0,
            "extensions.enabledScopes": 15,
            "xpinstall.signatures.required": False,
            "extensions.readin-yidu.testOrigins": self.test_origins,
            # Lets the tests reach the plugin object (Zotero.__readinYidu), e.g. to fake opening a browser (v0.4.0)
            "extensions.readin-yidu.testHooks": True,
            # The plugin checks readin.cc for a newer version when Zotero starts; not in tests (test_update.py turns it on).
            "extensions.readin-yidu.checkOnStart": False,
            **self.extra_prefs,
        }
        (profile / "user.js").write_text(
            "".join(f"user_pref({json.dumps(k)}, {json.dumps(v)});\n" for k, v in prefs.items())
        )
        env = dict(os.environ, MOZ_HEADLESS="1", **({"TZ": self.tz} if self.tz else {}))
        self.log = open(self.tmp / "zotero.log", "w")
        self.proc = subprocess.Popen(
            [self.binary, "-no-remote", "-profile", str(profile), "-ZoteroDebugText"],
            env=env, stdout=self.log, stderr=subprocess.STDOUT,
        )
        deadline = time.time() + 60
        while time.time() < deadline:
            try:
                status, body = self.call("GET", "/readin/ping")
                if status == 200:
                    self.ping = body
                    return
            except OSError:
                pass
            if self.proc.poll() is not None:
                raise RuntimeError("test Zotero quit; log: " + str(self.tmp / "zotero.log"))
            time.sleep(0.5)
        raise RuntimeError("test Zotero did not answer within 60 s")

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        if getattr(self, "log", None):
            self.log.close()
        if getattr(self, "tmp", None) and not os.environ.get("KEEP_TEST_ZOTERO"):
            shutil.rmtree(self.tmp, ignore_errors=True)

    def call(self, method, path, body=None, origin=ORIGIN, headers=None):
        """Talk to the plugin the way a web page would: GET, or POST with a plain-text JSON body."""
        data = None if body is None else (body if isinstance(body, (bytes, str)) else json.dumps(body, ensure_ascii=False))
        if isinstance(data, str):
            data = data.encode("utf-8")
        req = urllib.request.Request(self.base + path, data=data, method=method)
        if origin:
            req.add_header("Origin", origin)
        if data is not None:
            req.add_header("Content-Type", "text/plain;charset=UTF-8")
        for k, v in (headers or {}).items():
            req.add_header(k, v)
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                raw, status, self.last_headers = r.read(), r.status, dict(r.headers)
        except urllib.error.HTTPError as e:
            raw, status, self.last_headers = e.read(), e.code, dict(e.headers)
        text = raw.decode("utf-8") if raw else ""
        try:
            return status, json.loads(text) if text else None
        except ValueError:
            return status, text

    def eval(self, js):
        """Run JavaScript inside the test Zotero (test kit only)."""
        req = urllib.request.Request(self.base + "/readin-test/eval", data=js.encode("utf-8"), method="POST")
        req.add_header("Content-Type", "text/plain;charset=UTF-8")
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                result = json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            result = json.loads(e.read().decode("utf-8"))
        if "error" in result:
            raise RuntimeError(result["error"])
        return result["value"]

    def seed(self):
        """Two collections, three papers with PDFs, one paper without a PDF, one standalone PDF."""
        papers = [
            ("Notes on Reading: How Annotation Shapes Memory", "2021", "Journal of Reading Research",
             [["Alice", "Smith"], ["Bo", "Chen"]], "English test - Notes on Reading.pdf", "论文"),
            ("城市绿地与居民健康的关系", "2023", "城市规划学刊", [["伟", "王"]], "中文测试-城市绿地.pdf", "论文"),
            ("A Twenty-Page Study of Long Documents", "2019", "Document Studies",
             [["Carol", "Jones"]], "长文档测试-20页.pdf", "方法"),
            ("A Paper Without Its PDF", "2020", "Nowhere Journal", [["Dan", "Lee"]], None, "方法"),
        ]
        js = """
        const libraryID = Zotero.Libraries.userLibraryID;
        const cols = {};
        for (const name of ["论文", "方法"]) {
          const c = new Zotero.Collection(); c.libraryID = libraryID; c.name = name; await c.saveTx(); cols[name] = c;
        }
        const out = [];
        for (const [title, year, journal, authors, file, col] of PAPERS) {
          const item = new Zotero.Item("journalArticle");
          item.libraryID = libraryID;
          item.setField("title", title); item.setField("date", year); item.setField("publicationTitle", journal);
          item.setCreators(authors.map((n) => ({ firstName: n[0], lastName: n[1], creatorType: "author" })));
          item.setCollections([cols[col].id]);
          await item.saveTx();
          let att = null;
          if (file) att = await Zotero.Attachments.importFromFile({ file: DIR + "/" + file, parentItemID: item.id });
          out.push({ title, item: item.key, pdf: att && att.key, collection: cols[col].key });
        }
        const loose = await Zotero.Attachments.importFromFile({ file: DIR + "/带目录测试.pdf", libraryID });
        out.push({ title: "standalone", item: loose.key, pdf: loose.key, collection: null });
        return out;
        """.replace("PAPERS", json.dumps(papers, ensure_ascii=False)).replace("DIR", json.dumps(str(TEST_PDFS)))
        return self.eval(js)
