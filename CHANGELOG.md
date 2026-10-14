# Changelog

## v1.8.0

### Finland and London official-source expansion

- Added **Fintraffic LIIPI** as a key-free national Finnish Park & Ride provider. OSM Parking caches the healthy full official GeoJSON inventory and locally applies the exact radius instead of depending on Fintraffic's currently broken spatial-query path.
- Fintraffic CAR utilization includes a producer timestamp, exact free/capacity counts and `openNow`; fresh plausible values are classified as verified **live**. Static facility/capacity data remains available when the utilization sub-feed fails.
- Added **Transport for London Car Parks** from the official Unified API `Place/Type/CarPark` inventory: WGS84 location, capacity, accessible bays, opening information and daily tariffs.
- TfL occupancy enrichment is deliberately optional/fault-isolated. The occupancy endpoints returned HTTP 500 during development probes; static Places remain usable and the sub-feed retries every five minutes.
- When TfL occupancy recovers, internally consistent bay totals are classified as **reported**, never timestamp-verified live, because the occupancy response contains no publisher observation timestamp.
- Added provider-derived offline applicability polygons generated from the official 256 Fintraffic car-facility geometries and 58 TfL CarPark Places, each buffered by exactly 10 km in an appropriate local CRS. No hand-written country/city rectangle is required at runtime.
- Direct TfL data outranks an equal-quality ParkenDD duplicate through the existing source-quality precedence; independent sources remain complementary.

### Deferred after live probes

- **Norway Parkeringsregisteret:** the official catalogue still advertises a public register, but the published legacy API root and likely collection paths all returned HTTP 404. No broken provider is shipped.
- **Seoul Open Data:** the real-time `GetParkingInfo` sample returned current capacity/parked count, producer update time and freshness status, but the official API-key URL is plaintext HTTP on port 8088 and the HTTPS form failed. OSM Parking will not send a user's API key over unencrypted transport.

### Verified external schemas

Development probes on 14 October 2026 observed:
- Fintraffic full JSON + GeoJSON: HTTP 200, 784 facilities, 256 with positive CAR capacity; utilization feed HTTP 200 with timestamped current rows. The separate geometry search endpoint returned upstream HTTP 500/PostGIS class error.
- TfL Place/Type/CarPark: HTTP 200, 58 official Places; global and single-car-park occupancy requests returned HTTP 500 at that time.
- Seoul GetParkingInfo sample: HTTP 200 with 122 total city-car-park records and producer timestamp fields; HTTPS:8088 failed.
- Norway legacy parking-register endpoints: HTTP 404.

### Compatibility

No config migration or new credentials are required. Existing providers, response action, authoritative coverage engine, queried/contributing/winning source reporting and dashboard card behavior remain unchanged.

## v1.7.0

### Luxembourg and Swiss official-source expansion

- Added **Ville de Luxembourg** official parking JSON feed. Fresh open/non-faulted facilities expose verified live free spaces from the feed's shared publisher timestamp; stale/faulted facilities remain static only.
- Added **CFL Luxembourg Park & Ride** list/details APIs. WGS84 locations, total/PMR/EV capacity and exact free-space counts are supported. Because the JSON details endpoint has no producer measurement timestamp, availability is classified as **reported**, never verified live.
- Added **Kanton Basel-Stadt dataset 100088** as a direct official minute-updated source with fresh publisher timestamp, free/total spaces, status, address and coordinates.
- Added **Stadt Zürich PLS** direct integration: official RSS free-space/status/timestamp data is joined by PLS pid to the city's official WFS `poi_parkhaus_view` layer for WGS84 position, capacity, address and accessible/EV capacity.
- Zürich keeps static WFS garages when the RSS feed fails; one failed CFL detail request keeps the list-level static P+R site.
- Direct Basel/Zürich authority data outranks an equal-quality ParkenDD duplicate through the existing source-quality ranking; ParkenDD remains complementary/fallback coverage rather than being disabled.
- Added 22 offline contracts covering freshness, faults, impossible counts, RSS parsing, WFS/RSS joins, fallback behavior and direct-source deduplication.

### Verified external schemas

