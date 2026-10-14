#!/usr/bin/env python3
"""Read-only schema probes for next parking providers."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request

OUT=Path("provider-evidence-next2"); OUT.mkdir(exist_ok=True)
UA="HomeAssistant-OSM-Parking-Provider-Probe/1.0"


def fetch(name,url,*,headers=None,limit=8*1024*1024):
    result={"name":name,"url":url,"checked_at":datetime.now(UTC).isoformat()}
    try:
        req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"application/json",**(headers or {})})
        with urllib.request.urlopen(req,timeout=25) as response:
            result["http_status"]=response.status
            result["content_type"]=response.headers.get_content_type()
            raw=response.read(limit+1)
            if len(raw)>limit: raise ValueError("response_too_large")
            (OUT/f"{name}.bin").write_bytes(raw)
            result["bytes"]=len(raw)
            try:
                payload=json.loads(raw)
                result["json"]=True
                result["root_type"]=type(payload).__name__
                if isinstance(payload,dict):
                    result["keys"]=sorted(payload)[:80]
                    for key in ("results","features","row","GetParkInfo"):
                        value=payload.get(key)
                        if isinstance(value,list): result["records"]=len(value)
                        elif isinstance(value,dict): result[f"{key}_keys"]=sorted(value)[:80]
                elif isinstance(payload,list):
                    result["records"]=len(payload)
                    if payload and isinstance(payload[0],dict):
                        result["sample_keys"]=sorted(payload[0])[:120]
            except Exception:
                result["json"]=False
                result["head"]=raw[:700].decode("utf-8","replace")
            result["ok"]=True
    except urllib.error.HTTPError as exc:
        result.update(ok=False,http_status=exc.code,error_type="HTTPError")
        try:
            body=exc.read(2000)
            result["error_head"]=body.decode("utf-8","replace")
        except Exception: pass
    except Exception as exc:
        result.update(ok=False,error_type=type(exc).__name__)
    return result


def main():
    out=[]
    # Fintraffic: spatial facility search near Helsinki + all current utilizations.
    params=urllib.parse.urlencode({
        "geometry":"POINT(24.9384 60.1699)",
        "maxDistance":"10000",
        "limit":"100",
    })
    out.append(fetch("fintraffic_facilities",f"https://parking.fintraffic.fi/api/v1/facilities?{params}",headers={"Digitraffic-User":"ha-osm-parking"}))
    out.append(fetch("fintraffic_utilizations","https://parking.fintraffic.fi/api/v1/utilizations",headers={"Digitraffic-User":"ha-osm-parking"}))
    out.append(fetch("fintraffic_facilities_all","https://parking.fintraffic.fi/api/v1/facilities?limit=-1",headers={"Digitraffic-User":"ha-osm-parking"}))
    out.append(fetch("fintraffic_facilities_geojson","https://parking.fintraffic.fi/api/v1/facilities.geojson?limit=-1",headers={"Digitraffic-User":"ha-osm-parking"}))
    out.append(fetch("fintraffic_facility_268","https://parking.fintraffic.fi/api/v1/facilities/268",headers={"Digitraffic-User":"ha-osm-parking"}))
    out.append(fetch("fintraffic_utilization_268","https://parking.fintraffic.fi/api/v1/facilities/268/utilization",headers={"Digitraffic-User":"ha-osm-parking"}))

    # Statens vegvesen register: base + likely public collection routes.
    base="https://www.vegvesen.no/ws/no/vegvesen/veg/parkeringsomraade/parkeringsregisteret/v1"
    for suffix in ("","/","/parkeringsomraader","/parkeringsomrade","/parkeringsomrader","/parkingAreas"):
        out.append(fetch("norway_"+(suffix.strip("/").replace("/","_") or "base"),base+suffix))

    # TfL anonymous public API: live occupancy + authoritative Place geometry.
    out.append(fetch("tfl_occupancy","https://api.tfl.gov.uk/Occupancy/CarPark"))
    out.append(fetch("tfl_places","https://api.tfl.gov.uk/Place/Type/CarPark"))
    out.append(fetch("tfl_occupancy_800491","https://api.tfl.gov.uk/Occupancy/CarPark/CarParks_800491"))

    # Seoul official sample key is documented for max five rows.
    out.append(fetch("seoul_sample","http://openapi.seoul.go.kr:8088/sample/json/GetParkInfo/1/5/"))
    out.append(fetch("seoul_realtime_sample","http://openapi.seoul.go.kr:8088/sample/json/GetParkingInfo/1/5/"))

    (OUT/"summary.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(out,ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
