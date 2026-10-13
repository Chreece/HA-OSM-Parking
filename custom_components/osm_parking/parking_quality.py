"""Source-aware parking normalization and conservative, deterministic deduplication.

Live measured counts > reported counts without measurement time > estimated
occupancy > predictions > static. Individual parking bays and distinct nearby
facilities must never collapse just because their coordinates are close.
"""

from __future__ import annotations

from datetime import UTC, datetime
from difflib import SequenceMatcher
import math
import re
import unicodedata
from typing import Any

LIVE_MAX_AGE_SECONDS = 60 * 60
FUTURE_TOLERANCE_SECONDS = 5 * 60

QUALITY_ORDER = {
    "static": 0,
    "predicted": 1,
    "estimated": 2,
    "reported": 3,
    "live": 4,
}

_GARBAGE_NAMES = {
    "parking", "park", "car", "lot", "public", "garage", "garages",
    "parkhaus", "parkplatz", "carpark", "estacionamiento", "estacionamento",
    "aparcamiento", "parc", "stationnement", "otopark", "oto",
    "parkoviště", "parkoviste", "stathmeysi", "πάρκινγκ", "παρκινγκ",
    "στάθμευση", "σταθμευση", "θέσεις", "parkinglot",
}
_GENERIC_TYPES = {"", "unknown", "other", "parking"}
_STREET_TYPES = {"street", "street_side", "on_street", "onstreet", "on_kerb"}
_MEASUREMENT_FIELDS = (
    "free_capacity", "occupied_capacity", "closed_capacity",
    "realtime_updated_at", "opening_status",
)


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


def _timestamp(raw: Any) -> datetime | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        parsed = datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return None
        return parsed.astimezone(UTC)
    except (TypeError, ValueError, OverflowError):
        return None


def _valid_coordinates(item: dict[str, Any]) -> tuple[float, float] | None:
    try:
        lat = float(item["latitude"])
        lon = float(item["longitude"])
        if math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180:
            return lat, lon
    except (KeyError, ValueError, TypeError, OverflowError):
        pass
    return None


def normalize_facility(
    original: dict[str, Any],
    *,
    now: datetime | None = None,
) -> dict[str, Any] | None:
    """Sanitize a provider response and distinguish reported from fresh live."""
    if not isinstance(original, dict):
        return None
    coordinates = _valid_coordinates(original)
    if coordinates is None or original.get("record_type") == "zone":
        return None

    item = dict(original)
    item["latitude"], item["longitude"] = coordinates
    for key in (
        "capacity", "free_capacity", "occupied_capacity",
        "closed_capacity", "accessible_capacity", "accessible_free_capacity",
        "ev_capacity", "ev_free_capacity",
    ):
        if key in item:
            value = _count(item[key])
            if value is None:
                item.pop(key)
            else:
                item[key] = value

    capacity = item.get("capacity")
    free = item.get("free_capacity")
    if capacity is not None and free is not None and free > capacity:
        item.pop("free_capacity", None)
        item.pop("occupied_capacity", None)
        free = None

    kind = str(item.get("availability_kind") or "").strip().lower()
    if kind not in QUALITY_ORDER:
        kind = (
            "live" if item.get("has_realtime_data") else
            "estimated" if (
                item.get("has_estimated_occupancy")
                or item.get("estimated_occupancy_percent") is not None
                or item.get("estimated_occupancy_ratio") is not None
            ) else "static"
        )

    if kind in {"live", "reported"}:
        if free is None:
            kind = "static"
        elif kind == "live" and item.get("realtime_updated_at") is not None:
            stamp = _timestamp(item.get("realtime_updated_at"))
            reference = now or datetime.now(UTC)
            if stamp is None or not (
                -FUTURE_TOLERANCE_SECONDS
                <= (reference - stamp).total_seconds()
                <= LIVE_MAX_AGE_SECONDS
            ):
                kind = "static"
                item["availability_stale"] = True
            else:
                item["availability_freshness"] = "verified"
        elif kind == "live":
            # Some official endpoints document realtime output but omit a
            # producer timestamp; retain the claim but disclose uncertainty.
            item["availability_freshness"] = "unverified"
        else:
            item["availability_freshness"] = "unverified"

        if kind == "static":
            item.pop("free_capacity", None)
            item.pop("occupied_capacity", None)
            item.pop("closed_capacity", None)
            item.pop("realtime_updated_at", None)

    if kind == "estimated":
        try:
            ratio = item.get("estimated_occupancy_ratio")
            pct = item.get("estimated_occupancy_percent")
            valid = (
                ratio is not None and math.isfinite(float(ratio))
                and 0 <= float(ratio) <= 1
            ) or (
                pct is not None and math.isfinite(float(pct))
                and 0 <= float(pct) <= 100
            )
        except (TypeError, ValueError, OverflowError):
            valid = False
        if not valid:
            kind = "static"
            for key in (
                "estimated_occupancy_ratio", "estimated_occupancy_percent",
                "estimated_occupancy_level", "has_estimated_occupancy",
            ):
                item.pop(key, None)

    if kind == "predicted" and not (
        item.get("predicted_occupancy_ratio") is not None
        or item.get("predicted_occupancy_percent") is not None
    ):
        kind = "static"

    item["availability_kind"] = kind
    item["has_realtime_data"] = kind == "live"
    item["has_estimated_occupancy"] = kind == "estimated"
    provider = str(item.get("provider") or "unknown")
    if kind in {"live", "reported", "estimated", "predicted"}:
        item.setdefault("availability_source", provider)
    item.setdefault("metadata_source", provider)
    item["data_sources"] = list(dict.fromkeys(
        str(s) for s in (item.get("data_sources") or [provider]) if s
    ))
    return item


