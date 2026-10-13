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
