# Changelog

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
