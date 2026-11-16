/* global Zotero, ReadINYidu:writable */
// Shared settings and helpers. The bridge (bridge.js) and the menus (ui.js) hang off this object.

ReadINYidu = {
  id: null,
  version: null,
  rootURI: null,

  PREF: "extensions.readin-yidu.",

  // Only ReadIN's own pages may talk to the plugin. Every other website is refused.
  ORIGINS: [
    "https://beta.anqapdf.app",
    "https://cn-beta.anqapdf.app",
    "https://anqapdf.app",
    "https://readin.cc",
    "https://www.readin.cc",
  ],
  DEFAULT_SITE: "https://beta.anqapdf.app",

  STRINGS: {
    open: { zh: "在 ReadIN 打开", en: "Open in ReadIN" },
  },

  startup(info) {
    Object.assign(this, info);
    this.bridge.start();
    this.ui.start();
    Zotero.debug(`ReadIN 译读 ${this.version} started`);
  },

  shutdown() {
    this.ui.stop();
    this.bridge.stop();
  },

  pref(name, fallback) {
    const value = Zotero.Prefs.get(this.PREF + name, true);
    return value === undefined ? fallback : value;
  },

  setPref(name, value) {
    Zotero.Prefs.set(this.PREF + name, value, true);
  },

  // Extra origins exist only for automated tests (set in the test profile, never by the plugin).
  allowedOrigins() {
    const extra = String(this.pref("testOrigins", ""))
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    return [...this.ORIGINS, ...extra];
  },

  // Which ReadIN to open: the one that last connected (international or mainland), else the default.
  site() {
    const site = this.pref("site", "");
    return this.allowedOrigins().includes(site) && site.startsWith("http") ? site : this.DEFAULT_SITE;
  },

  t(key) {
    const s = this.STRINGS[key];
    return String(Zotero.locale || "").toLowerCase().startsWith("zh") ? s.zh : s.en;
  },

  libraryID() {
    return Zotero.Libraries.userLibraryID;
  },

  item(key) {
    const item = Zotero.Items.getByLibraryAndKey(this.libraryID(), String(key || ""));
    if (!item || item.deleted) throw new Error("not found: " + key);
    return item;
  },

  isPDF(item) {
    return item.isAttachment() && item.attachmentContentType === "application/pdf";
  },

  pdfsOf(item) {
    if (this.isPDF(item)) return [item];
    if (!item.isRegularItem()) return [];
    return Zotero.Items.get(item.getAttachments()).filter((a) => !a.deleted && this.isPDF(a));
  },

  openInReadIN(attachmentKey) {
    Zotero.launchURL(`${this.site()}/#zotero=${encodeURIComponent(attachmentKey)}`);
  },
};
