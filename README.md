<!-- ko-fi-support -->
<p align="center">
  <a href="https://ko-fi.com/chreece">
    <img src="https://raw.githubusercontent.com/Chreece/pir2ha/main/.github/ko-fi-banner.svg" alt="Support Chreece on Ko-fi" width="600">
  </a>
</p>

<p align="center">
  <img src="https://raw.githubusercontent.com/Chreece/HA-OSM-Parking/main/assets/banner.svg" alt="OSM Parking for Home Assistant" width="100%">
</p>

<p align="center">
  <a href="https://github.com/Chreece/HA-OSM-Parking/actions/workflows/validate.yml"><img alt="HACS + Hassfest" src="https://github.com/Chreece/HA-OSM-Parking/actions/workflows/validate.yml/badge.svg"></a>
  <a href="https://github.com/Chreece/HA-OSM-Parking/releases"><img alt="Latest release" src="https://img.shields.io/github/v/release/Chreece/HA-OSM-Parking?display_name=tag"></a>
  <a href="LICENSE"><img alt="MIT License" src="https://img.shields.io/github/license/Chreece/HA-OSM-Parking"></a>
  <a href="https://my.home-assistant.io/redirect/hacs_repository/?owner=Chreece&repository=HA-OSM-Parking&category=integration"><img alt="Open in HACS" src="https://my.home-assistant.io/badges/hacs_repository.svg"></a>
</p>

# OSM Parking

**OSM Parking** is a Home Assistant custom integration that follows a destination entity and finds nearby parking from OpenStreetMap plus supported public/open parking APIs. OpenStreetMap / Overpass remains the worldwide baseline, while regional providers can add richer metadata and realtime availability. It includes a bundled interactive Lovelace map card.

## Highlights

- Worldwide OpenStreetMap / Overpass baseline plus automatic municipal and national open-data providers.
- Source-quality ranking, deduplication and provider provenance with live, reported, estimated, predicted and static distinctions.
- Automatic, validated Athens municipal controlled-parking zone overlays.
- Live free-space/occupancy data is shown when a supported provider exposes it.
- Zero-key public providers work automatically; Prague, NSW, Taiwan and Singapore URA providers support optional API credentials through a four-step wizard.
- OSM/static operation is event-driven; periodic refresh is enabled only while realtime provider data is active or while a failed source is recovering.
- Handles Home Assistant startup cleanly while the destination entity is still restoring.
- Searches a configurable radius and sorts the final results by distance.
- Categories: paid, open/surface, street, underground, multi-storey, Park & Ride, and other.
- One configurable maximum result count applied independently to each enabled category.
- Optional private/restricted parking.
- Shows capacity, access, opening hours, operator and OSM pricing metadata when available.
- Uses multiple public Overpass instances with failover.
- Uses a bounding-box Overpass query for lower server cost, then enforces the exact circular radius locally.
- Bundled `custom:osm-parking-map-card` using MapLibre + OpenFreeMap.
- Local Home Assistant brand icon included under `custom_components/osm_parking/brand/`.

## Screenshots

The redesigned card keeps the map compact and puts parking results, search, filters and sorting within easy reach.

### Desktop — dark mode

<p align="center">
  <img src="https://raw.githubusercontent.com/Chreece/HA-OSM-Parking/main/assets/screenshots/card-desktop-dark.png" alt="New OSM Parking card in dark mode with compact map, search, sorting and parking result cards — sample data" width="720">
</p>

### Desktop — light mode

<p align="center">
  <img src="https://raw.githubusercontent.com/Chreece/HA-OSM-Parking/main/assets/screenshots/card-desktop-light.png" alt="New OSM Parking card in light mode with the same compact map and result layout — sample data" width="720">
</p>

### Mobile — Greek interface and expanded filters

