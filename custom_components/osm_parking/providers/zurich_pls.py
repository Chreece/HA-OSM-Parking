"""Stadt Zürich PLS live feed joined to official municipal WFS geography."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
import math
import re
from time import monotonic
from typing import Any
from urllib.parse import parse_qs, urlparse
import xml.etree.ElementTree as ET

from aiohttp import ClientError, ClientSession

from .base import ProviderFetchResult, geo_uri, haversine_m, navigation_url

RSS_URL = "https://www.pls-zh.ch/plsFeed/rss"
WFS_URL = (
    "https://www.ogd.stadt-zuerich.ch/wfs/geoportal/"
    "Oeffentlich_zugaengliche_Parkhaeuser"
)
WFS_LAYER = "poi_parkhaus_view"
PROVIDER_NAME = "Stadt Zürich Parkleitsystem"
PROVIDER_URL = "https://data.stadt-zuerich.ch/dataset/parkleitsystem"
GEO_URL = (
    "https://data.stadt-zuerich.ch/dataset/"
    "geo_oeffentlich_zugaengliche_parkhaeuser"
)
STATIC_CACHE_SECONDS = 12 * 60 * 60
LIVE_MAX_AGE_SECONDS = 10 * 60
MAX_XML_BYTES = 2_000_000


def _count(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
        if math.isfinite(number) and number >= 0 and number.is_integer():
            return int(number)
    except (TypeError, ValueError, OverflowError):
        pass
    return None


def _pid(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        query = parse_qs(urlparse(value.strip()).query)
        pid = query.get("pid", [None])[0]
        if isinstance(pid, str) and pid.strip():
            return pid.strip().casefold()
    except (TypeError, ValueError):
        pass
    return None


def _timestamp(item: dict[str, str]) -> str | None:
    raw = (
        item.get("{http://purl.org/dc/elements/1.1/}date")
        or item.get("pubDate")
    )
    if not raw:
        return None
    try:
        if "T" in raw:
            stamp = datetime.fromisoformat(
                raw.strip().replace("Z", "+00:00")
            )
        else:
            stamp = parsedate_to_datetime(raw.strip())
        if stamp.tzinfo is None:
            return None
        utc = stamp.astimezone(UTC)
        age = (datetime.now(UTC) - utc).total_seconds()
        if -300 <= age <= LIVE_MAX_AGE_SECONDS:
            return utc.isoformat()
    except (TypeError, ValueError, OverflowError):
        pass
    return None


def _live_items(raw: bytes) -> dict[str, dict[str, Any]]:
    if len(raw) > MAX_XML_BYTES:
        raise ValueError("Zürich RSS exceeds safe size")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as err:
        raise ValueError("Invalid Zürich RSS XML") from err

    result: dict[str, dict[str, Any]] = {}
    for node in root.findall(".//item"):
        values = {
            child.tag: (child.text or "").strip()
            for child in list(node)
        }
        pid = _pid(values.get("link") or values.get("guid"))
        if not pid:
            continue
        description = values.get("description", "")
        match = re.fullmatch(
            r"\s*([^/]+?)\s*/\s*(\d+)\s*",
            description,
        )
        status = match.group(1).strip().casefold() if match else ""
        free = _count(match.group(2)) if match else None
        result[pid] = {
            "free": free,
            "status": status,
            "updated_at": _timestamp(values),
            "link": values.get("link"),
            "title": values.get("title"),
        }
    if not result:
        raise ValueError("Zürich RSS contains no usable parking items")
    return result


class ZurichPlsProvider:
    uid = "zurich_pls"
    name = PROVIDER_NAME
    fetch_timeout = 25

    def __init__(self) -> None:
        self._sites: list[dict[str, Any]] | None = None
        self._sites_at = 0.0
        self._lock = asyncio.Lock()

    def applies(self, lat: float, lon: float) -> bool:
        return 47.24 <= lat <= 47.52 and 8.35 <= lon <= 8.75

    async def _static_sites(
        self,
        session: ClientSession,
    ) -> list[dict[str, Any]]:
        if (
            self._sites is not None
            and monotonic() - self._sites_at < STATIC_CACHE_SECONDS
        ):
            return self._sites
        async with self._lock:
            if (
                self._sites is not None
                and monotonic() - self._sites_at < STATIC_CACHE_SECONDS
            ):
                return self._sites
            try:
                async with session.get(
                    WFS_URL,
                    params={
                        "service": "WFS",
                        "version": "1.1.0",
                        "request": "GetFeature",
                        "typename": WFS_LAYER,
                        "outputFormat": "GeoJSON",
                        "srsName": "EPSG:4326",
                    },
                    timeout=20,
                    headers={
                        "Accept": "application/geo+json, application/json",
                        "User-Agent": "HomeAssistant-OSM-Parking/1.7.0",
                    },
                ) as response:
                    response.raise_for_status()
                    payload = await response.json(content_type=None)
            except (ClientError, TimeoutError, ValueError) as err:
                raise RuntimeError(f"{PROVIDER_NAME} WFS: {err}") from err
            features = payload.get("features") if isinstance(payload, dict) else None
            if (
                not isinstance(features, list)
                or not features
                or len(features) > 500
            ):
                raise RuntimeError(f"{PROVIDER_NAME}: invalid WFS inventory")
            sites = [
                feature
                for feature in features
                if isinstance(feature, dict)
            ]
            self._sites = sites
            self._sites_at = monotonic()
            return sites

    async def _live(
        self,
        session: ClientSession,
    ) -> dict[str, dict[str, Any]]:
        try:
            async with session.get(
                RSS_URL,
                timeout=15,
                headers={
                    "Accept": "application/xml, text/xml, */*",
                    "User-Agent": "HomeAssistant-OSM-Parking/1.7.0",
                },
            ) as response:
                response.raise_for_status()
                raw = await response.read()
        except (ClientError, TimeoutError, ValueError) as err:
            raise RuntimeError(f"{PROVIDER_NAME} RSS: {err}") from err
        return _live_items(raw)

    async def async_fetch(
        self,
        session: ClientSession,
        lat: float,
        lon: float,
        radius_m: int,
        options: dict[str, Any] | None = None,
    ) -> ProviderFetchResult:
        static_task = self._static_sites(session)
        live_task = self._live(session)
        static, live = await asyncio.gather(static_task, live_task)

        suggestions = [
            item
            for feature in static
            if (
                item := self._normalize(
                    feature, live, lat, lon, radius_m
                )
            ) is not None
        ]
        return ProviderFetchResult(
            provider=self.uid,
            suggestions=suggestions,
            live_refresh_seconds=60 if suggestions else None,
        )

    @staticmethod
    def _normalize(
        feature: Any,
        live: dict[str, dict[str, Any]],
        destination_lat: float,
        destination_lon: float,
        radius_m: int,
    ) -> dict[str, Any] | None:
        if not isinstance(feature, dict):
            return None
        geometry = feature.get("geometry")
        props = feature.get("properties")
        if (
            not isinstance(geometry, dict)
            or geometry.get("type") != "Point"
            or not isinstance(props, dict)
        ):
            return None
        coords = geometry.get("coordinates")
        if not isinstance(coords, (list, tuple)) or len(coords) < 2:
            return None
        try:
            lon = float(coords[0])
            lat = float(coords[1])
        except (TypeError, ValueError, OverflowError):
            return None
        if not (
            math.isfinite(lat)
            and math.isfinite(lon)
            and 47.2 <= lat <= 47.6
            and 8.3 <= lon <= 8.8
        ):
            return None
        distance = round(
            haversine_m(
                destination_lat, destination_lon, lat, lon
            )
        )
        if distance > radius_m:
            return None

        poi_id = props.get("poi_id") or props.get("id") or feature.get("id")
        if poi_id in (None, ""):
            return None
        name = str(
            props.get("name")
            or props.get("objekt")
            or poi_id
        )
        result: dict[str, Any] = {
            "provider": "zurich_pls",
            "provider_name": PROVIDER_NAME,
            "provider_id": f"zurich:{poi_id}",
            "provider_url": GEO_URL,
            "name": name,
            "distance_m": distance,
            "latitude": round(lat, 7),
            "longitude": round(lon, 7),
            "category": "multi_storey",
            "parking_type": "parking_garage",
            "fee": "unknown",
            "access": "unknown",
            "availability_kind": "static",
            "has_realtime_data": False,
            "navigation_url": navigation_url(lat, lon),
            "geo_uri": geo_uri(lat, lon),
            "source_attribution": (
                "Stadt Zürich Open Data / PLS Parkleitsystem AG (CC0)"
            ),
        }
        if props.get("adresse"):
            result["address"] = str(props["adresse"])

        capacity = _count(props.get("anzahl_oeffentliche_pp"))
        accessible = _count(props.get("davon_behinderten_pp"))
        ev = _count(props.get("davon_elektro_pp"))
        if capacity is not None:
            result["capacity"] = capacity
        if accessible is not None:
            result["accessible_capacity"] = accessible
        if ev is not None:
            result["ev_capacity"] = ev

        link = str(props.get("link_pls") or "")
        pid = _pid(link)
        if link.startswith("https://"):
            result["provider_url"] = link
        if not pid:
            return result

        current = live.get(pid)
        if not isinstance(current, dict):
            return result

        status = str(current.get("status") or "").casefold()
        if status == "closed":
            result["opening_status"] = "closed"
            return result

        free = _count(current.get("free"))
        updated_at = current.get("updated_at")
        if (
            status == "open"
            and isinstance(updated_at, str)
            and free is not None
            and (capacity is None or free <= capacity)
        ):
            result["availability_kind"] = "live"
            result["availability_freshness"] = "verified"
            result["has_realtime_data"] = True
            result["free_capacity"] = free
            result["realtime_updated_at"] = updated_at
            if capacity is not None:
                result["occupied_capacity"] = capacity - free
            result["opening_status"] = "full" if free == 0 else "open"
        return result
