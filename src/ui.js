/* global Zotero, ReadINYidu */
// "Open in ReadIN": right-click menu on a paper, and a button in the reader's toolbar (PDF; v0.7.0 web snapshots too).

ReadINYidu.ui = {
  menuID: null,
  toolbarHandler: null,

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
  },

  stop() {
    if (this.menuID) Zotero.MenuManager.unregisterMenu(this.menuID);
    if (this.toolbarHandler) Zotero.Reader.unregisterEventListener("renderToolbar", this.toolbarHandler);
    this.menuID = null;
    this.toolbarHandler = null;
  },

  renderToolbar({ reader, doc, append }) {
    if (reader.type !== "pdf" && reader.type !== "snapshot") return;
    const Y = ReadINYidu;
    const button = doc.createElement("button");
    button.className = "toolbar-button readin-yidu-open";
    button.title = Y.t("open");
    button.textContent = "ReadIN";
    button.style.cssText = "width:auto;padding:0 8px;font-weight:600;font-size:12px;";
    button.addEventListener("click", () => {
      const item = Zotero.Items.get(reader.itemID);
      if (item) Y.openInReadIN(item.key).catch((e) => Zotero.logError(e));
    });
    append(button);
  },
};