<p align="center">
  <img src="https://raw.githubusercontent.com/Chreece/HA-OSM-Parking/main/assets/screenshots/card-mobile-greek-dark.png" alt="Greek mobile parking card with compact dark map, distance sorting, availability labels and navigation — sample data" width="360">
  <img src="https://raw.githubusercontent.com/Chreece/HA-OSM-Parking/main/assets/screenshots/card-mobile-greek-filters.png" alt="Greek mobile card with parking-type, cost, data-quality, source and distance filters expanded — sample data" width="360">
</p>

> Browser renders of the actual shipped card using the standalone preview, sample parking records, preview icons and a local schematic map fixture. These are **not** live Home Assistant or municipal parking readings. In your installation the card uses its configured map style and real integration results.

Screenshots can be regenerated with `python3 tools/card/readme_screenshots.py` after installing the browser dependencies used by `.github/workflows/card-visual.yml`. Capture details and SHA-256 fingerprints are recorded in [`assets/screenshots/card-screenshots.json`](assets/screenshots/card-screenshots.json).

## Languages

The integration setup/options UI and bundled Lovelace card currently include translations for:

- English
- Greek
- German
- Spanish
- French
- Italian
- Dutch
- Polish
- Portuguese
- Brazilian Portuguese
- Russian
- Turkish
- Simplified Chinese
- Japanese

The card follows the current Home Assistant UI language automatically and falls back to English when the selected language is not available.

## Installation

### HACS

1. Open **HACS → Integrations**.
2. Add `https://github.com/Chreece/HA-OSM-Parking` as a custom repository of type **Integration**.
3. Install **OSM Parking**.
4. Restart Home Assistant.
5. Open **Settings → Devices & services → Add integration → OSM Parking**.

### Manual

Copy:

```text
custom_components/osm_parking
```

into your Home Assistant `config/custom_components/` directory and restart Home Assistant.

## Four-step guided setup and editing

The initial integration setup and **Settings → Devices & services → OSM Parking → Configure** both use the same short four-step wizard:

1. **Destination and distance:** Choose an entity that provides coordinates and set the parking search radius (100–10,000 m).
2. **Parking types:** Multiselect paid, surface, street, underground, multi-storey, Park & Ride and other parking. Choose the maximum results per category (1–25), whether to include private/restricted parking.
3. **Providers that require credentials:** Multiselect any additional providers to enable: Prague Golemio, Transport for NSW, Taiwan TDX and Singapore URA. These are not necessarily paid services; most have free developer/API-key options. **OpenStreetMap and all key-free municipal providers are automatic** and need no selection.
4. **Provider credentials (only when needed):** Only password fields for the providers selected in step 3 appear. Taiwan TDX requires a Client ID and Client Secret; others require one key each. When no credentialed provider is selected, this final screen is skipped.

The wizard **only saves after its last relevant step**. If you reopen the integration options, your previous destination, radius, parking types, zone choice and enabled credentialed providers are preselected. Existing API keys are **never shown or prefilled**; leaving an existing key field blank preserves the stored value. Deselecting a provider disables it without deleting its stored key, so it can be re-enabled later without re-entering credentials.

All 14 setup languages support the four step titles, field labels, parking type and provider option labels, credential descriptions and validation errors. This change retains the same underlying config entry fields as older versions, so existing installations need no data migration.

## Action: Find parking

OSM Parking provides the read-only response action **`osm_parking.find_parking`**. It searches arbitrary coordinates with the same official providers, source-quality ranking, deduplication, access filtering and fallbacks used by the sensor, but it **does not change the configured destination, sensor state, dashboard, or sensor polling/retry cycle**.

Only `latitude` and `longitude` are required. Optional `radius_m`, `parking_types`, `max_results` and `include_restricted` override the selected config entry for that call only. When omitted, those values come from the OSM Parking configuration. Provider enablement and API credentials always come from a loaded OSM Parking config entry.

When exactly one OSM Parking config entry is loaded it is selected automatically. If multiple entries are loaded, choose `config_entry_id` in the action's **Provider settings** section.

Example:

