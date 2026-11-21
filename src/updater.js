/* global Zotero, ChromeUtils, ReadINYidu */
// The plugin updating itself through Zotero's own add-on manager: the same as Tools → Plugins → ⚙ → Check for Updates,
// which reads update_url in manifest.json (https://readin.cc/yidu/update.json). No download, no dragging a file.
// - ReadIN found the plugin too old and the person clicked "Update now": POST /readin/update (bridge.js).
// - Each time Zotero starts, check once (Zotero by itself checks only about once a day), unless the person
//   turned automatic updates off for this plugin in Tools → Plugins.
// Installing the new version replaces this one on the spot: this copy stops, the new one starts (no restart).

ReadINYidu.updater = {
  START_DELAY: 20, // seconds after Zotero starts, so the check doesn't slow down opening Zotero
  TIMEOUT: 30, // seconds to wait for readin.cc
  installing: "", // the version being installed right now
  stopped: false,

  start() {
    this.stopped = false;
    const Y = ReadINYidu;
    if (!Y.pref("checkOnStart", true)) return; // tests turn this off
    const delay = Number(Y.pref("checkDelay", this.START_DELAY)) * 1000;
    Zotero.Promise.delay(delay)
      .then(() => (this.stopped ? null : this.check({ manual: false })))
      .then((result) => result && Zotero.debug(`ReadIN 译读: update check on start: ${JSON.stringify(result)}`))
      .catch((e) => Zotero.logError(e));
  },

  stop() {
    this.stopped = true;
  },

  async manager() {
    const { AddonManager } = ChromeUtils.importESModule("resource://gre/modules/AddonManager.sys.mjs");
    const addon = await AddonManager.getAddonByID(ReadINYidu.id);
    if (!addon) throw new Error("the plugin is not in Zotero's add-on manager");
    return { AddonManager, addon };
  },

  // → { status, version, to?, error? }
  //   status: "updating" (found `to`, installing it now), "latest" (nothing newer), "off" (automatic updates
  //   turned off; only on the start-up check), "failed" (couldn't reach readin.cc, or the update file is wrong)
  async check({ manual }) {
    const version = ReadINYidu.version;
    if (this.installing) return { status: "updating", version, to: this.installing };
    const { AddonManager, addon } = await this.manager();
    if (!manual && !AddonManager.shouldAutoUpdate(addon)) return { status: "off", version };
    return new Promise((resolve) => {
      let done = false;
      const finish = (result) => {
        if (!done) {
          done = true;
          resolve(result);
        }
      };
      Zotero.Promise.delay(this.TIMEOUT * 1000).then(() => finish({ status: "failed", version, error: "timeout" }));
      addon.findUpdates(
        {
          onUpdateAvailable: (_addon, install) => {
            this.installing = install.version;
            finish({ status: "updating", version, to: install.version });
            // Answer ReadIN first: installing stops this copy of the plugin (and its doors on the local server).
            Zotero.Promise.delay(500)
              .then(() => install.install())
              .catch((e) => {
                this.installing = "";
                Zotero.logError(e);
              });
          },
          // A failed check also calls onNoUpdateAvailable, so wait for onUpdateFinished to tell the two apart.
          onUpdateFinished: (_addon, error) => finish(error ? { status: "failed", version, error: `update check error ${error}` } : { status: "latest", version }),
        },
        manual ? AddonManager.UPDATE_WHEN_USER_REQUESTED : AddonManager.UPDATE_WHEN_PERIODIC_UPDATE,
      );
    });
  },
};
