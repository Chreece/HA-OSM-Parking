# Changelog

## v0.8.0

### Added

- Official **Métropole de Lyon** 2026 OGC API Features provider: live vacancy, capacity, coordinates, tariffs, operator and accessibility metadata.
- Two independent, key-free **Nantes Naolib** providers: public garages and Park & Ride sites.
- Offline provider contract tests for valid/stale statuses, impossible counts, coordinates, provider separation and absence of invented live data.

### Changed

- Lyon and Nantes feeds refresh about every 2 minutes when facilities are in range; OSM/static-only locations still do not poll.
- Development-branch pushes no longer trigger validation Actions. Pull requests and main updates remain validated.

### Data integrity

- Lyon availability must be fresh within 15 minutes and cannot exceed published capacity.
- Nantes Naolib status 0 is invalid, 1 is closed, 2 is for subscribers only, and 5 is publicly open. Live vacancy requires the official timestamp to be fresh within 15 minutes.
- Nantes published capacity refers to short-stay users rather than every bay including season-ticket subscribers.
- Invalid coordinates or negative/inconsistent counts never become parking suggestions.

## v0.7.0

### Added

- Added **Eurométropole de Strasbourg Open Data** realtime parking occupancy. The official feed publishes total/free spaces, operating state and coordinates and is refreshed every 3 minutes.
- Added **Montpellier Méditerranée Métropole NGSI-LD OffStreetParking** using the municipality's current 2026 API portal. The provider reads standardized location, name, layout, total spaces, available spaces, opening status, address and observed timestamps.
- Added **Ayuntamiento de Málaga Open Data** municipal parking occupancy by joining the official minute-updated occupancy CSV with its official parking catalog for IDs, names, addresses and coordinates.
- Málaga live rows that do not have an official catalog coordinate are intentionally skipped rather than assigned guessed locations.

### Changed

- Strasbourg live parking requests refresh every 3 minutes while current availability is present.
- Montpellier live parking requests refresh every 5 minutes and availability is only treated as realtime while the NGSI-LD `observedAt` timestamp is fresh.
- Málaga municipal occupancy refreshes every 60 seconds while matching catalogued parking is available.
- All three providers are automatic and require no API key.
- Provider failures remain isolated: successful OSM or other provider results stay visible while a failed regional source is retried.

### Data integrity

- Strasbourg status code `0` is treated as realtime unavailable rather than as zero free spaces.
- Montpellier stale `availableSpotNumber` values are not exposed as current live vacancy.
- Málaga only reports the published `libres` count; total capacity is not invented when it is absent from the official live/catalog feeds.


## v0.6.0

### Added

- Added **Open Transport Data Switzerland / SBB P+Rail Bike-and-Car-Parking** as an automatic key-free provider for Switzerland and nearby cross-border facilities.
- Swiss car-parking records include facility/operator/address metadata and preserve the source's current **estimated occupancy** separately from exact realtime vacancy.
- The bundled card now displays localized estimated occupancy percentages and LOW/MEDIUM/HIGH occupancy levels without presenting estimates as exact free-space counts.
- Added **Stadt St.Gallen Open Data** for minute-updated parking guidance, including total/free/occupied spaces, EV spaces, accessible spaces, opening state and update timestamps.

### Changed

- Provider merging now ranks source quality: exact realtime data > estimated occupancy > static provider data > OSM baseline metadata.
- A later static provider can no longer erase a stronger realtime availability state from an already-merged parking facility.
- Estimated occupancy can enrich a merged facility without replacing exact realtime free-space data.
- Swiss estimated-occupancy results refresh every 30 minutes while estimates are present; St.Gallen live results refresh every 60 seconds.
- Static/OSM-only results remain event-driven and do not poll after a successful refresh.

### Data integrity

- St.Gallen vacancy values are only exposed as realtime when their upstream timestamp is sufficiently fresh; stale values remain usable only as non-live facility metadata.
- Swiss occupancy remains explicitly marked as **estimated** because the upstream feed publishes an estimated occupancy ratio rather than exact free spaces.


## v0.5.0

### Added

- Expanded OSM Parking into a broader worldwide multi-provider integration while retaining OpenStreetMap / Overpass as the universal baseline.
- Added **Netherlands RDW Open Data** for national public garages and Park & Ride locations.
- Added **Stad Gent Open Data** for realtime public parking occupancy in Ghent.
- Added **ParkenDD / ParkAPI** for key-free live parking feeds across supported European cities including Germany, Denmark and Switzerland.
- Added **Helsinki Parkkihubi** parking-area data and current area statistics, including privacy-safe handling of suppressed low occupancy counts.
- Added **Dublin City Council Open Data** by combining the live CPDATA feed with official parking coordinates.
- Added **Brussels Open Data** public parking facilities.
- Added **City of Melbourne Parking Bay Sensors** for individual near-realtime on-street bay availability with stale-sensor protection.
- Added **Madrid Open Data Parking** for official rotational car parks, total capacity, tariffs and realtime free-space counts with timestamp freshness checks.
- Added optional **Prague Golemio Parking v3** support with a user's free Golemio API key.
- Added optional **Transport for NSW Car Park API** support with a user's TfNSW Open Data API key.
- Added optional **Taiwan TDX Parking** support with TDX Client ID / Client Secret and OAuth token caching.
- Added optional provider credential fields to the Home Assistant Options flow. Credentials are never required for the automatic public providers.
- Added credential redaction from Home Assistant diagnostics.

