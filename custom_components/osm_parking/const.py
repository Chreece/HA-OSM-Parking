from __future__ import annotations

DOMAIN = "osm_parking"
PLATFORMS = ["sensor"]

CONF_DESTINATION_ENTITY = "destination_entity"
CONF_RADIUS_M = "radius_m"
CONF_REFRESH_MINUTES = "refresh_minutes"
CONF_INCLUDE_RESTRICTED = "include_restricted"
CONF_MAX_RESULTS = "max_results"

DEFAULT_RADIUS_M = 1500
DEFAULT_REFRESH_MINUTES = 15
DEFAULT_INCLUDE_RESTRICTED = False
DEFAULT_MAX_PER_CATEGORY = 5

CATEGORY_PAID = "paid"
CATEGORY_OPEN = "open"
CATEGORY_STREET = "street"
CATEGORY_UNDERGROUND = "underground"
CATEGORY_MULTI_STOREY = "multi_storey"
CATEGORY_PARK_AND_RIDE = "park_and_ride"
CATEGORY_OTHER = "other"

CATEGORIES = (
    CATEGORY_PAID,
    CATEGORY_OPEN,
    CATEGORY_STREET,
    CATEGORY_UNDERGROUND,
    CATEGORY_MULTI_STOREY,
    CATEGORY_PARK_AND_RIDE,
    CATEGORY_OTHER,
)

CATEGORY_LABELS = {
    CATEGORY_PAID: "Paid parking",
    CATEGORY_OPEN: "Open / surface parking",
    CATEGORY_STREET: "Street parking",
    CATEGORY_UNDERGROUND: "Underground parking",
    CATEGORY_MULTI_STOREY: "Multi-storey parking",
    CATEGORY_PARK_AND_RIDE: "Park & ride",
    CATEGORY_OTHER: "Other parking",
}


def enabled_key(category: str) -> str:
    """Return the config key controlling a category."""
    return f"category_{category}_enabled"


def max_key(category: str) -> str:
    """Return the legacy per-category limit key."""
    return f"category_{category}_max_results"
