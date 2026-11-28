/* global Zotero */
// Test-only plugin for dev/test_toolbar_button.py: Zotero starts plugins one after another and waits for each,
// so a plugin that takes a while to start (like some big ones do) makes the plugins after it start late.
function install() {}
function uninstall() {}
async function startup() {
  await Zotero.initializationPromise;
  Zotero.debug("slow test plugin: starting (8 s)");
  await Zotero.Promise.delay(8000);
  Zotero.debug("slow test plugin: started");
}
function shutdown() {}
