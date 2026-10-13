#!/usr/bin/env python3
"""Build the card beta from the unchanged, checksum-pinned v1.2.0 base.

The temporary transport fragments are removed after materializing readable
source and test files. Subsequent builds use those readable sources directly.
No network requests, credentials, provider changes or main-branch writes.
"""
from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
import re
import subprocess
import zlib

ROOT = Path(__file__).resolve().parents[1]
BASE = "9bdbaea3db1e1961d4da4702ebbcb989ef5015ee"
BASE_CARD_BLOB = "c28ec31d1fe2c835d1f7c1c9046c0c931e5a751f"
VERSION = "1.3.0b1"
CARD = "custom_components/osm_parking/frontend/osm-parking-map-card.js"
SOURCE = "tools/card-preview/modern-card-extension.js"
FILES = {
    SOURCE,
    "tools/card-preview/tests/browser_tests.py",
    "tools/card-preview/preview/index.html",
    "tools/card-preview/preview/mock-map.js",
}
ENCODED_SHA = "8bf506456a4ce911cde9feec2999022095206255f63855a4a6ad1dd8a6c4a8c0"
DECODED_SHA = "ebf2c66c8dde62ebf465cb4c9555a1521478efd58ecd5a5fda11832185d84b64"
NOTES = """# OSM Parking v1.3.0b1 — Card redesign beta

**Opt-in beta. Stable v1.2.0 and the main branch are unchanged.**

## Included

- Compact 250 px default map with Expand and Fit results controls.
- Automatic Home Assistant light/dark theme matching and manual selection,
  using OpenFreeMap Positron and Dark styles rather than CSS inversion.
- Search, parking-type, fee, distance and data-quality filters.
- Sort by nearest/farthest, type, name, available spaces or data quality.
- Cleaner result cards, direct navigation, source details and coordinated
  list/marker selection. Filter choices persist within the browser tab.
- A graphical card editor for the sensor, title, map height and theme.
- Parking results remain usable when map tiles fail to load.
- Greek and the other existing interface languages are retained.

## Installation

In HACS, open OSM Parking, enable beta/pre-release versions, then use the
Download/Redownload version picker to select **v1.3.0b1**. Restart Home
Assistant and reload the dashboard. No separate patch installer is needed.
The manual ZIP contains custom_components/osm_parking for manual installs.

Existing explicitly configured heights are respected. Set **map_height: 250**
in the card editor or YAML to use the compact height on an older card.

## Scope and test limits

The four-step configuration flow, provider backends, credentials and
best-source deduplication are unchanged. Filters operate on results already
returned by the integration; they do not query new providers or expand the
configured radius. Reported counts and estimates are not labelled verified
live availability. Price sorting across incompatible tariffs is not offered.

The publication workflow runs the existing Python contracts, JavaScript
syntax/version checks, HACS and Hassfest, plus browser interactions against
the **complete bundled card**. Browser tests use synthetic Home Assistant
states, storage and a MapLibre double; they do not prove real Home Assistant
integration, external tile connectivity or municipal API reachability.

## Rollback

Use HACS Redownload and select **v1.2.0**, then restart Home Assistant and
reload the dashboard. Configuration entries and saved credentials remain
compatible. Disable beta/pre-release versions to stay on stable releases.
"""


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=ROOT)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def materialize() -> None:
    directory = ROOT / "tools/beta-bootstrap"
    parts = [directory / f"source-{i}.b64" for i in range(1, 8)]
    if any(path.exists() for path in parts):
        if not all(path.is_file() for path in parts):
            raise SystemExit("Incomplete beta source transfer")
        encoded = b"".join(path.read_bytes().strip() for path in parts)
        if sha256(encoded) != ENCODED_SHA:
            raise SystemExit("Beta transfer checksum mismatch")
        raw = zlib.decompress(base64.b64decode(encoded, validate=True))
        if sha256(raw) != DECODED_SHA:
            raise SystemExit("Beta source checksum mismatch")
        mapping = json.loads(raw)
        if not isinstance(mapping, dict) or set(mapping) != FILES:
            raise SystemExit("Unexpected beta source paths")
        for name, text in mapping.items():
            if not isinstance(text, str):
                raise SystemExit("Non-text beta source")
            path = ROOT / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        for part in parts:
            part.unlink()
        directory.rmdir()
    if not all((ROOT / name).is_file() for name in FILES):
        raise SystemExit("Readable beta source is incomplete")


