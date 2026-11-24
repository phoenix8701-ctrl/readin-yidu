/* global Zotero, IOUtils, ChromeUtils, ReadINYidu */
// The bridge: a few doors on Zotero's own local server (port 23119 by default) so ReadIN's web page
// can list papers, fetch a PDF, and write highlights and notes back as native Zotero items.
//
// Rules the browser imposes (checked on Zotero 10 + Chrome 157, 2026-11-16):
// - Zotero blocks browser requests unless the endpoint sets allowRequestsFromUnsafeWebContent;
//   we then check the Origin header ourselves and only answer ReadIN's own pages.
// - Zotero answers OPTIONS without CORS headers, so ReadIN only sends "simple" requests:
//   GET, or POST with a plain-text body that holds JSON (no Content-Type header, no preflight).
// - Zotero's server can only send text, so PDF bytes travel as base64url.

ReadINYidu.bridge = {
  API: 6, // 2 (v0.2.0): translated PDFs saved back as attachments; 3 (v0.3.0): ReadIN can ask for an update (/readin/update);
  // 4 (v0.4.0): /readin/hello remembers the browser ReadIN is set up in, and "Open in ReadIN" opens that browser;
  // 5 (v0.5.0): notes with live Zotero citations (/readin/notes/save takes { doc }), a note the user edited is left alone
  // (sig), /readin/notes/remove, and a highlight saved again without a page label keeps the one it has;
  // 6 (v0.6.0): ReadIN also shows Zotero's image (box) and text annotations and saves its edits to them
  TAG: "ReadIN 译文",
  paths: [],

  start() {
    const Y = ReadINYidu;
    const get = (path, fn) => this.add(path, "GET", (req) => fn(req.searchParams, req));
    const post = (path, fn) => this.add(path, "POST", (req) => fn(this.json(req), req));

    get("/readin/ping", () => ({
      ok: true, plugin: "readin-yidu", version: Y.version, api: this.API, zotero: Zotero.version, site: Y.site(),
      menu: Boolean(Y.ui.menuID), update: true, browser: Y.pref("browser", ""),
    }));
    // ReadIN says hello when it connects, so "Open in ReadIN" opens the same ReadIN (international or mainland).
    // v0.4.0: and in the same browser. ReadIN sends { browser, ready }: ready is true only when ReadIN is set up in that browser
    // (its own AI access or an account), so a browser Zotero merely opened once doesn't take over. A set-up browser
    // we can't open by name ("other") means: use the default browser.
    post("/readin/hello", (body, req) => {
      if (/^https:\/\//.test(req.headers.origin)) Y.setPref("site", req.headers.origin);
      if (body && body.ready === true && typeof body.browser === "string") {
        Y.setPref("browser", Y.BROWSERS[body.browser] ? body.browser : "default");
      }
      return { ok: true, site: Y.site(), browser: Y.pref("browser", "") };
    });
    get("/readin/collections", () => ({ collections: this.collections() }));
    get("/readin/items", (q) => this.items(q.get("collection"), q.get("keys")));
    get("/readin/item", (q) => this.itemInfo(q.get("key")));
    get("/readin/file", (q) => this.file(q.get("key")));
    get("/readin/annotations", (q) => this.annotations(q.get("key")));
    post("/readin/annotations/save", (body) => this.saveAnnotation(body));
    post("/readin/annotations/delete", (body) => this.deleteAnnotations(body));
    post("/readin/notes/save", (body) => this.saveNote(body));
    post("/readin/notes/remove", (body) => this.removeNote(body));
    // v0.2.0: ReadIN's translated PDF goes back under the same paper
    get("/readin/translations", (q) => this.translations(q.get("key")));
    post("/readin/attach", (body) => this.attach(body));
    post("/readin/open", (body) => this.open(body));
    // v0.3.0: ReadIN found the plugin too old → update now through Zotero's add-on manager (updater.js)
    post("/readin/update", () => Y.updater.check({ manual: true }));
  },

  stop() {
    for (const path of this.paths) delete Zotero.Server.Endpoints[path];
    this.paths = [];
  },

  add(path, method, handler) {
    const bridge = this;
    const Endpoint = function () {};
    Endpoint.prototype = {
      supportedMethods: [method],
      supportedDataTypes: "*",
      allowRequestsFromUnsafeWebContent: true,
      // One parameter: Zotero passes { method, pathname, searchParams, headers, data } and sends what we return.
      init: async function (req) {
        return bridge.respond(req, handler);
      },
    };
    Zotero.Server.Endpoints[path] = Endpoint;
    this.paths.push(path);
  },

  async respond(req, handler) {
    const headers = { "Content-Type": "application/json; charset=utf-8" };
    const origin = req.headers.origin;
    if (!origin || !ReadINYidu.allowedOrigins().includes(origin)) {
      return [403, headers, JSON.stringify({ error: "origin not allowed" })];
    }
    headers["Access-Control-Allow-Origin"] = origin;
    headers["Vary"] = "Origin";
    try {
      return [200, headers, JSON.stringify(await handler(req))];
    } catch (e) {
      const status = e.status || (/^not found/.test(e.message) ? 404 : 500);
      if (status === 500) Zotero.logError(e);
      return [status, headers, JSON.stringify({ error: e.message })];
    }
  },

  // text/plain bodies arrive already decoded from UTF-8.
  json(req) {
    if (typeof req.data !== "string") return req.data || {};
    try {
      return JSON.parse(req.data);
    } catch (e) {
      throw this.bad("body is not JSON");
    }
  },

  bad(message) {
    const e = new Error(message);
    e.status = 400;
    return e;
  },

  collections() {
    return Zotero.Collections.getByLibrary(ReadINYidu.libraryID(), true).map((c) => ({
      key: c.key, name: c.name, parentKey: c.parentKey || null,
    }));
  },

  describe(item) {
    const Y = ReadINYidu;
    return {
      key: item.key,
      title: item.getDisplayTitle(),
      csl: Zotero.Utilities.Item.itemToCSLJSON(item),
      collections: item.getCollections().map((id) => Zotero.Collections.get(id).key),
      dateModified: Zotero.Date.sqlToISO8601(item.dateModified),
      pdfs: Y.pdfsOf(item).map((a) => ({ key: a.key, filename: a.attachmentFilename, linkMode: a.attachmentLinkMode })),
    };
  },

  async items(collectionKey, keys) {
    const Y = ReadINYidu;
    let items;
    if (keys) {
      items = keys.split(",").map((k) => Y.item(k.trim()));
    } else if (collectionKey) {
      const collection = Zotero.Collections.getByLibraryAndKey(Y.libraryID(), collectionKey);
      if (!collection) throw new Error("not found: " + collectionKey);
      items = collection.getChildItems(false, false);
    } else {
      items = await Zotero.Items.getAll(Y.libraryID(), true, false);
    }
    // Standalone PDFs (no parent item) count as papers too.
    items = items.filter((i) => i.isRegularItem() || (Y.isPDF(i) && i.isTopLevelItem()));
    return { items: items.map((i) => this.describe(i)) };
  },

  // key may be a paper or one of its PDFs; "pdf" is the PDF to open.
  itemInfo(key) {
    const Y = ReadINYidu;
    const item = Y.item(key);
    const paper = Y.isPDF(item) && item.parentItem ? item.parentItem : item;
    const pdf = Y.isPDF(item) ? item : Y.pdfsOf(paper)[0] || null;
    return { item: this.describe(paper), pdf: pdf && { key: pdf.key, filename: pdf.attachmentFilename } };
  },

  async file(key) {
    const att = ReadINYidu.item(key);
    if (!ReadINYidu.isPDF(att)) throw this.bad("not a PDF attachment");
    const path = await att.getFilePathAsync();
    if (!path) {
      const e = new Error("file not on this computer");
      e.status = 404;
      throw e;
    }
    const bytes = await IOUtils.read(path);
    return { key, filename: att.attachmentFilename, size: bytes.length, base64url: ChromeUtils.base64URLEncode(bytes, { pad: false }) };
  },

  async annotations(key) {
    const att = ReadINYidu.item(key);
    if (!ReadINYidu.isPDF(att)) throw this.bad("not a PDF attachment");
    const list = [];
    for (const a of att.getAnnotations()) list.push(await Zotero.Annotations.toJSON(a));
    return { annotations: list };
  },

  sortIndex(pageIndex, offset, top) {
    const pad = (n, width) => String(Math.max(0, Math.round(Number(n) || 0))).padStart(width, "0");
    return `${pad(pageIndex, 5)}|${pad(offset, 6)}|${pad(top, 5)}`;
  },

  async saveAnnotation({ attachmentKey, annotation: a }) {
    const Y = ReadINYidu;
    const att = Y.item(attachmentKey);
    if (!Y.isPDF(att)) throw this.bad("not a PDF attachment");
    // v0.6.0: image (a box drawn around a formula or a figure) and text (words typed on the page) too. Ink stays read-only.
    if (!a || !["highlight", "underline", "note", "image", "text"].includes(a.type)) throw this.bad("type must be highlight, underline, note, image or text");
    const pageIndex = Number(a.pageIndex);
    if (!Number.isInteger(pageIndex) || pageIndex < 0) throw this.bad("bad pageIndex");
    const rects = a.rects;
    if (!Array.isArray(rects) || !rects.length || !rects.every((r) => Array.isArray(r) && r.length === 4 && r.every(Number.isFinite))) {
      throw this.bad("rects must be [[x1, y1, x2, y2], ...]");
    }
    let existing = null;
    if (a.key) {
      try {
        Zotero.DataObjectUtilities.checkKey(a.key);
      } catch (e) {
        throw this.bad("bad key");
      }
      existing = Zotero.Items.getByLibraryAndKey(Y.libraryID(), a.key);
      if (existing) {
        if (!existing.isAnnotation() || existing.parentItemID !== att.id) throw this.bad("key belongs to something else");
        if (existing.annotationIsExternal) throw this.bad("annotation lives in the PDF file and is read-only");
        if (existing.deleted) {
          existing.deleted = false;
        }
      }
    }
    // v0.4.1: Zotero replaces an annotation's tags with the ones we pass. ReadIN doesn't send tags yet, so editing a highlight
    // in ReadIN (a thought, a color) used to wipe the tags added in Zotero. Keep them unless ReadIN sends its own list.
    const tags = Array.isArray(a.tags)
      ? a.tags.map((t) => String(t).trim()).filter(Boolean).map((name) => ({ name }))
      : existing
        ? existing.getTags().map((t) => ({ name: t.tag }))
        : [];
    const item = await Zotero.Annotations.saveFromJSON(att, {
      key: a.key || Zotero.DataObjectUtilities.generateKey(),
      type: a.type,
      text: String(a.text || ""),
      comment: String(a.comment || ""),
      color: /^#[0-9a-f]{6}$/i.test(a.color) ? a.color : "#ffd400",
      // v0.5.0: ReadIN sends the page number printed on the paper for its own highlights. Without one (a highlight made
      // in Zotero), keep the label Zotero gave it instead of falling back to the PDF page number.
      pageLabel: String(a.pageLabel || (existing && existing.annotationPageLabel) || pageIndex + 1),
      sortIndex: this.sortIndex(pageIndex, a.offset, a.top),
      position: a.type === "text"
        ? { pageIndex, rects, fontSize: Number(a.fontSize) > 0 ? Number(a.fontSize) : 14, rotation: Number(a.rotation) || 0 }
        : { pageIndex, rects },
      tags,
    });
    return { key: item.key, dateModified: Zotero.Date.sqlToISO8601(item.dateModified) };
  },

  // Deleted highlights go to Zotero's trash, so a mistake can be undone there.
  async deleteAnnotations({ attachmentKey, keys }) {
    const Y = ReadINYidu;
    const att = Y.item(attachmentKey);
    if (!Array.isArray(keys)) throw this.bad("keys must be a list");
    const ids = [];
    const trashed = [];
    for (const key of keys) {
      const a = Zotero.Items.getByLibraryAndKey(Y.libraryID(), key);
      if (!a || !a.isAnnotation() || a.parentItemID !== att.id || a.deleted || a.annotationIsExternal) continue;
      ids.push(a.id);
      trashed.push(key);
    }
    if (ids.length) await Zotero.Items.trashTx(ids);
    return { trashed };
  },

  // The paper a translated PDF belongs under: the regular item, or a standalone PDF itself.
  paperOf(key) {
    const Y = ReadINYidu;
    const item = Y.item(key);
    return Y.isPDF(item) && item.parentItem ? item.parentItem : item;
  },

  // Translated PDFs ReadIN saved earlier (tagged "ReadIN 译文"), newest first.
  translationsUnder(paper) {
    const ids = paper.isRegularItem() ? paper.getAttachments() : [];
    return ids
      .map((id) => Zotero.Items.get(id))
      .filter((a) => a && !a.deleted && a.hasTag(this.TAG))
      .sort((a, b) => (b.dateAdded > a.dateAdded ? 1 : -1));
  },

  translations(key) {
    const items = this.translationsUnder(this.paperOf(key)).map((a) => ({
      key: a.key, title: a.getField("title"), filename: a.attachmentFilename, dateAdded: Zotero.Date.sqlToISO8601(a.dateAdded),
    }));
    return { items };
  },

  // files: [{ name, title, base64url }]; replace: keys of earlier translations to move to the trash.
  async attach({ parentKey, files, replace }) {
    const Y = ReadINYidu;
    const paper = this.paperOf(parentKey);
    if (!Array.isArray(files) || !files.length || files.length > 4) throw this.bad("files must be a list of 1-4");
    const added = [];
    for (const f of files) {
      if (!f || typeof f.base64url !== "string" || !f.base64url) throw this.bad("file has no data");
      const name = String(f.name || "ReadIN.pdf").replace(/[\\/:*?"<>|\u0000-\u001f]/g, "_").slice(0, 150);
      const bytes = new Uint8Array(ChromeUtils.base64URLDecode(f.base64url, { padding: "ignore" }));
      if (bytes.length < 5 || String.fromCharCode(...bytes.subarray(0, 5)) !== "%PDF-") throw this.bad("not a PDF");
      const dir = PathUtils.join(Zotero.getTempDirectory().path, "readin-" + Zotero.Utilities.randomString(8));
      await IOUtils.makeDirectory(dir);
      const path = PathUtils.join(dir, name.toLowerCase().endsWith(".pdf") ? name : name + ".pdf");
      try {
        await IOUtils.write(path, bytes);
        const options = { file: path, contentType: "application/pdf", title: String(f.title || name).slice(0, 300) };
        if (paper.isRegularItem()) {
          options.parentItemID = paper.id;
        } else {
          options.libraryID = Y.libraryID();
          options.collections = paper.getCollections();
        }
        const att = await Zotero.Attachments.importFromFile(options);
        att.addTag(this.TAG);
        await att.saveTx();
        added.push({ key: att.key, title: att.getField("title"), filename: att.attachmentFilename });
      } finally {
        await IOUtils.remove(dir, { recursive: true, ignoreAbsent: true });
      }
    }
    // Only earlier ReadIN translations under this paper may be replaced; they go to Zotero's trash.
    const mine = new Map(this.translationsUnder(paper).map((a) => [a.key, a]));
    const ids = (Array.isArray(replace) ? replace : []).map((k) => mine.get(k)).filter((a) => a && !added.some((x) => x.key === a.key)).map((a) => a.id);
    if (ids.length) await Zotero.Items.trashTx(ids);
    return { items: added, trashed: ids.length };
  },

  // Open an attachment in Zotero's own reader and bring Zotero to the front.
  async open({ key }) {
    const att = ReadINYidu.item(key);
    if (!ReadINYidu.isPDF(att)) throw this.bad("not a PDF attachment");
    await Zotero.Reader.open(att.id);
    try {
      Zotero.getMainWindow()?.focus();
    } catch (e) {
      // no window (headless test Zotero)
    }
    return { ok: true };
  },

  // ReadIN's notes under the paper: "ReadIN 笔记" (the reader's own notes) and "ReadIN AI 整理".
  // v0.5.0: ReadIN may send { doc } instead of html; we build the note the way Zotero builds "Add Note from Annotations",
  // so highlights link to their place in the PDF and every citation is a real Zotero citation (Word's Add Note keeps them live).
  // sig: the text of the note as we last wrote it (see noteSig). If the note no longer matches, the user edited it in Zotero:
  // it's theirs now, so we leave it alone and write a fresh note (reply carries kept: the key of the one we left).
  async saveNote({ parentKey, noteKey, html, doc, sig }) {
    const Y = ReadINYidu;
    const parent = Y.item(parentKey);
    if (!parent.isRegularItem()) throw this.bad("notes go under a paper, not an attachment");
    if (doc && typeof doc === "object") html = await this.noteFromDoc(parent, doc);
    if (typeof html !== "string" || !html.trim()) throw this.bad("html is empty");
    let note = this.ourNote(parent, noteKey);
    let kept = null;
    if (note && typeof sig === "string" && sig && this.noteSig(note.getNote()) !== sig) {
      kept = note.key;
      note = null;
    }
    // If the user deleted or moved our note, start a new one instead of resurrecting it.
    if (!note) {
      note = new Zotero.Item("note");
      note.libraryID = parent.libraryID;
      note.parentID = parent.id;
    }
    note.setNote(html);
    await note.saveTx();
    return { key: note.key, sig: this.noteSig(note.getNote()), ...(kept ? { kept } : {}) };
  },

  // A note ReadIN no longer needs (e.g. the AI note after all AI summaries were deleted): to the trash, unless the user edited it.
  async removeNote({ parentKey, noteKey, sig }) {
    const parent = ReadINYidu.item(parentKey);
    const note = this.ourNote(parent, noteKey);
    if (!note || (typeof sig === "string" && sig && this.noteSig(note.getNote()) !== sig)) return { trashed: false };
    await Zotero.Items.trashTx([note.id]);
    return { trashed: true };
  },

  ourNote(parent, noteKey) {
    const note = noteKey ? Zotero.Items.getByLibraryAndKey(parent.libraryID, noteKey) : null;
    return note && note.isNote() && !note.deleted && note.parentItemID === parent.id ? note : null;
  },

  // What the user would notice changing: the words of the note. Markup and the text of citations don't count
  // (Zotero's note editor rewrites both when it opens a note, and refreshes citations when the paper's details change).
  noteSig(html) {
    const text = String(html || "")
      .replace(/<span class="citation-item">[\s\S]*?<\/span>/g, "")
      .replace(/<span class="citation"[^>]*>[^<]*<\/span>/g, "")
      .replace(/<[^>]+>/g, " ")
      .replace(/&nbsp;/g, " ").replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&amp;/g, "&")
      .replace(/\s+/g, " ")
      .trim();
    let hash = 0x811c9dc5; // FNV-1a
    for (let i = 0; i < text.length; i++) {
      hash ^= text.charCodeAt(i);
      hash = Math.imul(hash, 0x01000193) >>> 0;
    }
    return `${text.length}-${hash.toString(16)}`;
  },

  // doc: { title, link: { href, text }, attachmentKey, sections: [{ heading, items }] }
  // items: { kind: "highlight", annotation, text, comment, page, label } | { kind: "note", text, page } | { kind: "insight", question, text }
  // label: words after the quote, e.g. "（译文）" for a highlight on ReadIN's translation (so it never passes for the paper's own words)
  // A highlight whose Zotero annotation exists is written by Zotero's own serializer (the user's note template, a link to
  // the spot in the PDF, the annotation's page label); others get the same kind of citation with the page ReadIN sends.
  async noteFromDoc(parent, doc) {
    const U = Zotero.EditorInstanceUtilities;
    const text = (s) => U._transformTextToHTML(String(s == null ? "" : s).trim());
    const attr = (s) => String(s).replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    const uris = [Zotero.URI.getItemURI(parent)];
    const itemData = Zotero.Utilities.Item.itemToCSLJSON(parent);
    const cite = (locator) => {
      const item = { uris };
      if (locator) item.locator = String(locator);
      const citation = { citationItems: [item], properties: {} };
      const formatted = U.formatCitation({ citationItems: [{ ...item, itemData }], properties: {} });
      return `<span class="citation" data-citation="${encodeURIComponent(JSON.stringify(citation))}">${formatted}</span>`;
    };
    let att = null;
    try {
      att = doc.attachmentKey ? ReadINYidu.item(doc.attachmentKey) : null;
    } catch (e) {
      att = null;
    }
    let html = `<h1>${text(doc.title || "ReadIN")}</h1>\n`;
    if (doc.link && /^https:\/\//.test(doc.link.href || "")) {
      html += `<p><a href="${attr(doc.link.href)}">${text(doc.link.text || doc.link.href)}</a></p>\n`;
    }
    for (const section of Array.isArray(doc.sections) ? doc.sections : []) {
      const items = (Array.isArray(section.items) ? section.items : []).filter((it) => it && String(it.text || "").trim());
      if (!items.length) continue;
      html += `<h2>${text(section.heading)}</h2>\n`;
      for (const it of items) {
        if (it.kind === "highlight") {
          const a = this.liveAnnotation(att, it.annotation);
          if (a) {
            const json = await Zotero.Annotations.toJSON(a);
            json.attachmentItemID = att.id;
            json.id = a.key;
            html += U.serializeAnnotations([json], true).html + "\n";
          } else {
            html += `<p>${text(`“${String(it.text).trim()}”`)}${it.label ? text(it.label) : ""} ${cite(it.page)}${it.comment ? ` ${text(it.comment)}` : ""}</p>\n`;
          }
        } else if (it.kind === "insight") {
          if (it.question) html += `<p><strong>${text(it.question)}</strong></p>\n`;
          html += `<p>${text(it.text)} ${cite(null)}</p>\n`;
        } else {
          html += `<p>${text(it.text)} ${cite(it.page)}</p>\n`;
        }
      }
    }
    return `<div data-citation-items="${encodeURIComponent(JSON.stringify([{ uris, itemData }]))}" data-schema-version="9">${html}</div>`;
  },

  // The Zotero highlight ReadIN's highlight was saved as (only a live one on this PDF).
  liveAnnotation(att, key) {
    if (!att || typeof key !== "string" || !key) return null;
    const a = Zotero.Items.getByLibraryAndKey(att.libraryID, key);
    return a && a.isAnnotation() && a.parentItemID === att.id && !a.deleted && ["highlight", "underline"].includes(a.annotationType) ? a : null;
  },
};