Development probes on 14 October 2026 observed:
- Luxembourg City: HTTP 200 JSON, `last_build_date` + keyed `parking` map with total/current free, fault/open/full flags, coordinates, P+R, accessibility, EV, tariffs and opening data.
- CFL: HTTP 200 list/details JSON with WGS84, capacity and current total/PMR/EV free spaces; no producer timestamp in details.
- Basel: HTTP 200 Opendatasoft v2.1, 16/16 records with minute-fresh `published` timestamps.
- Zürich: HTTP 200 RSS with 37 timestamped items; official WFS exposes `poi_parkhaus_view` with 136 geocoded public garages.

### Compatibility

No configuration migration is required. Existing ParkenDD/ParkAPI providers, authoritative RDW coverage, coordinate response action, provider-stage reporting, map icons and dashboard behavior remain unchanged.

## v1.6.0

### Authoritative provider coverage

- Added a reusable offline GeoJSON coverage engine with cached Polygon/MultiPolygon point-in-polygon evaluation and provenance metadata.
- Replaced the hand-shaped Netherlands RDW coverage bands with a geometry derived directly from the official Kadaster/PDOK **BRK Bestuurlijke Gebieden – Landgebied** source.
- The development generator transforms the official boundary to EPSG:28992, applies a true 10 km buffer matching the integration's maximum search radius, topology-preserving simplifies it, then ships the WGS84 result.
- Runtime RDW selection performs **no network call** to determine country coverage. The generated exact geometry (~76 KB) and buffered runtime geometry (~16 KB) are bundled with the component.
- Coverage provenance (Kadaster/PDOK, BRK Landgebied, CC BY 4.0) is exposed in provider status.
- Added geometry parser/provenance/border regression tests. Dutch cities remain inside, Aachen is included only by the 10 km search buffer, and Cologne/Düsseldorf/Dortmund/Frankfurt remain outside.

### Provider market research

- Added a new free/open, free-with-key and commercial provider matrix.
- Highest-priority free/open candidates: Luxembourg City + CFL P+R, Basel direct live feed, Zürich PLS direct live feed, Fintraffic LIIPI, Norway Parkeringsregisteret, Seoul OpenAPI and TfL occupancy.
- Commercial/partner candidates documented separately: Parkopedia, INRIX Parking Services, TomTom Parking API, ParkBee, ParkWhiz, Passport and EasyPark.
- Documented duplicate policy: authoritative direct feeds can outrank aggregator duplicates when fresher; aggregators remain complementary/fallback sources; equivalent endpoints of the same dataset are fallbacks, not separate providers.

### Compatibility

No configuration migration is required. The coordinate response action, queried/contributing/winning provider reporting, deduplication, credentials and dashboard behavior remain unchanged.

## v1.5.1

### Provider selection transparency

- Split provider diagnostics into **queried**, **contributing** and **winning** stages.
- `providers_queried` now lists only sources that were actually contacted after geographic, credential, enablement and retry-cooldown checks.
- `providers_contributing` lists successful sources that returned at least one usable parking facility or zone before deduplication and result limits.
- `winning_sources` lists providers whose record won deduplication and survives in the final parking list.
- Kept `providers_used` for backward compatibility, but it now aliases `winning_sources` instead of meaning merely “successful request”.
- The `osm_parking.find_parking` action returns all three provider stages as well.

### Netherlands RDW selection

- Replaced the previous broad Netherlands rectangle with several conservative Netherlands-shaped coverage bands plus a small border buffer for searches near the national border.
- Dutch coverage such as Amsterdam, Rotterdam, Maastricht, Groningen and Enschede remains enabled, including a narrow cross-border search margin near Aachen.
- Cologne, Düsseldorf, Dortmund and Frankfurt no longer trigger RDW.
- The RDW API still applies the requested radius to actual returned facilities, so the geofence only controls whether the provider is worth contacting.

### Compatibility

No configuration migration is required. Provider result normalization, source-quality ranking, deduplication, credentials, the coordinate response action and the dashboard UI remain otherwise unchanged.

## v1.5.0

### Coordinate parking response action

