"""Tests for the bridge, against a throwaway Zotero (about 30 seconds).

    python3 dev/test_bridge.py
"""

import base64
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from zotero_kit import TEST_PDFS, TestZotero  # noqa: E402

failures = []


def check(name, ok, detail=""):
    print(("  ok   " if ok else "  FAIL ") + name + ("" if ok else f"  -> {detail}"))
    if not ok:
        failures.append(name)


def unb64(s):
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def main():
    started = time.time()
    with TestZotero() as z:
        print(f"test Zotero {z.ping['zotero']}, plugin {z.ping['version']}")
        seeded = {row["title"]: row for row in z.seed()}
        notes = seeded["Notes on Reading: How Annotation Shapes Memory"]
        long_doc = seeded["A Twenty-Page Study of Long Documents"]

        print("who may connect")
        status, body = z.call("GET", "/readin/ping")
        check("ReadIN page gets an answer", status == 200 and body["plugin"] == "readin-yidu" and body["api"] == 2, body)
        check("answer allows that page (CORS)", z.last_headers.get("Access-Control-Allow-Origin") == "https://beta.anqapdf.app", z.last_headers)
        for origin in ["https://cn-beta.anqapdf.app", "https://readin.cc"]:
            status, _ = z.call("GET", "/readin/ping", origin=origin)
            check(f"{origin} allowed", status == 200, status)
        status, body = z.call("GET", "/readin/items", origin="https://evil.example.org")
        check("other website refused", status == 403 and "Access-Control-Allow-Origin" not in z.last_headers, (status, body))
        status, _ = z.call("GET", "/readin/items", origin="null")
        check("file:// page refused (no test origins set)", status == 403, status)
        status, _ = z.call("GET", "/readin/items", origin=None, headers={"User-Agent": "Mozilla/5.0"})
        check("browser request without Origin refused", status in (403, 0) or status >= 400, status)

        print("which ReadIN to open")
        check("default is the international site", z.ping["site"] == "https://beta.anqapdf.app", z.ping)
        status, body = z.call("POST", "/readin/hello", {}, origin="https://cn-beta.anqapdf.app")
        check("hello from the mainland site switches to it", status == 200 and body["site"] == "https://cn-beta.anqapdf.app", body)
        z.call("POST", "/readin/hello", {})
        status, body = z.call("GET", "/readin/ping")
        check("hello from the international site switches back", body["site"] == "https://beta.anqapdf.app", body)

        print("papers and collections")
        status, body = z.call("GET", "/readin/collections")
        names = sorted(c["name"] for c in body["collections"])
        check("collections listed", names == ["方法", "论文"], names)
        status, body = z.call("GET", "/readin/items")
        titles = sorted(i["title"] for i in body["items"])
        check("all papers listed, incl. standalone PDF", len(titles) == 5, titles)
        paper = next(i for i in body["items"] if i["key"] == notes["item"])
        check("CSL title and authors", paper["csl"]["title"].startswith("Notes on Reading") and paper["csl"]["author"][1]["family"] == "Chen", paper["csl"])
        check("paper lists its PDF", [p["key"] for p in paper["pdfs"]] == [notes["pdf"]], paper["pdfs"])
        no_pdf = next(i for i in body["items"] if i["title"] == "A Paper Without Its PDF")
        check("paper without PDF has empty pdfs", no_pdf["pdfs"] == [], no_pdf)
        status, body = z.call("GET", "/readin/items?collection=" + notes["collection"])
        check("filter by collection", sorted(i["title"] for i in body["items"]) == sorted(["Notes on Reading: How Annotation Shapes Memory", "城市绿地与居民健康的关系"]), body)
        chinese = next(i for i in body["items"] if i["title"].startswith("城市"))
        check("Chinese title and author", chinese["csl"]["author"][0]["family"] == "王" and chinese["csl"]["container-title"] == "城市规划学刊", chinese["csl"])
        status, body = z.call("GET", "/readin/items?collection=NOPE1234")
        check("unknown collection -> 404", status == 404, (status, body))

        status, body = z.call("GET", "/readin/item?key=" + notes["pdf"])
        check("item by PDF key -> parent paper + that PDF", body["item"]["key"] == notes["item"] and body["pdf"]["key"] == notes["pdf"], body)
        status, body = z.call("GET", "/readin/item?key=" + notes["item"])
        check("item by paper key -> its PDF", body["pdf"]["key"] == notes["pdf"], body)
        status, body = z.call("GET", "/readin/item?key=ZZZZZZZZ")
        check("unknown key -> 404", status == 404, (status, body))

        print("PDF files")
        t0 = time.time()
        status, body = z.call("GET", "/readin/file?key=" + long_doc["pdf"])
        raw = unb64(body["base64url"])
        original = (TEST_PDFS / "长文档测试-20页.pdf").read_bytes()
        check(f"20-page PDF arrives byte for byte ({len(raw)} bytes, {int((time.time() - t0) * 1000)} ms)", raw == original, (len(raw), len(original)))
        status, body = z.call("GET", "/readin/file?key=" + notes["item"])
        check("asking for a paper (not a PDF) -> 400", status == 400, (status, body))
        z.eval(f"""
          const att = Zotero.Items.getByLibraryAndKey(Zotero.Libraries.userLibraryID, "{seeded['城市绿地与居民健康的关系']['pdf']}");
          await IOUtils.remove(await att.getFilePathAsync());
        """)
        status, body = z.call("GET", "/readin/file?key=" + seeded["城市绿地与居民健康的关系"]["pdf"])
        check("PDF missing on disk -> 404 with a reason", status == 404 and "not on this computer" in body["error"], (status, body))

        print("highlights")
        rect = [63, 701.67, 267.99, 719.67]
        status, body = z.call("POST", "/readin/annotations/save", {
            "attachmentKey": notes["pdf"],
            "annotation": {"type": "highlight", "text": "Chapter 1. Notes on Reading", "comment": "随想：这是重点", "color": "#ffd400", "pageIndex": 0, "rects": [rect], "top": 72},
        })
        check("create highlight", status == 200 and len(body.get("key", "")) == 8, (status, body))
        key = body["key"]
        status, body = z.call("GET", "/readin/annotations?key=" + notes["pdf"])
        a = body["annotations"][0]
        check("read it back", len(body["annotations"]) == 1 and a["text"] == "Chapter 1. Notes on Reading" and a["comment"] == "随想：这是重点", a)
        check("position and sort order", a["position"] == {"pageIndex": 0, "rects": [rect]} and a["sortIndex"] == "00000|000000|00072", a)
        status, body = z.call("POST", "/readin/annotations/save", {
            "attachmentKey": notes["pdf"],
            "annotation": {"key": key, "type": "highlight", "text": "Chapter 1. Notes on Reading", "comment": "改过的随想", "color": "#2ea8e5", "pageIndex": 0, "rects": [rect]},
        })
        status, body = z.call("GET", "/readin/annotations?key=" + notes["pdf"])
        a = body["annotations"][0]
        check("update same highlight (comment, color)", len(body["annotations"]) == 1 and a["comment"] == "改过的随想" and a["color"] == "#2ea8e5", body)
        status, body = z.call("POST", "/readin/annotations/save", {
            "attachmentKey": notes["pdf"],
            "annotation": {"type": "note", "comment": "一张便签", "pageIndex": 1, "rects": [[100, 500, 122, 522]]},
        })
        check("create sticky note on page 2", status == 200, (status, body))
        bad_cases = [
            ({"type": "ink", "pageIndex": 0, "rects": [rect]}, "unsupported type"),
            ({"type": "highlight", "pageIndex": -1, "rects": [rect]}, "negative page"),
            ({"type": "highlight", "pageIndex": 0, "rects": [[1, 2, 3]]}, "bad rect"),
            ({"key": notes["item"], "type": "highlight", "pageIndex": 0, "rects": [rect]}, "key of a paper"),
            ({"key": "not-a-key!", "type": "highlight", "pageIndex": 0, "rects": [rect]}, "malformed key"),
        ]
        for annotation, label in bad_cases:
            status, body = z.call("POST", "/readin/annotations/save", {"attachmentKey": notes["pdf"], "annotation": annotation})
            check(f"refuse {label}", status == 400, (status, body))
        status, body = z.call("POST", "/readin/annotations/save", {"attachmentKey": long_doc["pdf"], "annotation": {"key": key, "type": "highlight", "pageIndex": 0, "rects": [rect]}})
        check("refuse moving a highlight to another PDF", status == 400, (status, body))
        status, body = z.call("POST", "/readin/annotations/save", "not json")
        check("refuse a body that is not JSON", status == 400, (status, body))

        status, body = z.call("POST", "/readin/annotations/delete", {"attachmentKey": notes["pdf"], "keys": [key, "ZZZZZZZZ"]})
        check("delete -> only real keys trashed", body == {"trashed": [key]}, body)
        in_trash = z.eval(f'return Zotero.Items.getByLibraryAndKey(Zotero.Libraries.userLibraryID, "{key}").deleted')
        check("deleted highlight is in Zotero's trash (can undo)", in_trash is True, in_trash)
        status, body = z.call("GET", "/readin/annotations?key=" + notes["pdf"])
        check("trashed highlight no longer listed", [x["type"] for x in body["annotations"]] == ["note"], body)
        status, body = z.call("POST", "/readin/annotations/save", {
            "attachmentKey": notes["pdf"],
            "annotation": {"key": key, "type": "highlight", "text": "Chapter 1. Notes on Reading", "pageIndex": 0, "rects": [rect]},
        })
        restored = z.eval(f'return Zotero.Items.getByLibraryAndKey(Zotero.Libraries.userLibraryID, "{key}").deleted')
        check("saving a trashed highlight again brings it back", status == 200 and restored is False, (status, body, restored))
        external = z.eval(f"""
          const att = Zotero.Items.getByLibraryAndKey(Zotero.Libraries.userLibraryID, "{notes['pdf']}");
          const a = await Zotero.Annotations.saveFromJSON(att, {{ key: Zotero.DataObjectUtilities.generateKey(), type: "highlight", text: "x", comment: "", color: "#ffd400",
            pageLabel: "1", sortIndex: "00000|000000|00010", position: {{ pageIndex: 0, rects: [[1, 1, 2, 2]] }}, isExternal: true }});
          return a.key;
        """)
        status, body = z.call("POST", "/readin/annotations/save", {"attachmentKey": notes["pdf"], "annotation": {"key": external, "type": "highlight", "pageIndex": 0, "rects": [rect]}})
        check("refuse editing a highlight stored inside the PDF file", status == 400, (status, body))
        status, body = z.call("POST", "/readin/annotations/delete", {"attachmentKey": notes["pdf"], "keys": [external]})
        check("refuse deleting a highlight stored inside the PDF file", body == {"trashed": []}, body)

        print("notes")
        html = "<h1>ReadIN 笔记</h1><p>AI 总结：批注帮助记忆。</p>"
        status, body = z.call("POST", "/readin/notes/save", {"parentKey": notes["item"], "html": html})
        check("create note under the paper", status == 200, (status, body))
        note_key = body["key"]
        saved = z.eval(f'return Zotero.Items.getByLibraryAndKey(Zotero.Libraries.userLibraryID, "{note_key}").getNote()')
        check("note text kept (Chinese)", "AI 总结：批注帮助记忆。" in saved, saved)
        status, body = z.call("POST", "/readin/notes/save", {"parentKey": notes["item"], "noteKey": note_key, "html": html.replace("记忆", "理解")})
        count = z.eval(f'return Zotero.Items.getByLibraryAndKey(Zotero.Libraries.userLibraryID, "{notes["item"]}").getNotes().length')
        check("update the same note, not a second one", body["key"] == note_key and count == 1, (body, count))
        z.eval(f'await Zotero.Items.trashTx([Zotero.Items.getByLibraryAndKey(Zotero.Libraries.userLibraryID, "{note_key}").id])')
        status, body = z.call("POST", "/readin/notes/save", {"parentKey": notes["item"], "noteKey": note_key, "html": html})
        check("user trashed our note -> a new one is made", status == 200 and body["key"] != note_key, body)
        status, body = z.call("POST", "/readin/notes/save", {"parentKey": notes["pdf"], "html": html})
        check("refuse a note under a PDF", status == 400, (status, body))

        print("translated PDFs back into Zotero (v0.2.0)")
        pdf_bytes = sorted(TEST_PDFS.glob("*.pdf"))[0].read_bytes()
        b64 = base64.urlsafe_b64encode(pdf_bytes).decode().rstrip("=")
        status, body = z.call("GET", f"/readin/translations?key={notes['item']}")
        check("no translations yet", status == 200 and body == {"items": []}, body)
        status, body = z.call("POST", "/readin/attach", {"parentKey": notes["pdf"], "files": [{"name": "Notes（中文译文）.pdf", "title": "Notes（中文译文）", "base64url": b64}]})
        check("attach a translated PDF (given the PDF's key, it goes under the paper)", status == 200 and len(body.get("items", [])) == 1, (status, body))
        first = body["items"][0]["key"] if status == 200 else ""
        info = z.eval(f"""
          const a = Zotero.Items.getByLibraryAndKey(Zotero.Libraries.userLibraryID, "{first}");
          const path = await a.getFilePathAsync();
          return {{ parent: a.parentItem.key, title: a.getField("title"), tag: a.hasTag("ReadIN 译文"), pdf: a.isPDFAttachment(), size: (await IOUtils.read(path)).length }};
        """)
        check("saved as a child PDF with title and tag, same bytes", info == {"parent": notes["item"], "title": "Notes（中文译文）", "tag": True, "pdf": True, "size": len(pdf_bytes)}, info)
        status, body = z.call("GET", f"/readin/translations?key={notes['item']}")
        check("translations lists it", [i["key"] for i in body["items"]] == [first], body)
        status, body = z.call("POST", "/readin/attach", {"parentKey": notes["item"], "replace": [first, notes["pdf"]], "files": [
            {"name": "Notes（中文译文）.pdf", "title": "Notes（中文译文）", "base64url": b64},
            {"name": "Notes（中英对照）.pdf", "title": "Notes（中英对照）", "base64url": b64}]})
        newer = [i["key"] for i in body.get("items", [])]
        status2, listed = z.call("GET", f"/readin/translations?key={notes['item']}")
        original_ok = z.eval(f'return !Zotero.Items.getByLibraryAndKey(Zotero.Libraries.userLibraryID, "{notes["pdf"]}").deleted')
        check("save again replacing the earlier one: old one in the trash, the original PDF untouched (not ours)", status == 200 and body.get("trashed") == 1
              and sorted(i["key"] for i in listed["items"]) == sorted(newer) and original_ok, (body, listed, original_ok))
        status, body = z.call("POST", "/readin/attach", {"parentKey": notes["item"], "files": [{"name": "x.pdf", "base64url": base64.urlsafe_b64encode(b"hello world").decode()}]})
        check("refuse something that is not a PDF", status == 400, (status, body))
        status, body = z.call("POST", "/readin/attach", {"parentKey": notes["item"], "files": []})
        check("refuse an empty list", status == 400, (status, body))
        status, body = z.call("POST", "/readin/open", {"key": newer[0] if newer else ""})
        check("open in Zotero's reader", status == 200 and body.get("ok") is True, (status, body))

        print("menu and reader button")
        found = z.eval("""
          const listeners = Zotero.Reader._registeredListeners.filter((l) => l.pluginID === "yidu@readin.cc");
          return listeners.map((l) => l.type);
        """)
        check("reader toolbar button registered", found == ["renderToolbar"], found)
        check("right-click menu registered", z.ping.get("menu") is True, z.ping)

        print("turning the plugin off removes the doors")
        z.eval("""
          const { AddonManager } = ChromeUtils.importESModule("resource://gre/modules/AddonManager.sys.mjs");
          const addon = await AddonManager.getAddonByID("yidu@readin.cc");
          await addon.disable();
        """)
        status, _ = z.call("GET", "/readin/ping")
        check("after disabling: 404", status == 404, status)
        gone = z.eval('return Zotero.Reader._registeredListeners.filter((l) => l.pluginID === "yidu@readin.cc").length')
        check("after disabling: reader button gone", gone == 0, gone)

    print("never connected, in mainland China's time zone: open the mainland version (v0.1.2)")
    with TestZotero(port=23149, tz="Asia/Shanghai") as cn:
        check("Asia/Shanghai: default is the mainland site", cn.ping["site"] == "https://cn-beta.anqapdf.app", cn.ping)
        cn.call("POST", "/readin/hello", {})
        status, body = cn.call("GET", "/readin/ping")
        check("Asia/Shanghai: after connecting from the international site, open that one", body["site"] == "https://beta.anqapdf.app", body)

    print(f"\n{'all passed' if not failures else str(len(failures)) + ' failed'} in {time.time() - started:.0f} s")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