```yaml
- action: osm_parking.find_parking
  data:
    latitude: 50.110924
    longitude: 8.682127
    radius_m: 2000
    parking_types:
      - underground
      - multi_storey
      - park_and_ride
    max_results: 5
  response_variable: parking_search
```

The response contains:

- `parkings`: ordered parking records. Each record can include name, latitude/longitude, distance, category, fee/access, capacity/free capacity, price, opening information, provider/source data and navigation links.
- `count`: number of returned parking records.
- `category_counts`: returned count for each supported category.
- `providers_queried`: sources that were actually contacted for this search.\n- `providers_contributing`: successful sources that returned at least one usable facility or zone before deduplication/result limits.\n- `winning_sources`: sources whose parking record won deduplication and survived the final category/radius/result limits.\n- `providers_used`: backward-compatible alias of `winning_sources`.
- `partial_data` and `unavailable_sources`: whether some sources failed while other sources still returned usable parking.
- `availability_counts`: counts of timestamp-verified live, reported and estimated records.
- The effective radius, categories, per-category limit and restricted-parking setting.

For example, after checking `{{ parking_search.count > 0 }}`, the closest parking name is `{{ parking_search.parkings[0].name }}`.

A source outage does not invalidate healthy overlapping sources. If no usable source can complete the search, the action raises a normal Home Assistant action error instead of returning an error code inside the response.

## Destination entity

The setup screen automatically scans Home Assistant and lists the entities that are currently usable as OSM Parking destinations.

A supported entity must have a valid state and numeric coordinate attributes in either of these forms:

- `latitude` + `longitude`
- `lat` + `lon`
- `lat` + `lng`

The dropdown shows the friendly name, entity ID and current coordinates, so there is no need to guess which entities are compatible.

The OSM Parking coordinator subscribes to the selected entity. Parking is fetched when the integration starts and whenever the destination state/name/coordinates meaningfully change. OSM/static-only successful operation does not poll periodically; realtime and estimated-occupancy providers can request their own refresh cadence as described below.

Example:

```yaml
state: LANXESS arena, Willy-Brandt-Platz, Deutz, Innenstadt, Köln, Nordrhein-Westfalen, 50679, Deutschland
attributes:
  lat: 50.9384967
  lon: 6.9828844
```

## Dashboard card

### Card loading and browser cache

In normal Home Assistant storage mode, OSM Parking registers its bundled card as a versioned Lovelace module resource. This avoids dashboard/card startup races and stale ES-module caching after Home Assistant restarts or integration updates. YAML resource mode falls back to Home Assistant's frontend extra-module loader.


The integration serves and registers its card automatically. Point the card at the **OSM Parking sensor**, not the source/geocode sensor:

```yaml
type: custom:osm-parking-map-card
entity: sensor.parking_suggestions
title: Parking suggestions
map_height: 220
theme_mode: auto
show_list: true
show_destination: true
show_price: true
```

The map shows the destination, numbered parking markers, distance, category, access, price information when known, and navigation/OSM actions.

## Card error and recovery states

The bundled card distinguishes between different failure conditions instead of only showing a generic unavailable sensor:

- **Destination source unavailable** — open/fix the selected source entity; OSM Parking refreshes when it becomes valid again.
- **Destination coordinates missing** — the source must expose `latitude` + `longitude`, `lat` + `lon`, or `lat` + `lng`.
- **Overpass temporarily unavailable** — this is normally an external service issue. OSM Parking retries automatically and the card shows the active retry interval plus a **Retry now** action.
- **No parking found** — the request succeeded; increase the radius or enable additional parking categories if appropriate.
- **Map dependency failed to load** — the card retries MapLibre from a fallback CDN and can retry in-place without requiring a hard page reload.

Technical error details are available in a collapsible section when useful.

## Parking data providers

