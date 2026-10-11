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
</p>

# OSM Parking

**OSM Parking** is a Home Assistant custom integration that follows a destination entity and finds nearby parking from OpenStreetMap through Overpass. It includes a bundled interactive Lovelace map card.

## Highlights

- Follows the configured destination entity immediately when its state or coordinates change.
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

Choose any Home Assistant entity that exposes either:

- `latitude` + `longitude`
- `lat` + `lon`

The OSM Parking coordinator subscribes to that configured entity. When it changes, parking is refreshed immediately; the normal polling interval remains as a periodic refresh.

Example:

```yaml
state: LANXESS arena, Willy-Brandt-Platz, Deutz, Innenstadt, Köln, Nordrhein-Westfalen, 50679, Deutschland
attributes:
  lat: 50.9384967
  lon: 6.9828844
```

## Dashboard card

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

The remote search uses a rectangular bounding box because it is inexpensive for Overpass to evaluate. Results are then filtered locally using the exact configured radius, so the user-facing search remains circular.

## Diagnostics

Home Assistant diagnostics are supported. Coordinates and navigation/location fields are redacted from diagnostics where appropriate.

## Contributing / issues

Bug reports and feature requests are welcome:

- [Issues](https://github.com/Chreece/HA-OSM-Parking/issues)

When reporting a data-fetch problem, include the Home Assistant log entry and diagnostics if possible.

## Data and attribution

Parking data comes from [OpenStreetMap](https://www.openstreetmap.org/) contributors through Overpass API instances. Map rendering uses MapLibre and OpenFreeMap. Data completeness depends on local OSM tagging.

## Support

If you find the project useful, you can support development on [Ko-fi](https://ko-fi.com/chreece).

## License

MIT
