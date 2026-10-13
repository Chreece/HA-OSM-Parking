from __future__ import annotations

from typing import Any

from aiohttp import ClientError, ClientSession

from .base import ProviderFetchResult, bounding_box, geo_uri, haversine_m, navigation_url

ENDPOINT = "https://api.data.gov.hk/v1/carpark-info-vacancy"
PROVIDER_NAME = "Hong Kong DATA.GOV.HK"


class HongKongParkingProvider:
    """Hong Kong government car-park information and vacancy provider."""

    uid = "hong_kong_data_gov"
    name = PROVIDER_NAME

    def applies(self, lat: float, lon: float) -> bool:
        """Return whether coordinates are inside the Hong Kong region."""
        return 22.05 <= lat <= 22.65 and 113.75 <= lon <= 114.55

    async def async_fetch(
        self,
        session: ClientSession,
        lat: float,
        lon: float,
        radius_m: int,
    ) -> ProviderFetchResult:
        """Fetch nearby parking information and realtime vacancy."""
        south, west, north, east = bounding_box(lat, lon, radius_m)
        extent = f"{west:.7f},{south:.7f},{east:.7f},{north:.7f}"

        info = await self._get(
            session,
            {
                "data": "info",
                "vehicleTypes": "privateCar",
                "extent": extent,
                "lang": "en_US",
            },
        )

        info_items = info.get("results") if isinstance(info, dict) else None
        if not isinstance(info_items, list):
            raise RuntimeError(f"{PROVIDER_NAME}: invalid info response")

        ids = [
            str(item.get("park_Id"))
            for item in info_items
            if item.get("park_Id") is not None
        ]

        vacancy_by_id: dict[str, dict[str, Any]] = {}
        if ids:
            vacancy = await self._get(
                session,
                {
                    "data": "vacancy",
                    "vehicleTypes": "privateCar",
                    "carparkIds": ",".join(ids),
                    "lang": "en_US",
                },
            )
            vacancy_items = vacancy.get("results") if isinstance(vacancy, dict) else None
            if isinstance(vacancy_items, list):
                vacancy_by_id = {
                    str(item.get("park_Id")): item
                    for item in vacancy_items
                    if item.get("park_Id") is not None
                }

        suggestions: list[dict[str, Any]] = []
        live = False
        for item in info_items:
            park_id = str(item.get("park_Id") or "")
            normalized = self._normalize(
                item,
                vacancy_by_id.get(park_id),
                lat,
                lon,
                radius_m,
            )
            if normalized is None:
                continue
            suggestions.append(normalized)
            live = live or bool(normalized.get("has_realtime_data"))

        return ProviderFetchResult(
            provider=self.uid,
            suggestions=suggestions,
            live_refresh_seconds=300 if live else None,
        )

    async def _get(
        self,
        session: ClientSession,
        params: dict[str, str],
    ) -> dict[str, Any]:
        try:
            async with session.get(
                ENDPOINT,
                params=params,
                timeout=15,
                headers={"User-Agent": "HomeAssistant-OSM-Parking/0.4.0"},
            ) as response:
                response.raise_for_status()
                payload = await response.json(content_type=None)
        except (ClientError, TimeoutError, ValueError) as err:
            raise RuntimeError(f"{PROVIDER_NAME}: {err}") from err

        if not isinstance(payload, dict):
            raise RuntimeError(f"{PROVIDER_NAME}: invalid response")
        return payload

    @staticmethod
    def _normalize(
        item: dict[str, Any],
        vacancy_item: dict[str, Any] | None,
        destination_lat: float,
        destination_lon: float,
        radius_m: int,
    ) -> dict[str, Any] | None:
        try:
            lat = float(item["latitude"])
            lon = float(item["longitude"])
        except (KeyError, TypeError, ValueError):
            return None

        distance = round(haversine_m(destination_lat, destination_lon, lat, lon))
        if distance > radius_m:
            return None

        private = item.get("privateCar")
        private_info = private if isinstance(private, dict) else {}
        charges = private_info.get("hourlyCharges") or []
        has_fee = bool(
            charges
            or private_info.get("dayNightParks")
            or private_info.get("monthlyCharges")
        )

        site_type = str(item.get("carpark_Type") or "").lower()
        if has_fee:
            category = "paid"
        elif site_type == "metered":
            category = "street"
        elif site_type == "multi-storey":
            category = "multi_storey"
        elif site_type == "off-street":
            category = "open"
        else:
            category = "other"

        result: dict[str, Any] = {
            "provider": "hong_kong",
            "provider_name": PROVIDER_NAME,
            "provider_id": f"hk:{item.get('park_Id', 'unknown')}",
            "name": str(item.get("name") or "Parking"),
            "distance_m": distance,
            "latitude": round(lat, 7),
            "longitude": round(lon, 7),
            "category": category,
            "parking_type": site_type or "unknown",
            "fee": "yes" if has_fee else "unknown",
            "access": "unknown",
            "navigation_url": navigation_url(lat, lon),
            "geo_uri": geo_uri(lat, lon),
            "has_realtime_data": False,
        }

        if item.get("website"):
            result["provider_url"] = str(item["website"])

        if item.get("displayAddress"):
            result["address"] = str(item["displayAddress"])

        if item.get("opening_status"):
            result["opening_status"] = str(item["opening_status"])

        capacity = private_info.get("space")
        if capacity is not None:
            try:
                result["capacity"] = int(capacity)
            except (TypeError, ValueError):
                pass

        if len(charges) == 1 and isinstance(charges[0], dict):
            charge = charges[0]
            price = charge.get("price")
            charge_type = str(charge.get("type") or "")
            remark = charge.get("remark")
            if price is not None and not remark:
                unit = (
                    "hour"
                    if charge_type == "hourly"
                    else "half hour"
                    if charge_type == "half-hourly"
                    else charge_type
                )
                result["price"] = (
                    "HK$" + str(price) + " / " + unit if unit else "HK$" + str(price)
                )

        if vacancy_item:
            vacancy_list = vacancy_item.get("privateCar")
            if isinstance(vacancy_list, list):
                vacancy_candidates = [
                    row
                    for row in vacancy_list
                    if isinstance(row, dict) and row.get("vacancy") is not None
                ]
                if vacancy_candidates:
                    row = vacancy_candidates[0]
                    try:
                        result["free_capacity"] = int(row["vacancy"])
                        result["has_realtime_data"] = True
                    except (TypeError, ValueError):
                        pass
                    if row.get("lastupdate"):
                        result["realtime_updated_at"] = str(row["lastupdate"])

        return result