- Added **`osm_parking.find_parking`**, a response-only Home Assistant action for searching arbitrary latitude/longitude coordinates and returning a structured `parkings` list.
- Supports optional search radius, parking-type multiselect, maximum results per category, restricted/private parking, and a config-entry selector for provider settings and credentials.
- If exactly one OSM Parking config entry is loaded, the action uses it automatically. Multiple loaded entries require an explicit selection.
- Omitting optional search fields reuses the selected configuration's settings; action overrides are ephemeral and do not modify the config entry.
- Reuses the same provider isolation, source-quality ranking, deduplication, regional fallback and access filtering as the normal sensor.
- Action searches use a separate provider supervisor/backoff path and lock, so they do not mutate the sensor state, polling interval or recovery cycle.
- Partial source failures return healthy parking records together with `partial_data` and `unavailable_sources`. Complete source failure raises a translated Home Assistant error.
- Added action/field/error translations in all supported integration languages and a graphical `services.yaml` action form.
- Added isolated service-action tests plus a real coordinator contract proving coordinate searches leave sensor state unchanged.

### Compatibility

The four-step configuration flow, credentials, automatic Athens GIS handling, type-icon map markers, folded result behavior and dashboard card remain otherwise unchanged. No configuration migration is required.

## v1.4.1

### Parking-type icons

- Replaced visible ordinal numbers on the map and result badges with matching parking-type SVG icons for all seven categories. Unknown types have a safe generic fallback.
- Kept stable facility keys and display indices internally, including distinct facilities sharing the same name and type. Filter/sort changes never match by icon appearance.
- Preserved marker-driven list expansion, highlight and scroll, keyboard activation, reduced motion, map-only popups and camera position.
- Added translated type/name hover and accessibility labels. Unnamed facilities no longer acquire a visible ordinal fallback name.
- Embedded licensed vector glyphs so markers do not wait for remote image, font or lazy-loaded icon requests. Refreshes reuse marker buttons and unchanged icon nodes.
- Added icon/identity unit and real-browser regression coverage. Refreshed the README gallery with sample-data screenshots of the shipped card.

### Compatibility

Provider backends, API credentials, automatic Athens GIS, failure isolation, source-quality deduplication and the four-step setup are unchanged. No configuration migration or new YAML setting is required. Browser tests use the complete card, real MapLibre and local sample data, not the user's live Home Assistant.

## v1.4.0

### Map-first result browsing

- Results start folded on a fresh card load; the map and local filter/sort controls remain visible.
- Clicking or keyboard-activating a parking marker expands the list, highlights the matching stable facility and scrolls it into view. It does not change the map camera or request new data.
- Added a localized Show/Hide results button in all 14 card languages. Ordinary updates preserve expansion without scrolling again; reloading starts folded.
- Preserve explicit map-only mode, list-to-map focus, reduced-motion scrolling, source deduplication and the pending provider-resilience changes below.

### Automatic sources and fault isolation

- Removed the manual Athens GIS switch from setup and options in all 14 languages. Usable official polygons are selected automatically only around Athens, ignoring obsolete manual flags.
- Validate projection, polygon structure, closed rings, finite coordinates, geographic bounds and inventory completeness before accepting GIS data. An unavailable or invalid feed contributes no layer and never implies parking permission or vacancy.
- Isolate optional-provider imports, construction, eligibility checks, fetch deadlines, result parsing and merging. Malformed records do not discard other healthy results.
- Added source-local retry backoff, rate-limit-aware equivalent endpoint fallback and credential-safe diagnostic source status. Failed-source occupancy is never replayed.
- Athens WFS routes and Toulouse Opendatasoft formats are equivalent primary/fallback access, not duplicated providers. Complementary overlapping sources retain their coverage and best-source deduplication.
- Added the Toulouse Metropole BNLS static facility adapter; renewed official-source research for Bordeaux, Galway and Greece.
- Shortened English, Greek and German category-chip labels. Existing categories, restrictions, credentials, four-step setup and card appearance are retained.
- Added fault-injection tests against the actual coordinator, source supervisor, GIS validator and endpoint fallback.

### Testing limits

Public endpoint probes report only the test runner's point-in-time observations, not guaranteed availability from every Home Assistant network. The user's live installation is not modified by release testing.

