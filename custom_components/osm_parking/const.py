from __future__ import annotations

DOMAIN = "osm_parking"
PLATFORMS = ["sensor"]

CONF_DESTINATION_ENTITY = "destination_entity"
CONF_RADIUS_M = "radius_m"
CONF_INCLUDE_RESTRICTED = "include_restricted"
CONF_MAX_RESULTS = "max_results"

CONF_GOLEMIO_ENABLED = "golemio_enabled"
CONF_GOLEMIO_API_KEY = "golemio_api_key"
CONF_TFNSW_ENABLED = "tfnsw_enabled"
CONF_TFNSW_API_KEY = "tfnsw_api_key"
CONF_TDX_ENABLED = "tdx_enabled"
CONF_TDX_CLIENT_ID = "tdx_client_id"
CONF_TDX_CLIENT_SECRET = "tdx_client_secret"

PROVIDER_SECRET_KEYS = (
    CONF_GOLEMIO_API_KEY,
    CONF_TFNSW_API_KEY,
    CONF_TDX_CLIENT_ID,
    CONF_TDX_CLIENT_SECRET,
)

DEFAULT_RADIUS_M = 1500
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
