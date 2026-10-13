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
- Live free-space/occupancy data is shown when a supported provider exposes it.
- Zero-key public providers work automatically; Prague, NSW and Taiwan providers can be enabled with optional free developer credentials.
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

### Desktop dashboard example

<p align="center">
  <img src="https://raw.githubusercontent.com/Chreece/HA-OSM-Parking/main/assets/screenshots/dashboard-desktop.svg"
       alt="OSM Parking dashboard card on Home Assistant desktop"
       width="100%">
</p>

### Mobile dashboard example

<p align="center">
  <img src="https://raw.githubusercontent.com/Chreece/HA-OSM-Parking/main/assets/screenshots/dashboard-mobile.svg"
       alt="OSM Parking dashboard card on Home Assistant mobile"
       width="520">
</p>

> Example dashboard views using the bundled OSM Parking map card. Parking availability, names, categories, pricing and OpenStreetMap data vary by location.

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
height: 450
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

OSM Parking uses a provider model. **OpenStreetMap / Overpass is always the worldwide baseline.** Additional providers are queried only when the destination falls inside their geographic coverage. Public providers work automatically; credentialed providers remain optional.

| Provider | Coverage | Realtime | Credentials |
| --- | --- | ---: | --- |
| OpenStreetMap / Overpass | Worldwide | No | None |
| ParkAPI / MobiData BW | ParkAPI-covered Central European regions | When source provides it | None |
| ParkenDD / ParkAPI | Supported European cities | Yes where upstream provides it | None |
| Netherlands RDW Open Data | Netherlands | Static locations | None |
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
| Prague Golemio Parking v3 | Prague | Yes | Optional free API key |
| Transport for NSW Car Park API | NSW supported facilities | Yes | Optional Open Data API key |
| Taiwan TDX Parking | Taiwan | Yes | Optional Client ID + Client Secret |

Provider results are normalized into the same parking model and conservatively merged with OSM results. When two sources describe the same facility, OSM links/descriptive data can be retained while the regional provider contributes live capacity, free spaces, opening status or provider metadata. Individual physical parking-bay feeds such as Melbourne can opt out of merging so nearby bays remain distinct.

### Optional provider credentials

Open **Settings → Devices & services → OSM Parking → Configure** to add optional credentials. Leaving these fields empty has no effect on the automatic public providers.

- **Prague Golemio** — create a free key at `api.golemio.cz/api-keys`; used only for destinations in Prague.
- **Transport for NSW** — use a Transport for NSW Open Data API key; used only for NSW destinations.
- **Taiwan TDX** — enter the Client ID and Client Secret from the TDX member center; OAuth access tokens are obtained and cached automatically.

Credentials are stored in the Home Assistant config entry and are redacted from diagnostics.

### Refresh behaviour

- **OSM/static data only:** startup + destination changes; no successful periodic polling.
- **Melbourne / Singapore / Madrid / St.Gallen / Málaga live data:** approximately 60-second refresh while live data is active.
- **Strasbourg live data:** 3-minute refresh, matching the official source cadence.
- **Lyon and Nantes live feeds:** 2-minute refresh while covered facilities are in range, including when upstream availability is temporarily invalid.
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

Helsinki's public statistics intentionally suppress exact occupancy when the real count is three or less. OSM Parking preserves that privacy behavior and does **not** reverse-engineer an exact free-space count from a suppressed value.

### Unsupported/private app feeds

ParkOut and AthensWay are useful Athens parking services, but no stable documented public third-party API has been identified. OSM Parking does not scrape undocumented private/mobile endpoints. They can be added when an official read-only integration API or reusable open-data feed is available.

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

Depending on destination, parking data may come from OpenStreetMap/Overpass and supported municipal or national open-data sources such as MobiData BW/ParkAPI, ParkenDD, RDW, Stad Gent, Stadt St.Gallen, Open Transport Data Switzerland/SBB P+Rail, Brussels Open Data, Dublin City Council, Helsinki Parkkihubi, Strasbourg Open Data, Montpellier NGSI-LD, Málaga Open Data, Singapore data.gov.sg, Hong Kong DATA.GOV.HK, City of Melbourne and Madrid Open Data. Optional credentialed providers include Golemio, Transport for NSW and Taiwan TDX.

Each provider's original attribution/licence remains applicable. The integration exposes provider/source information on normalized results where available. Map rendering uses MapLibre and OpenFreeMap.

## Support

If you find the project useful, you can support development on [Ko-fi](https://ko-fi.com/chreece).

## License

MIT