## v1.3.1

### README screenshot refresh

- Replaced the old SVG dashboard examples with new PNG browser screenshots of the shipped compact parking card.
- Added desktop dark/light views and Greek mobile views, including the expanded parking-type, cost, data-quality, source and distance filters.
- Captures use the actual bundled card and pinned MapLibre with illustrative parking records and a labelled local map fixture. They are not screenshots of a live Home Assistant installation or evidence of current vacancies.
- Added a reproducible screenshot command and source/image fingerprints for future documentation updates.
- Updated the README card example to the current compact map options.

### Compatibility and validation

- Retains the v1.3.0 card behavior, all provider backends, credentials, the four-step setup, source-quality ranking and deduplication. Runtime changes are limited to the release version labels.
- Revalidated Python contracts, JavaScript filter/sort tests and real-browser interactions, themes, mobile layouts and visible map controls before preparing the gallery.
- Existing configuration remains compatible; restart Home Assistant and reload the dashboard after updating.

## v1.3.0

### Card redesign

- Compact 220 px map, expandable on demand, with fit-to-results and light/dark/automatic theme controls. Automatic mode follows Home Assistant's theme; real OpenFreeMap dark vector styling is used instead of color inversion.
- Search and local filters for parking types, cost, data quality, winning source, maximum distance and available spaces supported by live data. Changing presentation does not request parking data or alter backend deduplication.
- Sort by distance, type, name, free-first, available places, data quality or source. Unknown prices/counts are not treated as zero or free. List and marker numbering use the same visible order.
- Refreshed result rows with distance, source provenance, honest live/reported/estimated/predicted/static labels, navigation links and expandable details.
- Browser-local filter and sort preferences are scoped to the Home Assistant user and entity; storage-denied/private browsing works without persistence.
- Preserve map position on periodic updates and filter/sort changes. The fit button recenters explicitly. Parking results and navigation remain usable if map loading fails.
- Keep Athens zone overlays across map theme changes, and clean up observers, markers and WebGL resources on card removal.
- Existing card type, resource URL, data providers and four-step integration configuration remain unchanged. Existing explicit `height` values remain respected; `map_height` takes precedence.

### Validation

- Browser tests exercise desktop/mobile, all 14 languages, live theme changes, search/filter/sort, matching marker numbering, persistence, empty/error states, map failure and reconnects.
- Preview screenshots use labelled sample parking records and a local map fixture, not the user's Home Assistant runtime or actual vacancy readings.

## v1.2.0

### Added

- Replaced the crowded single-page setup and options form with a **four-step wizard**: destination/distance, parking categories, credentialed-provider multiselect, and conditional credential entry.
- Parking categories now have one searchable multiselect rather than seven separate toggles; the existing maximum-per-category, restricted parking, and experimental Athens zone settings remain available in step two.
- Credential-requiring providers can be enabled together with a multiselect in step three; only their relevant API key or client ID/secret fields appear in step four.
- Added 14-language step titles, descriptions, selector option labels and validation errors.
- Added offline wizard-navigation and persistence regression tests covering initial setup, editing, validation, conditional screens, and credential secrecy.

### Changed

- No API credentials screen is shown when zero credential-requiring providers are selected.
- OpenStreetMap and all municipal providers that require no credentials remain fully automatic and are not cluttering the provider selector.
- Previously saved credentials are never prefilled or sent back to the frontend. Leaving a field blank keeps its secret; disabling a provider retains its key for easy later reactivation.
- Stored category booleans, provider-enabled flags, distance, destination and API credential keys remain backward-compatible. Reconfiguration saves once at the end and reloads the integration.
- Compatible source entities are still listed by friendly name, entity ID and coordinates. An unchanged existing source can be edited even while temporarily unavailable; a new source must provide valid coordinates.

### Validation

- All previously implemented data sources, live-vs-reported classification, failure isolation, Athens zone visualization and best-source deduplication stay unchanged.
- Regression tests verify that malformed selections, missing keys and invalid radii cannot silently save a partial configuration.

## v1.1.0

### Added

