from __future__ import annotations

from typing import Any

from aiohttp import ClientError, ClientSession

from ..const import CONF_GOLEMIO_API_KEY, CONF_GOLEMIO_ENABLED
from .base import ProviderFetchResult, bounding_box, geo_uri, haversine_m, navigation_url

PARKING_ENDPOINT = "https://api.golemio.cz/v3/parking"
MEASUREMENTS_ENDPOINT = "https://api.golemio.cz/v3/parking-measurements"
PROVIDER_NAME = "Golemio Prague Open Data"
PROVIDER_URL = "https://api.golemio.cz/docs/public-openapi/"


class GolemioParkingProvider:
    """Prague Golemio Parking v3 provider."""

    uid = "golemio_prague"
    name = PROVIDER_NAME
    enabled_option = CONF_GOLEMIO_ENABLED
    required_options = (CONF_GOLEMIO_API_KEY,)

    def applies(self, lat: float, lon: float) -> bool:
        """Return whether coordinates are inside Prague and surroundings."""
        return 49.80 <= lat <= 50.25 and 14.10 <= lon <= 14.80

    async def async_fetch(
        self,
        session: ClientSession,
        lat: float,
        lon: float,
        radius_m: int,
        options: dict[str, Any] | None = None,
    ) -> ProviderFetchResult:
        """Fetch Prague parking locations and latest occupancy measurements."""
        token = str((options or {}).get(CONF_GOLEMIO_API_KEY, "")).strip()
        if not token:
            return ProviderFetchResult(provider=self.uid, suggestions=[])

        south, west, north, east = bounding_box(lat, lon, radius_m)
        headers = {
            "X-Access-Token": token,
            "User-Agent": "HomeAssistant-OSM-Parking/0.5.0",
        }

        parking = await self._get_json(
            session,
            PARKING_ENDPOINT,
            headers,
            {
                "boundingBox": (
                    f"{north:.7f},{west:.7f},{south:.7f},{east:.7f}"
                ),
                "activeOnly": "true",
                "limit": "10000",
            },
        )

        features = parking.get("features") if isinstance(parking, dict) else None
        if not isinstance(features, list):
            raise RuntimeError(f"{PROVIDER_NAME}: invalid parking response")

        ids: list[str] = []
        for feature in features:
            if not isinstance(feature, dict):
                continue
            props = feature.get("properties")
            properties = props if isinstance(props, dict) else {}
            parking_id = properties.get("id") or feature.get("id")
            if parking_id:
                ids.append(str(parking_id))

        measurements: dict[str, dict[str, Any]] = {}
        if ids:
            params: list[tuple[str, str]] = [
                ("parkingId[]", parking_id) for parking_id in ids
            ]
            params.append(("limit", "10000"))
            live = await self._get_json(
                session,
                MEASUREMENTS_ENDPOINT,
                headers,
                params,
                allow_list=True,
            )
            if isinstance(live, list):
                measurements = {
                    str(row.get("parking_id")): row
                    for row in live
                    if isinstance(row, dict) and row.get("parking_id")
                }

        suggestions: list[dict[str, Any]] = []
        has_live = False
        for feature in features:
            if not isinstance(feature, dict):
                continue
            normalized = self._normalize(
                feature,
                measurements,
                lat,
                lon,
                radius_m,
            )
            if normalized is None:
                continue
            suggestions.append(normalized)
            has_live = has_live or bool(normalized.get("has_realtime_data"))

        return ProviderFetchResult(
            provider=self.uid,
            suggestions=suggestions,
            live_refresh_seconds=60 if has_live else None,
        )

    async def _get_json(
        self,
        session: ClientSession,
        url: str,
        headers: dict[str, str],
        params: Any,
        *,
        allow_list: bool = False,
    ) -> Any:
        try:
            async with session.get(
                url,
                headers=headers,
                params=params,
                timeout=20,
            ) as response:
                response.raise_for_status()
                payload = await response.json(content_type=None)
        except (ClientError, TimeoutError, ValueError) as err:
            raise RuntimeError(f"{PROVIDER_NAME}: {err}") from err

        if not isinstance(payload, (dict, list)):
            raise RuntimeError(f"{PROVIDER_NAME}: invalid JSON response")
        if isinstance(payload, list) and not allow_list:
            raise RuntimeError(f"{PROVIDER_NAME}: unexpected list response")
        return payload

    @staticmethod
    def _coordinates(
        feature: dict[str, Any],
        properties: dict[str, Any],
    ) -> tuple[float, float] | None:
        centroid = properties.get("centroid")
        if isinstance(centroid, dict):
            coordinates = centroid.get("coordinates")
            if isinstance(coordinates, list) and len(coordinates) >= 2:
                try:
                    return float(coordinates[1]), float(coordinates[0])
                except (TypeError, ValueError):
                    pass
            try:
                return float(centroid["lat"]), float(centroid["lon"])
            except (KeyError, TypeError, ValueError):
                pass

        geometry = feature.get("geometry")
        if isinstance(geometry, dict):
            coordinates = geometry.get("coordinates")
            if isinstance(coordinates, list) and len(coordinates) >= 2:
                try:
                    return float(coordinates[1]), float(coordinates[0])
                except (TypeError, ValueError):
                    pass
        return None

    @classmethod
    def _normalize(
        cls,
        feature: dict[str, Any],
        measurements: dict[str, dict[str, Any]],
        destination_lat: float,
        destination_lon: float,
        radius_m: int,
    ) -> dict[str, Any] | None:
        raw_props = feature.get("properties")
        props = raw_props if isinstance(raw_props, dict) else {}
        coordinates = cls._coordinates(feature, props)
        if coordinates is None:
            return None
        lat, lon = coordinates

        distance = round(haversine_m(destination_lat, destination_lon, lat, lon))
        if distance > radius_m:
            return None

        parking_id = str(props.get("id") or feature.get("id") or "")
        if not parking_id:
            return None

        parking_type = str(props.get("parking_type") or "other").casefold()
        policy = str(props.get("parking_policy") or "").casefold()

        if policy == "park_and_ride":
            category = "park_and_ride"
        elif parking_type == "on_street":
            category = "street"
        elif parking_type == "underground":
            category = "underground"
        elif parking_type == "multi_storey":
            category = "multi_storey"
        elif parking_type in {"surface", "rooftop"}:
            category = "open"
        else:
            category = "other"

        payment = props.get("payment")
        has_payment = isinstance(payment, dict) and any(payment.values())
        has_fee = bool(
            policy == "commercial"
            or props.get("tariff")
            or has_payment
        )
        if has_fee and category != "park_and_ride":
            category = "paid"

        contact = props.get("contact")
        contact_data = contact if isinstance(contact, dict) else {}
        address = props.get("address")
        address_data = address if isinstance(address, dict) else {}

        result: dict[str, Any] = {
            "provider": "golemio",
            "provider_name": PROVIDER_NAME,
            "provider_id": f"golemio:{parking_id}",
            "provider_url": str(
                contact_data.get("web_url") or PROVIDER_URL
            ),
            "name": str(props.get("name") or "Parking"),
            "distance_m": distance,
            "latitude": round(lat, 7),
            "longitude": round(lon, 7),
            "category": category,
            "parking_type": parking_type,
            "fee": "yes" if has_fee else "unknown",
            "access": (
                "customers"
                if policy == "customer_only"
                else "unknown"
            ),
            "has_realtime_data": False,
            "navigation_url": navigation_url(lat, lon),
            "geo_uri": geo_uri(lat, lon),
        }

        if address_data.get("address_formatted"):
            result["address"] = str(address_data["address_formatted"])
        elif address_data.get("street_address"):
            pieces = [
                str(address_data.get("street_address") or "").strip(),
                str(address_data.get("house_number") or "").strip(),
                str(address_data.get("address_locality") or "").strip(),
            ]
            result["address"] = " ".join(piece for piece in pieces if piece)

        try:
            if props.get("capacity") is not None:
                result["capacity"] = int(props["capacity"])
        except (TypeError, ValueError):
            pass

        measurement = measurements.get(parking_id)
        if measurement:
            result["has_realtime_data"] = True
            for source, target in (
                ("total_spot_number", "capacity"),
                ("free_spot_number", "free_capacity"),
                ("occupied_spot_number", "occupied_capacity"),
                ("closed_spot_number", "closed_capacity"),
            ):
                if measurement.get(source) is not None:
                    try:
                        result[target] = int(measurement[source])
                    except (TypeError, ValueError):
                        pass
            if measurement.get("last_updated"):
                result["realtime_updated_at"] = str(
                    measurement["last_updated"]
                )

        return result
