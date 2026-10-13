from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from aiohttp import ClientError, ClientSession

from .base import ProviderFetchResult, geo_uri, haversine_m, navigation_url

BASE_URL = "https://webmint.munimadrid.es/MTPAR_RSINFO/restInfoParking"
LIST_ENDPOINT = f"{BASE_URL}/listParking"
DETAIL_ENDPOINT = f"{BASE_URL}/detailParking"
PROVIDER_NAME = "Madrid Open Data Parking"
PROVIDER_URL = (
    "https://datos.madrid.es/dataset/"
    "50027-0-aparcamientosocupacionyservicios"
)
_LIVE_MAX_AGE_SECONDS = 30 * 60
_DETAIL_CONCURRENCY = 6


class MadridParkingProvider:
    """Madrid public rotational parking and realtime occupancy provider."""

    uid = "madrid_open_data"
    name = PROVIDER_NAME

    def applies(self, lat: float, lon: float) -> bool:
        """Return whether coordinates are in Madrid municipality."""
        return 40.25 <= lat <= 40.65 and -3.95 <= lon <= -3.45

    async def async_fetch(
        self,
        session: ClientSession,
        lat: float,
        lon: float,
        radius_m: int,
        options: dict[str, Any] | None = None,
    ) -> ProviderFetchResult:
        """Fetch nearby car parks and their detailed live occupancy."""
        payload = await self._get_json(
            session,
            LIST_ENDPOINT,
            {"language": "ES"},
        )
        parking_rows = self._parking_rows(payload)

        nearby: list[dict[str, Any]] = []
        for row in parking_rows:
            coordinates = self._coordinates(row)
            if coordinates is None:
                continue
            row_lat, row_lon = coordinates
            if haversine_m(lat, lon, row_lat, row_lon) <= radius_m:
                nearby.append(row)

        if not nearby:
            return ProviderFetchResult(provider=self.uid, suggestions=[])

        semaphore = asyncio.Semaphore(_DETAIL_CONCURRENCY)

        async def fetch_detail(row: dict[str, Any]) -> tuple[dict[str, Any], Any]:
            parking_id = row.get("id")
            family = str(row.get("family") or "001")
            if parking_id is None:
                return row, None
            async with semaphore:
                try:
                    detail = await self._get_json(
                        session,
                        DETAIL_ENDPOINT,
                        {
                            "id": str(parking_id),
                            "family": family,
                            "language": "ES",
                            "publicData": "true",
                        },
                    )
                except RuntimeError:
                    detail = None
                return row, detail

        detailed = await asyncio.gather(
            *[fetch_detail(row) for row in nearby]
        )

        suggestions: list[dict[str, Any]] = []
        has_live = False
        for row, detail_payload in detailed:
            normalized = self._normalize(
                row,
                detail_payload,
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
        params: dict[str, str],
    ) -> Any:
        try:
            async with session.get(
                url,
                params=params,
                timeout=20,
                headers={
                    "Accept": "application/json",
                    "User-Agent": "HomeAssistant-OSM-Parking/0.5.0",
                },
            ) as response:
                response.raise_for_status()
                return await response.json(content_type=None)
        except (ClientError, TimeoutError, ValueError) as err:
            raise RuntimeError(f"{PROVIDER_NAME}: {err}") from err

    @classmethod
    def _parking_rows(cls, payload: Any) -> list[dict[str, Any]]:
        """Find parking records defensively across service wrapper variants."""
        result: list[dict[str, Any]] = []

        def visit(value: Any) -> None:
            if isinstance(value, list):
                for child in value:
                    visit(child)
                return
            if not isinstance(value, dict):
                return

            if (
                value.get("id") is not None
                and cls._coordinates(value) is not None
                and (
                    value.get("family") is not None
                    or value.get("name") is not None
                    or value.get("nickName") is not None
                    or value.get("address") is not None
                )
            ):
                result.append(value)
                return

            for child in value.values():
                visit(child)

        visit(payload)

        deduped: dict[str, dict[str, Any]] = {}
        for row in result:
            key = f"{row.get('family', '001')}:{row.get('id')}"
            deduped[key] = row
        return list(deduped.values())

    @staticmethod
    def _coordinates(item: dict[str, Any]) -> tuple[float, float] | None:
        try:
            return float(item["latitude"]), float(item["longitude"])
        except (KeyError, TypeError, ValueError):
            return None

    @classmethod
    def _detail_record(cls, payload: Any) -> dict[str, Any] | None:
        if not isinstance(payload, (dict, list)):
            return None

        candidates: list[dict[str, Any]] = []

        def visit(value: Any) -> None:
            if isinstance(value, list):
                for child in value:
                    visit(child)
                return
            if not isinstance(value, dict):
                return

            if (
                value.get("id") is not None
                and (
                    "lstOccupation" in value
                    or "lstFeatures" in value
                    or "lstRates" in value
                    or cls._coordinates(value) is not None
                )
            ):
                candidates.append(value)

            for child in value.values():
                visit(child)

        visit(payload)
        return candidates[0] if candidates else None

    @staticmethod
    def _iter_dicts(value: Any) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []

        def visit(node: Any) -> None:
            if isinstance(node, list):
                for child in node:
                    visit(child)
            elif isinstance(node, dict):
                result.append(node)
                for child in node.values():
                    visit(child)

        visit(value)
        return result

    @staticmethod
    def _parse_time(value: Any) -> datetime | None:
        if not value:
            return None
        text = str(value).strip()
        for candidate in (
            text,
            text.replace("Z", "+00:00"),
        ):
            try:
                parsed = datetime.fromisoformat(candidate)
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=UTC)
                return parsed.astimezone(UTC)
            except ValueError:
                continue
        return None

    @classmethod
    def _normalize(
        cls,
        row: dict[str, Any],
        detail_payload: Any,
        destination_lat: float,
        destination_lon: float,
        radius_m: int,
    ) -> dict[str, Any] | None:
        detail = cls._detail_record(detail_payload)
        source = detail or row
        coordinates = cls._coordinates(source) or cls._coordinates(row)
        if coordinates is None:
            return None
        lat, lon = coordinates

        distance = round(haversine_m(destination_lat, destination_lon, lat, lon))
        if distance > radius_m:
            return None

        parking_id = str(row.get("id") or source.get("id") or "")
        if not parking_id:
            return None

        name = str(
            source.get("name")
            or source.get("nickName")
            or row.get("name")
            or row.get("nickName")
            or "Parking"
        )

        result: dict[str, Any] = {
            "provider": "madrid_open_data",
            "provider_name": PROVIDER_NAME,
            "provider_id": f"madrid:{parking_id}",
            "provider_url": PROVIDER_URL,
            "name": name,
            "distance_m": distance,
            "latitude": round(lat, 7),
            "longitude": round(lon, 7),
            "category": "other",
            "parking_type": str(
                source.get("type") or row.get("type") or "rotational"
            ).casefold(),
            "fee": "unknown",
            "access": "unknown",
            "has_realtime_data": False,
            "navigation_url": navigation_url(lat, lon),
            "geo_uri": geo_uri(lat, lon),
        }

        address = source.get("address") or row.get("address")
        if address:
            result["address"] = str(address)

        detail_dicts = cls._iter_dicts(detail or {})
        features = [
            item
            for item in detail_dicts
            if "content" in item
            and (
                "nameField" in item
                or "nameFieldTranslated" in item
            )
        ]
        occupations = [
            item
            for item in detail_dicts
            if "free" in item and ("moment" in item or "renewalIndex" in item)
        ]
        rates = [
            item
            for item in detail_dicts
            if "rate" in item
            and (
                "minutesStayEnd" in item
                or "minutesStayInitiation" in item
                or "description" in item
            )
        ]

        for feature in features:
            feature_name = str(feature.get("name") or "").casefold()
            field_name = str(feature.get("nameField") or "").casefold()
            if (
                str(feature.get("code") or "") == "001"
                or (
                    "tipo plaza" in field_name
                    and feature_name in {"total", "totales"}
                )
            ):
                try:
                    result["capacity"] = int(
                        str(feature.get("content") or "").replace(".", "")
                    )
                    break
                except ValueError:
                    pass

        occupation = None
        for item in occupations:
            if (
                str(item.get("code") or "") == "001"
                or str(item.get("name") or "").casefold()
                in {"total", "totales"}
            ):
                occupation = item
                break
        if occupation is None and len(occupations) == 1:
            occupation = occupations[0]

        if occupation is not None:
            try:
                free = int(occupation["free"])
            except (TypeError, ValueError):
                free = -1
            moment = cls._parse_time(occupation.get("moment"))
            fresh = False
            if moment is not None:
                age = (datetime.now(UTC) - moment).total_seconds()
                fresh = -300 <= age <= _LIVE_MAX_AGE_SECONDS
            if free >= 0 and fresh:
                result["free_capacity"] = free
                result["has_realtime_data"] = True
            if moment is not None:
                result["realtime_updated_at"] = moment.isoformat()

        if rates:
            result["fee"] = "yes"
            result["category"] = "paid"
            result["pricing"] = {
                "tariffs": [
                    {
                        key: item[key]
                        for key in (
                            "description",
                            "minutesStayInitiation",
                            "minutesStayEnd",
                            "periodPricing",
                            "rate",
                            "scheduleInitial",
                            "scheduleEnd",
                        )
                        if item.get(key) not in (None, "")
                    }
                    for item in rates[:12]
                ]
            }

        return result