OSM Parking uses a provider model. **OpenStreetMap / Overpass is always the worldwide baseline.** Additional providers are considered from the search coordinates. A provider is queried only when its `applies(latitude, longitude)` coverage check passes, required credentials are available, it is enabled (when optional), and it is not in source-specific retry cooldown. Public providers work automatically; credentialed providers remain optional.

Provider reporting has three distinct stages:

- **Providers queried**: sources that were actually contacted. A successful query can still return zero nearby parking.
- **Providers contributing**: queried sources that returned at least one structurally usable parking facility or zone before deduplication and category/result limiting.
- **Winning sources / Providers used**: providers whose record actually won deduplication and remains in the final returned parking list. The legacy `providers_used` attribute now has this precise meaning.

This distinction prevents a successful-but-empty regional API call from looking as if its data was used.

| Provider | Coverage | Realtime | Credentials |
| --- | --- | ---: | --- |
| OpenStreetMap / Overpass | Worldwide | No | None |
| Toulouse Métropole BNLS | Toulouse public garages | Static inventory; equivalent API fallback | None |
| Ville de Paris Open Data / BNLS | Paris concession garages | Static capacity, tariffs, accessibility | None |
| Ayuntamiento de Zaragoza | Zaragoza public garages | Static facilities, no occupancy | None |
| Singapore URA | Singapore URA car parks | Reported available car lots (timestamp not supplied) | Optional URA access key |
| İBB / İSPARK | İstanbul, Turkey | Reported counts, upstream measurement time not published | None |
| İzmir Municipality / İZUM | İzmir, Turkey | Reported counts, upstream measurement time not published | None |
| ParkAPI / MobiData BW | ParkAPI-covered Central European regions | When source provides it | None |
| ParkenDD / ParkAPI | Supported European cities | Yes where upstream provides it | None |
| Netherlands RDW Open Data | Official Kadaster/PDOK Netherlands geometry + 10 km search buffer | Static locations | None |
| Stad Gent Open Data | Ghent, Belgium | Yes | None |
| Stadt St.Gallen Open Data | St.Gallen, Switzerland | Yes, minute-updated | None |
| Open Transport Data Switzerland / SBB P+Rail | Switzerland + nearby cross-border facilities | Estimated occupancy where supplied | None |
| Brussels Open Data | Brussels Capital Region | No | None |
| Dublin City Council Open Data | Dublin | Yes | None |
| Helsinki Parkkihubi | Helsinki | Area statistics | None |
| Singapore HDB / data.gov.sg | Singapore HDB car parks | Yes | None |
| Hong Kong DATA.GOV.HK | Hong Kong | Yes | None |
| City of Melbourne Parking Bay Sensors | Central Melbourne street bays | Yes | None |
| Madrid Open Data Parking | Madrid rotational car parks | Yes | None |
| Strasbourg Open Data | Strasbourg Eurométropole structured car parks | Yes, 3-minute feed | None |
| Montpellier NGSI-LD Open Data | Montpellier Métropole structured car parks | Yes | None |
| Málaga Open Data | Málaga municipal public car parks | Yes, 1-minute feed | None |
| Métropole de Lyon Open Data | Greater Lyon public car parks | Yes when source is fresh | None |
| Nantes Naolib public garages | Nantes public garages | Yes, 2-minute feed | None |
| Nantes Naolib Park & Ride | Nantes Métropole P+R | Yes, 2-minute feed | None |
| Métropole Européenne de Lille Open Data | Lille Métropole | Yes when upstream reports a fresh, known-open state | None |
| SMMAG / M Mobilités | Grenoble-area garages and P+R | Yes when official joined measurements are fresh | None |
| Prague Golemio Parking v3 | Prague | Yes | Optional free API key |
| Transport for NSW Car Park API | NSW supported facilities | Yes | Optional Open Data API key |
| Taiwan TDX Parking | Taiwan | Yes | Optional Client ID + Client Secret |

