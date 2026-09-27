from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
import logging
import math
from typing import Any

from aiohttp import ClientError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CATEGORIES,
    CATEGORY_MULTI_STOREY,
    CATEGORY_OPEN,
    CATEGORY_OTHER,
    CATEGORY_PAID,
    CATEGORY_PARK_AND_RIDE,
    CATEGORY_STREET,
    CATEGORY_UNDERGROUND,
    CONF_DESTINATION_ENTITY,
    CONF_INCLUDE_RESTRICTED,
    CONF_MAX_RESULTS,
    CONF_RADIUS_M,
    CONF_REFRESH_MINUTES,
    DEFAULT_INCLUDE_RESTRICTED,
    DEFAULT_MAX_PER_CATEGORY,
    DEFAULT_RADIUS_M,
    DEFAULT_REFRESH_MINUTES,
    enabled_key,
)

_LOGGER = logging.getLogger(__name__)

OVERPASS_ENDPOINTS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
)

RESTRICTED_ACCESS = {
    "private",
    "customers",
    "permit",
    "residents",
    "destination",
    "delivery",
    "no",
}
STREET_TYPES = {
    "street_side",
    "lane",
    "on_street",
    "on_kerb",
    "half_on_kerb",
    "shoulder",
}
OPEN_TYPES = {"surface", "carports", "rooftop"}


class OsmParkingCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetch and classify parking suggestions around a destination."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.entry = entry
        minutes = int(
            entry.options.get(
                CONF_REFRESH_MINUTES,
                entry.data.get(CONF_REFRESH_MINUTES, DEFAULT_REFRESH_MINUTES),
            )
        )
        super().__init__(
            hass,
            logger=_LOGGER,
            name="OSM Parking",
            update_interval=timedelta(minutes=minutes),
        )

    def _option(self, key: str, default: Any) -> Any:
        return self.entry.options.get(key, self.entry.data.get(key, default))

    def _category_enabled(self, category: str) -> bool:
        return bool(self._option(enabled_key(category), True))

    def _category_limit(self) -> int:
        """Return the one limit applied independently to every enabled category."""
        return max(1, int(self._option(CONF_MAX_RESULTS, DEFAULT_MAX_PER_CATEGORY)))

    async def _async_update_data(self) -> dict[str, Any]:
        destination_entity = str(self._option(CONF_DESTINATION_ENTITY, "")).strip()
        if not destination_entity:
            raise UpdateFailed("No destination entity configured")

        state = self.hass.states.get(destination_entity)
        if state is None:
            raise UpdateFailed(f"Destination entity {destination_entity} not found")

        lat = self._float_attr(state.attributes, ("latitude", "lat"))
        lon = self._float_attr(state.attributes, ("longitude", "lon", "lng"))
        if lat is None or lon is None:
            raise UpdateFailed(
                f"Destination entity {destination_entity} has no latitude/longitude attributes"
            )

        display_name = str(state.attributes.get("display_name") or "").strip()
        state_name = str(state.state or "").strip()
        friendly_name = str(state.attributes.get("friendly_name") or "").strip()
        if display_name:
            destination_name = display_name
        elif state_name.lower() not in {"unknown", "unavailable", "none", ""}:
            destination_name = state_name
        elif friendly_name:
            destination_name = friendly_name
        else:
            destination_name = destination_entity

        radius = int(self._option(CONF_RADIUS_M, DEFAULT_RADIUS_M))
        include_restricted = bool(
            self._option(CONF_INCLUDE_RESTRICTED, DEFAULT_INCLUDE_RESTRICTED)
        )

        payload, source = await self._query_overpass(lat, lon, radius)
        suggestions = self._build_suggestions(
            payload, lat, lon, include_restricted
        )
        raw_result_count = len(payload.get("elements", []))

        buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for item in suggestions:
            buckets[item["category"]].append(item)

        selected: list[dict[str, Any]] = []
        category_counts: dict[str, int] = {}

        for category in CATEGORIES:
            if not self._category_enabled(category):
                category_counts[category] = 0
                continue

            category_items = sorted(
                buckets.get(category, []), key=lambda item: item["distance_m"]
            )
            chosen = category_items[: self._category_limit()]
            selected.extend(chosen)
            category_counts[category] = len(chosen)

        selected.sort(key=lambda item: item["distance_m"])

        # A public Overpass instance can occasionally return a syntactically valid
        # but empty response. Do not wipe a known-good result set for the same
        # destination/radius just because one refresh came back empty.
        status = "ok"
        if not selected and self.data:
            previous = self.data
            same_destination = (
                previous.get("destination_entity") == destination_entity
                and previous.get("destination_latitude") == lat
                and previous.get("destination_longitude") == lon
                and previous.get("radius_m") == radius
            )
            previous_suggestions = previous.get("suggestions")
            if (
                same_destination
                and isinstance(previous_suggestions, list)
                and previous_suggestions
            ):
                selected = list(previous_suggestions)
                category_counts = dict(previous.get("category_counts") or category_counts)
                status = "stale"

        return {
            "status": status,
            "destination_entity": destination_entity,
            "destination_name": destination_name,
            "destination_latitude": lat,
            "destination_longitude": lon,
            "radius_m": radius,
            "max_results_per_category": self._category_limit(),
            "source": source,
            "raw_result_count": raw_result_count,
            "error": None,
            "category_counts": category_counts,
            "suggestions": selected,
        }

    async def _query_overpass(
        self, lat: float, lon: float, radius: int
    ) -> tuple[dict[str, Any], str]:
        query = f"""
[out:json][timeout:25];
(
  nwr["amenity"="parking"](around:{radius},{lat},{lon});
);
out center tags;
""".strip()

        session = async_get_clientsession(self.hass)
        last_error: Exception | None = None

        for endpoint in OVERPASS_ENDPOINTS:
            try:
                async with session.post(
                    endpoint,
                    data={"data": query},
                    timeout=30,
                    headers={"User-Agent": "HomeAssistant-OSM-Parking/0.2.2"},
                ) as response:
                    response.raise_for_status()
                    payload = await response.json(content_type=None)
                    # Empty payloads are suspicious for an urban parking search;
                    # try the next public instance before accepting an empty set.
                    if payload.get("elements"):
                        return payload, endpoint
                    last_error = ValueError(f"{endpoint} returned zero elements")
            except (ClientError, TimeoutError, ValueError) as err:
                last_error = err

        if last_error and "returned zero elements" in str(last_error):
            return {"elements": []}, OVERPASS_ENDPOINTS[-1]

        raise UpdateFailed(f"Overpass request failed: {last_error}")

    def _build_suggestions(
        self,
        payload: dict[str, Any],
        destination_lat: float,
        destination_lon: float,
        include_restricted: bool,
    ) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        seen: set[tuple[str, int]] = set()

        for element in payload.get("elements", []):
            osm_type = str(element.get("type", ""))
            try:
                osm_id = int(element["id"])
            except (KeyError, TypeError, ValueError):
                continue

            key = (osm_type, osm_id)
            if key in seen:
                continue
            seen.add(key)

            tags = element.get("tags") or {}
            access = str(tags.get("access", "unknown"))
            if not include_restricted and access in RESTRICTED_ACCESS:
                continue

            lat, lon = self._element_lat_lon(element)
            if lat is None or lon is None:
                continue

            distance = round(
                self._haversine_m(destination_lat, destination_lon, lat, lon)
            )
            category = self._category(tags)
            parking_type = str(tags.get("parking", "unknown"))
            fee = str(tags.get("fee", "unknown"))
            name = str(tags.get("name") or self._fallback_name(category))
            price, pricing = self._pricing(tags)

            item: dict[str, Any] = {
                "osm_type": osm_type,
                "osm_id": osm_id,
                "name": name,
                "distance_m": distance,
                "latitude": round(lat, 7),
                "longitude": round(lon, 7),
                "category": category,
                "parking_type": parking_type,
                "fee": fee,
                "access": access,
            }

            if price is not None:
                item["price"] = price
            if pricing:
                item["pricing"] = pricing

            for source, target in (
                ("capacity", "capacity"),
                ("capacity:disabled", "capacity_disabled"),
                ("maxstay", "maxstay"),
                ("opening_hours", "opening_hours"),
                ("operator", "operator"),
            ):
                if source in tags:
                    item[target] = str(tags[source])

            item["osm_url"] = (
                f"https://www.openstreetmap.org/{osm_type}/{osm_id}"
            )
            item["navigation_url"] = (
                "https://www.google.com/maps/dir/?api=1&destination="
                f"{lat:.7f},{lon:.7f}&travelmode=driving"
            )
            item["geo_uri"] = (
                f"geo:{lat:.7f},{lon:.7f}?q={lat:.7f},{lon:.7f}"
            )
            result.append(item)

        return result

    @staticmethod
    def _float_attr(
        attrs: dict[str, Any], names: tuple[str, ...]
    ) -> float | None:
        for name in names:
            if name not in attrs:
                continue
            try:
                return float(attrs[name])
            except (TypeError, ValueError):
                pass
        return None

    @staticmethod
    def _element_lat_lon(
        element: dict[str, Any],
    ) -> tuple[float | None, float | None]:
        try:
            if "lat" in element and "lon" in element:
                return float(element["lat"]), float(element["lon"])
            center = element.get("center") or {}
            return float(center["lat"]), float(center["lon"])
        except (KeyError, TypeError, ValueError):
            return None, None

    @staticmethod
    def _pricing(
        tags: dict[str, Any],
    ) -> tuple[str | None, dict[str, str]]:
        """Extract OSM pricing without inventing a cost."""
        pricing: dict[str, str] = {}

        for source, target in (
            ("charge", "charge"),
            ("charge:conditional", "charge_conditional"),
            ("fee:conditional", "fee_conditional"),
        ):
            value = tags.get(source)
            if value not in (None, ""):
                pricing[target] = str(value)

        if "charge" in pricing:
            return pricing["charge"], pricing
        if "charge_conditional" in pricing:
            return pricing["charge_conditional"], pricing
        if "fee_conditional" in pricing:
            return pricing["fee_conditional"], pricing

        if str(tags.get("fee", "")).lower() == "no":
            return "free", {}

        return None, pricing

    @staticmethod
    def _category(tags: dict[str, Any]) -> str:
        parking = str(tags.get("parking", "")).lower()
        fee = str(tags.get("fee", "")).lower()
        park_ride = str(tags.get("park_ride", "")).lower()

        if fee in {"yes", "interval"} or "fee:conditional" in tags:
            return CATEGORY_PAID
        if park_ride not in {"", "no", "unknown"}:
            return CATEGORY_PARK_AND_RIDE
        if parking in STREET_TYPES:
            return CATEGORY_STREET
        if parking == "underground":
            return CATEGORY_UNDERGROUND
        if parking == "multi-storey":
            return CATEGORY_MULTI_STOREY
        if parking in OPEN_TYPES or not parking:
            return CATEGORY_OPEN
        return CATEGORY_OTHER

    @staticmethod
    def _fallback_name(category: str) -> str:
        return {
            CATEGORY_PAID: "Paid parking",
            CATEGORY_OPEN: "Open parking",
            CATEGORY_STREET: "Street-side parking",
            CATEGORY_UNDERGROUND: "Underground parking",
            CATEGORY_MULTI_STOREY: "Multi-storey parking",
            CATEGORY_PARK_AND_RIDE: "Park & ride",
            CATEGORY_OTHER: "Parking",
        }.get(category, "Parking")

    @staticmethod
    def _haversine_m(
        lat1: float, lon1: float, lat2: float, lon2: float
    ) -> float:
        radius = 6_371_000.0
        p1 = math.radians(lat1)
        p2 = math.radians(lat2)
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(p1)
            * math.cos(p2)
            * math.sin(dlon / 2) ** 2
        )
        return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
