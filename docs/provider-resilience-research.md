# Automatic source usability and research — 13 October 2026

## Implementation rules

HTTP 200 alone does not make parking data usable. Validate the response contract, geography and facility/zone records before including them. Broken imports, constructors, eligibility checks, network requests, parsing and merging are isolated. Retry state is per config entry. Failed-source vacancy values are not replayed: a healthy overlapping source can take over through best-source deduplication.

Equivalent interfaces for **the same dataset** are sequential primary/fallback requests. Different overlapping datasets must not be globally suppressed because they have unique facilities. OpenStreetMap, ParkAPI, ParkenDD and municipal providers remain complementary. Alternate routes on one host are not independent infrastructure.

## Athens, Greece

Official layer: `geonode:zones_stathmeusis`.

- Municipal dataset: https://opendata.cityofathens.gr/en/dataset/gis-athens-86d8dc0c-25a9-11ec-9787-0242ac130009
- Official preview: https://gis.cityofathens.gr/geoserver/gwc/demo/geonode%3Azones_stathmeusis?format=image%2Fgif&gridSet=EPSG%3A900913
- European catalogue: https://data.europa.eu/data/datasets/2366a51f-8e8b-4425-832a-50143e2942eb?locale=en

The layer describes controlled parking zones, not live free spaces. The automatic provider tries the official `/geoserver/ows` WFS route, then `/geoserver/wfs` only after the preferred route fails. Validate finite WGS84 coordinates within Athens, closed non-degenerate rings, polygon nesting, inventory completeness and bounded size. No usable polygons means no overlay, not zero vacancy. Catalogue publication dates do not prove current road-sign rules.

The old manual experimental switch is removed, including for entries with its saved value false. Valid static polygons cache for 24 hours. A failed refresh does not extend an expired cache. `show_zones: false` remains a card display preference. WMS images and UTFGrid previews are not interchangeable with WFS polygons and are not used as structured parking permissions.

## Toulouse, France — static adapter

- BNLS facility inventory: https://data.toulouse-metropole.fr/explore/dataset/parcs-de-stationnement/
- Separate P+R inventory: https://data.toulouse-metropole.fr/explore/dataset/parkings-relais/

The documented facility fields include national `id`, WGS84 `xlong`/`ylat`, capacity and tariffs. Explore v2.1 and records v1.0 expose the same dataset, so they are fallback formats rather than independent providers. Truncated, empty or unusable inventories are rejected. A 24-hour static cache does not start successful background polling. Total capacity is never labelled live vacancy. The separate P+R inventory is a future coverage candidate, not a mirror of every BNLS garage.

## Bordeaux, France — researched, not shipped

- Current DataHub inventory: https://datahub.bordeaux-metropole.fr/explore/dataset/st_park_p/
- Availability page: https://datahub.bordeaux-metropole.fr/pages/parking-disponibilite/

The current official portal describes public garages and P+R metadata and provides an availability page. Its inventory advertises a 2 minute 30 second refresh; this alone does not establish valid measured vacancies for every record. Inspect exact vacancy fields and source timestamps, public terms, and whether older portal hostnames are redirects or equivalent responses before enabling a provider. Do not count old and new portal URLs twice.

## Galway, Ireland — researched, not shipped

- Council catalogue: https://data.gov.ie/dataset/carparkingopendata3
- Official ArcGIS layer: https://services-eu1.arcgis.com/Zmea819kt4Uu8kML/arcgis/rest/services/CarParkingOpenData/FeatureServer/0

The layer documents EPSG:4326 Point geometry, `OBJECTID`, `NAME`, `TYPE`, `NO_SPACES`, `Lat` and `Long`. JSON and GeoJSON queries could be equivalent fallback formats. The catalogue declares CC BY 4.0. The service reports a 2024 layer edit and a 2021 data edit: newer catalogue publication dates do not establish current occupancy. Treat this as static location/capacity data, pending a successful query and record-level validation.

## Probe evidence

`tools/probe_parking_sources.py` performs bounded, read-only requests to these fixed public endpoints, without user credentials. Its Actions artifact records status, response shape and observation time. Success is a point-in-time result from that runner, not guaranteed access from every Home Assistant network. Failed probes do not become live measurements or break the integration. Retain explicit source attribution and do not bypass authentication or rate limits.
