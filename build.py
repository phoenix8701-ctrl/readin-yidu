"""Package the plugin: dist/readin-yidu-<version>.xpi and dist/update.json.

    python3 build.py
"""

import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DOWNLOAD_BASE = "https://readin.cc/yidu"

manifest = json.loads((ROOT / "manifest.json").read_text())
version = manifest["version"]
plugin_id = manifest["applications"]["zotero"]["id"]
files = ["manifest.json", "bootstrap.js", "LICENSE", *sorted(p.relative_to(ROOT).as_posix() for p in (ROOT / "src").glob("*.js")),
         *sorted(p.relative_to(ROOT).as_posix() for p in (ROOT / "icons").glob("*.png"))]

dist = ROOT / "dist"
dist.mkdir(exist_ok=True)
xpi = dist / f"readin-yidu-{version}.xpi"
with zipfile.ZipFile(xpi, "w", zipfile.ZIP_DEFLATED) as z:
    for name in files:
        z.write(ROOT / name, name)

update = {"addons": {plugin_id: {"updates": [{
    "version": version,
    "update_link": f"{DOWNLOAD_BASE}/{xpi.name}",
    "applications": {"zotero": {"strict_min_version": manifest["applications"]["zotero"]["strict_min_version"]}},
}]}}}
(dist / "update.json").write_text(json.dumps(update, indent=2) + "\n")
print(f"{xpi.relative_to(ROOT)} ({xpi.stat().st_size // 1024} KB), dist/update.json")
