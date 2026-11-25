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
  CN_SITE: "https://cn-beta.anqapdf.app",
  // Time zones in mainland China: before the first connection, open the mainland version there
  // (the international version's AI can't be reached from mainland China).
  CN_ZONES: ["Asia/Shanghai", "Asia/Chongqing", "Asia/Chungking", "Asia/Harbin", "Asia/Urumqi", "Asia/Kashgar", "PRC"],

  STRINGS: {
    open: { zh: "在 ReadIN 打开", en: "Open in ReadIN" },
  },

  // v0.4.0: "Open in ReadIN" opens the browser you actually use ReadIN in, not just the computer's default browser
  // (the default one may be another browser that has none of your ReadIN settings and notes).
  // ReadIN tells us which browser it runs in through /readin/hello, and only when it is set up there (bridge.js).
  // mac: the app's bundle id for `open -b`; exe: the program name Windows lists under "App Paths";
  // scheme: a URL scheme Windows hands to that browser (Edge registers microsoft-edge:).
  BROWSERS: {
    edge: { mac: "com.microsoft.edgemac", exe: "msedge.exe", scheme: "microsoft-edge" },
    chrome: { mac: "com.google.Chrome", exe: "chrome.exe" },
    firefox: { mac: "org.mozilla.firefox", exe: "firefox.exe" },
    safari: { mac: "com.apple.Safari" },
    brave: { mac: "com.brave.Browser", exe: "brave.exe" },
    opera: { mac: "com.operasoftware.Opera", exe: "opera.exe" },
    vivaldi: { mac: "com.vivaldi.Vivaldi", exe: "vivaldi.exe" },
    arc: { mac: "company.thebrowser.Browser" },
  },

  startup(info) {
    Object.assign(this, info);
    this.bridge.start();
    this.ui.start();
    this.updater.start();
    // Test profiles only (dev/zotero_kit.py sets testHooks; nobody else does): let the tests reach this object
    if (this.pref("testHooks", false) === true) Zotero.__readinYidu = this;
    Zotero.debug(`ReadIN 译读 ${this.version} started`);
  },

  shutdown() {
    if (Zotero.__readinYidu === this) delete Zotero.__readinYidu;
    this.updater.stop();
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

  // Which ReadIN to open: the one that last connected (international or mainland), else by time zone.
  site() {
    const site = this.pref("site", "");
    return this.allowedOrigins().includes(site) && site.startsWith("http") ? site : this.defaultSite();
  },

  // Never connected yet: the mainland version in mainland China's time zones, the international one elsewhere.
  defaultSite(zone = null) {
    let tz = zone;
    if (tz === null) {
      try {
        tz = Intl.DateTimeFormat().resolvedOptions().timeZone || "";
      } catch (e) {
        tz = "";
      }
    }
    return this.CN_ZONES.includes(tz) ? this.CN_SITE : this.DEFAULT_SITE;
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

  // v0.7.0: web snapshots (a saved web page, text/html, stored in Zotero; not a plain link to a URL)
  isSnapshot(item) {
    return item.isAttachment() && item.attachmentContentType === "text/html" && item.attachmentLinkMode !== Zotero.Attachments.LINK_MODE_LINKED_URL;
  },

  snapshotsOf(item) {
    if (this.isSnapshot(item)) return [item];
    if (!item.isRegularItem()) return [];
    return Zotero.Items.get(item.getAttachments()).filter((a) => !a.deleted && this.isSnapshot(a));
  },

  // What "Open in ReadIN" opens for this item: its PDF, or else its web snapshot (v0.7.0)
  readable(item) {
    return this.pdfsOf(item)[0] || this.snapshotsOf(item)[0] || null;
  },

  openInReadIN(attachmentKey) {
    return this.launch(`${this.site()}/#zotero=${encodeURIComponent(attachmentKey)}`);
  },

  // Open a ReadIN page in the browser ReadIN last said it is set up in; if that fails (or we don't know yet), the default
  // browser as before. Returns "edge", "chrome", … or "default" (the tests look at lastLaunch).
  async launch(url) {
    const name = this.pref("browser", "");
    let how = "default";
    if (this.BROWSERS[name]) {
      try {
        if (await this.launchIn(name, url)) how = name;
      } catch (e) {
        Zotero.debug(`ReadIN 译读: couldn't open ${name} (${e}), using the default browser`);
      }
    }
    if (how === "default") Zotero.launchURL(url);
    this.lastLaunch = { how, url };
    return how;
  },

  async launchIn(name, url) {
    const b = this.BROWSERS[name];
    if (Zotero.isMac && b.mac) {
      // `open -b` exits with an error when that browser isn't installed → the default browser instead
      await Zotero.Utilities.Internal.exec("/usr/bin/open", ["-b", b.mac, url]);
      return true;
    }
    if (Zotero.isWin) {
      if (b.scheme) {
        try {
          Zotero.launchURL(`${b.scheme}:${url}`);
          return true;
        } catch (e) {
          // no handler for that scheme: try the program itself
        }
      }
      const program = b.exe && this.windowsProgram(b.exe);
      if (!program) return false;
      // Don't wait: a browser that wasn't open yet keeps running. exec() throws right away if the file can't run.
      Zotero.Utilities.Internal.exec(program, [url]).catch((e) => Zotero.debug(`ReadIN 译读: ${program} ${e}`));
      return true;
    }
    return false;
  },

  // Where Windows says a browser is installed (HKCU first, then HKLM, "App Paths"); null if it isn't.
  windowsProgram(exe) {
    const Ci = Components.interfaces;
    for (const root of [Ci.nsIWindowsRegKey.ROOT_KEY_CURRENT_USER, Ci.nsIWindowsRegKey.ROOT_KEY_LOCAL_MACHINE]) {
      const key = Components.classes["@mozilla.org/windows-registry-key;1"].createInstance(Ci.nsIWindowsRegKey);
      try {
        key.open(root, `SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\App Paths\\${exe}`, Ci.nsIWindowsRegKey.ACCESS_READ);
        const path = key.readStringValue("").replace(/^"(.*)"$/, "$1");
        if (path) return path;
      } catch (e) {
        // not installed for this user / on this computer
      } finally {
        try {
          key.close();
        } catch (e) {
          // wasn't open
        }
      }
    }
    return null;
  },
};
