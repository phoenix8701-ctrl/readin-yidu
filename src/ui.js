/* global Zotero, ReadINYidu */
// "Open in ReadIN": right-click menu on a paper, and a button in the reader's toolbar (PDF; v0.7.0 web snapshots too).

ReadINYidu.ui = {
  menuID: null,
  toolbarHandler: null,
  BUTTON: "readin-yidu-open",

  start() {
    const Y = ReadINYidu;
    try {
      this.menuID = Zotero.MenuManager.registerMenu({
        menuID: "readin-yidu-open",
        pluginID: Y.id,
        target: "main/library/item",
        menus: [{
          menuType: "menuitem",
          onShowing: (event, context) => {
            context.menuElem.setAttribute("label", Y.t("open"));
            const items = context.items || [];
            context.setVisible(items.length === 1 && Boolean(Y.readable(items[0])));
          },
          onCommand: (event, context) => {
            const att = Y.readable(context.items[0]);
            if (att) Y.openInReadIN(att.key).catch((e) => Zotero.logError(e));
          },
        }],
      });
    } catch (e) {
      Zotero.logError(e);
    }

    this.toolbarHandler = (event) => this.renderToolbar(event);
    Zotero.Reader.registerEventListener("renderToolbar", this.toolbarHandler, Y.id);
    // v0.8.2: Zotero only asks for toolbar buttons at the moment it draws a reader's toolbar. Zotero starts plugins
    // one after another, so with slow plugins before this one, the PDF Zotero reopens from last time is drawn
    // before we are listening, and it had no ReadIN button (right-click still worked). Add it to readers already open.
    for (const reader of this.openReaders()) {
      try {
        this.addToOpenReader(reader);
      } catch (e) {
        Zotero.logError(e);
      }
    }
  },

  stop() {
    if (this.menuID) Zotero.MenuManager.unregisterMenu(this.menuID);
    if (this.toolbarHandler) Zotero.Reader.unregisterEventListener("renderToolbar", this.toolbarHandler);
    this.menuID = null;
    this.toolbarHandler = null;
    // Take our buttons off the readers still open (an update starts the new copy right away, and it adds its own).
    for (const reader of this.openReaders()) {
      try {
        for (const button of this.doc(reader)?.querySelectorAll(`.${this.BUTTON}`) || []) {
          const section = button.parentElement;
          button.remove();
          if (section?.classList.contains("section") && !section.childElementCount) section.remove();
        }
      } catch (e) {
        Zotero.logError(e);
      }
    }
  },

  // Readers open right now, in tabs and in their own windows (a tab Zotero hasn't loaded yet has none: it is drawn,
  // and asks for buttons, when it is first shown).
  openReaders() {
    return Array.isArray(Zotero.Reader._readers) ? [...Zotero.Reader._readers] : [];
  },

  doc(reader) {
    return reader?._iframeWindow?.document || null;
  },

  // The same place Zotero puts it: a section in the toolbar's custom sections (right side, before Appearance).
  addToOpenReader(reader) {
    const doc = this.doc(reader);
    if (!this.wanted(reader) || !doc || doc.querySelector(`.${this.BUTTON}`)) return false;
    const sections = doc.querySelector(".toolbar .custom-sections");
    if (!sections) return false; // still loading: Zotero draws the toolbar soon and asks us then
    const section = doc.createElement("div");
    section.className = "section";
    section.append(this.button(reader, doc));
    sections.append(section);
    return true;
  },

  wanted(reader) {
    return reader.type === "pdf" || reader.type === "snapshot";
  },

  button(reader, doc) {
    const Y = ReadINYidu;
    const button = doc.createElement("button");
    button.className = `toolbar-button ${this.BUTTON}`;
    button.title = Y.t("open");
    button.textContent = "ReadIN";
    button.style.cssText = "width:auto;padding:0 8px;font-weight:600;font-size:12px;";
    button.addEventListener("click", () => {
      const item = Zotero.Items.get(reader.itemID);
      if (item) Y.openInReadIN(item.key).catch((e) => Zotero.logError(e));
    });
    return button;
  },

  renderToolbar({ reader, doc, append }) {
    if (!this.wanted(reader)) return;
    append(this.button(reader, doc));
  },
};
