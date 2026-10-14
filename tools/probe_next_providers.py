#!/usr/bin/env python3
"""Read-only probes for official parking sources in the next provider batch."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request

OUT = Path("provider-evidence-next")
OUT.mkdir(exist_ok=True)

TARGETS = {
    "luxembourg_vdl": (
        "https://feed.vdl.lu/circulation/parking/feed.json",
        {},
        "json",
    ),
    "cfl_list": (
        "https://pr-mobile-a.cfl.lu/OpenData/ParkAndRide/",
        {},
        "json",
    ),
    "basel": (
        "https://data.bs.ch/api/explore/v2.1/catalog/datasets/100088/records",
        {"limit": "100"},
        "json",
    ),
    "zurich": (
        "https://www.pls-zh.ch/plsFeed/rss",
        {},
        "xml",
    ),
}


def get(name, target):
    url, params, kind = target
    if params:
        url += "?" + urllib.parse.urlencode(params)
    result = {
        "name": name,
        "url": url,
        "kind": kind,
        "checked_at": datetime.now(UTC).isoformat(),
    }
    try:
        req = urllib.request.Request(
            url,
            headers={
                "Accept": (
                    "application/json"
                    if kind == "json"
                    else "application/xml,text/xml,application/rss+xml"
                ),
                "User-Agent": "HomeAssistant-OSM-Parking-Provider-Probe/1.0",
            },
        )
        with urllib.request.urlopen(req, timeout=20) as response:
            result["http_status"] = response.status
            result["content_type"] = response.headers.get_content_type()
            raw = response.read(8 * 1024 * 1024 + 1)
            if len(raw) > 8 * 1024 * 1024:
                raise ValueError("response_too_large")
            path = OUT / f"{name}.{kind}"
            path.write_bytes(raw)
            result["bytes"] = len(raw)
            if kind == "json":
                payload = json.loads(raw)
                result["root_type"] = type(payload).__name__
                if isinstance(payload, dict):
                    result["keys"] = sorted(payload)[:50]
                    for key in ("results", "features", "parkings", "data"):
                        if isinstance(payload.get(key), list):
                            result["records"] = len(payload[key])
                            break
                elif isinstance(payload, list):
                    result["records"] = len(payload)
                    if payload and isinstance(payload[0], dict):
                        result["sample_keys"] = sorted(payload[0])[:80]
            else:
                text = raw.decode("utf-8", errors="replace")
                result["head"] = text[:500]
            result["ok"] = True
    except urllib.error.HTTPError as exc:
        result.update(ok=False, http_status=exc.code, error_type="HTTPError")
    except Exception as exc:
        result.update(ok=False, error_type=type(exc).__name__)
    return result


def main():
    summary = [get(name, target) for name, target in TARGETS.items()]
    (OUT / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
