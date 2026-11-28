"""Tests for the bridge, against a throwaway Zotero (about 30 seconds).

    python3 dev/test_bridge.py
"""

import base64
import json
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
        check("ReadIN page gets an answer", status == 200 and body["plugin"] == "readin-yidu" and body["api"] == 9 and body.get("update") is True, body)
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

        print("which browser to open (v0.4.0)")
        url = "https://beta.anqapdf.app/#zotero=ABCD2345"
        check("not known yet", body.get("browser") == "", body)
        status, body = z.call("POST", "/readin/hello", {"browser": "edge", "ready": False})
        check("a browser where ReadIN isn't set up doesn't count", body.get("browser") == "", body)
        status, body = z.call("POST", "/readin/hello", {"browser": "edge", "ready": True})
        check("set up in Edge: remembered", body.get("browser") == "edge", body)
        check("ping says which browser", z.call("GET", "/readin/ping")[1].get("browser") == "edge")
        # Fake the launching: record what would be opened, never open a real browser
        z.eval("""Zotero.__calls = []; Zotero.__saved = { exec: Zotero.Utilities.Internal.exec, launch: Zotero.launchURL, isMac: Zotero.isMac, isWin: Zotero.isWin, program: Zotero.__readinYidu.windowsProgram };
          Zotero.Utilities.Internal.exec = async (cmd, args) => { Zotero.__calls.push(['exec', String(cmd), ...args]); if (args.includes('com.nosuch.browser')) throw new Error('exit status 1'); return true; };
          Zotero.launchURL = (u) => { if (u.startsWith('nosuch-scheme:')) throw new Error('no handler'); Zotero.__calls.push(['launch', u]); };
          return true;""")
        opened = "Zotero.__calls = []; return Zotero.__readinYidu.openInReadIN('ABCD2345').then((how) => [how, Zotero.__calls]);"
        how, calls = z.eval("Zotero.isMac = true; Zotero.isWin = false; " + opened)
        check("Mac: opens Edge by name (open -b), not the default browser", how == "edge" and calls == [["exec", "/usr/bin/open", "-b", "com.microsoft.edgemac", url]], (how, calls))
        how, calls = z.eval("Zotero.__readinYidu.BROWSERS.edge.mac = 'com.nosuch.browser'; " + opened)
        check("Mac: that browser isn't installed -> the default browser", how == "default" and calls[-1] == ["launch", url], (how, calls))
        z.eval("Zotero.__readinYidu.BROWSERS.edge.mac = 'com.microsoft.edgemac'; return true;")
        how, calls = z.eval("Zotero.isMac = false; Zotero.isWin = true; " + opened)
        check("Windows: Edge through microsoft-edge:", how == "edge" and calls == [["launch", "microsoft-edge:" + url]], (how, calls))
        how, calls = z.eval("Zotero.__readinYidu.BROWSERS.edge.scheme = 'nosuch-scheme'; Zotero.__readinYidu.windowsProgram = (exe) => exe === 'msedge.exe' ? 'C:\\\\Edge\\\\msedge.exe' : null; " + opened)
        check("Windows: no microsoft-edge: handler -> msedge.exe from App Paths", how == "edge" and calls == [["exec", "C:\\Edge\\msedge.exe", url]], (how, calls))
        z.eval("Zotero.__readinYidu.BROWSERS.edge.scheme = 'microsoft-edge'; return true;")
        z.call("POST", "/readin/hello", {"browser": "chrome", "ready": True})
        how, calls = z.eval("Zotero.__readinYidu.windowsProgram = (exe) => exe === 'chrome.exe' ? 'C:\\\\Chrome\\\\chrome.exe' : null; " + opened)
        check("Windows: set up in Chrome -> chrome.exe from App Paths", how == "chrome" and calls == [["exec", "C:\\Chrome\\chrome.exe", url]], (how, calls))
        how, calls = z.eval("Zotero.__readinYidu.windowsProgram = () => null; " + opened)
        check("Windows: Chrome not found -> the default browser", how == "default" and calls == [["launch", url]], (how, calls))
        status, body = z.call("POST", "/readin/hello", {"browser": "other", "ready": True})
        how, calls = z.eval(opened)
        check("set up in a browser we can't open by name -> the default browser", body.get("browser") == "default" and how == "default" and calls == [["launch", url]], (body, how, calls))
        z.eval("""const s = Zotero.__saved; Zotero.Utilities.Internal.exec = s.exec; Zotero.launchURL = s.launch; Zotero.isMac = s.isMac; Zotero.isWin = s.isWin;
          Zotero.__readinYidu.windowsProgram = s.program; return true;""")

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
        # v0.4.1: tags added in Zotero survive when ReadIN saves the highlight again without tags
        z.eval(f"const a = Zotero.Items.getByLibraryAndKey(Zotero.Libraries.userLibraryID, '{key}'); a.addTag('方法'); a.addTag('样本量'); return a.saveTx().then(() => true);")
        z.call("POST", "/readin/annotations/save", {
            "attachmentKey": notes["pdf"],
            "annotation": {"key": key, "type": "highlight", "text": "Chapter 1. Notes on Reading", "comment": "又改了一次", "color": "#2ea8e5", "pageIndex": 0, "rects": [rect]},
        })
        status, body = z.call("GET", "/readin/annotations?key=" + notes["pdf"])
        a = body["annotations"][0]
        check("saving again without tags keeps the tags added in Zotero (v0.4.1)", a["comment"] == "又改了一次" and sorted(t["name"] for t in a.get("tags", [])) == ["方法", "样本量"], a.get("tags"))
        z.call("POST", "/readin/annotations/save", {
            "attachmentKey": notes["pdf"],
            "annotation": {"key": key, "type": "highlight", "text": "Chapter 1. Notes on Reading", "comment": "又改了一次", "color": "#2ea8e5", "pageIndex": 0, "rects": [rect], "tags": ["方法", " 研究空白 "]},
        })
        status, body = z.call("GET", "/readin/annotations?key=" + notes["pdf"])
        a = body["annotations"][0]
        check("ReadIN sends its own tags: they replace the list", sorted(t["name"] for t in a.get("tags", [])) == ["方法", "研究空白"], a.get("tags"))
        status, body = z.call("POST", "/readin/annotations/save", {
            "attachmentKey": notes["pdf"],
            "annotation": {"type": "note", "comment": "一张便签", "pageIndex": 1, "rects": [[100, 500, 122, 522]]},
        })
        check("create sticky note on page 2", status == 200, (status, body))
        # v0.6.0: boxes (image) and text annotations can be saved too (ReadIN shows them and sends its edits)
        box = [80, 300, 260, 420]
        status, body = z.call("POST", "/readin/annotations/save", {
            "attachmentKey": notes["pdf"],
            "annotation": {"type": "image", "comment": "框住的公式", "color": "#2ea8e5", "pageIndex": 0, "rects": [box], "tags": ["公式"]},
        })
        check("create a box (image annotation)", status == 200 and len(body.get("key", "")) == 8, (status, body))
        box_key = body.get("key")
        z.call("POST", "/readin/annotations/save", {
            "attachmentKey": notes["pdf"],
            "annotation": {"key": box_key, "type": "image", "comment": "改过的想法", "color": "#ff6666", "pageIndex": 0, "rects": [box]},
        })
        status, body = z.call("GET", "/readin/annotations?key=" + notes["pdf"])
        b = next((x for x in body["annotations"] if x.get("key") == box_key), None)
        check("box read back as an image annotation with the new thought and color, tags kept", b and b["type"] == "image" and b["comment"] == "改过的想法"
              and b["color"] == "#ff6666" and b["position"]["rects"] == [box] and [t["name"] for t in b.get("tags", [])] == ["公式"], b)
        status, body = z.call("POST", "/readin/annotations/save", {
            "attachmentKey": notes["pdf"],
            "annotation": {"type": "text", "comment": "页边写的字", "color": "#ffd400", "pageIndex": 0, "rects": [[300, 650, 420, 670]], "fontSize": 12},
        })
        check("create a text annotation (keeps its font size)", status == 200, (status, body))
        status, body = z.call("GET", "/readin/annotations?key=" + notes["pdf"])
        t = next((x for x in body["annotations"] if x["type"] == "text"), None)
        check("text annotation read back with font size", t and t["comment"] == "页边写的字" and t["position"].get("fontSize") == 12, t)
        status, body = z.call("POST", "/readin/annotations/delete", {"attachmentKey": notes["pdf"], "keys": [box_key, (t or {}).get("key", "")]})
        check("delete box and text annotation", len(body.get("trashed", [])) == 2, body)
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

        print("notes with live citations (v0.5.0)")
        status, body = z.call("GET", "/readin/ping")
        check("api 9 (v0.9.0 add papers from ReadIN; v0.8.0 rename papers)", body.get("api") == 9, body)
        # a ReadIN highlight with the page number printed on the paper
        status, body = z.call("POST", "/readin/annotations/save", {
            "attachmentKey": notes["pdf"],
            "annotation": {"type": "highlight", "text": "Chapter 1. Notes on Reading", "comment": "这是想法", "color": "#ffd400", "pageIndex": 0, "rects": [rect], "pageLabel": "347"},
        })
        live_key = body["key"]
        label = z.eval(f'return Zotero.Items.getByLibraryAndKey(Zotero.Libraries.userLibraryID, "{live_key}").annotationPageLabel')
        check("highlight keeps the printed page ReadIN sends", label == "347", label)
        z.call("POST", "/readin/annotations/save", {
            "attachmentKey": notes["pdf"],
            "annotation": {"key": live_key, "type": "highlight", "text": "Chapter 1. Notes on Reading", "comment": "这是想法", "color": "#ffd400", "pageIndex": 0, "rects": [rect]},
        })
        label = z.eval(f'return Zotero.Items.getByLibraryAndKey(Zotero.Libraries.userLibraryID, "{live_key}").annotationPageLabel')
        check("saved again without a page label: keeps the one it has (not the PDF page number)", label == "347", label)
        doc = {
            "title": "ReadIN 笔记",
            "link": {"href": "https://beta.anqapdf.app/#zotero=" + notes["pdf"], "text": "在 ReadIN 打开这篇"},
            "attachmentKey": notes["pdf"],
            "sections": [
                {"heading": "我的理解", "items": [{"kind": "insight", "question": "这篇的结论是什么?", "text": "批注帮助记忆 & 理解 <b>尤其</b>是复习时"}]},
                {"heading": "高亮和想法", "items": [
                    {"kind": "highlight", "annotation": live_key, "text": "Chapter 1. Notes on Reading", "comment": "这是想法", "page": "347"},
                    {"kind": "highlight", "annotation": None, "text": "译文上的一句", "comment": "译文上画的", "page": "348", "label": "（译文）"},
                    {"kind": "highlight", "annotation": "ZZZZZZZZ", "text": "A highlight Zotero no longer has", "page": "348–349"},
                ]},
                {"heading": "随想", "items": [{"kind": "note", "text": "第一行\n第二行", "page": "350"}, {"kind": "note", "text": "   "}]},
                {"heading": "空的一节", "items": []},
            ],
        }
        status, body = z.call("POST", "/readin/notes/save", {"parentKey": notes["item"], "doc": doc})
        check("save a note from ReadIN's items", status == 200 and body.get("key") and body.get("sig"), (status, body))
        live_note, live_sig = body.get("key"), body.get("sig")
        info = z.eval(f"""
          const lib = Zotero.Libraries.userLibraryID;
          const note = Zotero.Items.getByLibraryAndKey(lib, "{live_note}");
          const paper = Zotero.Items.getByLibraryAndKey(lib, "{notes['item']}");
          const html = note.getNote();
          const Parser = typeof DOMParser !== "undefined" ? DOMParser : Zotero.getMainWindow().DOMParser;
          const d = new Parser().parseFromString(html, "text/html");
          const box = d.querySelector("div[data-schema-version]");
          const items = box ? JSON.parse(decodeURIComponent(box.getAttribute("data-citation-items"))) : [];
          const highlights = [...d.querySelectorAll("span.highlight[data-annotation]")].map((s) => JSON.parse(decodeURIComponent(s.dataset.annotation)).annotationKey);
          const cites = [...d.querySelectorAll("span.citation[data-citation]")].map((s) => JSON.parse(decodeURIComponent(s.dataset.citation)));
          // what Word's "Add Note" does with a note: Zotero's own code that turns citations into live fields
          const session = Object.create(Zotero.Integration.Session.prototype);
          const [text, citations] = await session._processNote(note);
          return {{
            title: note.getNoteTitle(), paperURI: Zotero.URI.getItemURI(paper), items: items.map((i) => i.uris[0]), itemTitle: items[0] && items[0].itemData.title,
            highlights, locators: cites.map((c) => c.citationItems[0].locator || null), uris: [...new Set(cites.map((c) => c.citationItems[0].uris[0]))],
            word: citations.map((c) => c.citationItems[0].locator || null), wordText: text,
            headings: [...d.querySelectorAll("h2")].map((h) => h.textContent), link: d.querySelector("a") && d.querySelector("a").getAttribute("href"),
            body: d.body.textContent,
          }};
        """)
        check("note title is ReadIN 笔记; link back to ReadIN", info["title"] == "ReadIN 笔记" and info["link"].endswith("#zotero=" + notes["pdf"]), info["title"])
        check("metadata container names the paper (like Zotero's own notes)", info["items"] == [info["paperURI"]] and info["itemTitle"].startswith("Notes on Reading"), info["items"])
        check("the live highlight links to its Zotero annotation (click → shows it in the PDF)", info["highlights"] == [live_key], info["highlights"])
        check("every citation points at the paper", info["uris"] == [info["paperURI"]], info["uris"])
        check("citations: 我的理解 without a page, highlights and 随想 with the printed page", info["locators"] == [None, "347", "348", "348–349", "350"], info["locators"])
        check("Word's Add Note finds 5 live citations in it (Zotero's integration code)", info["word"] == [None, "347", "348", "348–349", "350"], info["word"])
        check("empty sections and blank items are left out", info["headings"] == ["我的理解", "高亮和想法", "随想"], info["headings"])
        check("text is escaped, not run as HTML; the thought follows its highlight", "批注帮助记忆 & 理解" in info["body"] and "<b>" not in info["body"] and "这是想法" in info["body"] and "译文上画的" in info["body"], info["body"][:300])
        check("a highlight on the translation says so right after the quote", "“译文上的一句”（译文）" in info["body"], info["body"][:400])
        status, body = z.call("POST", "/readin/notes/save", {"parentKey": notes["item"], "noteKey": live_note, "sig": live_sig, "doc": doc})
        check("save again with the sig: same note", body.get("key") == live_note and not body.get("kept"), body)
        live_sig = body.get("sig")
        # Zotero's note editor rewrites markup and refreshes citation text: not an edit
        z.eval(f"""
          const note = Zotero.Items.getByLibraryAndKey(Zotero.Libraries.userLibraryID, "{live_note}");
          note.setNote(note.getNote().replace(/<span class="citation-item">[^<]*<\\/span>/g, '<span class="citation-item">Smith and Chen, 2021</span>').replace("<h2>", '<h2 style="">'));
          await note.saveTx(); return true;
        """)
        status, body = z.call("POST", "/readin/notes/save", {"parentKey": notes["item"], "noteKey": live_note, "sig": live_sig, "doc": doc})
        check("Zotero rewrote markup / citation text only: still ours, updated in place", body.get("key") == live_note and not body.get("kept"), body)
        live_sig = body.get("sig")
        # the user writes in the note in Zotero
        z.eval(f"""
          const note = Zotero.Items.getByLibraryAndKey(Zotero.Libraries.userLibraryID, "{live_note}");
          note.setNote(note.getNote().replace("</h1>", "</h1><p>我自己加的一句话</p>"));
          await note.saveTx(); return true;
        """)
        status, body = z.call("POST", "/readin/notes/save", {"parentKey": notes["item"], "noteKey": live_note, "sig": live_sig, "doc": doc})
        kept = z.eval(f'return Zotero.Items.getByLibraryAndKey(Zotero.Libraries.userLibraryID, "{live_note}").getNote()')
        check("the user edited our note: left alone (kept), a fresh note written", body.get("kept") == live_note and body.get("key") != live_note and "我自己加的一句话" in kept, body)
        fresh_note, fresh_sig = body.get("key"), body.get("sig")
        status, body = z.call("POST", "/readin/notes/remove", {"parentKey": notes["item"], "noteKey": live_note, "sig": live_sig})
        check("remove refuses a note the user edited", body == {"trashed": False}, body)
        status, body = z.call("POST", "/readin/notes/remove", {"parentKey": notes["item"], "noteKey": fresh_note, "sig": fresh_sig})
        gone = z.eval(f'return Zotero.Items.getByLibraryAndKey(Zotero.Libraries.userLibraryID, "{fresh_note}").deleted')
        check("remove trashes our own unedited note", body == {"trashed": True} and gone is True, (body, gone))
        status, body = z.call("POST", "/readin/notes/save", {"parentKey": notes["item"], "html": "<h1>ReadIN AI 整理</h1><p>要点</p>"})
        check("old-style html still works (older ReadIN), and now returns a sig", status == 200 and body.get("sig"), body)
        z.eval(f'await Zotero.Items.trashTx([Zotero.Items.getByLibraryAndKey(Zotero.Libraries.userLibraryID, "{body.get("key")}").id, Zotero.Items.getByLibraryAndKey(Zotero.Libraries.userLibraryID, "{live_note}").id])')
        z.call("POST", "/readin/annotations/delete", {"attachmentKey": notes["pdf"], "keys": [live_key]})

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
        # v0.5.1: also run for real (Zotero 9 too): the menu Zotero builds, and the button in an open PDF
        pdf_item = z.eval(f"""
          const parent = new Zotero.Item('journalArticle'); parent.setField('title', 'menu test'); await parent.saveTx();
          const att = await Zotero.Attachments.importFromFile({{ file: {json.dumps(str(sorted(TEST_PDFS.glob("*.pdf"))[0]))}, parentItemID: parent.id }});
          return [parent.id, att.id];""")
        menu_js = """
          const win = Zotero.getMainWindow();
          await win.ZoteroPane.selectItem(%d);
          await win.ZoteroPane.buildItemContextMenu();
          const popup = win.document.getElementById('zotero-itemmenu');
          popup.dispatchEvent(new win.Event('popupshowing'));
          await Zotero.Promise.delay(300);
          return [...popup.querySelectorAll('menuitem.zotero-custom-menu-item')].filter((m) => !m.hidden).map((m) => m.getAttribute('label'));
        """ % pdf_item[0]
        shown = z.eval(menu_js)
        check("right-click a paper with a PDF: one 在 ReadIN 打开", shown == ["在 ReadIN 打开"], shown)
        z.eval("""
          const { AddonManager } = ChromeUtils.importESModule("resource://gre/modules/AddonManager.sys.mjs");
          const addon = await AddonManager.getAddonByID("yidu@readin.cc");
          await addon.disable(); await Zotero.Promise.delay(500); await addon.enable(); await Zotero.Promise.delay(1500);
        """)
        shown = z.eval(menu_js)
        check("plugin restarted (like after an update): still just one, no leftover copy", shown == ["在 ReadIN 打开"], shown)
        # v0.8.1: the menu in Zotero's language: Traditional Chinese (Taiwan wording), Japanese, English
        labels = z.eval("""const Y = Zotero.__readinYidu;
          return ["zh-CN", "zh-TW", "zh-HK", "ja", "ja-JP", "en-US", "fr-FR"].map((l) => Y.t("open", l));""")
        check("menu words by Zotero's language", labels == ["在 ReadIN 打开", "在 ReadIN 中開啟", "在 ReadIN 中開啟", "ReadIN で開く", "ReadIN で開く", "Open in ReadIN", "Open in ReadIN"], labels)
        for locale, want in [("zh-TW", "在 ReadIN 中開啟"), ("ja", "ReadIN で開く"), ("en-US", "Open in ReadIN")]:
            shown = z.eval("const saved = Zotero.locale; Zotero.locale = %s; try {%s} finally { Zotero.locale = saved; }" % (json.dumps(locale), menu_js))
            check(f"right-click in a {locale} Zotero: {want}", shown == [want], shown)
        button = z.eval("""
          const reader = await Zotero.Reader.open(%d);
          for (let i = 0; i < 60; i++) {
            const b = reader?._iframeWindow?.document?.querySelector('.readin-yidu-open');
            if (b) { const text = [b.textContent, b.title]; reader.close?.(); return text; }
            await Zotero.Promise.delay(250);
          }
          return null;
        """ % pdf_item[1])
        check("open the PDF: ReadIN button in the reader toolbar", button == ["ReadIN", "在 ReadIN 打开"], button)

        print("web snapshots (v0.7.0)")
        snap = z.eval("""
          const html = '<!DOCTYPE html><html><head><meta charset="utf-8"><title>Snapshot Test</title></head><body><article><h1>Snapshot Test</h1><p>' + 'Reading on the web. '.repeat(40) + '</p></article></body></html>';
          const path = PathUtils.join(PathUtils.tempDir, 'readin-snapshot-test.html');
          await IOUtils.writeUTF8(path, html);
          const parent = new Zotero.Item('webpage'); parent.setField('title', 'A Saved Web Page'); await parent.saveTx();
          const att = await Zotero.Attachments.importFromFile({ file: path, parentItemID: parent.id, contentType: 'text/html' });
          return [parent.key, att.key, parent.id];""")
        status, body = z.call("GET", f"/readin/item?key={snap[0]}")
        check("paper with only a web snapshot: no pdf, the snapshot instead", status == 200 and body["pdf"] is None and (body.get("snapshot") or {}).get("key") == snap[1], body)
        check("the paper lists its snapshot", [x["key"] for x in body["item"].get("snapshots", [])] == [snap[1]], body["item"])
        status, body = z.call("GET", f"/readin/item?key={snap[1]}")
        check("asking for the snapshot itself: that snapshot, under its paper", body["pdf"] is None and body["snapshot"]["key"] == snap[1] and body["item"]["key"] == snap[0], body)
        status, body = z.call("GET", f"/readin/file?key={snap[1]}")
        check("snapshot file: its HTML", status == 200 and b"Snapshot Test" in unb64(body["base64url"]), (status, body.get("filename") if isinstance(body, dict) else body))
        status, body = z.call("GET", f"/readin/annotations?key={snap[1]}")
        check("snapshot annotations: an empty list, not an error", status == 200 and body["annotations"] == [], (status, body))
        status, body = z.call("GET", f"/readin/item?key={notes['item']}")
        check("paper with a PDF: still a PDF, no snapshot", body.get("pdf") and body["pdf"]["key"] in [x["key"] for x in body["item"]["pdfs"]] and body.get("snapshot") is None, body)
        shown = z.eval(menu_js.replace(f"selectItem({pdf_item[0]})", f"selectItem({snap[2]})"))
        check("right-click a paper with only a snapshot: 在 ReadIN 打开", shown == ["在 ReadIN 打开"], shown)

        print("rename a paper from ReadIN (v0.8.0)")
        plain = seeded["A Paper Without Its PDF"]
        z.eval(f'''const item = Zotero.Items.getByLibraryAndKey(Zotero.Libraries.userLibraryID, "{plain['item']}");
          item.setCreators([...item.getCreators(), {{ firstName: "Eve", lastName: "Editor", creatorType: "editor" }}]); await item.saveTx(); return true;''')
        fields = lambda key: z.eval(f'''const item = Zotero.Items.getByLibraryAndKey(Zotero.Libraries.userLibraryID, "{key}");
          return {{ title: item.getField("title"), date: item.getField("date"), journal: item.getField("publicationTitle"),
            creators: item.getCreatorsJSON().map((c) => [c.creatorType, c.firstName || "", c.lastName || c.name || ""]) }};''')
        status, body = z.call("POST", "/readin/item/update", {"key": plain["item"], "title": "  A Paper  With a Better Title "})
        got = fields(plain["item"])
        check("title only: written (spaces tidied), nothing else touched", status == 200 and body.get("changed") is True and got["title"] == "A Paper With a Better Title"
              and got["date"] == "2020" and got["journal"] == "Nowhere Journal" and got["creators"] == [["author", "Dan", "Lee"], ["editor", "Eve", "Editor"]], (status, body, got))
        check("answers the item like /readin/items (with its CSL)", body.get("item", {}).get("csl", {}).get("title") == "A Paper With a Better Title", body)
        status, body = z.call("POST", "/readin/item/update", {"key": plain["item"], "creators": [{"firstName": "Dana", "lastName": "Lee"}, {"name": "Reading Lab"}], "date": "2021"})
        got = fields(plain["item"])
        check("authors and year: authors replaced, the editor stays", status == 200 and got["creators"] == [["author", "Dana", "Lee"], ["author", "", "Reading Lab"], ["editor", "Eve", "Editor"]]
              and got["date"] == "2021" and got["title"] == "A Paper With a Better Title", got)
        status, body = z.call("POST", "/readin/item/update", {"key": plain["item"], "title": "A Paper With a Better Title"})
        check("same title again: nothing to save", status == 200 and body.get("changed") is False, body)
        status, body = z.call("POST", "/readin/item/update", {"key": plain["item"], "title": "   "})
        check("empty title refused", status == 400, (status, body))
        status, body = z.call("POST", "/readin/item/update", {"key": "ZZZZ2345", "title": "x"})
        check("unknown item: 404", status == 404, (status, body))
        loose = seeded["standalone"]
        status, body = z.call("POST", "/readin/item/update", {"key": loose["item"], "title": "A Loose PDF Renamed", "date": "1999"})
        title = z.eval(f'return Zotero.Items.getByLibraryAndKey(Zotero.Libraries.userLibraryID, "{loose["item"]}").getField("title")')
        check("a PDF without a parent: just its title", status == 200 and title == "A Loose PDF Renamed", (status, body, title))
        status, _ = z.call("POST", "/readin/item/update", {"key": plain["item"], "title": "Hacked"}, origin="https://evil.example.org")
        check("other website can't rename", status == 403 and fields(plain["item"])["title"] == "A Paper With a Better Title", status)

        print("adding a paper found from a reference (v0.9.0)")
        csl = {"type": "article-journal", "title": "Deep learning", "container-title": "Nature", "author": [{"family": "LeCun", "given": "Yann"}, {"family": "Bengio", "given": "Yoshua"}],
               "issued": {"date-parts": [[2015]]}}
        z.eval("Zotero.__readinYidu.lastFind = null; return true;")
        status, body = z.call("POST", "/readin/add", {"doi": "10.1038/nature14539", "csl": csl, "near": plain["item"]})
        new_key = body.get("key", "")
        added = z.eval(f'''const item = Zotero.Items.getByLibraryAndKey(Zotero.Libraries.userLibraryID, "{new_key}");
          return item ? {{ title: item.getField("title"), doi: item.getField("DOI"), journal: item.getField("publicationTitle"), date: item.getField("date"),
            authors: item.getCreatorsJSON().map((c) => c.lastName), collections: item.getCollections().map((id) => Zotero.Collections.get(id).key),
            type: Zotero.ItemTypes.getName(item.itemTypeID) }} : null;''') if new_key else None
        check("new paper made from what ReadIN found (title, journal, year, authors, DOI)", status == 200 and body.get("exists") is False and added
              and added["title"] == "Deep learning" and added["doi"] == "10.1038/nature14539" and added["journal"] == "Nature" and added["date"] == "2015"
              and added["authors"] == ["LeCun", "Bengio"] and added["type"] == "journalArticle", (status, body, added))
        check("put in the same collection as the paper being read", body.get("collection") is True and added and added["collections"] == [plain["collection"]], (body, added, plain["collection"]))
        check("Zotero is asked to find its PDF", z.eval("return Zotero.__readinYidu.lastFind") == new_key, z.eval("return Zotero.__readinYidu.lastFind"))
        status, body = z.call("POST", "/readin/add", {"doi": "https://doi.org/10.1038/NATURE14539", "csl": csl})
        check("same DOI again (other case, as a link): already there, nothing added", status == 200 and body.get("exists") is True and body.get("key") == new_key, body)
        status, body = z.call("POST", "/readin/add", {"doi": "10.5555/no-near-123", "csl": {"title": "A Paper Without a Home"}, "near": "ZZZZ2345"})
        home = z.eval(f'return Zotero.Items.getByLibraryAndKey(Zotero.Libraries.userLibraryID, "{body.get("key", "")}")?.getCollections().length ?? -1')
        check("unknown paper being read: added, just not in a collection", status == 200 and body.get("collection") is False and home == 0, (status, body, home))
        status, body = z.call("POST", "/readin/add", {"doi": "not a doi", "csl": csl})
        check("bad DOI refused", status == 400, (status, body))
        status, body = z.call("POST", "/readin/add", {"doi": "10.5555/untitled-1", "csl": {"title": "  "}})
        check("no title refused", status == 400, (status, body))
        status, _ = z.call("POST", "/readin/add", {"doi": "10.5555/evil-1", "csl": {"title": "Spam"}}, origin="https://evil.example.org")
        check("other website can't add", status == 403, status)

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
