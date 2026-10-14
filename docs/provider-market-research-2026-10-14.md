# Free and commercial parking-provider research — 14 October 2026

This inventory separates **open/public data**, **free developer access with credentials**, and **commercial/partner feeds**. A provider is not enabled merely because a web page or API exists. Before shipping, OSM Parking still requires a stable machine API, usable geographic data, clear reuse terms, bounded requests, and enough timestamp semantics to classify availability honestly.

## 1. Free/open candidates

| Provider | Access / licence | Parking data | Recommended OSM Parking role | Status |
| --- | --- | --- | --- | --- |
| **Ville de Luxembourg** | Key-free JSON; CC BY 4.0 | City garages, total/free spaces, address/accessibility/pricing; publisher says free-space values refresh every minute | Direct live municipal source | **Implemented in v1.7.0** |
| **CFL Luxembourg P+R** | Key-free public JSON + DATEX II | P+R list/details, WGS84 coordinates, total/free/PMR/EV capacity and occupancy | P+R complement to Ville de Luxembourg | **Implemented in v1.7.0 as reported availability** |
| **Basel-Stadt** | Key-free Opendatasoft; CC BY 4.0 / source attribution | Minute-updated garage free spaces, total, status, publication time, coordinates | Direct official source outranks equal ParkenDD duplicate | **Implemented in v1.7.0** |
| **Stadt Zürich Parkleitsystem** | Key-free RSS/XML + official WFS geography | Timestamped free spaces/status joined to 136 public-garage WFS records | Direct official source; ParkenDD remains complementary/fallback | **Implemented in v1.7.0** |
| **Fintraffic LIIPI, Finland** | Public interface, no login needed for data use | Nationwide P+R car facilities plus timestamped utilization | Direct static + verified-live source with facility-derived coverage | **Implemented in v1.8.0** |
| **Statens vegvesen Parkeringsregisteret, Norway** | Catalogue says public JSON / Norwegian Open Government Data licence | Nationwide registered parking areas/operators | National static coverage | **Deferred**: published legacy API and likely collection paths returned HTTP 404 on 14 Oct 2026 |
| **TfL Unified API, London** | Anonymous public use currently limited to 50 req/min; registration raises quota | 58 geocoded CarPark Places; optional bay occupancy | Static direct source + reported occupancy fallback | **Implemented in v1.8.0**; occupancy endpoint was HTTP 500 during probes and has no producer timestamp |
| **Seoul Open Data** | Free issued OpenAPI key | Separate static and real-time parking services with producer timestamp/freshness status | Strong credentialed official source | **Deferred for security**: official key endpoint is plaintext HTTP:8088; HTTPS probe failed |
| **Toulouse, Bordeaux, Galway** | Municipal/council open data | Static facilities and selected live/technical datasets already documented in the existing research files | Continue schema-specific work | Existing backlog |

### Free/open evidence

- Luxembourg City open-data portal: https://data.public.lu/en/datasets/mobilite-emplacements-de-parking-libres/
- Luxembourg City feed: https://feed.vdl.lu/circulation/parking/feed.json
- CFL P+R open data: https://data.public.lu/en/datasets/liste-des-p-r-cfl/
- Basel live occupancy: https://data.bs.ch/explore/dataset/100088/
- Zürich PLS realtime feed catalogue: https://data.stadt-zuerich.ch/dataset/parkleitsystem
- Fintraffic LIIPI documentation: https://parking.fintraffic.fi/docs/index.html
- Fintraffic service description: https://www.fintraffic.fi/en/digitalservices/Traffic-and-Public-Transport-Data-Services/information-service-park-and-ride-facilities-liipi
- Norway national parking register: https://data.norge.no/en/datasets/a0cf9785-601e-4c5b-b19c-74b639b5819a/parkeringsregisteret
- TfL Unified API: https://api.tfl.gov.uk/ and Occupancy/CarPark
- Seoul parking OpenAPI: https://data.seoul.go.kr/dataList/openApiView.do?infId=OA-13122&srvType=A

## 2. Free developer / mixed commercial-access APIs

These are not the same as unrestricted open data.

| Provider | Access model | Useful data | Caveat |
| --- | --- | --- | --- |
| **ParkWhiz v4** | Documentation describes a free API, OAuth2 access | Search, bookable parking locations, pricing and availability; sandbox available | Non-bookable inventory/drive-up rates require a licence; production scopes/partnership requirements need confirmation |
| **TfL registered product** | Free developer registration | Same Unified API with higher quota (500 req/min product advertised) | London/supported TfL coverage, not a general UK parking database |
| **Seoul OpenAPI** | Free API key issued by city portal | Official public parking and freshness-status fields | Per-key quotas/terms need normal credential handling |

ParkWhiz references:
- https://developer.parkwhiz.com/getting_started/
- https://developer.parkwhiz.com/v4/
- https://partners.parkwhiz.com/docs/technology-overview/apis/

## 3. Commercial / partner parking data

These should be optional providers only after the user supplies their own contracted credentials. OSM Parking must not proxy, scrape, or redistribute data outside the provider's licence.

