"""Capture the shipped card for the README, without live data or credentials.

Uses the real pinned MapLibre library and the existing standalone HA preview.
The offline grid is a labelled local fixture, not real street/tile evidence.
This does not replace the UI interaction tests or test a Home Assistant server.

Run after installing the same browser dependencies as card-visual.yml:
    python3 tools/card/readme_screenshots.py
"""
from __future__ import annotations

from functools import partial
import hashlib
import http.server
import json
import os
from pathlib import Path
import struct
import subprocess
import threading

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "assets/screenshots"
CARD = ROOT / "custom_components/osm_parking/frontend/osm-parking-map-card.js"
VERSION = json.loads((ROOT / "custom_components/osm_parking/manifest.json").read_text())["version"]


def fixture_style(dark: bool) -> dict:
    """Schematic local geometry, clearly attributed as non-geographic data."""
    features = []
    for n in range(-12, 13):
        x, y = 6.983 + n * .0015, 50.938 + n * .001
        for points in ([[x, 50.915], [x + .008, 50.960]], [[6.950, y], [7.015, y + .002]]):
            features.append({"type": "Feature", "geometry": {"type": "LineString", "coordinates": points}, "properties": {}})
    return {
        "version": 8,
        "name": "README offline fixture - " + ("dark" if dark else "light"),
        "sources": {"fixture": {
            "type": "geojson",
            "attribution": "Sample map fixture — not geographic evidence",
            "data": {"type": "FeatureCollection", "features": features},
        }},
        "layers": [
            {"id": "background", "type": "background", "paint": {"background-color": "#14222d" if dark else "#edf1f3"}},
            {"id": "roads", "type": "line", "source": "fixture", "paint": {"line-color": "#3a5060" if dark else "#c7d1d7", "line-width": 3}},
        ],
    }


class QuietServer(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []
    report = {
        "version": VERSION,
        "capture_source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "frontend_sha256": hashlib.sha256(CARD.read_bytes()).hexdigest(),
        "method": "Chromium screenshots of the complete shipped card using real MapLibre 5.6.2 and the standalone Home Assistant preview",
        "sample_parking_records": True,
        "local_map_fixture": True,
        "real_home_assistant_runtime": False,
        "live_municipal_api_validation": False,
        "preview_icon_substitutes": True,
        "parking_type_glyphs": "Exact packaged SVG paths, not substitutes",
        "screenshots": [],
    }
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietServer, directory=str(ROOT)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with sync_playwright() as playwright:
            kwargs = {"headless": True, "args": ["--no-sandbox", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"]}
            if os.environ.get("CHROMIUM_PATH"):
                kwargs["executable_path"] = os.environ["CHROMIUM_PATH"]
            browser = playwright.chromium.launch(**kwargs)
            try:
                cases = [
                    ("card-desktop-dark.png", 900, "en", True, False),
                    ("card-desktop-light.png", 900, "en", False, False),
                    ("card-mobile-greek-dark.png", 390, "el", True, False),
                    ("card-mobile-greek-filters.png", 390, "el", True, True),
                ]
                for filename, width, language, dark, filters in cases:
                    page = browser.new_page(viewport={"width": width, "height": 1800}, device_scale_factor=1)
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    page.route("https://tiles.openfreemap.org/styles/**", lambda route: route.fulfill(status=200, content_type="application/json", body=json.dumps(fixture_style("dark" in route.request.url))))
                    page.goto(f"http://127.0.0.1:{server.server_port}/tests/card/preview.html")
                    page.wait_for_function("window.card?._map?.loaded() && window.card?._pins?.size === 5", timeout=30000)
                    assert page.evaluate("window.maplibregl.getVersion()") == "5.6.2"
                    page.evaluate("""({language, dark}) => {
                        // Keep stress-test names in the test fixture itself;
                        // use a readable illustrative name only for the gallery.
                        window.sampleItems = window.sampleItems.map(item => item.provider_id === 'C' ? {...item, name: 'Station Garage — North entrance'} : item);
                        window.attributes = {...window.attributes, suggestions: window.sampleItems};
                        window.ha = {...window.ha, language, states: {'sensor.parking_suggestions': {state: 'ok', attributes: window.attributes}}};
                        window.applyTheme(dark);
                        window.card.hass = window.ha;
                    }""", {"language": language, "dark": dark})
                    page.wait_for_function("(dark) => window.card._map.isStyleLoaded() && window.card._map.getStyle().name === 'README offline fixture - ' + (dark ? 'dark' : 'light') && !!window.card._map.getLayer('osm-parking-controlled-zones-fill')", arg=dark, timeout=30000)
                    page.locator(".results-toggle").click()
                    if filters:
                        page.locator(".filter-toggle").first.click()
                        assert page.locator(".filters-panel").is_visible()
                    assert page.locator(".result-card").count() == 5
                    assert page.locator(".osm-park-marker").count() == 5
                    assert page.locator(".version").inner_text() == "v" + VERSION
                    assert page.locator(".map").evaluate("e => e.getBoundingClientRect().height") == 220
                    assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
                    assert page.locator(".parking-explorer").evaluate("e => e.scrollWidth <= e.clientWidth + 1")
                    page.evaluate("() => document.fonts.ready")
                    page.evaluate("() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))")
                    page.wait_for_timeout(200)
                    path = OUT / filename
                    page.locator("osm-parking-map-card").screenshot(path=str(path), animations="disabled")
                    payload = path.read_bytes()
                    assert payload.startswith(b"\x89PNG\r\n\x1a\n")
                    w, h = struct.unpack(">II", payload[16:24])
                    assert w >= 350 and h > 500, (filename, w, h)
                    report["screenshots"].append({"file": filename, "width": w, "height": h, "language": language, "theme": "dark" if dark else "light", "filters_expanded": filters, "sha256": hashlib.sha256(payload).hexdigest()})
                    print(f"README_SCREENSHOT={filename}; {w}x{h}", flush=True)
                    page.close()
                assert not errors, errors
                report["page_errors"] = errors
                report["passed"] = True
                (OUT / "card-screenshots.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            finally:
                browser.close()
    finally:
        server.shutdown()
        server.server_close()
    print("README_SCREENSHOTS=4_PASS", flush=True)


if __name__ == "__main__":
    main()
