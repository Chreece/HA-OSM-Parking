"""Pure helpers for OSM Parking's four-step configuration wizard.

Keep existing category toggles, provider flags and secrets as the persisted
schema. Multiselect controls are wizard-only and never stored as options.
"""

from __future__ import annotations

from collections.abc import Mapping
import math
from typing import Any

from .const import (
    CATEGORIES,
    CONF_GOLEMIO_API_KEY,
    CONF_GOLEMIO_ENABLED,
    CONF_TDX_CLIENT_ID,
    CONF_TDX_CLIENT_SECRET,
    CONF_TDX_ENABLED,
    CONF_TFNSW_API_KEY,
    CONF_TFNSW_ENABLED,
    CONF_URA_ACCESS_KEY,
    CONF_URA_ENABLED,
    enabled_key,
)

CONF_PARKING_TYPES = "parking_types"
CONF_CREDENTIAL_PROVIDERS = "credential_providers"

CREDENTIAL_PROVIDERS: dict[str, tuple[str, tuple[str, ...]]] = {
    "golemio": (CONF_GOLEMIO_ENABLED, (CONF_GOLEMIO_API_KEY,)),
    "tfnsw": (CONF_TFNSW_ENABLED, (CONF_TFNSW_API_KEY,)),
    "tdx": (CONF_TDX_ENABLED, (CONF_TDX_CLIENT_ID, CONF_TDX_CLIENT_SECRET)),
    "ura": (CONF_URA_ENABLED, (CONF_URA_ACCESS_KEY,)),
}

PROVIDER_NAMES: dict[str, str] = {
    "golemio": "Prague Golemio",
    "tfnsw": "Transport for NSW",
    "tdx": "Taiwan TDX",
    "ura": "Singapore URA",
}


def selected_categories(settings: Mapping[str, Any]) -> list[str]:
    """Read existing per-category booleans with their historic defaults."""
    return [
        category for category in CATEGORIES
        if bool(settings.get(enabled_key(category), True))
    ]


def selected_credential_providers(settings: Mapping[str, Any]) -> list[str]:
    """Preselect working, previously enabled key-protected providers only.

    Previous options flows defaulted every provider to 'enabled', while
    silently skipping those without credentials. Do not preselect empty
    configurations, which would incorrectly force users to enter keys.
    """
    return [
        name
        for name, (enabled_flag, keys) in CREDENTIAL_PROVIDERS.items()
        if bool(settings.get(enabled_flag, True))
        and any(str(settings.get(key) or "").strip() for key in keys)
    ]


def valid_multiselect(
    values: Any, allowed: tuple[str, ...], *, allow_empty: bool = True
) -> bool:
    """Reject forged, duplicate or malformed selections."""
    if not isinstance(values, list):
        return False
    if not allow_empty and not values:
        return False
    if any(not isinstance(value, str) for value in values):
        return False
    return len(values) == len(set(values)) and set(values).issubset(allowed)


def category_flags(values: list[str]) -> dict[str, bool]:
    """Persist a multi-selection using the original integration settings."""
    return {enabled_key(category): category in values for category in CATEGORIES}


def credential_provider_flags(values: list[str]) -> dict[str, bool]:
    """Disable unselected providers without deleting their saved credentials."""
    return {
        enabled_flag: name in values
        for name, (enabled_flag, _keys) in CREDENTIAL_PROVIDERS.items()
    }


def credential_keys(values: list[str]) -> tuple[str, ...]:
    """Only fields belonging to providers selected in step three."""
    return tuple(
        key
        for name in values
        for key in CREDENTIAL_PROVIDERS[name][1]
    )


def prepared_credentials(
    previous: Mapping[str, Any],
    submitted: Mapping[str, Any],
    selected: list[str],
) -> tuple[dict[str, str], list[str]]:
    """Validate selected keys atomically; blank keeps a saved secret.

    Credentials of deselected providers are ignored and left stored for
    future reactivation. Never prefill secrets in any UI response.
    """
    changes: dict[str, str] = {}
    missing: list[str] = []
    for key in credential_keys(selected):
        raw = submitted.get(key)
        value = raw.strip() if isinstance(raw, str) else ""
        if value:
            changes[key] = value
        elif not str(previous.get(key) or "").strip():
            missing.append(key)
    return changes, missing


def valid_positive_integer(value: Any, minimum: int, maximum: int) -> bool:
    """Guard against bad values even if a frontend bypasses its selector."""
    if isinstance(value, bool):
        return False
    try:
        number = float(value)
        return (
            math.isfinite(number)
            and number.is_integer()
            and minimum <= number <= maximum
        )
    except (ValueError, TypeError, OverflowError):
        return False