| Provider | Commercial model | Data available | Integration assessment |
| --- | --- | --- | --- |
| **Parkopedia** | Contact-sales/licensed B2B API/feed | Global static off/on-street POIs, prices/hours/restrictions; dynamic occupancy/probability; payments | Excellent broad-coverage paid option. Build only with a documented customer API contract and attribution/caching rules |
| **INRIX Parking Services** | Credentials requested from INRIX; commercial parking platform | Off-street lots, on-street blocks/rules, rates, actual/predicted occupancy and probability | Excellent paid option; the legacy Occupancy API is deprecated, so target current IPS 3.0 contract only |
| **TomTom Parking API** | Sales/request-access; explicitly **not** in free evaluation or PAYG | Off-street availability/free spaces/trend/timestamp; parking prices; on-street parking probability | Strong automotive paid option. Current docs label portions Automotive-only/private preview; not suitable as a default public integration |
| **ParkBee Partner API** | Commercial partnership / onboarding | European locations, live availability/occupancy and live pricing; sandbox/docs through partnership | Good European paid/partner option, especially NL/BE/DE/UK |
| **Passport** | Partner ecosystem | Municipal parking rules/rates/zones/restrictions and payments across many client cities | Useful paid/partner rules/payment source; public material does not establish generic live bay availability |
| **EasyPark API** | Subscriber/authorized-partner agreement and API credentials | Parking/payment ecosystem and partner integrations | Commercial/contract-only. Do not treat as public parking data without explicit agreement |

Commercial evidence:
- Parkopedia parking data/API: https://business.parkopedia.com/parking-data
- Parkopedia mobility/API/feed: https://business.parkopedia.com/mobility
- INRIX docs: https://docs.inrix.com/ and https://docs.inrix.com/parking/lots/
- TomTom Parking API: https://docs.tomtom.com/parking-api/documentation/product-information/introduction
- TomTom availability restriction: https://docs.tomtom.com/parking-availability-api/documentation/parking-availability-api/parking-availability
- ParkBee partners: https://business.parkbee.com/en/for-partners/parking-apps
- ParkBee pricing/partner model: https://business.parkbee.com/en/pricing
- Passport developers: https://www.passportinc.com/resources/developers/
- EasyPark API policy: https://developer.easyparkgroup.com/EasyPark_SaaS_API_Acceptable_Use_Policy_2021_1_EN.pdf

## 4. Priority order

### Free/open
1. **Bordeaux** — qualify the current direct availability semantics/timestamps before enabling live counts.
2. **Galway** — official ArcGIS static facilities/capacity once current schema is revalidated.
3. **Norway Parkeringsregisteret** — wait for a working current machine endpoint from Statens vegvesen.
4. **Seoul** — wait for an official HTTPS API-key transport (or other secure delivery) before accepting user credentials.

### Commercial
1. **Parkopedia** — broadest global static/dynamic option if a user has a licence.
2. **INRIX Parking Services 3.0** — rich lots/rules/occupancy and predictions.
3. **ParkBee** — strong European live supply/pricing partner source.
4. **TomTom** — technically excellent, but current parking APIs are sales-gated/automotive-only.
5. **ParkWhiz** — useful North American search/booking source; separate free/public scope from licensed non-bookable data.
6. **Passport / EasyPark** — partnership-centric payment/rules integrations, not default public discovery feeds.

## 5. Duplicate/fallback policy

Adding more providers should **not** mean blindly returning more copies:

1. Direct municipal/operator data with a valid producer timestamp can outrank aggregator data for the same facility.
2. Aggregators such as ParkenDD remain useful when the direct municipal feed is absent or unavailable and for cities without a dedicated adapter.
3. Equivalent endpoints exposing the *same dataset* are sequential fallbacks, not separate providers.
4. Independent sources with overlapping coverage are queried independently and merged only when the facility match is strong.
5. Exact free-space measurements outrank reported/estimated/predicted/static values according to the existing quality model.
6. Commercial providers must never silently replace open data solely because they are paid; quality/freshness and user configuration determine the winner.

## 6. Coverage geometry policy

Where an authority publishes an authoritative service-area/country boundary, provider applicability should use a **bundled, source-attributed geometry** generated during development instead of a hand-written rectangle. The runtime must remain offline for this decision.

The first implementation is Netherlands RDW:

- source: Kadaster/PDOK **BRK Bestuurlijke Gebieden – Landgebied**;
- authority: Kadaster via PDOK;
- licence: CC BY 4.0;
- source API: https://api.pdok.nl/kadaster/brk-bestuurlijke-gebieden/ogc/v1
- official geometry is transformed to RD New, buffered by 10 km (the integration's maximum search radius), simplified with topology preservation, transformed back to WGS84, and shipped as GeoJSON;
- the unbuffered derived geometry is also retained for provenance/tests;
- no runtime call to PDOK is required to decide whether RDW should run.

This same mechanism can be reused for future national or contractual coverage polygons when the publisher exposes authoritative geometry.
