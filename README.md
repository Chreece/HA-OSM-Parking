<!-- ko-fi-support -->
<p align="center">
  <a href="https://ko-fi.com/chreece">
    <img src="https://raw.githubusercontent.com/Chreece/pir2ha/main/.github/ko-fi-banner.svg" alt="Support Chreece on Ko-fi" width="600">
  </a>
</p>

# OSM Parking for Home Assistant

[![HACS validation](https://github.com/Chreece/HA-OSM-Parking/actions/workflows/validate.yml/badge.svg)](https://github.com/Chreece/HA-OSM-Parking/actions/workflows/validate.yml)

Home Assistant custom integration that finds parking around a destination using OpenStreetMap / Overpass data.

## Features

- Uses any Home Assistant entity exposing destination latitude/longitude.
- Configurable search radius and refresh interval.
- Parking categories: paid, surface/open, street, underground, multi-storey, Park & Ride, and other.
- One maximum-results value applied independently to every enabled category.
- Final results sorted by distance.
- Optional inclusion of private/restricted parking.
- Exposes OSM capacity, access, opening-hours, operator and pricing metadata when available.
- Bundled `custom:osm-parking-map-card` showing the destination and suggestions on an interactive map.
- Map card is served and loaded by the integration itself; no separate `www` copy is required.

## Install with HACS

Until the repository is included in HACS defaults:

1. Open HACS.
2. Add `https://github.com/Chreece/HA-OSM-Parking` as a custom repository of type **Integration**.
3. Install **OSM Parking**.
4. Restart Home Assistant.
5. Go to **Settings → Devices & services → Add integration → OSM Parking**.

## Destination entity

The selected destination entity must expose coordinates in either of these attributes:

- `latitude` / `longitude`
- `lat` / `lon`

The display name is taken from `display_name` when available, otherwise from the entity state and then `friendly_name`.

Example destination entity:

```yaml
state: LANXESS arena, Willy-Brandt-Platz, Deutz, Innenstadt, Köln, Nordrhein-Westfalen, 50679, Deutschland
attributes:
  latitude: 50.9384967
  longitude: 6.9828844
```

## Dashboard card

The integration registers the bundled card automatically. Add it to a dashboard with YAML:

```yaml
type: custom:osm-parking-map-card
entity: sensor.parking_suggestions
title: Parking suggestions
height: 450
show_list: true
show_destination: true
show_price: true
```

Use the actual sensor entity created by your OSM Parking config entry.

The card displays:

- destination marker
- numbered parking markers
- distance and parking type
- access restrictions when known
- explicit OSM price/charge information when available
- paid/free status when OSM only provides `fee=yes/no`
- navigation and OpenStreetMap actions

The map uses MapLibre with OpenFreeMap rather than OpenStreetMap's volunteer raster tile servers.

## Pricing

OSM data does not always contain an exact parking price. The integration does not invent one.

- `fee=no` → free
- `fee=yes` without charge data → paid, exact amount unknown
- `charge`, `charge:conditional`, or `fee:conditional` → exposed as provided by OSM

## Data source

Parking data is queried from public Overpass API instances and ultimately comes from OpenStreetMap contributors. Availability and completeness depend on local OSM tagging.

## Issues

Please report bugs or feature requests in the repository's Issues section and include Home Assistant diagnostics where useful.
