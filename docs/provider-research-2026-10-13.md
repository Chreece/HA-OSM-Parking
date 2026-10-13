# Official worldwide parking research — 13 October 2026

A public map or a successful API GET is not proof that reported parking
counts are fresh. We require verified publisher timestamps to call exact
vacancy counts LIVE. Historical measurements, predictions, geospatial zone
polygons and facility inventories must stay separate.

## Newly implemented in v1.0.0

| Area | Verified API or dataset | Data classification | Limitations |
| --- | --- | --- | --- |
| İstanbul, Turkey | https://api.ibb.gov.tr/ispark/Park ; https://data.ibb.gov.tr/dataset/ispark-otopark-bilgileri | Reported free places, capacity, geometry, hours | No reliable producer observation time in list; reported, not verified live. Runtime API reachability unproven from this build environment |
| İzmir, Turkey | https://openapi.izmir.bel.tr/api/ibb/izum/otoparklar ; https://acikveri.bizizmir.com/dataset/otopark-doluluk-ve-lokasyon-bilgileri | Reported free/occupied, type, locations and accessible spaces | Publisher measurement time absent; counts reported. Official open-data attribution applies. Access outside Turkey may fail |
| Athens, Greece | https://opendata.cityofathens.gr/en/dataset/gis-athens-86d8dc0c-25a9-11ec-9787-0242ac130009 | Static municipal controlled-parking polygons | Optional WFS off by default; GIS gateway intermittently unavailable. No occupancy or permit eligibility implied |

## Greece — additional candidate sources

| City or region | Official site | Data and remaining blocker |
| --- | --- | --- |
| Athens | https://opendata.cityofathens.gr/ | Extra regulated zones and accessible areas; no reliable public realtime vacancies confirmed |
| Thessaloniki | https://thesi.gr/ | Visitor/resident on-street parking rules; confirm maintained geospatial dataset and open third-party access |
| Patras | https://catalog.data.patras.gr/group/metafores-kai-stathmeysh | Parking sensor fields and locations, but inspected source was historic, not a verified maintained live feed |
| Piraeus | https://city.piraeus.gov.gr/en/open-data | Smart-parking dataset references; anonymous stable live endpoint and timestamps unverified |
| Crete | https://opendata.crete.gov.gr/ | Island facilities via OGC; review non-commercial dataset licensing before reuse |
| Volos | Municipal public parking inventory | Confirm current metadata schema, download endpoint and redistribution terms |

ParkOut and AthensWay are not scraped: there is no established documented
and authorized public third-party integration API.

## Global candidates (not yet active)

| Country/city | Official source | Type | Next validation |
| --- | --- | --- | --- |
| Zaragoza, Spain | https://www.zaragoza.es/sede/portal/movilidad/trafico/estacionamiento | Structured car parks and reported/estimated occupancy | Distinguish predicted/estimated versus measured, check API pagination |
| London, UK | https://api.tfl.gov.uk/Occupancy/CarPark | Car-park occupancy for supported TfL facilities | Free registered access may be needed; join live records to location inventory and verify timestamps |
| Seoul, South Korea | https://data.seoul.go.kr/ | Municipal parking availability | Registered API key, date freshness, coordinate join and licensed reuse |
| Singapore URA | https://data.gov.sg/datasets/d_9bf8620ecfdc8a5f8f77e3f02160af5c/view | Official static URA parking capacity | Separate from already-supported HDB live feed; a static GEOJSON is NOT realtime vacancy |
| Paris, France | https://opendata.paris.fr/explore/dataset/stationnement-en-ouvrage/ | Garage locations, entrances and tariffs | GeoJSON/ODS v2.1 parsing, cache and official BNLS fields |
| Toulouse, France | https://data.toulouse-metropole.fr/ | Parking facilities | Confirm the authoritative current dataset before implementation |
| France nationwide | https://transport.data.gouv.fr/ | Standardized parking locations and metadata | Licensing, standard IDs, frequency and duplicate matches |
| Stockholm, Sweden | https://openparking.stockholm.se/ | Locations and visitor-space capacity | No actual realtime free-space values in public API; static only |
| Montréal, Canada | https://donnees.montreal.ca/ | Municipal paid street and garage inventory | Static unless a timestamped authoritative vacancy feed is found |
| Toronto, Canada | https://open.toronto.ca/ | Green P facilities | Verify live occupancy instead of assuming static data is live |
| Mexico City, Mexico | https://datos.cdmx.gob.mx/ | Public geospatial parking locations | Static geography and rights review |
| Brisbane, Australia | https://www.data.brisbane.qld.gov.au/ | Municipal inventories and occupancy predictions | Forecasts must be marked predicted, not free-space measurements |
| Austria, countrywide | https://www.oeamtc.at/ | Car-park availability services | Contract or paid access; do not silently use as free public API |

## Release gates for future automatic providers

1. Confirm an official publisher or explicit authorized reuse and attribution.
2. Verify the current raw schema with a real publisher response and fixtures.
3. Validate coordinates and WGS84 CRS before rendering.
4. Treat the source's observed timestamp differently from the local fetch time.
5. Reject negative/fractional, stale or beyond-capacity counts.
6. Do not merge different garages, individual parking bays and street regulation zones.
7. Keep API keys optional, secure and redacted from diagnostics.
8. Isolate regional failures without taking down OSM results, and do not scrape
   undocumented commercial/private app endpoints.
