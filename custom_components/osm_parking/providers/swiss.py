from __future__ import annotations

from time import monotonic
from typing import Any

from aiohttp import ClientError, ClientSession

from .base import ProviderFetchResult, geo_uri, haversine_m, navigation_url

PERMALINK = (
    "https://data.opentransportdata.swiss/"
    "dataset/bike-and-car-parking/permalink"
)
PROVIDER_NAME = "Open Transport Data Switzerland / SBB P+Rail"
PROVIDER_URL = (
    "https://data.opentransportdata.swiss/"
    "dataset/bike-and-car-parking"
)
CACHE_SECONDS = 30 * 60


class SwissParkingProvider:
    """Swiss Bike-and-Car-Parking GeoJSON provider."""

    uid = "swiss_open_transport"
    name = PROVIDER_NAME

    def __init__(self) -> None:
        self._features: list[dict[str, Any]] = []
        self._loaded_at = 0.0

    def applies(self, lat: float, lon: float) -> bool:
        """Cover Switzerland plus the dataset's nearby cross-border facilities."""
        return 44.5 <= lat <= 49.5 and 5.0 <= lon <= 12.0

    async def async_fetch(
        self,
        session: ClientSession,
        lat: float,
        lon: float,
        radius_m: int,
        options: dict[str, Any] | None = None,
    ) -> ProviderFetchResult:
        """Fetch nearby car parking and estimated occupancy where supplied."""
        features = await self._async_features(session)
        suggestions: list[dict[str, Any]] = []
        has_estimated_occupancy = False

        for feature in features:
            normalized = self._normalize(
                feature,
                lat,
                lon,
                radius_m,
            )
            if normalized is None:
                continue
            suggestions.append(normalized)
            has_estimated_occupancy = (
                has_estimated_occupancy
                or bool(normalized.get("has_estimated_occupancy"))
            )

        return ProviderFetchResult(
            provider=self.uid,
            suggestions=suggestions,
            live_refresh_seconds=1800 if has_estimated_occupancy else None,
        )

    async def _async_features(
        self,
        session: ClientSession,
    ) -> list[dict[str, Any]]:
        now = monotonic()
        if self._features and now - self._loaded_at < CACHE_SECONDS:
            return self._features

        try:
            async with session.get(
                PERMALINK,
                timeout=45,
                headers={
                    "User-Agent": "HomeAssistant-OSM-Parking/0.6.0"
                },
            ) as response:
                response.raise_for_status()
                payload = await response.json(content_type=None)
        except (ClientError, TimeoutError, ValueError) as err:
            raise RuntimeError(f"{PROVIDER_NAME}: {err}") from err

        features = payload.get("features") if isinstance(payload, dict) else None
        if not isinstance(features, list):
            raise RuntimeError(f"{PROVIDER_NAME}: invalid GeoJSON response")

        self._features = [
            feature
            for feature in features
            if isinstance(feature, dict)
        ]
        self._loaded_at = now
        return self._features

    @classmethod
    def _normalize(
        cls,
        feature: dict[str, Any],
        destination_lat: float,
        destination_lon: float,
        radius_m: int,
    ) -> dict[str, Any] | None:
        raw_props = feature.get("properties")
        props = raw_props if isinstance(raw_props, dict) else {}

        if str(props.get("parkingFacilityCategory") or "").upper() != "CAR":
            return None

        coordinates = cls._geometry_center(feature.get("geometry"))
        if coordinates is None:
            return None
        lat, lon = coordinates

        distance = round(
            haversine_m(
                destination_lat,
                destination_lon,
                lat,
                lon,
            )
        )
        if distance > radius_m:
            return None

        facility_type = str(
            props.get("parkingFacilityType") or "PARKING"
        ).upper()
        category = (
            "park_and_ride"
            if facility_type == "PARK_AND_RAIL"
            else "open"
        )

        feature_id = str(feature.get("id") or props.get("id") or "")
        name = cls._text_value(
            props.get("displayName")
            or props.get("name")
        ) or "Parking"

        call_to_action = cls._url_value(props.get("callToAction"))

        result: dict[str, Any] = {
            "provider": "swiss_open_transport",
            "provider_name": PROVIDER_NAME,
            "provider_id": f"swiss:{feature_id or lat}:{lon}",
            "provider_url": call_to_action or PROVIDER_URL,
            "name": name,
            "distance_m": distance,
            "latitude": round(lat, 7),
            "longitude": round(lon, 7),
            "category": category,
            "parking_type": facility_type.casefold(),
            "fee": "unknown",
            "access": "unknown",
            "has_realtime_data": False,
            "navigation_url": navigation_url(lat, lon),
            "geo_uri": geo_uri(lat, lon),
            "source_attribution": "Open Data Platform Mobility Switzerland / SBB",
        }

        operator = cls._text_value(props.get("operator"))
        if operator:
            result["operator"] = operator

        address = cls._address_value(props.get("address"))
        if address:
            result["address"] = address

        operation_time = cls._text_value(props.get("operationTime"))
        if operation_time:
            result["opening_hours"] = operation_time

        capacity = cls._capacity_value(props.get("capacities"))
        if capacity is not None:
            result["capacity"] = capacity

        occupancy = props.get("currentEstimatedOccupancy")
        try:
            ratio = float(occupancy)
        except (TypeError, ValueError):
            ratio = -1.0

        if 0.0 <= ratio <= 1.0:
            result["has_estimated_occupancy"] = True
            result["estimated_occupancy_ratio"] = round(ratio, 4)
            result["estimated_occupancy_percent"] = round(ratio * 100)

            level = str(
                props.get("currentEstimatedOccupancyLevel") or ""
            ).upper()
            if level in {"LOW", "MEDIUM", "HIGH"}:
                result["estimated_occupancy_level"] = level

        if props.get("eChargingStationOperatorID"):
            result["ev_charging_operator_id"] = str(
                props["eChargingStationOperatorID"]
            )

        return result

    @classmethod
    def _geometry_center(
        cls,
        geometry: Any,
    ) -> tuple[float, float] | None:
        if not isinstance(geometry, dict):
            return None

        geometry_type = str(geometry.get("type") or "")
        if geometry_type == "GeometryCollection":
            geometries = geometry.get("geometries")
            if not isinstance(geometries, list):
                return None

            for child in geometries:
                if (
                    isinstance(child, dict)
                    and child.get("type") == "Point"
                ):
                    point = cls._geometry_center(child)
                    if point is not None:
                        return point

            points: list[tuple[float, float]] = []
            for child in geometries:
                cls._collect_points(child, points)
            return cls._points_center(points)

        if geometry_type == "Point":
            coordinates = geometry.get("coordinates")
            if isinstance(coordinates, list) and len(coordinates) >= 2:
                try:
                    lon = float(coordinates[0])
                    lat = float(coordinates[1])
                except (TypeError, ValueError):
                    return None
                if -90 <= lat <= 90 and -180 <= lon <= 180:
                    return lat, lon
            return None

        points: list[tuple[float, float]] = []
        cls._collect_points(geometry, points)
        return cls._points_center(points)

    @classmethod
    def _collect_points(
        cls,
        geometry: Any,
        result: list[tuple[float, float]],
    ) -> None:
        if not isinstance(geometry, dict):
            return

        if geometry.get("type") == "GeometryCollection":
            for child in geometry.get("geometries") or []:
                cls._collect_points(child, result)
            return

        def walk(value: Any) -> None:
            if not isinstance(value, list):
                return
            if (
                len(value) >= 2
                and isinstance(value[0], (int, float))
                and isinstance(value[1], (int, float))
            ):
                lon = float(value[0])
                lat = float(value[1])
                if -90 <= lat <= 90 and -180 <= lon <= 180:
                    result.append((lat, lon))
                return
            for child in value:
                walk(child)

        walk(geometry.get("coordinates"))

    @staticmethod
    def _points_center(
        points: list[tuple[float, float]],
    ) -> tuple[float, float] | None:
        if not points:
            return None
        lats = [point[0] for point in points]
        lons = [point[1] for point in points]
        return (
            (min(lats) + max(lats)) / 2,
            (min(lons) + max(lons)) / 2,
        )

    @classmethod
    def _text_value(cls, value: Any) -> str | None:
        if isinstance(value, str):
            text = value.strip()
            return text or None
        if isinstance(value, dict):
            for key in (
                "displayName",
                "name",
                "value",
                "text",
                "description",
            ):
                text = cls._text_value(value.get(key))
                if text:
                    return text
        return None

    @classmethod
    def _address_value(cls, value: Any) -> str | None:
        text = cls._text_value(value)
        if text:
            return text
        if not isinstance(value, dict):
            return None

        parts: list[str] = []
        for key in (
            "streetAddress",
            "street",
            "houseNumber",
            "postalCode",
            "zipCode",
            "city",
            "locality",
            "municipality",
        ):
            raw = value.get(key)
            if raw not in (None, ""):
                part = str(raw).strip()
                if part and part not in parts:
                    parts.append(part)
        return " ".join(parts) if parts else None

    @classmethod
    def _url_value(cls, value: Any) -> str | None:
        if isinstance(value, str):
            text = value.strip()
            if text.startswith(("https://", "http://")):
                return text
            return None
        if isinstance(value, dict):
            for key in ("url", "href", "webUrl", "uri"):
                found = cls._url_value(value.get(key))
                if found:
                    return found
            for child in value.values():
                found = cls._url_value(child)
                if found:
                    return found
        if isinstance(value, list):
            for child in value:
                found = cls._url_value(child)
                if found:
                    return found
        return None

    @classmethod
    def _capacity_value(cls, value: Any) -> int | None:
        preferred = {
            "total",
            "totalcapacity",
            "capacity",
            "parkingcapacity",
            "numberofspaces",
            "spaces",
        }
        found: list[int] = []

        def walk(current: Any, key_hint: str = "") -> None:
            if isinstance(current, bool):
                return
            if isinstance(current, (int, float)):
                normalized_key = "".join(
                    char
                    for char in key_hint.casefold()
                    if char.isalnum()
                )
                if normalized_key in preferred:
                    numeric = int(current)
                    if numeric >= 0:
                        found.append(numeric)
                return
            if isinstance(current, dict):
                for key, child in current.items():
                    walk(child, str(key))
                return
            if isinstance(current, list):
                for child in current:
                    walk(child, key_hint)

        if isinstance(value, (int, float)) and not isinstance(value, bool):
            numeric = int(value)
            return numeric if numeric >= 0 else None

        walk(value)
        return max(found) if found else None
