from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import timedelta
import logging
import math
from typing import Any

from aiohttp import ClientError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
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
    DEFAULT_INCLUDE_RESTRICTED,
    DEFAULT_MAX_PER_CATEGORY,
    DEFAULT_RADIUS_M,
    enabled_key,
)
from .providers import PROVIDERS, ProviderFetchResult
from .parking_quality import merge_facilities

_LOGGER = logging.getLogger(__name__)

OVERPASS_ENDPOINTS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
)
OVERPASS_RETRYABLE_STATUS = {429, 500, 502, 503, 504}
OVERPASS_ATTEMPTS = 2
OVERPASS_RETRY_DELAY = 3

FAILED_REFRESH_FIRST_RETRY = timedelta(minutes=1)
FAILED_REFRESH_INTERVAL = timedelta(minutes=5)

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
        self._preferred_endpoint: str | None = None
        self._failed_refreshes = 0
        super().__init__(
            hass,
            logger=_LOGGER,
            name="OSM Parking",
        )

    def _option(self, key: str, default: Any) -> Any:
        return self.entry.options.get(key, self.entry.data.get(key, default))

    @property
    def retry_interval_seconds(self) -> int | None:
        """Return the active recovery-polling interval in seconds."""
        if self.last_update_success or self.update_interval is None:
            return None
        return int(self.update_interval.total_seconds())

    @callback
    def async_reset_retry_cycle(self) -> None:
        """Cancel failure polling before a fresh event-driven refresh."""
        self._failed_refreshes = 0
        self.update_interval = None
        self._async_unsub_refresh()

    @callback
    def _async_refresh_finished(self) -> None:
        """Use periodic polling only for live data or failed refresh recovery."""
        if self.last_update_success:
            self._failed_refreshes = 0
            live_refresh_seconds = int(
                (self.data or {}).get("live_refresh_seconds") or 0
            )
            if live_refresh_seconds > 0:
                self.update_interval = timedelta(seconds=live_refresh_seconds)
                if self._listeners and not self.hass.is_stopping:
                    self._schedule_refresh()
            elif self.update_interval is not None:
                self.update_interval = None
                self._async_unsub_refresh()
            return

        self._failed_refreshes += 1
        self.update_interval = (
            FAILED_REFRESH_FIRST_RETRY
            if self._failed_refreshes == 1
            else FAILED_REFRESH_INTERVAL
        )

        # During the initial refresh the sensor platform has not subscribed yet.
        # The first listener will schedule this interval automatically.
        if self._listeners and not self.hass.is_stopping:
            self._schedule_refresh()

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
            return self._waiting_data(
                destination_entity,
                "Destination entity is not available yet",
                error_code="source_unavailable",
            )

        display_name = str(state.attributes.get("display_name") or "").strip()
        state_name = str(state.state or "").strip()
        friendly_name = str(state.attributes.get("friendly_name") or "").strip()

        lat = self._float_attr(state.attributes, ("latitude", "lat"))
        lon = self._float_attr(state.attributes, ("longitude", "lon", "lng"))
        if (
            state_name.lower() in {"unknown", "unavailable", "none", ""}
            or lat is None
            or lon is None
        ):
            return self._waiting_data(
                destination_entity,
                "Waiting for destination coordinates",
                destination_name=display_name or friendly_name or destination_entity,
                error_code="source_coordinates_missing",
            )
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

        session = async_get_clientsession(self.hass)
        provider_options = {
            **self.entry.data,
            **self.entry.options,
        }
        applicable_providers = [
            provider
            for provider in PROVIDERS
            if provider.applies(lat, lon)
            and (
                not getattr(provider, "enabled_option", None)
                or bool(
                    provider_options.get(
                        getattr(provider, "enabled_option"),
                        bool(getattr(provider, "enabled_default", True)),
                    )
                )
            )
            and all(
                str(provider_options.get(key, "")).strip()
                for key in getattr(provider, "required_options", ())
            )
        ]

        fetches = [
            self._query_overpass(lat, lon, radius),
            *[
                provider.async_fetch(
                    session,
                    lat,
                    lon,
                    radius,
                    provider_options,
                )
                for provider in applicable_providers
            ],
        ]
        fetch_results = await asyncio.gather(*fetches, return_exceptions=True)

        overpass_result = fetch_results[0]
        source: str | None = None
        raw_result_count = 0
        provider_errors: dict[str, str] = {}
        providers_used: list[str] = []
        suggestions: list[dict[str, Any]] = []
        parking_zones: list[dict[str, Any]] = []
        overpass_error: str | None = None
        live_refresh_seconds: list[int] = []

        if isinstance(overpass_result, BaseException):
            overpass_error = str(overpass_result)
        else:
            payload, source = overpass_result
            raw_result_count = len(payload.get("elements", []))
            suggestions = merge_facilities([], self._build_suggestions(
                payload, lat, lon, radius, include_restricted
            ))
            providers_used.append("openstreetmap")

        provider_suggestion_count = 0
        for provider, result in zip(
            applicable_providers,
            fetch_results[1:],
            strict=True,
        ):
            if isinstance(result, BaseException):
                provider_errors[provider.uid] = str(result)
                continue

            provider_result: ProviderFetchResult = result
            providers_used.append(provider_result.provider)
            provider_suggestion_count += len(provider_result.suggestions)
            parking_zones.extend(provider_result.zones)
            suggestions = self._merge_provider_suggestions(
                suggestions,
                provider_result.suggestions,
            )
            if provider_result.live_refresh_seconds:
                live_refresh_seconds.append(provider_result.live_refresh_seconds)

        if overpass_error and provider_suggestion_count == 0 and not parking_zones:
            raise UpdateFailed(overpass_error)

        realtime_result_count = sum(
            1 for item in suggestions if item.get("availability_kind") == "live"
        )
        reported_result_count = sum(
            1 for item in suggestions if item.get("availability_kind") == "reported"
        )
        estimated_result_count = sum(
            1 for item in suggestions if item.get("availability_kind") == "estimated"
        )

        # Live providers need periodic refreshes. Partial-provider failures also
        # get a temporary 5-minute recovery cadence; once every active provider
        # succeeds and no live data remains, polling stops again.
        if overpass_error or provider_errors:
            live_refresh_seconds.append(300)

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

        return {
            "status": "ok",
            "destination_entity": destination_entity,
            "destination_name": destination_name,
            "destination_latitude": lat,
            "destination_longitude": lon,
            "radius_m": radius,
            "max_results_per_category": self._category_limit(),
            "source": source,
            "raw_result_count": raw_result_count,
            "provider_result_count": provider_suggestion_count,
            "providers_used": providers_used,
            "provider_errors": provider_errors,
            "partial_data": bool(overpass_error or provider_errors),
            "realtime_result_count": realtime_result_count,
            "reported_result_count": reported_result_count,
            "estimated_result_count": estimated_result_count,
            "live_refresh_seconds": (
                min(live_refresh_seconds) if live_refresh_seconds else None
            ),
            "error": overpass_error if overpass_error else None,
            "error_code": None,
            "auto_retry": False,
            "retry_after_seconds": None,
            "category_counts": category_counts,
            "suggestions": selected,
            "parking_zones": parking_zones,
            "parking_zone_count": len(parking_zones),
        }

    def _waiting_data(
        self,
        destination_entity: str,
        error: str,
        *,
        destination_name: str | None = None,
        error_code: str = "waiting_for_destination",
    ) -> dict[str, Any]:
        """Return a valid coordinator state while the source entity is restoring."""
        return {
            "status": "waiting",
            "destination_entity": destination_entity,
            "destination_name": destination_name or destination_entity,
            "destination_latitude": None,
            "destination_longitude": None,
            "radius_m": int(self._option(CONF_RADIUS_M, DEFAULT_RADIUS_M)),
            "max_results_per_category": self._category_limit(),
            "source": None,
            "raw_result_count": 0,
            "provider_result_count": 0,
            "providers_used": [],
            "provider_errors": {},
            "partial_data": False,
            "realtime_result_count": 0,
            "reported_result_count": 0,
            "estimated_result_count": 0,
            "live_refresh_seconds": None,
            "error": error,
            "error_code": error_code,
            "auto_retry": False,
            "retry_after_seconds": None,
            "category_counts": {category: 0 for category in CATEGORIES},
            "suggestions": [],
            "parking_zones": [],
            "parking_zone_count": 0,
        }

    async def _query_overpass(
        self, lat: float, lon: float, radius: int
    ) -> tuple[dict[str, Any], str]:
        south, west, north, east = self._bounding_box(lat, lon, radius)
        query = f"""
[out:json][timeout:10];
nwr["amenity"="parking"]({south:.7f},{west:.7f},{north:.7f},{east:.7f});
out center tags qt;
""".strip()

        session = async_get_clientsession(self.hass)
        errors: list[str] = []

        endpoints = list(OVERPASS_ENDPOINTS)
        if self._preferred_endpoint in endpoints:
            endpoints.remove(self._preferred_endpoint)
            endpoints.insert(0, self._preferred_endpoint)

        for attempt in range(1, OVERPASS_ATTEMPTS + 1):
            empty_source: str | None = None

            for endpoint in endpoints:
                try:
                    async with session.post(
                        endpoint,
                        data={"data": query},
                        timeout=15,
                        headers={"User-Agent": "HomeAssistant-OSM-Parking/0.4.0"},
                    ) as response:
                        if response.status in OVERPASS_RETRYABLE_STATUS:
                            errors.append(
                                f"attempt {attempt} {endpoint}: "
                                f"HTTP {response.status}"
                            )
                            continue

                        if 400 <= response.status < 500:
                            detail = (await response.text())[:200].replace("\n", " ")
                            raise UpdateFailed(
                                f"Overpass rejected the query: HTTP "
                                f"{response.status} from {endpoint}: {detail}"
                            )

                        response.raise_for_status()
                        payload = await response.json(content_type=None)

                        if payload.get("elements"):
                            self._preferred_endpoint = endpoint
                            return payload, endpoint

                        # A successful empty response is valid. Check the rest of
                        # this round before accepting it, but do not retry it as a
                        # transient server failure.
                        empty_source = endpoint
                        errors.append(
                            f"attempt {attempt} {endpoint}: empty result"
                        )
                except (ClientError, TimeoutError, ValueError) as err:
                    errors.append(f"attempt {attempt} {endpoint}: {err}")

            if empty_source is not None:
                self._preferred_endpoint = empty_source
                return {"elements": []}, empty_source

            if attempt < OVERPASS_ATTEMPTS:
                await asyncio.sleep(OVERPASS_RETRY_DELAY)
                # Start the retry round on a different public instance.
                endpoints = endpoints[1:] + endpoints[:1]

        detail = "; ".join(errors) if errors else "no endpoint returned data"
        raise UpdateFailed(
            f"All Overpass endpoints failed after "
            f"{OVERPASS_ATTEMPTS} attempts: {detail}"
        )

    def _build_suggestions(
        self,
        payload: dict[str, Any],
        destination_lat: float,
        destination_lon: float,
        radius: int,
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
            # The Overpass query uses a cheap bounding box for server-side
            # efficiency; enforce the configured circular radius locally.
            if distance > radius:
                continue

            category = self._category(tags)
            parking_type = str(tags.get("parking", "unknown"))
            fee = str(tags.get("fee", "unknown"))
            name = str(tags.get("name") or self._fallback_name(category))
            price, pricing = self._pricing(tags)

            item: dict[str, Any] = {
                "provider": "osm",
                "provider_name": "OpenStreetMap",
                "data_sources": ["openstreetmap"],
                "has_realtime_data": False,
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

    def _merge_provider_suggestions(
        self,
        current: list[dict[str, Any]],
        incoming: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Normalize and deduplicate; the best valid measurement always wins."""
        return merge_facilities(current, incoming)

    @staticmethod
    def _bounding_box(
        lat: float, lon: float, radius_m: int
    ) -> tuple[float, float, float, float]:
        """Return a bounding box that fully contains the configured radius."""
        lat_delta = radius_m / 111_320.0
        cos_lat = max(abs(math.cos(math.radians(lat))), 0.01)
        lon_delta = radius_m / (111_320.0 * cos_lat)
        return (
            max(-90.0, lat - lat_delta),
            max(-180.0, lon - lon_delta),
            min(90.0, lat + lat_delta),
            min(180.0, lon + lon_delta),
        )

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
