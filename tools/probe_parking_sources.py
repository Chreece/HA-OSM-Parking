"""Bounded public-data probes, without credentials or external writes."""
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
import json
import time
import urllib.error
import urllib.parse
import urllib.request

OUT=Path('provider-evidence');OUT.mkdir(exist_ok=True)
WFS={'service':'WFS','version':'2.0.0','request':'GetFeature','typeNames':'geonode:zones_stathmeusis','outputFormat':'application/json','srsName':'EPSG:4326','count':'500'}
queries={
'athens_ows':('https://gis.cityofathens.gr/geoserver/ows',WFS),
'athens_wfs':('https://gis.cityofathens.gr/geoserver/wfs',WFS),
'toulouse_v2':('https://data.toulouse-metropole.fr/api/explore/v2.1/catalog/datasets/parcs-de-stationnement/records',{'limit':'100'}),
'toulouse_v1':('https://data.toulouse-metropole.fr/api/records/1.0/search/',{'dataset':'parcs-de-stationnement','rows':'1000'}),
'bordeaux_current':('https://datahub.bordeaux-metropole.fr/api/explore/v2.1/catalog/datasets/st_park_p/records',{'limit':'2'}),
'galway':('https://services-eu1.arcgis.com/Zmea819kt4Uu8kML/arcgis/rest/services/CarParkingOpenData/FeatureServer/0/query',{'where':'1=1','outFields':'*','outSR':'4326','f':'geojson','resultRecordCount':'1000'}),
}


def probe(entry):
    name,(url,params)=entry;start=time.monotonic()
    result={'name':name,'endpoint':url,'checked_at':datetime.now(UTC).isoformat()}
    try:
        request=urllib.request.Request(url+'?'+urllib.parse.urlencode(params),headers={'Accept':'application/json','User-Agent':'HomeAssistant-OSM-Parking-Source-Verification'})
        with urllib.request.urlopen(request,timeout=10) as response:
            result['http_status']=response.status
            raw=response.read(8*1024*1024+1)
            if len(raw)>8*1024*1024:raise ValueError('Size limit')
            data=json.loads(raw)
            result['keys']=list(data)[:30] if isinstance(data,dict) else ['list']
            (OUT/(name+'.json')).write_text(json.dumps(data,ensure_ascii=False,indent=2))
            for field in ('features','results','records'):
                if isinstance(data,dict) and isinstance(data.get(field),list):
                    result['records']=len(data[field]);break
            result['json_read']=True
    except urllib.error.HTTPError as exc:result.update(http_status=exc.code,error_type=type(exc).__name__)
    except Exception as exc:result['error_type']=type(exc).__name__
    result['seconds']=round(time.monotonic()-start,2)
    return result


if __name__=='__main__':
    with ThreadPoolExecutor(max_workers=3) as executor:results=list(executor.map(probe,queries.items()))
    (OUT/'probes.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
    print(json.dumps(results,ensure_ascii=False,indent=2))