### Changed

- Provider implementations now receive optional configuration independently, allowing credentialed providers to coexist with key-free providers without affecting users who do not configure them.
- Providers requiring credentials are silently skipped until all required credentials are present and the destination is inside their geographic coverage.
- Realtime polling remains provider-driven: only active live feeds trigger successful periodic refreshes; static/OSM-only locations remain event-driven.
- Individual parking-bay providers can opt out of geographic deduplication, preventing adjacent physical bays from being collapsed into one result.
- Partial provider outages do not discard successful results from other sources and remain eligible for automatic recovery retries.
- Validation no longer runs on every development push; direct-main development is validated once at the end of a batch, while pull requests still validate automatically.

### Provider notes

- **No credentials required:** OSM/Overpass, ParkAPI/MobiData BW, ParkenDD, Netherlands RDW, Ghent, Brussels, Dublin, Helsinki, Singapore HDB, Hong Kong DATA.GOV.HK, Melbourne and Madrid.
- **Optional free developer credentials:** Prague Golemio, Transport for NSW and Taiwan TDX.
- ParkOut and AthensWay are still intentionally not scraped: no stable documented public third-party API has been identified, so they are not treated as supported providers.


## v0.4.0

### Added

- Introduced an extensible multi-provider parking architecture while keeping OpenStreetMap / Overpass as the worldwide baseline.
- Added **ParkAPI / MobiData BW** support for nearby car parking in Central Europe, including realtime capacity, free spaces, opening status and provider metadata when supplied.
- Added **Hong Kong DATA.GOV.HK** support using the official one-stop car park information and realtime vacancy API.
- Added **Singapore HDB / data.gov.sg** support by combining the HDB Carpark Information dataset with the official realtime Carpark Availability API.
- Added built-in SVY21 (EPSG:3414) to WGS84 conversion for Singapore HDB parking coordinates.
- Added normalized provider metadata to parking suggestions: provider, provider ID, realtime availability, capacity, free spaces, update timestamp and provider URL.
- The Lovelace card now shows realtime free/total spaces, source/provider information and realtime update timestamps.

### Changed

- Supplemental provider requests are automatically selected by destination geography; irrelevant providers are not queried.
- Results from OpenStreetMap and supplemental providers are merged conservatively by proximity and name similarity to avoid duplicate parking facilities.
- Realtime/provider metadata is merged into the corresponding OSM parking result when both sources describe the same facility.
- OpenStreetMap failure no longer necessarily makes the whole integration fail: if a regional provider still returns usable parking, OSM Parking shows that partial data and retries missing sources automatically.
- Partial provider failures now use temporary 5-minute recovery polling and stop once all non-live providers recover.
- Live data polling is enabled only while realtime provider data is active: Singapore uses a 60-second feed cadence, while ParkAPI and Hong Kong are refreshed every 5 minutes.
- Static/OSM-only destinations remain event-driven with no successful background polling.

### Notes

- OpenStreetMap remains the global fallback and primary worldwide source.
- ParkAPI/MobiData BW, Singapore data.gov.sg and Hong Kong DATA.GOV.HK are public/open data sources and require no user API credentials for the implemented access paths.
- More providers can now be added behind the normalized provider interface without changing the card data model.


## v0.3.11

### Fixed

- The OSM Parking sensor now stays available as a status sensor when a refresh fails, exposing `state: error` plus structured failure details instead of losing all diagnostic attributes behind Home Assistant's generic `unavailable` state.
- The Lovelace card now explains why parking data cannot render and whether the user can do anything about it.
- Destination-source failures show actionable guidance, the expected coordinate attributes, an **Open source entity** action, **Retry now**, and integration settings.
- Public Overpass outages are identified as external service failures, show the active automatic retry interval, and offer **Retry now** without implying the user must fix the external service.
- Successful searches with zero results are shown as an informational state with suggestions to increase the radius or enable more categories.
- Generic/query-rejected failures expose collapsible technical details and a direct issue-report action.
- A failed MapLibre CDN load no longer poisons the browser session. The loader clears the failed shared promise, retries from a second CDN, and lets the user retry the map without a hard page refresh.

### Changed

- Failure and recovery guidance is localized across all supported card languages.
- Stale parking suggestions from the last successful update are no longer presented as current data after a failed refresh.


## v0.3.10

### Changed

- Localized the bundled Lovelace card to the same 14 languages as the setup/options UI.
- Card titles, suggestion counts, waiting/empty states, destination labels, distance/type/price/access labels, navigation text, free/paid status and parking category names now follow the Home Assistant UI language.
- Unsupported Home Assistant languages fall back to English automatically.


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
