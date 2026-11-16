/* global Zotero, Services, Components, IOUtils, PathUtils, ChromeUtils */
// Test-only helper installed in the throwaway test Zotero: POST /readin-test/eval runs JavaScript inside
// Zotero and returns the result. It does NOT accept browser requests (no allowRequestsFromUnsafeWebContent).
function install() {}
function uninstall() {}
async function startup() {
  await Zotero.initializationPromise;
  const Endpoint = function () {};
  Endpoint.prototype = {
    supportedMethods: ["POST"],
    supportedDataTypes: "*",
    init: async function (req) {
      try {
        const Cu = Components.utils;
        const sandbox = Cu.Sandbox(Services.scriptSecurityManager.getSystemPrincipal(), { sandboxName: "yidu-testkit" });
        Object.assign(sandbox, { Zotero, IOUtils, PathUtils, ChromeUtils });
        const value = await Cu.evalInSandbox("(async () => {\n" + req.data + "\n})()", sandbox);
        return [200, "application/json", JSON.stringify({ value: value === undefined ? null : value })];
      } catch (e) {
        return [500, "application/json", JSON.stringify({ error: String(e) + "\n" + (e.stack || "") })];
      }
    },
  };
  Zotero.Server.Endpoints["/readin-test/eval"] = Endpoint;
}
function shutdown() {
  delete Zotero.Server.Endpoints["/readin-test/eval"];
}
