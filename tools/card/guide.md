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

Map markers and rows share the same visible numbering. Click a result to focus its marker; use the navigation link to open directions. Refresh is explicit; changing filters does not call Home Assistant update services. Pan/zoom is retained during ordinary updates. The fit button resets the view to visible results and the destination.

Design references: [OpenFreeMap styles](https://openfreemap.org/quick_start/), [MapLibre map API](https://maplibre.org/maplibre-gl-js/docs/API/classes/Map/), and [W3C pointer target sizing](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html). Existing source timestamps, attribution, zone warnings, source-selection and deduplication remain authoritative.
