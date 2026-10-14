# Observed official-source usability — 13 October 2026

Read-only probe time: **20:13 UTC**, GitHub Actions runner.

Reproducible run and downloadable raw evidence: https://github.com/Chreece/HA-OSM-Parking/actions/runs/38461029174

| Source | Actual observation | Interpretation |
| --- | --- | --- |
| Athens WFS `/geoserver/ows` | Request failed with `URLError`; no JSON captured | No usable polygons observed from this runner. Do not display an invented overlay. This is not proof of a permanent or worldwide outage. |
| Athens WFS `/geoserver/wfs` | Request failed with `URLError`; no JSON captured | The equivalent same-host route also failed. It is a route fallback, not independent hosting. |
| Toulouse Explore v2.1 | HTTP 200; all 23 records accepted by the actual provider's inventory validator | Usable static facility inventory, not live free spaces. |
| Toulouse records v1.0 | HTTP 200; all 23 records accepted by the same validator | Equivalent representation of the same inventory; used only when the preferred route fails. |
| Bordeaux DataHub `st_park_p` | HTTP 200; two requested sample records, catalogue reports 100 total | Promising additional source. Has `libres`, `total`, `connecte`, `etat` and `mdate`; these need explicit operational and timestamp semantics before a live provider is enabled. |
| Galway council ArcGIS query | HTTP 200; 17 GeoJSON Point features, EPSG:4326 | Readable static locations and `NO_SPACES` capacities. No live occupancy fields in this response. |

## Field-level findings

The Toulouse payload uses `gratuit: F/T` and `public: T/F`, rather than JSON booleans. It uses singular `type_usager` (for example `tous, residents`) and `gestionnaire`. The adapter explicitly translates these to fee/access/operator metadata while preserving the original cached record. Empty, malformed and truncated inventories are rejected.

In the two-record Bordeaux sample, Brandenburg P+R had `connecte: 1` and an `mdate` of **2026-10-13T20:08:39+00:00**. Bord'Eau Village had `connecte: 0` and an `mdate` of **2026-10-11T12:38:42+00:00**. Both still contained numerical `libres` values. A successful request or a numeric free-space field is therefore insufficient evidence of fresh live availability. The meaning of `mdate` must also be established: a row-update time is not automatically a sensor-measurement time.

Bordeaux and Galway are researched candidates, not enabled providers in this release. Their official sources and access qualifications are in [the research inventory](provider-resilience-research.md). Toulouse is implemented as static data. Athens is automatically evaluated near Athens and included only after its official polygons validate; failures enter bounded retry backoff without replaying expired geometry or failed-source vacancy values.

## Limits

These observations establish only the responses received by this runner at the recorded time. They do not guarantee the same network access from the user's Home Assistant, prove current road-sign rules, or establish a long-term service-level agreement. No user API credentials were used. Public data was read but not modified.