def replace_once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise SystemExit(f"Expected one source anchor: {old!r}")
    return text.replace(old, new, 1)


def build() -> None:
    git("merge-base", "--is-ancestor", BASE, "HEAD")
    materialize()
    original = git("show", f"{BASE}:{CARD}")
    blob = hashlib.sha1(
        b"blob " + str(len(original)).encode() + b"\0" + original
    ).hexdigest()
    if blob != BASE_CARD_BLOB:
        raise SystemExit("Stable frontend base does not match v1.2.0")
    extension = (ROOT / SOURCE).read_text(encoding="utf-8")
    if "class OsmParkingMapCardCompact extends OsmParkingMapCardV070" not in extension:
        raise SystemExit("Missing compact card implementation")
    anchor = "if (!customElements.get('osm-parking-map-card')) {"
    card = replace_once(original.decode("utf-8"), anchor, extension + "\n\n" + anchor)
    card = replace_once(
        card,
        "  customElements.define('osm-parking-map-card', OsmParkingMapCardV070);",
        "  customElements.define('osm-parking-map-card', OsmParkingMapCardCompact);",
    )
    card = replace_once(card, '<span class="version">v1.2.0</span>',
                        f'<span class="version">v{VERSION}</span>')
    (ROOT / CARD).write_text(card, encoding="utf-8")

    manifest_path = ROOT / "custom_components/osm_parking/manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest["version"] not in {"1.2.0", VERSION}:
        raise SystemExit("Unexpected manifest version; refusing downgrade")
    manifest["version"] = VERSION
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    init_path = ROOT / "custom_components/osm_parking/__init__.py"
    init = init_path.read_text(encoding="utf-8")
    old = re.findall(r'^CARD_VERSION = "([^"]+)"$', init, re.M)
    if len(old) != 1 or old[0] not in {"1.2.0", VERSION}:
        raise SystemExit("Unexpected frontend resource version")
    init_path.write_text(init.replace(f'CARD_VERSION = "{old[0]}"',
                                     f'CARD_VERSION = "{VERSION}"'), encoding="utf-8")

    notes = ROOT / "docs/card-redesign-beta.md"
    notes.parent.mkdir(parents=True, exist_ok=True)
    notes.write_text(NOTES, encoding="utf-8")
    changelog = ROOT / "CHANGELOG.md"
    text = changelog.read_text(encoding="utf-8")
    heading = f"## v{VERSION}\n"
    if heading not in text:
        entry = (
            heading + "\n### Pre-release\n\n"
            "- Compact theme-aware map, modern result cards, runtime filters and sorting.\n"
            "- Graphical card editor, direct navigation and coordinated list/map selection.\n"
            "- Existing providers, credentials and four-step setup remain unchanged.\n"
            "- Opt-in beta only; v1.2.0 remains the stable release.\n"
            "- See [beta installation and test limitations](docs/card-redesign-beta.md).\n\n"
        )
        text = replace_once(text, "# Changelog\n\n", "# Changelog\n\n" + entry)
        changelog.write_text(text, encoding="utf-8")

    # Only version metadata and frontend may change inside the HA component.
    allowed = {CARD, "custom_components/osm_parking/manifest.json",
               "custom_components/osm_parking/__init__.py"}
    changed = git("diff", "--name-only", BASE, "--", "custom_components/osm_parking").decode().splitlines()
    if not set(changed).issubset(allowed):
        raise SystemExit(f"Unexpected backend changes: {set(changed) - allowed}")
    print(json.dumps({"version": VERSION, "base": BASE,
                      "frontend_sha256": sha256(card.encode()),
                      "frontend_bytes": len(card.encode()),
                      "backend_preserved": True}, indent=2))


if __name__ == "__main__":
    build()
