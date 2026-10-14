"""Ville de Luxembourg official parking feed.

The feed publishes one build timestamp for the current free-space snapshot.
Only fresh, non-faulted records are classified as live; static metadata remains
usable when occupancy is stale or the source marks a parking as in failure.
"""

from __future__ import annotations

from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
import math
from typing import Any

from aiohttp import ClientError, ClientSession

from .base import ProviderFetchResult, geo_uri, haversine_m, navigation_url

ENDPOINT = "https://feed.vdl.lu/circulation/parking/feed.json"
PROVIDER_NAME = "Ville de Luxembourg Parking Open Data"
PROVIDER_URL = "https://data.public.lu/en/datasets/mobilite-emplacements-de-parking-libres/"
LIVE_MAX_AGE_SECONDS = 10 * 60


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


def _fresh_build_time(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        stamp = parsedate_to_datetime(value.strip())
        if stamp.tzinfo is None:
            return None
        utc = stamp.astimezone(UTC)
        age = (datetime.now(UTC) - utc).total_seconds()
        if -300 <= age <= LIVE_MAX_AGE_SECONDS:
            return utc.isoformat()
    except (TypeError, ValueError, OverflowError):
        pass
    return None


def _localized(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(value, dict):
        for key in ("en", "de", "fr"):
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
    return None


def _fee(value: Any) -> str:
    raw = str(value or "").strip().casefold()
    if raw == "payant":
        return "yes"
    if raw in {"gratuit", "free"}:
        return "no"
    # Values such as gratuit24h later become paid, so don't claim "free".
    return "unknown"


class LuxembourgCityParkingProvider:
    uid = "luxembourg_city"
    name = PROVIDER_NAME
    fetch_timeout = 20

    def applies(self, lat: float, lon: float) -> bool:
        # City feed only; envelope includes the integration's maximum-radius
        # approach from neighbouring municipalities.
        return 49.48 <= lat <= 49.75 and 5.95 <= lon <= 6.30

    async def async_fetch(
        self,
        session: ClientSession,
        lat: float,
        lon: float,
        radius_m: int,
        options: dict[str, Any] | None = None,
    ) -> ProviderFetchResult:
        try:
            async with session.get(
                ENDPOINT,
                timeout=15,
                headers={
                    "Accept": "application/json",
                    "User-Agent": "HomeAssistant-OSM-Parking/1.7.0",
                },
            ) as response:
                response.raise_for_status()
                payload = await response.json(content_type=None)
        except (ClientError, TimeoutError, ValueError) as err:
            raise RuntimeError(f"{PROVIDER_NAME}: {err}") from err

        parking = payload.get("parking") if isinstance(payload, dict) else None
        if not isinstance(parking, dict) or not parking:
            raise RuntimeError(f"{PROVIDER_NAME}: invalid parking inventory")
        recorded_at = _fresh_build_time(payload.get("last_build_date"))

        suggestions = [
            item
            for raw in parking.values()
            if (
                item := self._normalize(
                    raw, lat, lon, radius_m, recorded_at
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
        raw: Any,
        destination_lat: float,
        destination_lon: float,
        radius_m: int,
        recorded_at: str | None,
    ) -> dict[str, Any] | None:
        if not isinstance(raw, dict):
            return None
        parking_id = raw.get("id")
        location = raw.get("localisation")
        if parking_id in (None, "") or not isinstance(location, dict):
            return None
        try:
            lat = float(location["latitude"])
            lon = float(location["longitude"])
        except (KeyError, TypeError, ValueError, OverflowError):
            return None
        if not (
            math.isfinite(lat)
            and math.isfinite(lon)
            and 49.4 <= lat <= 49.8
            and 5.8 <= lon <= 6.4
        ):
            return None
        distance = round(
            haversine_m(
                destination_lat, destination_lon, lat, lon
            )
        )
        if distance > radius_m:
            return None

        divers = raw.get("divers")
        divers = divers if isinstance(divers, dict) else {}
        payment = raw.get("paiement")
        payment = payment if isinstance(payment, dict) else {}
        nominal = raw.get("nominal")
        nominal = nominal if isinstance(nominal, dict) else {}
        restrictions = raw.get("restrictions")
        restrictions = restrictions if isinstance(restrictions, dict) else {}

        is_pr = divers.get("park_and_ride") is True
        fee = _fee(payment.get("politique_tarifaire"))
        category = (
            "park_and_ride"
            if is_pr
            else "paid"
            if fee == "yes"
            else "other"
        )
        result: dict[str, Any] = {
            "provider": "luxembourg_city",
            "provider_name": PROVIDER_NAME,
            "provider_id": f"vdl:{parking_id}",
            "provider_url": PROVIDER_URL,
            "name": str(raw.get("titre") or f"Parking {parking_id}"),
            "distance_m": distance,
            "latitude": round(lat, 7),
            "longitude": round(lon, 7),
            "category": category,
            "parking_type": "park_and_ride" if is_pr else "off_street",
            "fee": fee,
            "access": "unknown",
            "availability_kind": "static",
            "has_realtime_data": False,
            "navigation_url": navigation_url(lat, lon),
            "geo_uri": geo_uri(lat, lon),
            "source_attribution": "Ville de Luxembourg Open Data (CC BY 4.0)",
        }

        entrances = location.get("entree")
        if isinstance(entrances, list):
            for entrance in entrances:
                if isinstance(entrance, dict) and entrance.get("adresse"):
                    result["address"] = str(entrance["adresse"])
                    break

        opening = _localized(raw.get("ouverture"))
        if opening:
            result["opening_hours"] = opening
        transport = _localized(location.get("mobilite"))
        if transport:
            result["public_transport"] = transport

        total = _count(raw.get("total"))
        free = _count(raw.get("actuel"))
        if total is not None:
            result["capacity"] = total

        for source, target in (
            ("handicapes", "accessible_capacity"),
            ("e-cars", "ev_capacity"),
        ):
            count = _count(nominal.get(source))
            if count is not None:
                result[target] = count

        max_height = restrictions.get("max_hauteur")
        if isinstance(max_height, str) and max_height.strip():
            result["max_height"] = max_height.strip()

        if raw.get("ouvert") is False:
            result["opening_status"] = "closed"
            return result

        if raw.get("panne") is True:
            result["source_status"] = "fault"
            return result

        if recorded_at is None:
            return result

        if (
            free is not None
            and total is not None
            and free <= total
        ):
            result["availability_kind"] = "live"
            result["has_realtime_data"] = True
            result["availability_freshness"] = "verified"
            result["free_capacity"] = free
            result["occupied_capacity"] = total - free
            result["realtime_updated_at"] = recorded_at
            if raw.get("complet") is True or free == 0:
                result["opening_status"] = "full"
            else:
                result["opening_status"] = "open"
        return result