def _fold(text: Any) -> str:
    value = unicodedata.normalize("NFKD", str(text or "").casefold())
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return " ".join(re.findall(r"\w+", value))


def _significant(text: Any) -> str:
    return " ".join(word for word in _fold(text).split() if word not in _GARBAGE_NAMES)


def _facility_kind(item: dict[str, Any]) -> str:
    category = str(item.get("category") or "").casefold()
    form = str(item.get("parking_type") or "").casefold()
    if category == "street" or form in _STREET_TYPES or "street" in form:
        return "street"
    if category == "park_and_ride" or "park_and_ride" in form:
        return "p+r"
    return "facility"


def _distance_m(a: dict[str, Any], b: dict[str, Any]) -> float:
    lat1, lon1 = _valid_coordinates(a) or (float("nan"), float("nan"))
    lat2, lon2 = _valid_coordinates(b) or (float("nan"), float("nan"))
    if not all(map(math.isfinite, (lat1, lon1, lat2, lon2))):
        return math.inf
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi, dlon = p2 - p1, math.radians(lon2 - lon1)
    radius = 6371000.0
    x = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(x), math.sqrt(max(0, 1 - x)))


def likely_same_facility(a: dict[str, Any], b: dict[str, Any]) -> bool:
    """Never collapse individual bays or two differently named close sites."""
    if (
        a.get("merge_with_other_sources") is False
        or b.get("merge_with_other_sources") is False
    ):
        return False

    same_provider = str(a.get("provider") or "") == str(b.get("provider") or "")
    a_id, b_id = a.get("provider_id"), b.get("provider_id")
    distance = _distance_m(a, b)
    if not math.isfinite(distance):
        return False
    if same_provider and a_id and b_id:
        return a_id == b_id and distance <= 150
    if same_provider:
        return False

    a_type, b_type = _facility_kind(a), _facility_kind(b)
    if (a_type == "street") != (b_type == "street"):
        return False

    left, right = _significant(a.get("name")), _significant(b.get("name"))
    if left and right:
        similarity = SequenceMatcher(None, left, right).ratio()
        if left == right and distance <= 65:
            return True
        return distance <= 35 and similarity >= 0.75
    # Generic/no names: coincidence alone is not enough except essentially
    # identical points, where an OSM node often duplicates a municipal point.
    return distance <= (6 if left or right else 3)


def _source_priority(item: dict[str, Any]) -> int:
    provider = str(item.get("provider") or "").casefold()
    if provider in {"osm", "openstreetmap", ""}:
        return 10
    if provider in {"parkapi", "parkendd"}:
        return 30
    return 50


def _score(item: dict[str, Any]) -> tuple[int, int, float, int, int, str]:
    kind = str(item.get("availability_kind") or "static")
    stamp = _timestamp(item.get("realtime_updated_at"))
    priority = _source_priority(item)
    return (
        QUALITY_ORDER.get(kind, 0),
        int(stamp is not None),
        stamp.timestamp() if stamp is not None else 0.0,
        priority,
        sum(bool(item.get(k)) for k in ("address", "operator", "price", "opening_hours")),
        str(item.get("provider") or ""),
    )


def _merge_pair(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    best, other = (a, b) if _score(a) >= _score(b) else (b, a)
    output = dict(best)
    for key in (
        "osm_url", "osm_id", "osm_type", "navigation_url", "geo_uri",
        "operator", "address", "opening_hours", "price", "pricing",
        "maxstay", "accessible_capacity", "accessible_free_capacity",
        "ev_capacity", "ev_free_capacity", "provider_url",
    ):
        if output.get(key) in (None, "", "unknown") and other.get(key) not in (None, "", "unknown"):
            output[key] = other[key]

    best_free = output.get("free_capacity")
    if output.get("capacity") is None and other.get("capacity") is not None:
        other_capacity = other["capacity"]
        if best_free is None or other_capacity >= best_free:
            output["capacity"] = other_capacity

    # If the winner has only a generic category, retain a specific category
    # from the other source. Paid remains an OSM filter category except for P+R.
    if (
        output.get("category") in (None, "other", "paid")
        and other.get("category") == "park_and_ride"
    ):
        output["category"] = "park_and_ride"
    elif output.get("category") in (None, "other") and other.get("category") not in (None, "other"):
        output["category"] = other["category"]

    if output.get("fee") in (None, "", "unknown") and other.get("fee") in ("yes", "no"):
        output["fee"] = other["fee"]

    # Never mix a weaker record's live counters, measured timestamp or status
    # into the chosen availability source.
    if output.get("availability_kind") == "estimated":
        for key in (
            "estimated_occupancy_ratio", "estimated_occupancy_percent",
            "estimated_occupancy_level",
        ):
            if output.get(key) is None and other.get(key) is not None:
                output[key] = other[key]
    output["data_sources"] = list(dict.fromkeys(
        [*(a.get("data_sources") or [a.get("provider")]),
         *(b.get("data_sources") or [b.get("provider")])]
    ))
    output["deduplicated_source_count"] = len(output["data_sources"])
    output["metadata_source"] = best.get("metadata_source") or best.get("provider")
    return output


def merge_facilities(
    current: list[dict[str, Any]],
    incoming: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return clean, deduplicated results without mutating upstream records."""
    merged = []
    for original in [*current, *incoming]:
        item = normalize_facility(original)
        if item is None:
            continue
        found = next((index for index, existing in enumerate(merged)
                      if likely_same_facility(existing, item)), None)
        if found is None:
            merged.append(item)
        else:
            merged[found] = _merge_pair(merged[found], item)
    return merged
