# Changelog

## v0.3.9

### Changed

- Added Simplified Chinese and Japanese translations, bringing the setup/options UI to 14 languages.
- Existing configured destinations can now be preserved from the Options screen even if that source is temporarily unavailable at the moment the form is opened.
- New configurations remain restricted to destination entities that currently expose valid supported coordinates.


## v0.3.8

### Changed

- The destination selector now scans Home Assistant and lists only entities that currently expose valid coordinates.
- Destination options show the friendly name, entity ID and current latitude/longitude to make the correct source obvious.
- Removed the project-specific `sensor.termine_geocode` default from the public config flow.
- The setup and options screens now explain the supported entity format: `latitude` + `longitude`, or `lat` + `lon`/`lng`.
- Invalid or currently unusable destination entities are rejected directly in the form with a translated validation error.
- Added translations for Greek, German, Spanish, French, Italian, Dutch, Polish, Portuguese, Brazilian Portuguese, Russian and Turkish.


## v0.3.7

### Fixed

- Fixed intermittent Lovelace **Configuration error** screens that required a hard browser refresh.
- The bundled dashboard card now registers through Home Assistant's Lovelace resource collection in storage mode instead of relying on an un-awaited frontend extra-module import.
- The card resource URL is cache-busted by both release version and Home Assistant process, allowing the browser to recover from a failed/stale ES-module import after a backend restart.
- The static card route is registered before the Lovelace resource is created or updated.
- YAML resource mode retains the frontend extra-module loader as a compatibility fallback.

### Changed

- Added `lovelace` as an explicit integration dependency so resource registration happens only after Lovelace is ready.


## v0.3.6

### Changed

- Normal operation remains fully event-driven: startup and meaningful destination changes trigger refreshes, with no background polling after success.
- If a real Overpass refresh fails, OSM Parking now automatically enters temporary failure polling.
- The first automatic retry happens after 1 minute; continued failures retry every 5 minutes.
- Any successful refresh immediately disables failure polling.
- A meaningful destination change cancels the previous retry cycle and performs a fresh request for the new destination.

### Fixed

- A temporary Overpass outage during Home Assistant startup no longer aborts the OSM Parking config entry setup.
- The sensor can remain loaded while Overpass is unavailable and recover automatically as soon as a retry succeeds.


## v0.3.5

### Fixed

- Fixed the remaining Home Assistant event-loop `import_module` warning.
- Removed a stale `CONF_REFRESH_MINUTES` import left behind after periodic polling was removed in v0.3.3.
- The stale import caused executor loading to raise `ImportError`, which made Home Assistant fall back to importing OSM Parking on the event loop.
- Legacy `refresh_minutes` migration now uses the literal legacy key without reintroducing the removed runtime setting.

### Validation

- Added a CI contract check that verifies every symbol imported from `const.py` actually exists, preventing this exact regression from passing validation again.


## v0.3.4

### Fixed

- Added real per-version release notes to GitHub releases so HACS / Home Assistant update information can show the actual changelog.
- Explicitly enable Home Assistant's import executor for the integration.
- Removed the synchronous frontend-file existence check from async setup to avoid filesystem I/O on the Home Assistant event loop.

### Changed

- Release publishing now extracts the matching version section directly from `CHANGELOG.md` and uses it as the GitHub release body.


## v0.3.3

### Changed

- Removed periodic Overpass polling entirely.
- Parking is now fetched once on Home Assistant/integration startup and again only when the configured destination meaningfully changes.
- Unrelated attribute updates on the destination entity no longer trigger an Overpass request.
- Removed the refresh-interval option from setup/options.
- Existing config entries are migrated automatically and the legacy refresh setting is discarded.


## v0.3.2

### Fixed

- Improved resilience when public Overpass instances return transient HTTP 429/500/502/503/504 errors.
- Retries the public endpoint pool once after a short delay instead of failing after a single pass.
- Remembers the last successful Overpass endpoint and tries it first on the next refresh.
- Uses shorter per-request and server-side query timeouts so an overloaded endpoint cannot block the entire refresh for as long.
- Non-retryable 4xx query errors now fail immediately with the response detail instead of being mistaken for temporary server outages.
- No stale parking result or alternate destination fallback was introduced.


## v0.3.1

### Changed

- Enforced strict HACS validation with no ignored checks.
- Added a one-click **Open in HACS** badge to the README.
- Added crisp vector desktop and mobile dashboard examples.
- Restored the Ko-fi support banner and replaced the project hero with a vector banner.
- Prepared the repository for submission to the default HACS store.

### Validation

- Hassfest passes.
- All integration-side HACS checks pass; default-store publication additionally requires GitHub repository description and topics metadata.


## v0.3.0

### Added

- Dedicated bundled `custom:osm-parking-map-card`.
- OpenFreeMap + MapLibre map rendering.
- Destination marker and numbered parking markers.
- Parking list with distance, category, access and pricing information.
- Paid, open/surface, street, underground, multi-storey, Park & Ride and other categories.
- One shared maximum-results setting applied independently to every enabled category.
- Local Home Assistant / HACS brand assets.
- Project banner and polished HACS installation documentation.
- Home Assistant diagnostics.
- Greek and English translations.

### Changed

- The OSM Parking coordinator now follows the configured destination entity immediately.
- Destination listeners are registered before the first coordinator refresh, so startup restoration does not break the dependency chain.
- The integration stays loaded in a waiting state until the configured destination has valid coordinates.
- Overpass searches now use a lightweight bounding box and enforce the configured circular radius locally.
- Public Overpass failover now uses multiple current endpoints.
- The obsolete `overpass.kumi.systems` endpoint was replaced by `overpass.private.coffee`.
- Results are capped per category first and globally sorted by distance afterward.

### Fixed

- Destination changes not refreshing the OSM Parking sensor.
- Startup races where the destination entity was temporarily unavailable.
- OSM raster-tile 403 errors in the map card.
- Map markers escaping the map container.
- Incorrect/stale destination labels in the frontend.
- Refresh-interval selector type validation.
- Public Overpass HTTP 500/504 failures now fail over to other instances.

### Notes

Parking and pricing completeness depends on OpenStreetMap tagging and the availability of public Overpass API instances.
