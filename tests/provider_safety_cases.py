"""Fault injection against real provider/coordinator code, with isolated HA stubs."""
from pathlib import Path
import asyncio
from datetime import UTC, datetime
import json
import sys
import types
import unittest
from unittest.mock import patch, AsyncMock

ROOT=Path(__file__).resolve().parents[1]
PKG=ROOT/'custom_components/osm_parking'
for name,directory in [('custom_components',PKG.parent),('custom_components.osm_parking',PKG)]:
    m=types.ModuleType(name);m.__path__=[str(directory)];sys.modules[name]=m
ah=types.ModuleType('aiohttp')
ah.ClientError=type('ClientError',(Exception,),{})
ah.ClientSession=type('ClientSession',(),{})
sys.modules['aiohttp']=ah
for name in ('homeassistant','homeassistant.helpers','homeassistant.config_entries','homeassistant.core','homeassistant.helpers.aiohttp_client','homeassistant.helpers.update_coordinator'):
    m=types.ModuleType(name);m.__path__=[];sys.modules[name]=m
sys.modules['homeassistant.config_entries'].ConfigEntry=types.SimpleNamespace
sys.modules['homeassistant.core'].HomeAssistant=types.SimpleNamespace
sys.modules['homeassistant.core'].callback=lambda f:f
sys.modules['homeassistant.helpers.aiohttp_client'].async_get_clientsession=lambda h:h.session
class CoordinatorBase:
    @classmethod
    def __class_getitem__(cls,_):return cls
    def __init__(self,hass,**kwargs):
        self.hass=hass;self.last_update_success=True;self.data={};self.update_interval=None;self._listeners=[]
    def _async_unsub_refresh(self):pass
    def _schedule_refresh(self):pass
sys.modules['homeassistant.helpers.update_coordinator'].DataUpdateCoordinator=CoordinatorBase
sys.modules['homeassistant.helpers.update_coordinator'].UpdateFailed=type('UpdateFailed',(Exception,),{})
from custom_components.osm_parking import provider_runtime as runtime
from custom_components.osm_parking import coordinator
from custom_components.osm_parking import providers as registry
from custom_components.osm_parking.providers import athens_zones as athens
from custom_components.osm_parking.providers import toulouse
from custom_components.osm_parking.providers.resilient_http import Endpoint, EndpointPool
from custom_components.osm_parking.providers.base import ProviderFetchResult as Result


def row(provider='healthy',**changes):
    return dict(provider=provider,provider_id=provider+':1',name='Central Garage',latitude=37.98,longitude=23.73,category='underground',fee='unknown',availability_kind='static',**changes)


def zone():
    return {'type':'Feature','geometry':{'type':'Polygon','coordinates':[[[23.728,37.978],[23.74,37.978],[23.74,37.985],[23.728,37.985],[23.728,37.978]]]},'properties':{'name':'Zone A','record_type':'zone'}}


class Provider:
    def __init__(self,uid='healthy',value=None,fail=None,applies_fail=False):
        self.uid=uid;self.value=value if value is not None else Result(uid,[row(uid)])
        self.fail=fail;self.applies_fail=applies_fail;self.calls=0
    def applies(self,lat,lon):
        if self.applies_fail:raise ValueError('SECRET in eligibility')
        return True
    async def async_fetch(self,*args):
        self.calls+=1
        if self.fail:raise self.fail
        return self.value


class Response:
    def __init__(self,value=None,status=200,raw=None,headers=None):
        self.status=status;self.headers=headers or {};self.body=raw if raw is not None else json.dumps(value).encode();self.content=self
    async def __aenter__(self):return self
    async def __aexit__(self,*args):pass
    async def iter_chunked(self,_):yield self.body
    def raise_for_status(self):
        if self.status>=400:raise ah.ClientError('HTTP error SECRET')
    async def json(self,**_):return json.loads(self.body)
    async def text(self):return self.body.decode()


class Session:
    def __init__(self,*responses):self.responses=list(responses);self.calls=[]
    def get(self,url,**kwargs):
        self.calls.append((url,kwargs))
        if not self.responses:raise AssertionError('Unexpected network request')
        return self.responses.pop(0)
    post=get


