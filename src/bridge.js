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
  API: 3, // 2 (v0.2.0): translated PDFs saved back as attachments; 3 (v0.3.0): ReadIN can ask for an update (/readin/update)
  TAG: "ReadIN 译文",
  paths: [],

  start() {
    const Y = ReadINYidu;
    const get = (path, fn) => this.add(path, "GET", (req) => fn(req.searchParams, req));
    const post = (path, fn) => this.add(path, "POST", (req) => fn(this.json(req), req));

    get("/readin/ping", () => ({
      ok: true, plugin: "readin-yidu", version: Y.version, api: this.API, zotero: Zotero.version, site: Y.site(),
      menu: Boolean(Y.ui.menuID), update: true,
    }));
    // ReadIN says hello when it connects, so "Open in ReadIN" opens the same ReadIN (international or mainland).
    post("/readin/hello", (body, req) => {
      if (/^https:\/\//.test(req.headers.origin)) Y.setPref("site", req.headers.origin);
      return { ok: true, site: Y.site() };
    });
    get("/readin/collections", () => ({ collections: this.collections() }));
    get("/readin/items", (q) => this.items(q.get("collection"), q.get("keys")));
    get("/readin/item", (q) => this.itemInfo(q.get("key")));
    get("/readin/file", (q) => this.file(q.get("key")));
    get("/readin/annotations", (q) => this.annotations(q.get("key")));
    post("/readin/annotations/save", (body) => this.saveAnnotation(body));
    post("/readin/annotations/delete", (body) => this.deleteAnnotations(body));
    post("/readin/notes/save", (body) => this.saveNote(body));
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
    if (!a || !["highlight", "underline", "note"].includes(a.type)) throw this.bad("type must be highlight, underline or note");
    const pageIndex = Number(a.pageIndex);
    if (!Number.isInteger(pageIndex) || pageIndex < 0) throw this.bad("bad pageIndex");
    const rects = a.rects;
    if (!Array.isArray(rects) || !rects.length || !rects.every((r) => Array.isArray(r) && r.length === 4 && r.every(Number.isFinite))) {
      throw this.bad("rects must be [[x1, y1, x2, y2], ...]");
    }
    if (a.key) {
      try {
        Zotero.DataObjectUtilities.checkKey(a.key);
      } catch (e) {
        throw this.bad("bad key");
      }
      const existing = Zotero.Items.getByLibraryAndKey(Y.libraryID(), a.key);
      if (existing) {
        if (!existing.isAnnotation() || existing.parentItemID !== att.id) throw this.bad("key belongs to something else");
        if (existing.annotationIsExternal) throw this.bad("annotation lives in the PDF file and is read-only");
        if (existing.deleted) {
          existing.deleted = false;
        }
      }
    }
    const item = await Zotero.Annotations.saveFromJSON(att, {
      key: a.key || Zotero.DataObjectUtilities.generateKey(),
      type: a.type,
      text: String(a.text || ""),
      comment: String(a.comment || ""),
      color: /^#[0-9a-f]{6}$/i.test(a.color) ? a.color : "#ffd400",
      pageLabel: String(a.pageLabel || pageIndex + 1),
      sortIndex: this.sortIndex(pageIndex, a.offset, a.top),
      position: { pageIndex, rects },
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

  async saveNote({ parentKey, noteKey, html }) {
    const Y = ReadINYidu;
    const parent = Y.item(parentKey);
    if (!parent.isRegularItem()) throw this.bad("notes go under a paper, not an attachment");
    if (typeof html !== "string" || !html.trim()) throw this.bad("html is empty");
    let note = noteKey ? Zotero.Items.getByLibraryAndKey(Y.libraryID(), noteKey) : null;
    // If the user deleted or moved our note, start a new one instead of resurrecting it.
    if (!note || !note.isNote() || note.deleted || note.parentItemID !== parent.id) {
      note = new Zotero.Item("note");
      note.libraryID = Y.libraryID();
      note.parentID = parent.id;
    }
    note.setNote(html);
    await note.saveTx();
    return { key: note.key };
  },
};