- **Ville de Paris Open Data / BNLS** parking provider with static WGS84 facility locations, national IDs, fees, accessible/EV capacities and access restrictions.
- **Ayuntamiento de Zaragoza** static parking inventory, using the official documented municipal REST API and WGS84 verification.
- **Singapore URA** optional-access-key provider joining official daily car-park details with 3–5-minute parking availability using stable URA car-park IDs, car-only filtering and SVY21 conversion.
- Translated URA credentials across the 14 supported languages; added offline schema and deduplication tests.
- Extended the source research to Toulouse, Bordeaux and Galway and differentiated their real-time prospects from static data.

### Changed

- Paris and Zaragoza static catalogs cache for 24 hours without triggering successful periodic polling.
- URA daily details and token are cached separately; when facilities are in range, reported counts update every 5 minutes.
- The existing include-restricted-parking setting now filters municipal provider results, not only OpenStreetMap.

### Data integrity

- URA counts without an upstream measurement time remain **reported**; they never outrank fresh publisher-timestamped live values.
- Zaragoza's estimated street-zone occupancy and VINCI map occupancy are not fabricated from static garage records.
- Paris capacity is static metadata, never a live vacancy claim.
- Public-endpoint reachability and URA authentication still require a real Home Assistant runtime test; offline tests do not establish live service availability.

## v1.0.0

### Added

- Official **İstanbul İBB/İSPARK** key-free facility and reported vacancy provider.
- Official **İzmir Municipality/İZUM** key-free facility and reported vacancy provider, including accessible spaces when supplied.
- Optional **City of Athens controlled-parking zones** from municipal GeoServer WFS; default disabled because the public service can fail.
- New data-quality and facility-deduplication engine with source provenance, matching safeguards and stronger-source selection.
- Zone polygons rendered separately from parking markers, with signage cautions and localized labels.
- Expanded offline regression contracts for quality ranking, Turkish API schemas and Greek controlled-zone geometries.
- A worldwide provider candidate research and access/licence matrix.

### Changed

- Fresh publisher-timestamped live counts outrank reported counts without observation time, estimated occupancy, predicted values and static metadata.
- No legacy live claim without a publisher timestamp is displayed as timestamp-verified live.
- Nearby but distinct garages, individual physical bays and street parking are preserved instead of merged by proximity alone.
- Merging retains useful location/price/operator metadata without overwriting the winning free-space measurement.
- Dashboard distinguishes reported counts, actual measurement time and download time.
- A failed refresh clears stale zone polygons, counts and parking suggestions.

### Data integrity

- Impossible/negative/fractional vacancy values and stale timestamps are rejected.
- Zone shapes never enter physical-facility counts and do not imply fees, restrictions or available spots.
- İstanbul, İzmir and Athens runtime municipal service reachability is not guaranteed by offline tests and must be checked on the target Home Assistant installation.

## v0.9.0

### Added

- Added **Métropole Européenne de Lille official WFS** parking availability, including published names, addresses, coordinates, total/free spaces, status and producer timestamp.
- Added **SMMAG / M Mobilités Grenoble** parking provider joining its official geographic catalogue to its independent live availability feed by parking ID. Includes garage, surface and Park & Ride categorization where available.
- Added 17 standalone contract tests exercising both new sources, covering local timestamps, joins, missing data, invalid counts, stale feeds, future timestamps and geographic filtering.

### Changed

- Lille live-source refresh is every 5 minutes when nearby facilities are present. Grenoble is every 2 minutes; its mostly static catalog is cached for 6 hours.
- All existing 0.8.0 providers, dashboard behavior, per-category options and regional failure isolation remain in place.

### Data integrity

- Lille open status must be explicitly recognized; undocumented/closed statuses are not silently treated as free public parking. Stale data older than 15 minutes cannot be reported live.
- Grenoble vacancy requires a matching official catalog ID and a producer Unix timestamp no older than 10 minutes. Missing/invalid readings never become zero vacancy.
- Live counts must be nonnegative integers and cannot exceed known published capacity. Invalid coordinates and out-of-radius sites are dropped.
- Realtime source assertions are validated by unit tests; live API reachability still depends on the providers' public services at runtime.

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