The RDW provider now uses a **bundled authoritative Netherlands geometry** derived directly from Kadaster/PDOK **BRK Bestuurlijke Gebieden – Landgebied** (CC BY 4.0), rather than hand-written rectangles or regional bands. During development the official WGS84 shape is projected to Dutch RD New, buffered by exactly 10 km (the integration's maximum search radius), topology-preserving simplified, transformed back to WGS84 and shipped with the integration. Runtime provider selection is therefore offline and deterministic—no extra PDOK request is needed. The unbuffered derived geometry is also retained for provenance/tests. Searches just across the border can still discover Dutch parking, while Cologne, Düsseldorf, Dortmund and Frankfurt stay outside the RDW coverage buffer.

The coverage loader is generic and can be reused by other providers when their publisher exposes an authoritative service-area or country geometry. Provider diagnostics expose the coverage authority/licence when applicable.

Maintainers can reproduce the bundled RDW geometry with `python tools/generate_authoritative_coverage.py` (development dependencies: Shapely and pyproj); Home Assistant runtime has no geometry-generation dependency.

Provider results are normalized into the same parking model and conservatively merged with OSM results. When two sources describe the same facility, OSM links/descriptive data can be retained while the regional provider contributes live capacity, free spaces, opening status or provider metadata. Individual physical parking-bay feeds such as Melbourne can opt out of merging so nearby bays remain distinct.

### Paris, Zaragoza and Singapore URA data integrity

- **Paris:** The official BNLS stationnement-en-ouvrage catalog uses WGS84, stable national garage IDs, one-hour tariffs and static total/accessible/EV capacities. Refreshed roughly twice yearly; never labelled live. Subscriber-only sites are excluded unless restricted parking is enabled.
- **Zaragoza:** The documented municipal REST inventory provides public car-park locations and optional static capacity. Its map displays separate VINCI occupancy and **estimated** controlled-street occupancy, but no verified open API contract for those measurements has been established. The integration does not invent counts.
- **Singapore URA:** The official Car_Park_Details and Car_Park_Availability feeds use an optional AccessKey and daily token. SVY21 coordinates are transformed to WGS84; only passenger-car lots (lotType C) are considered. Numbers are **reported**, never verified live, because the availability feed has no producer measurement timestamp. The unrelated 26 MB quarterly individual-lot GeoJSON is not downloaded as facility points.
- All new data stays subject to the existing best-valid-source deduplication. Municipal provider failure cannot erase other successful sources.

### Source-quality precedence and deduplication

Parking facilities from different sources are conservatively deduplicated using nearby coordinates, meaningful name similarity and type compatibility. Different nearby garages stay separate; individual street bays and segments may explicitly opt out of merging. One facility keeps the strongest valid availability while OSM navigation links, prices and other missing metadata can enrich it.

The source-quality order is: **verified live** (fresh upstream measurement timestamp), **reported** (plausible count but no publisher measurement time), **estimated occupancy**, **predicted occupancy**, then **static facility details**. Within the same category, newer verified measurements take precedence. Display attributes expose availability_kind, availability_source, availability_freshness, metadata_source, data_sources and deduplicated_source_count.

İstanbul İSPARK and İzmir İZUM publish counts but not dependable upstream observation times in their parking-list responses. They are therefore **reported**, never timestamp-verified live. Their current-location feeds refresh every five minutes while a covered facility is in the search radius; API failures are isolated from OSM. The time at which Home Assistant downloaded the response is not the original measurement time. Unsupported parking tariffs are never invented. Pre-existing provider responses without upstream timestamps are likewise classified as reported when they contain plausible counts.

### Automatic public sources and Athens GIS

No Athens GIS switch is required in setup or options. Official polygons are considered automatically only around Athens and after validating GeoJSON, projection, closed rings and geographic bounds. Unusable responses contribute no overlay. Valid static zones cache for 24 hours; failed requests use source-specific recovery backoff. Old `athens_zones_enabled` flags are ignored. `show_zones: false` remains a card display preference.

Equivalent Athens WFS routes and Toulouse Opendatasoft v2/v1 formats are primary/fallback access to the same dataset, not additional parking providers. Fallback is attempted only after transport or data validation failure. These routes share infrastructure; they do not offer an independent mirror during a whole-host outage. Complementary overlapping feeds remain enabled and are deduplicated by facility, so their unique coverage is not lost.

Provider imports, construction, eligibility, requests, payloads and merging are isolated. Supplemental requests have a 30-second default total budget (at most 45 seconds for an explicit provider budget); Athens has an 18-second budget. Retries back off after consecutive failures (1 minute, 5 minutes, 30 minutes, 6 hours), with longer server rate limits respected. Successful static-only data stops polling. Diagnostics expose source status, active endpoint and retry time without API secrets or raw exception bodies.

No failed-source occupancy is replayed. Healthy overlapping sources can take over. Static capacity and controlled-zone boundaries are never presented as measured vacancy or parking permission; check local signage. Toulouse Metropole BNLS is a static garage inventory with equivalent API fallback.

### Optional provider credentials

Open **Settings → Devices & services → OSM Parking → Configure** to add optional credentials. Leaving these fields empty has no effect on the automatic public providers.

- **Prague Golemio** — create a free key at `api.golemio.cz/api-keys`; used only for destinations in Prague.
- **Transport for NSW** — use a Transport for NSW Open Data API key; used only for NSW destinations.
- **Taiwan TDX** — enter the Client ID and Client Secret from the TDX member center; OAuth access tokens are obtained and cached automatically.
- **Singapore URA** — register at the [official URA data API](https://eservice.ura.gov.sg/maps/api/) to obtain an AccessKey, then enter it in OSM Parking options. A daily API token is generated automatically; no URA requests occur without your key. The key is redacted from diagnostics.

Credentials are stored in the Home Assistant config entry and are redacted from diagnostics.

### Refresh behaviour

- **OSM/static data only:** startup + destination changes; no successful periodic polling.
- **Paris BNLS and Zaragoza:** static catalog cached 24 hours, with no successful background polling.
- **Singapore URA:** with user access key, car park details cached 12 hours, token cached up to 20 hours, reported availability refreshed about every 5 minutes if nearby facilities are found.
- **İstanbul and İzmir reported parking:** 5-minute refresh while facilities are nearby; not labelled verified live.
- **Athens zone GIS:** automatic in Athens, validated static cache for 24 hours and source-specific recovery backoff.
- **Melbourne / Singapore / Madrid / St.Gallen / Málaga live data:** approximately 60-second refresh while live data is active.
- **Strasbourg live data:** 3-minute refresh, matching the official source cadence.
- **Lyon and Nantes live feeds:** 2-minute refresh while covered facilities are in range, including when upstream availability is temporarily invalid.
- **Lille MEL:** 5-minute refresh when parking facilities are in range, matching the official 5-minute publication cadence.
- **Grenoble SMMAG:** 2-minute refresh when nearby parking is present; the static site catalogue is cached for six hours.
- **Montpellier / ParkAPI / ParkenDD / Hong Kong / Ghent / Dublin / Helsinki / Golemio / TfNSW or TDX live data:** provider-specific live refresh, generally 1–5 minutes.
- **Swiss estimated occupancy:** 30-minute refresh while estimated occupancy is available.
- **Any partial provider outage:** temporary 5-minute recovery refreshes until the missing source recovers.
- **Complete refresh failure:** first recovery retry after 1 minute, then every 5 minutes until success.

A regional provider failure does not discard good data from other providers. The card shows a partial-data notice and the missing source is retried automatically.

### Provider freshness and privacy

Realtime data is only labelled live when the upstream source is usable and sufficiently fresh. For example, Melbourne sensor timestamps are checked before a bay is shown as occupied/free, and ParkenDD data that has aged beyond its live-data window is treated as static.

Swiss `currentEstimatedOccupancy` values are shown as **estimated occupancy**, not as exact free spaces. St.Gallen free-space values are only treated as live when the upstream update timestamp is fresh.

Montpellier `availableSpotNumber` is only shown as realtime while its NGSI-LD `observedAt` timestamp is fresh. Strasbourg status code `0` is treated as unavailable realtime data. Málaga only exposes the municipality's published free-space count and does not infer total capacity.

Lyon exact vacancy is only labelled realtime while its official last_update timestamp is within 15 minutes. Nantes Naolib only exposes free spaces when grp_statut is 5 (open) and grp_horodatage is within 15 minutes; code 0 is invalid, 1 closed, and 2 subscribers only. Its grp_exploitation capacity covers short-stay customers, not subscriber bays.

Lille MEL vacancy uses its official WFS total/free fields and dtdate timestamp. Records older than 15 minutes, undocumented status values, closed sites or impossible counts are not presented as live.

Grenoble SMMAG uses the official static parking GeoJSON catalogue joined to the separate M Mobilités live feed by parking ID. Only producer-time-stamped measurements no older than 10 minutes with nonnegative, plausible counts are live; a missing reading does not mean zero vacancies. Only counted facilities can contribute live values. Licence: ODbL 1.0; retain attribution to M Mobilités / SMMAG.

Helsinki's public statistics intentionally suppress exact occupancy when the real count is three or less. OSM Parking preserves that privacy behavior and does **not** reverse-engineer an exact free-space count from a suppressed value.

### Unsupported/private app feeds

ParkOut and AthensWay are useful Athens parking services, but no stable documented public third-party API has been identified. OSM Parking does not scrape undocumented private/mobile endpoints. They can be added when an official read-only integration API or reusable open-data feed is available.

## Worldwide provider expansion research

See [the researched source inventory](docs/provider-research-2026-10-13.md) and the newer [free vs commercial provider market research](docs/provider-market-research-2026-10-14.md). The latter covers Luxembourg City/CFL, Basel, Zürich, Fintraffic, Norway, TfL, Seoul, ParkWhiz, Parkopedia, INRIX, TomTom, ParkBee, Passport and EasyPark, including access/licensing constraints. Listed candidates are **not automatically implemented**.

## Parking categories and result limits

The integration can independently enable:

- paid
- open / surface
- street
- underground
- multi-storey
- Park & Ride
- other

**Maximum results per category** is one shared value applied to every enabled category. Results are capped inside each category first, merged, then globally sorted by distance.

## Pricing

OSM often knows whether parking is paid without containing the exact tariff. The integration never invents a price.

- `fee=no` → free
- `fee=yes` → paid; exact price unknown
- `charge`, `charge:conditional`, or `fee:conditional` → shown as supplied by OSM

## Overpass reliability

OSM Parking uses public Overpass services. Public instances can occasionally return HTTP 5xx errors or time out, so the integration rotates through several documented global endpoints.

Normal operation does not poll periodically. If every Overpass attempt fails, temporary recovery polling starts automatically: the first retry is after 1 minute and continued failures retry every 5 minutes. Recovery polling stops immediately after the first successful refresh.

The remote search uses a rectangular bounding box because it is inexpensive for Overpass to evaluate. Results are then filtered locally using the exact configured radius, so the user-facing search remains circular.

## Diagnostics

Home Assistant diagnostics are supported. Coordinates and navigation/location fields are redacted from diagnostics where appropriate.

## Contributing / issues

Bug reports and feature requests are welcome:

- [Issues](https://github.com/Chreece/HA-OSM-Parking/issues)

When reporting a data-fetch problem, include the Home Assistant log entry and diagnostics if possible.

## Data and attribution

Depending on destination, parking data may come from OpenStreetMap/Overpass and supported municipal or national open-data sources such as MobiData BW/ParkAPI, ParkenDD, RDW, Stad Gent, Stadt St.Gallen, Open Transport Data Switzerland/SBB P+Rail, Brussels Open Data, Dublin City Council, Helsinki Parkkihubi, Strasbourg Open Data, Montpellier NGSI-LD, Málaga Open Data, Lille MEL Open Data, Grenoble SMMAG, Singapore data.gov.sg, Hong Kong DATA.GOV.HK, City of Melbourne and Madrid Open Data. Optional credentialed providers include Golemio, Transport for NSW and Taiwan TDX.

Each provider's original attribution/licence remains applicable. The integration exposes provider/source information on normalized results where available. Map rendering uses MapLibre and OpenFreeMap.

## Support

If you find the project useful, you can support development on [Ko-fi](https://ko-fi.com/chreece).

## License

MIT

## Compact parking explorer

The bundled card now defaults to a 220 px map and provides search, parking-type chips, cost/data-quality/source/distance filters, and sorting directly on the card. Filters are local to the results already returned by the integration; they cannot retrieve categories disabled in the integration or more results than its configured limits.

```yaml
type: custom:osm-parking-map-card
entity: sensor.parking_suggestions
map_height: 220
theme_mode: auto
sort_by: distance
remember_filters: true
```

`map_height` overrides the legacy `height` option; an explicitly configured legacy height is otherwise honored. `theme_mode` accepts `auto`, `light`, or `dark`. `map_style` remains a custom-style override; `map_style_light` and `map_style_dark` can specify separate styles. The runtime theme button cycles light, dark and automatic. No map API key is added.

`sort_by` accepts `distance`, `type`, `name`, `free_first`, `availability`, `data_quality` or `source`. Missing distance and vacancy values sort after known values. Free-first sorts known free sites before paid sites and unknown fees; it does **not** invent hourly prices from unstructured tariff strings. The available-only filter requires positive **live** free-space data; reported counts remain separately labelled.

`show_filters: false` hides the controls, `show_list: false` preserves map-only display, and `show_zones: false` hides zone boundaries. `remember_filters: false` disables browser-local preferences. For multiple cards using the same entity, set distinct `preference_key` values for independent preferences. Preferences are never written to the integration or shared across Home Assistant users.

The results list starts **collapsed** on each new card load. The map, search, filters and sorting stay usable. Click a parking marker to expand the list, highlight that exact facility and scroll it into view. This does not reset the map camera or expand every result's details. Use **Show results / Hide results** to fold the list manually. Expansion survives ordinary data/theme/filter updates but is not persisted across a reload. Keyboard activation and reduced-motion preferences are respected. An explicit `show_list: false` retains map-only mode, without auto-expansion.

Map markers and rows share the same parking-type icons; their facility IDs and display indices remain internal. Click a result to focus its marker; use the navigation link to open directions. Refresh is explicit; changing filters does not call Home Assistant update services. Pan/zoom is retained during ordinary updates. The fit button resets the view to visible results and the destination.

Design references: [OpenFreeMap styles](https://openfreemap.org/quick_start/), [MapLibre map API](https://maplibre.org/maplibre-gl-js/docs/API/classes/Map/), and [W3C pointer target sizing](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html). Existing source timestamps, attribution, zone warnings, source-selection and deduplication remain authoritative.

Further official-source research: [automatic provider research](docs/provider-resilience-research.md).

### Parking-type map icons

Parking markers use type icons instead of sequential numbers: a banknote for paid parking, P for surface parking, a road for street parking, a tunnel for underground parking, a building for multi-storey parking, a train/car for Park & Ride, and a question-mark location pin for other or unknown types. The same glyph is shown beside the matching result. Hover text and accessible button names include the translated parking type and facility name.

Numbers and ordering remain internal metadata. Matching uses the existing stable facility key, not icon appearance or row order, so two garages with identical icons and names still open their own results after sorting/filtering. Marker activation retains the folded-list behavior: expand, highlight and scroll to the correct row without changing the map camera. Ordinary updates do not scroll again. The glyphs are embedded in the card; no image service, icon font or extra browser dependency is required.
