/* global Zotero, Services */
// ReadIN 译读 — entry points Zotero calls when the plugin starts and stops.
var ReadINYidu;

function install() {}
function uninstall() {}

async function startup({ id, version, rootURI }) {
  await Zotero.initializationPromise;
  for (const file of ["yidu.js", "bridge.js", "ui.js", "updater.js"]) {
    Services.scriptloader.loadSubScript(rootURI + "src/" + file);
  }
  ReadINYidu.startup({ id, version, rootURI });
}

function shutdown() {
  if (ReadINYidu) ReadINYidu.shutdown();
  ReadINYidu = undefined;
}

function onMainWindowLoad() {}
function onMainWindowUnload() {}
