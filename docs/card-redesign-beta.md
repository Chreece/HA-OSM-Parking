# OSM Parking v1.3.0b1 — Card redesign beta

**Opt-in beta. Stable v1.2.0 and the main branch are unchanged.**

## Included

- Compact 250 px default map with Expand and Fit results controls.
- Automatic Home Assistant light/dark theme matching and manual selection,
  using OpenFreeMap Positron and Dark styles rather than CSS inversion.
- Search, parking-type, fee, distance and data-quality filters.
- Sort by nearest/farthest, type, name, available spaces or data quality.
- Cleaner result cards, direct navigation, source details and coordinated
  list/marker selection. Filter choices persist within the browser tab.
- A graphical card editor for the sensor, title, map height and theme.
- Parking results remain usable when map tiles fail to load.
- Greek and the other existing interface languages are retained.

## Installation

In HACS, open OSM Parking, enable beta/pre-release versions, then use the
Download/Redownload version picker to select **v1.3.0b1**. Restart Home
Assistant and reload the dashboard. No separate patch installer is needed.
The manual ZIP contains custom_components/osm_parking for manual installs.

Existing explicitly configured heights are respected. Set **map_height: 250**
in the card editor or YAML to use the compact height on an older card.

## Scope and test limits

The four-step configuration flow, provider backends, credentials and
best-source deduplication are unchanged. Filters operate on results already
returned by the integration; they do not query new providers or expand the
configured radius. Reported counts and estimates are not labelled verified
live availability. Price sorting across incompatible tariffs is not offered.

The publication workflow runs the existing Python contracts, JavaScript
syntax/version checks, HACS and Hassfest, plus browser interactions against
the **complete bundled card**. Browser tests use synthetic Home Assistant
states, storage and a MapLibre double; they do not prove real Home Assistant
integration, external tile connectivity or municipal API reachability.

## Rollback

Use HACS Redownload and select **v1.2.0**, then restart Home Assistant and
reload the dashboard. Configuration entries and saved credentials remain
compatible. Disable beta/pre-release versions to stay on stable releases.
