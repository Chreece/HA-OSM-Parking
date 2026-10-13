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