class Safety(unittest.IsolatedAsyncioTestCase):
    async def fetch(self,*providers):
        s=runtime.ProviderSupervisor();r=await s.fetch(providers,None,37.98,23.73,1000,{})
        return s,r

    async def test_exception_and_eligibility_failures_leave_healthy_results(self):
        for bad in [Provider('bad',fail=ValueError('SECRET')),Provider('bad',applies_fail=True)]:
            s,r=await self.fetch(bad,Provider())
            self.assertEqual([v.provider for v in r],['healthy'])
            self.assertIn('bad',s.errors);self.assertNotIn('SECRET',str(s.errors))

    async def test_malformed_response_does_not_abort(self):
        for bad in [None,{},'text',Result('bad',None),Result('bad',[],zones={})]:
            p=Provider('bad');p.value=bad
            s,r=await self.fetch(p,Provider())
            self.assertEqual(len(r),1);self.assertIn('bad',s.errors)

    async def test_one_bad_record_retains_good_record(self):
        s,r=await self.fetch(Provider(value=Result('healthy',[None,{},row(),row('bad',data_sources=3)])))
        self.assertEqual(len(r[0].suggestions),1)

    async def test_only_bad_records_is_failure_not_empty_coverage(self):
        s,r=await self.fetch(Provider(value=Result('healthy',[None,{}])))
        self.assertEqual(r,[]);self.assertIn('healthy',s.errors)

    async def test_empty_response_is_not_failure_or_polling(self):
        s,r=await self.fetch(Provider(value=Result('healthy',[],300)))
        self.assertIsNone(r[0].live_refresh_seconds);self.assertIsNone(s.retry_seconds)
        self.assertEqual(s.status['healthy']['status'],'no_coverage')

    async def test_timeout_does_not_hold_healthy_results_indefinitely(self):
        class Slow(Provider):
            fetch_timeout=.02
            async def async_fetch(self,*args):await asyncio.sleep(20)
        s,r=await asyncio.wait_for(self.fetch(Slow('slow'),Provider()),.3)
        self.assertEqual(len(r),1);self.assertEqual(s.status['slow']['error_type'],'TimeoutError')

    async def test_cancellation_is_not_a_provider_failure(self):
        class Cancelled(Provider):
            async def async_fetch(self,*args):raise asyncio.CancelledError
        with self.assertRaises(asyncio.CancelledError):await self.fetch(Cancelled())

    async def test_backoff_prevents_storm_and_recovery_resets(self):
        p=Provider('bad',fail=ValueError('SECRET'));s=runtime.ProviderSupervisor()
        await s.fetch([p],None,37.98,23.73,1000,{})
        self.assertEqual(p.calls,1);self.assertEqual(s.retry_seconds,60)
        await s.fetch([p],None,37.98,23.73,1000,{})
        self.assertEqual(p.calls,1);self.assertEqual(s.status['bad']['status'],'cooldown')
        for expected in (300,1800,21600):
            s._failures['bad'].retry_at=0
            await s.fetch([p],None,37.98,23.73,1000,{})
            self.assertEqual(s.retry_seconds,expected)
        p.fail=None;s._failures['bad'].retry_at=0
        await s.fetch([p],None,37.98,23.73,1000,{})
        self.assertIsNone(s.retry_seconds);self.assertNotIn('bad',s._failures)

    async def test_credential_gate_and_entry_isolation(self):
        p=Provider();p.required_options=('key',)
        s,r=await self.fetch(p);self.assertEqual(p.calls,0);self.assertEqual(s.errors,{})
        await runtime.ProviderSupervisor().fetch([p],None,37.98,23.73,1000,{'key':'secret'})
        self.assertEqual(p.calls,1)

    async def test_defensive_distance_category_interval(self):
        raw=row(distance_m='garbage');raw['category']=None
        result=runtime.clean_result(Result('p',[raw],float('nan')),'p',37.98,23.73,1000)
        self.assertEqual(result.suggestions[0]['distance_m'],0)
        self.assertEqual(result.suggestions[0]['category'],'other');self.assertIsNone(result.live_refresh_seconds)

    async def test_invalid_geography_and_static_vacancy_not_displayed(self):
        bad=row();bad['latitude']=float('nan')
        result=runtime.clean_result(Result('p',[bad,row(free_capacity=42)]),'p',37.98,23.73,1000)
        self.assertEqual(len(result.suggestions),1);self.assertNotIn('free_capacity',result.suggestions[0])

    async def test_merge_failure_is_atomic(self):
        s=runtime.ProviderSupervisor();prior=[row()]
        with patch.object(runtime,'merge_facilities',side_effect=ValueError('SECRET')):
            self.assertIs(s.merge(prior,Result('bad',[row('bad')])),prior)
        self.assertIn('bad',s.errors);self.assertNotIn('SECRET',str(s.errors))

    async def test_live_winner_fails_then_healthy_duplicate_takes_over(self):
        a=row('city',free_capacity=8,realtime_updated_at=datetime.now(UTC).isoformat());a['availability_kind']='live'
        b=row('backup',free_capacity=25);b['availability_kind']='reported'
        primary=Provider('city',Result('city',[a]));backup=Provider('backup',Result('backup',[b]));s=runtime.ProviderSupervisor()
        async def selected():
            merged=[]
            for result in await s.fetch([primary,backup],None,37.98,23.73,1000,{}):merged=s.merge(merged,result)
            return merged
        first=await selected();self.assertEqual(len(first),1);self.assertEqual(first[0]['free_capacity'],8)
        primary.fail=ValueError('offline')
        second=await selected();self.assertEqual(len(second),1);self.assertEqual(second[0]['free_capacity'],25)
        self.assertEqual(second[0]['availability_kind'],'reported')

    async def test_equivalent_fallback_only_on_failure(self):
        endpoints=(Endpoint('https://city.example/v2',{}),Endpoint('https://city.example/v1',{}))
        pool=EndpointPool(endpoints);session=Session(Response({'rows':[1]}))
        self.assertEqual(await pool.fetch(session,lambda p:p['rows']),[1]);self.assertEqual(len(session.calls),1)
        session=Session(Response(status=503),Response({'rows':[2]}))
        self.assertEqual(await pool.fetch(session,lambda p:p['rows']),[2]);self.assertEqual(len(session.calls),2)
        self.assertEqual(pool.last_source,endpoints[1].url)

    async def test_http_200_invalid_schema_uses_fallback(self):
        pool=EndpointPool((Endpoint('https://city.example/v2',{}),Endpoint('https://city.example/v1',{})))
        self.assertEqual(await pool.fetch(Session(Response({}),Response({'rows':[2]})),lambda p:p['rows']),[2])

    async def test_429_is_not_bypassed_via_alternate_route(self):
        pool=EndpointPool((Endpoint('https://city.example/v2',{}),Endpoint('https://city.example/v1',{})))
        session=Session(Response(status=429,headers={'Retry-After':'600'}))
        with self.assertRaises(RuntimeError):await pool.fetch(session,lambda p:p)
        self.assertEqual(len(session.calls),1)
        with self.assertRaises(RuntimeError):await pool.fetch(session,lambda p:p)
        self.assertEqual(len(session.calls),1)

    async def test_athens_automatic_even_with_old_flag_false(self):
        provider=athens.AthensParkingZonesProvider();session=Session(Response({'type':'FeatureCollection','features':[zone()]}));s=runtime.ProviderSupervisor()
        results=await s.fetch([provider],session,37.98,23.73,1000,{'athens_zones_enabled':False})
        self.assertEqual(len(results[0].zones),1);self.assertEqual(results[0].suggestions,[])
        self.assertFalse(hasattr(provider,'enabled_option'))
        await s.fetch([provider],session,37.98,23.73,1000,{})
        self.assertEqual(len(session.calls),1)

    async def test_athens_not_contacted_outside_region(self):
        s=runtime.ProviderSupervisor();session=Session()
        self.assertEqual(await s.fetch([athens.AthensParkingZonesProvider()],session,50.9,6.9,1000,{}),[])
        self.assertEqual(session.calls,[])

    async def test_athens_primary_failure_uses_valid_wfs_fallback(self):
        p=athens.AthensParkingZonesProvider();session=Session(Response(status=502),Response({'type':'FeatureCollection','features':[zone()]}));s=runtime.ProviderSupervisor()
        results=await s.fetch([p],session,37.98,23.73,1000,{})
        self.assertEqual(len(results[0].zones),1);self.assertTrue(s.status[p.uid]['fallback_used'])

    async def test_expired_athens_cache_not_extended_after_failed_refresh(self):
        p=athens.AthensParkingZonesProvider();p._cache=[zone()];p._loaded_at=-999999
        results=await runtime.ProviderSupervisor().fetch([p],Session(Response({}),Response({})),37.98,23.73,1000,{})
        self.assertEqual(results,[]);self.assertEqual(p._loaded_at,-999999)

    async def test_invalid_zones_projection_and_wrong_city(self):
        for change in ('open','utm','nan','wrong-city','point','degenerate'):
            z=zone();ring=z['geometry']['coordinates'][0]
            if change=='open':ring.pop()
            if change=='utm':ring[0]=[400000,4000000]
            if change=='nan':ring[0][0]=float('nan')
            if change=='wrong-city':z['geometry']['coordinates']=[[[1,43],[2,43],[2,44],[1,43]]]
            if change=='point':z['geometry']['type']='Point'
            if change=='degenerate':z['geometry']['coordinates']=[[[23.73,37.98]]*4]
            self.assertIsNone(athens._normalize(z,athens.ATHENS_BOUNDS),change)
        for p in ({'type':'FeatureCollection','features':[]},{'type':'FeatureCollection','features':[zone()],'crs':{'properties':{'name':'EPSG:2100'}}}):
            with self.assertRaises(ValueError):athens._catalog(p)

    async def test_toulouse_equivalent_formats_one_dataset(self):
        r={'id':'31555-P-1','nom':'Capitole','ylat':43.60,'xlong':1.44,'nb_places':250}
        v2=toulouse.ToulouseParkingProvider._catalog({'results':[r],'total_count':1})
        v1=toulouse.ToulouseParkingProvider._catalog({'records':[{'fields':r}],'nhits':1})
        self.assertEqual(v2,v1)
        item=toulouse.ToulouseParkingProvider._normalize(r,43.6,1.44,1000)
        self.assertEqual(item['provider'],'toulouse_bnls');self.assertNotIn('free_capacity',item)
        with self.assertRaises(ValueError):toulouse.ToulouseParkingProvider._catalog({'results':[r],'total_count':101})

    async def test_import_failure_preserves_other_providers(self):
        good=types.SimpleNamespace(Provider=lambda:Provider())
        with patch.object(registry,'import_module',side_effect=[ImportError('SECRET'),good]):
            providers,errors=registry.load_providers((('bad','Provider'),('good','Provider')))
        self.assertEqual(len(providers),1);self.assertEqual(errors,{'bad':'ImportError'})

    async def test_constructor_failure_preserves_other_providers(self):
        bad=types.SimpleNamespace(Provider=lambda:(_ for _ in ()).throw(ValueError('SECRET')));good=types.SimpleNamespace(Provider=lambda:Provider())
        with patch.object(registry,'import_module',side_effect=[bad,good]):
            providers,errors=registry.load_providers((('bad','Provider'),('good','Provider')))
        self.assertEqual(len(providers),1);self.assertEqual(errors,{'bad':'ValueError'})

    async def test_all_shipped_providers_load(self):
        self.assertEqual(registry.PROVIDER_LOAD_ERRORS,{})
        self.assertEqual(len(registry.PROVIDERS),31)

    def coordinator(self):
        state=types.SimpleNamespace(state='Athens',attributes={'latitude':37.98,'longitude':23.73})
        hass=types.SimpleNamespace(states=types.SimpleNamespace(get=lambda _:state),session=Session(),is_stopping=False)
        return coordinator.OsmParkingCoordinator(hass,types.SimpleNamespace(data={'destination_entity':'sensor.dest'},options={}))

    async def test_coordinate_action_search_is_read_only_and_uses_separate_supervisor(self):
        c = self.coordinator()
        c.data = {"sentinel": "sensor-state"}
        c.update_interval = None
        c._query_overpass = AsyncMock(return_value=({
            "elements": [
                {
                    "type": "node",
                    "id": 77,
                    "lat": 37.98,
                    "lon": 23.73,
                    "tags": {
                        "amenity": "parking",
                        "parking": "underground",
                    },
                },
                {
                    "type": "node",
                    "id": 78,
                    "lat": 37.981,
                    "lon": 23.731,
                    "tags": {
                        "amenity": "parking",
                        "parking": "surface",
                    },
                },
            ]
        }, "osm"))
        before_sensor_status = dict(c._provider_supervisor.status)
        with patch.object(coordinator, "PROVIDERS", []):
            result = await c.async_search_coordinates(
                37.98,
                23.73,
                radius_m=1000,
                parking_types=["underground"],
                max_results=2,
                include_restricted=False,
            )
        self.assertEqual(len(result["suggestions"]), 1)
        self.assertEqual(result["suggestions"][0]["category"], "underground")
        self.assertEqual(result["parking_types"], ["underground"])
        self.assertEqual(c.data, {"sentinel": "sensor-state"})
        self.assertIsNone(c.update_interval)
        self.assertEqual(c._provider_supervisor.status, before_sensor_status)

    async def test_real_coordinator_bad_provider_keeps_osm(self):
        c=self.coordinator();raw={'elements':[None,{'type':'node','id':3,'lat':37.98,'lon':23.73,'tags':{'amenity':'parking'}}]}
        c._query_overpass=AsyncMock(return_value=(raw,'osm'))
        with patch.object(coordinator,'PROVIDERS',[Provider('bad',fail=ValueError('SECRET'))]):data=await c._async_update_data()
        self.assertEqual(data['status'],'ok');self.assertEqual(len(data['suggestions']),1)
        self.assertTrue(data['partial_data']);self.assertNotIn('SECRET',str(data));self.assertLessEqual(data['live_refresh_seconds'],60)

    async def test_real_coordinator_bad_overpass_keeps_municipality(self):
        c=self.coordinator();c._query_overpass=AsyncMock(return_value=({'error':'oops'},'osm'))
        with patch.object(coordinator,'PROVIDERS',[Provider()]):data=await c._async_update_data()
        self.assertEqual(data['status'],'ok');self.assertEqual(len(data['suggestions']),1)

    async def test_real_coordinator_static_recovery_stops_polling(self):
        c=self.coordinator();c._query_overpass=AsyncMock(return_value=({'elements':[]},'osm'));p=Provider('bad',fail=ValueError())
        with patch.object(coordinator,'PROVIDERS',[p]):first=await c._async_update_data()
        self.assertIsNotNone(first['live_refresh_seconds']);p.fail=None;c._provider_supervisor._failures['bad'].retry_at=0
        with patch.object(coordinator,'PROVIDERS',[p]):second=await c._async_update_data()
        self.assertIsNone(second['live_refresh_seconds']);self.assertFalse(second['partial_data'])

    async def test_real_coordinator_all_sources_failed_reports_failure(self):
        c=self.coordinator();c._query_overpass=AsyncMock(side_effect=TimeoutError())
        with patch.object(coordinator,'PROVIDERS',[Provider('bad',fail=ValueError())]):
            with self.assertRaises(coordinator.UpdateFailed):await c._async_update_data()

    async def test_overpass_bad_payload_uses_next_mirror(self):
        c=self.coordinator();c.hass.session=Session(Response({'oops':'x'}),Response({'elements':[{'type':'node','id':1}]}))
        p,url=await c._query_overpass(37.98,23.73,1000)
        self.assertEqual(len(c.hass.session.calls),2);self.assertEqual(url,coordinator.OVERPASS_ENDPOINTS[1])

    async def test_nonfinite_destination_waits_without_requests(self):
        c=self.coordinator();c.hass.states.get('x').attributes['latitude']=float('nan');c._query_overpass=AsyncMock()
        data=await c._async_update_data();self.assertEqual(data['status'],'waiting');c._query_overpass.assert_not_called()

    async def test_ui_has_no_manual_gis_switch(self):
        for p in [PKG/'strings.json',*(PKG/'translations').glob('*.json')]:
            data=json.loads(p.read_text())
            for section in ('config','options'):self.assertNotIn('athens_zones_enabled',data[section]['step']['categories']['data'])
        greek=json.loads((PKG/'translations/el.json').read_text())
        self.assertTrue(all('Συμπερίληψη' not in v for v in greek['selector']['parking_types']['options'].values()))


if __name__=='__main__':unittest.main(verbosity=2)
