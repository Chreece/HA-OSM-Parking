# Fintraffic, TfL, Norway and Seoul probe evidence — 14 October 2026

These are point-in-time read-only probes from GitHub Actions. They establish
schema and transport behaviour observed by the development runner, not a
permanent service-level guarantee for every Home Assistant network.

## Fintraffic LIIPI

Official documentation: https://parking.fintraffic.fi/docs/index.html

Observed:
- "/api/v1/facilities?geometry=..." returned HTTP 500 with an upstream
  "NoClassDefFoundError: org/postgis/PGgeometry".
- "/api/v1/facilities?limit=-1" returned HTTP 200 with **784** facilities.
- "/api/v1/facilities.geojson?limit=-1" returned HTTP 200 with the same
  **784** facilities in GeoJSON.
- **256** facilities publish positive "CAR" built capacity.
- "/api/v1/utilizations" returned HTTP 200 with 39 current CAR utilization
  rows at probe time. Utilization includes facilityId, capacityType,
  usage, producer timestamp, spacesAvailable, capacity and openNow.
- Individual facility 268 returned static capacity/location metadata; its
  individual utilization returned a fresh timestamp and exact free spaces.

Implementation deliberately does **not** depend on Fintraffic's currently
broken spatial query. The full GeoJSON is cached for 12 hours and filtered
against the user's exact radius locally. The utilization feed is small and
timestamped. Fresh, plausible CAR utilization becomes verified **live**;
missing/stale/bad utilization leaves the official facility static.

The bundled applicability geometry is generated from Fintraffic's own 256
current car-facility polygons, buffered by 10 km in EPSG:3067.

## Transport for London

Official API: https://api.tfl.gov.uk/
Swagger: https://push-api-nile.tfl.gov.uk/swagger/ui/index.html

Observed:
- "/Place/Type/CarPark" returned HTTP 200 with **58** official car-park Places,
  including WGS84 coordinates, capacity, accessible bays, opening information,
  tariffs and OccupancyUrl.
- "/Occupancy/CarPark" returned HTTP 500.
- "/Occupancy/CarPark/CarParks_800491" also returned HTTP 500.

The provider therefore treats the Place inventory as authoritative static
parking and contains occupancy failure *inside* the provider so it cannot
remove usable facilities. It retries occupancy every five minutes while
nearby TfL facilities exist. If the endpoint recovers, valid bay totals become
**reported** availability: the occupancy schema exposes no producer observation
timestamp, so it is not promoted to verified live.

The bundled applicability geometry is generated from all 58 official TfL
CarPark Place coordinates, buffered by 10 km in EPSG:27700.

## Norway Parkeringsregisteret

Official catalogue:
https://data.norge.no/en/datasets/a0cf9785-601e-4c5b-b19c-74b639b5819a/parkeringsregisteret

The catalogue still describes a public national parking register, but the
published legacy API root and several likely collection paths all returned
HTTP **404** from the probe runner. OSM Parking does **not** ship a Norway
provider until Statens vegvesen exposes or documents a working current machine
endpoint.

## Seoul Open Data

Official current public-parking service:
https://data.seoul.go.kr/dataList/OA-21709/A/1/datasetView.do

Observed with Seoul's documented sample key:
- GetParkingInfo returned HTTP 200 with 122 total realtime city-car-park
  records and fields including total capacity, current parked vehicles,
  producer update timestamp and freshness/status code.
- The documented HTTP endpoint works.
- The HTTPS form on port 8088 failed from the probe runner.

Seoul's official developer guide continues to document the API-key endpoint as
plain HTTP on port 8088. OSM Parking will not transmit a user's private API key
over unencrypted HTTP. Seoul remains a strong candidate if the authority
provides an HTTPS endpoint or another secure official delivery mechanism.

## Reproducibility

Development probes are in "tools/probe_fintraffic_norway_tfl_seoul.py".
Provider applicability coverage can be regenerated with
"tools/generate_provider_facility_coverage.py".
