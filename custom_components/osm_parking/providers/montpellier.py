from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from aiohttp import ClientError, ClientSession

from .base import ProviderFetchResult, geo_uri, haversine_m, navigation_url

ENDPOINT = "https://portail-api-data.montpellier.fr/ngsi-ld/v1/entities"
PROVIDER_NAME = "Montpellier Méditerranée Métropole Open Data"
PROVIDER_URL = (
    "https://data.montpellier3m.fr/dataset/"
    "disponibilite-des-places-dans-les-parkings-de-"
    "montpellier-mediterranee-metropole"
)
LIVE_MAX_AGE_SECONDS = 15 * 60


class MontpellierParkingProvider:
    """NGSI-LD OffStreetParking provider for Montpellier Métropole."""

    uid = "montpellier_ngsi_ld"
    name = PROVIDER_NAME

    def applies(self, lat: float, lon: float) -> bool:
        """Return whether coordinates are in Montpellier Métropole."""
        return 43.40 <= lat <= 43.85 and 3.55 <= lon <= 4.20

    async def async_fetch(
        self,
        session: ClientSession,
        lat: float,
        lon: float,
        radius_m: int,
        options: dict[str, Any] | None = None,
    ) -> ProviderFetchResult:
        """Fetch normalized OffStreetParking entities."""
        try:
            async with session.get(
                ENDPOINT,
                params={
                    "type": "OffStreetParking",
                    "limit": "1000",
                },
                timeout=20,
                headers={
                    "Accept": "application/ld+json, application/json",
                    "User-Agent": "HomeAssistant-OSM-Parking/0.7.0",
                },
            ) as response:
                response.raise_for_status()
                payload = await response.json(content_type=None)
        except (ClientError, TimeoutError, ValueError) as err:
            raise RuntimeError(f"{PROVIDER_NAME}: {err}") from err

        if isinstance(payload, dict):
            entities = payload.get("results") or payload.get("entities")
        else:
            entities = payload

        if not isinstance(entities, list):
            raise RuntimeError(f"{PROVIDER_NAME}: invalid NGSI-LD response")

        suggestions: list[dict[str, Any]] = []
        has_live = False

        for entity in entities:
            if not isinstance(entity, dict):
                continue
            normalized = self._normalize(
                entity,
                lat,
                lon,
                radius_m,
            )
            if normalized is None:
                continue
            suggestions.append(normalized)
            has_live = has_live or bool(
                normalized.get("has_realtime_data")
            )

        return ProviderFetchResult(
            provider=self.uid,
            suggestions=suggestions,
            live_refresh_seconds=300 if has_live else None,
        )

    @staticmethod
    def _property_value(
        entity: dict[str, Any],
        key: str,
    ) -> Any:
        raw = entity.get(key)
        if isinstance(raw, dict) and "value" in raw:
            return raw["value"]
        return raw

    @classmethod
    def _normalize(
        cls,
        entity: dict[str, Any],
        destination_lat: float,
        destination_lon: float,
        radius_m: int,
    ) -> dict[str, Any] | None:
        location = cls._property_value(entity, "location")
        if not isinstance(location, dict):
            return None
        coordinates = location.get("coordinates")
        if not isinstance(coordinates, list) or len(coordinates) < 2:
            return None

        try:
            lon = float(coordinates[0])
            lat = float(coordinates[1])
        except (TypeError, ValueError):
            return None

        distance = round(haversine_m(destination_lat, destination_lon, lat, lon))
        if distance > radius_m:
            return None

        parking_id = str(entity.get("id") or "")
        if not parking_id:
            return None

        name = str(cls._property_value(entity, "name") or "Parking")
        layouts = cls._property_value(entity, "layout")
        if isinstance(layouts, str):
            layout_values = [layouts]
        elif isinstance(layouts, list):
            layout_values = [str(value) for value in layouts]
        else:
            layout_values = []

        layout_text = " ".join(layout_values).casefold()
        name_text = name.casefold()

        if (
            "p+tram" in name_text
            or "p + tram" in name_text
            or "park and ride" in name_text
        ):
            category = "park_and_ride"
        elif "underground" in layout_text:
            category = "underground"
        elif (
            "multilevel" in layout_text
            or "multi level" in layout_text
            or "multi-level" in layout_text
        ):
            category = "multi_storey"
        elif "surface" in layout_text:
            category = "open"
        else:
            category = "other"

        is_free_raw = cls._property_value(entity, "isFree")
        is_free_text = str(is_free_raw).strip().casefold()
        if is_free_text in {"true", "1", "yes"}:
            fee = "no"
        elif is_free_text in {"false", "0", "no"}:
            fee = "yes"
            if category != "park_and_ride":
                category = "paid"
        else:
            fee = "unknown"

        required_permit = str(
            cls._property_value(entity, "requiredPermit") or ""
        ).strip()
        access = (
            "unknown"
            if not required_permit
            or required_permit.casefold() == "nopermitneeded"
            else "permit"
        )

        available_property = entity.get("availableSpotNumber")
        available = cls._property_value(entity, "availableSpotNumber")
        observed_at = (
            available_property.get("observedAt")
            if isinstance(available_property, dict)
            else None
        )
        fresh = cls._is_fresh(observed_at)

        result: dict[str, Any] = {
            "provider": "montpellier",
            "provider_name": PROVIDER_NAME,
            "provider_id": f"montpellier:{parking_id}",
            "provider_url": PROVIDER_URL,
            "name": name,
            "distance_m": distance,
            "latitude": round(lat, 7),
            "longitude": round(lon, 7),
            "category": category,
            "parking_type": (
                layout_text.replace(" ", "_") if layout_text else "off_street"
            ),
            "fee": fee,
            "access": access,
            "has_realtime_data": False,
            "navigation_url": navigation_url(lat, lon),
            "geo_uri": geo_uri(lat, lon),
            "source_attribution": "Montpellier Méditerranée Métropole Open Data",
        }

        address = cls._property_value(entity, "address")
        if address not in (None, ""):
            result["address"] = str(address)

        total = cls._property_value(entity, "totalSpotNumber")
        try:
            total_int = int(total)
            if total_int >= 0:
                result["capacity"] = total_int
        except (TypeError, ValueError):
            pass

        if fresh:
            try:
                free = int(available)
                if free >= 0:
                    result["free_capacity"] = free
                    result["has_realtime_data"] = True
                    if result.get("capacity") is not None:
                        result["occupied_capacity"] = max(
                            0,
                            int(result["capacity"]) - free,
                        )
            except (TypeError, ValueError):
                pass

            if observed_at:
                result["realtime_updated_at"] = str(observed_at)

        status = cls._property_value(entity, "status")
        if status not in (None, ""):
            status_text = str(status).strip().casefold()
            if status_text in {"open", "opened", "working"}:
                result["opening_status"] = "open"
            elif status_text in {
                "closed",
                "close",
                "outofservice",
                "out_of_service",
            }:
                result["opening_status"] = "closed"
            else:
                result["opening_status"] = str(status)

        disabled = cls._property_value(entity, "disabledParkingNumber")
        try:
            disabled_int = int(disabled)
            if disabled_int >= 0:
                result["capacity_disabled"] = disabled_int
        except (TypeError, ValueError):
            pass

        return result

    @staticmethod
    def _is_fresh(value: Any) -> bool:
        if not value:
            return False
        try:
            parsed = datetime.fromisoformat(
                str(value).strip().replace("Z", "+00:00")
            )
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            age = (
                datetime.now(UTC) - parsed.astimezone(UTC)
            ).total_seconds()
            return -300 <= age <= LIVE_MAX_AGE_SECONDS
        except (TypeError, ValueError):
            return False
