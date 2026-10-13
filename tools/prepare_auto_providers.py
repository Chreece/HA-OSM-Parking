"""One-time, local-only source transformation on the reviewed release branch."""
from pathlib import Path
import ast
import json
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
PKG=ROOT/'custom_components/osm_parking'


def edit(path, old, new):
    text=path.read_text()
    if text.count(old)!=1:
        raise RuntimeError(f'Expected one patch target in {path}: {old[:100]}')
    path.write_text(text.replace(old,new),encoding='utf-8')


registry=PKG/'providers/__init__.py'
tree=ast.parse(registry.read_text())
imports={alias.name:node.module for node in tree.body if isinstance(node,ast.ImportFrom) for alias in node.names}
classes=next(node.value.elts for node in tree.body if isinstance(node,ast.AnnAssign) and getattr(node.target,'id','')=='PROVIDERS')
specs=[(imports[call.func.id],call.func.id) for call in classes]
specs.append(('toulouse','ToulouseParkingProvider'))
registry.write_text('''"""Load optional providers independently; broken modules cannot prevent setup."""
from importlib import import_module
import logging
from .base import ParkingProvider, ProviderFetchResult
_LOGGER=logging.getLogger(__name__)
PROVIDER_SPECS='''+repr(tuple(specs))+'''


def load_providers(specs=PROVIDER_SPECS):
    providers,errors=[],{}
    for module,class_name in specs:
        try:
            factory=getattr(import_module('.'+module,__name__),class_name)
            providers.append(factory())
        except Exception as exc:
            errors[module]=type(exc).__name__
            _LOGGER.warning('Parking provider %s unavailable (%s)',module,type(exc).__name__)
    return tuple(providers),errors


PROVIDERS,PROVIDER_LOAD_ERRORS=load_providers()
__all__=['PROVIDERS','PROVIDER_LOAD_ERRORS','ParkingProvider','ProviderFetchResult']
''',encoding='utf-8')

flow=PKG/'config_flow.py'
edit(flow,'\n    CONF_ATHENS_ZONES_ENABLED,\n','\n')
edit(flow,'''        vol.Required(
            CONF_ATHENS_ZONES_ENABLED,
            default=bool(settings.get(CONF_ATHENS_ZONES_ENABLED, False)),
        ): selector.BooleanSelector(),
''','')
edit(flow,'''                self._pending[CONF_ATHENS_ZONES_ENABLED] = bool(
                    user_input.get(CONF_ATHENS_ZONES_ENABLED, False)
                )''','''                # Public GIS usability is automatic, not a manual provider switch.
                self._pending.pop("athens_zones_enabled", None)''')

copy={
'en':'Select one or more parking categories and the maximum results per category. You can also include restricted/private parking.',
'el':'Επίλεξε έναν ή περισσότερους τύπους στάθμευσης και το μέγιστο πλήθος προτάσεων ανά τύπο. Προαιρετικά συμπεριέλαβε ιδιωτικούς ή περιορισμένους χώρους.',
'de':'Wähle mindestens eine Parkplatzart und die maximale Anzahl pro Kategorie. Private oder eingeschränkte Plätze sind optional.',
'fr':'Choisissez un ou plusieurs types de parking et le maximum par catégorie. Les parkings privés ou à accès limité sont facultatifs.',
'es':'Elige uno o más tipos de aparcamiento y el máximo por categoría. Puedes incluir plazas privadas o de acceso restringido.',
'it':'Scegli uno o più tipi di parcheggio e il massimo per categoria. Puoi includere parcheggi privati o ad accesso limitato.',
'nl':'Kies minimaal één parkeersoort en de limiet per categorie. Privéparkeerplaatsen zijn optioneel.',
'pl':'Wybierz rodzaje parkingów i limit wyników dla każdej kategorii. Miejsca prywatne lub z ograniczonym dostępem są opcjonalne.',
'pt':'Selecione os tipos de estacionamento e o máximo por categoria. Os parques privados ou restritos são opcionais.',
'pt-BR':'Selecione os tipos de estacionamento e o limite por categoria. Vagas privadas ou restritas são opcionais.',
'ru':'Выберите типы парковок и лимит для каждой категории. Частные парковки и места с ограниченным доступом можно включить отдельно.',
'tr':'Otopark türlerini ve kategori başına sonuç sınırını seçin. Özel veya kısıtlı park yerleri isteğe bağlıdır.',
'zh-Hans':'选择停车类型和每类结果上限，也可包含私人或限制进入的停车位。',
'ja':'駐車場の種類と種類ごとの最大件数を選びます。私有・利用制限のある駐車場も任意で含められます。',
}
short={
'en':['Paid parking','Surface parking','Street parking','Underground','Multi-storey','Park & Ride','Other'],
'el':['Επί πληρωμή','Υπαίθριο πάρκινγκ','Στον δρόμο','Υπόγειο πάρκινγκ','Πολυώροφο πάρκινγκ','Park & Ride','Άλλο'],
'de':['Kostenpflichtig','Oberirdisch','Straßenparken','Tiefgarage','Parkhaus','Park & Ride','Sonstige'],
}
for path in [PKG/'strings.json',*(PKG/'translations').glob('*.json')]:
    locale='en' if path.name=='strings.json' else path.stem
    data=json.loads(path.read_text())
    for section in ('config','options'):
        step=data[section]['step']['categories']
        step['data'].pop('athens_zones_enabled',None)
        step.get('data_description',{}).pop('athens_zones_enabled',None)
        if not step.get('data_description'):step.pop('data_description',None)
        step['description']=copy[locale]
    if locale in short:
        data['selector']['parking_types']['options']=dict(zip(['paid','open','street','underground','multi_storey','park_and_ride','other'],short[locale]))
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

coord=PKG/'coordinator.py'
edit(coord,'import asyncio\n','import asyncio\nimport json\n')
edit(coord,'from .providers import PROVIDERS, ProviderFetchResult','from .providers import PROVIDERS, PROVIDER_LOAD_ERRORS, ProviderFetchResult\nfrom .provider_runtime import ProviderSupervisor, clean_result')
edit(coord,'        self.entry = entry\n','        self.entry = entry\n        self._provider_supervisor = ProviderSupervisor()\n')
text=coord.read_text()
start=text.index('        applicable_providers = [')
end=text.index('\n        overpass_result = fetch_results[0]',start)
text=text[:start]+'''        async def bounded_overpass():
            # Bound the combined mirror attempts, not just one HTTP request.
            async with asyncio.timeout(40):
                return await self._query_overpass(lat, lon, radius)

        fetch_results = await asyncio.gather(
            bounded_overpass(),
            self._provider_supervisor.fetch(
                PROVIDERS, session, lat, lon, radius, provider_options,
            ),
            return_exceptions=True,
        )
        for result in fetch_results:
            if isinstance(result, asyncio.CancelledError):
                raise result
'''+text[end:]
start=text.index('        if isinstance(overpass_result, BaseException):')
end=text.index('\n        if overpass_error and provider_suggestion_count',start)
text=text[:start]+'''        if isinstance(overpass_result, Exception):
            overpass_error = 'OpenStreetMap unavailable (' + type(overpass_result).__name__ + ')'
        else:
            try:
                payload, source = overpass_result
                if not isinstance(payload, dict) or not isinstance(payload.get('elements'), list):
                    raise ValueError('Invalid Overpass payload')
                raw_result_count = len(payload['elements'])
                rows = self._build_suggestions(payload, lat, lon, radius, include_restricted)
                valid = clean_result(ProviderFetchResult('openstreetmap', rows), 'openstreetmap', lat, lon, radius)
                suggestions = merge_facilities([], valid.suggestions)
                providers_used.append('openstreetmap')
            except Exception as exc:
                overpass_error = 'OpenStreetMap data rejected (' + type(exc).__name__ + ')'

        provider_suggestion_count = 0
        supplemental = fetch_results[1]
        if isinstance(supplemental, Exception):
            provider_errors['provider_supervisor'] = type(supplemental).__name__
            supplemental = []
        for provider_result in supplemental:
            suggestions = self._provider_supervisor.merge(suggestions, provider_result)
            if provider_result.provider in self._provider_supervisor.errors:
                continue
            providers_used.append(provider_result.provider)
            provider_suggestion_count += len(provider_result.suggestions)
            parking_zones.extend(provider_result.zones)
            if provider_result.live_refresh_seconds:
                live_refresh_seconds.append(provider_result.live_refresh_seconds)
        provider_errors.update(self._provider_supervisor.errors)

        unique_zones = {}
        for zone in parking_zones:
            key = json.dumps(zone['geometry'], sort_keys=True, separators=(',', ':'))
            unique_zones.setdefault(key, zone)
        parking_zones = list(unique_zones.values())
'''+text[end:]
coord.write_text(text)
edit(coord,'''        if overpass_error or provider_errors:
            live_refresh_seconds.append(300)''','''        if overpass_error:
            live_refresh_seconds.append(300)
        if self._provider_supervisor.retry_seconds:
            live_refresh_seconds.append(self._provider_supervisor.retry_seconds)
        if 'provider_supervisor' in provider_errors:
            live_refresh_seconds.append(300)''')
edit(coord,'            "provider_errors": provider_errors,','            "provider_errors": provider_errors,\n            "provider_status": self._provider_supervisor.status,\n            "provider_load_errors": dict(PROVIDER_LOAD_ERRORS),')
edit(coord,'            "provider_errors": {},','            "provider_errors": {},\n            "provider_status": {},\n            "provider_load_errors": dict(PROVIDER_LOAD_ERRORS),')
edit(coord,'                        payload = await response.json(content_type=None)\n','''                        payload = await response.json(content_type=None)
                        if not isinstance(payload, dict) or not isinstance(payload.get('elements'), list) or payload.get('remark'):
                            raise ValueError('Unusable Overpass response')
''')
edit(coord,'        for element in payload.get("elements", []):\n','        for element in payload.get("elements", []):\n            if not isinstance(element, dict):\n                continue\n')
edit(coord,'            tags = element.get("tags") or {}\n','            tags = element.get("tags") or {}\n            if not isinstance(tags, dict):\n                continue\n')
edit(coord,'            if lat is None or lon is None:\n','            if lat is None or lon is None or not math.isfinite(lat) or not math.isfinite(lon) or not (-90 <= lat <= 90 and -180 <= lon <= 180):\n')
edit(coord,'''            try:
                return float(attrs[name])
            except (TypeError, ValueError):
                pass''','''            try:
                number = float(attrs[name])
                if not isinstance(attrs[name], bool) and math.isfinite(number):
                    return number
            except (TypeError, ValueError, OverflowError):
                pass''')
edit(coord,'            or lon is None\n','            or lon is None\n            or not (-90 <= lat <= 90 and -180 <= lon <= 180)\n')
edit(PKG/'diagnostics.py','    "geo_uri",\n','    "geo_uri",\n    "coordinates",\n')

p=ROOT/'tests/test_flow_wizard.py'
text=p.read_text().replace(', "athens_zones_enabled"}','}')
text=text.replace('self.assertTrue(result["data"]["athens_zones_enabled"])','self.assertNotIn("athens_zones_enabled", result["data"])')
text=text.replace('self.assertTrue(fields(page2)["athens_zones_enabled"].default)','self.assertNotIn("athens_zones_enabled", fields(page2))')
p.write_text(text)
p=ROOT/'tests/test_athens_zones.py'
p.write_text(p.read_text().replace('self.assertFalse(athens.AthensParkingZonesProvider().enabled_default)','self.assertFalse(hasattr(athens.AthensParkingZonesProvider(), "enabled_option"))'))

readme=ROOT/'README.md'
text=readme.read_text()
start=text.index('### Athens experimental parking-zone layer')
end=text.index('### Optional provider credentials',start)
text=text[:start]+'''### Automatic public sources and Athens GIS

No Athens GIS switch is required in setup or options. Official polygons are considered automatically only around Athens and after validating GeoJSON, projection, closed rings and geographic bounds. Unusable responses contribute no overlay. Valid static zones cache for 24 hours; failed requests use source-specific recovery backoff. Old `athens_zones_enabled` flags are ignored. `show_zones: false` remains a card display preference.

Equivalent Athens WFS routes and Toulouse Opendatasoft v2/v1 formats are primary/fallback access to the same dataset, not additional parking providers. Fallback is attempted only after transport or data validation failure. These routes share infrastructure; they do not offer an independent mirror during a whole-host outage. Complementary overlapping feeds remain enabled and are deduplicated by facility, so their unique coverage is not lost.

Provider imports, construction, eligibility, requests, payloads and merging are isolated. Supplemental requests have a 30-second default total budget (at most 45 seconds for an explicit provider budget); Athens has an 18-second budget. Retries back off after consecutive failures (1 minute, 5 minutes, 30 minutes, 6 hours), with longer server rate limits respected. Successful static-only data stops polling. Diagnostics expose source status, active endpoint and retry time without API secrets or raw exception bodies.

No failed-source occupancy is replayed. Healthy overlapping sources can take over. Static capacity and controlled-zone boundaries are never presented as measured vacancy or parking permission; check local signage. Toulouse Metropole BNLS is a static garage inventory with equivalent API fallback.

'''+text[end:]
text=text.replace(', and whether to enable the optional Athens controlled-parking zone overlay','')
text=text.replace('- Optional Athens municipal controlled-parking zone overlays (off by default).','- Automatic, validated Athens municipal controlled-parking zone overlays.')
text=text.replace('- **Athens zone GIS:** opt-in, static response cached 24 hours; failures participate in existing recovery polling.','- **Athens zone GIS:** automatic in Athens, validated static cache for 24 hours and source-specific recovery backoff.')
text=text.replace('| OpenStreetMap / Overpass | Worldwide | No | None |','| OpenStreetMap / Overpass | Worldwide | No | None |\n| Toulouse Métropole BNLS | Toulouse public garages | Static inventory; equivalent API fallback | None |')
text+='\nFurther official-source research: [automatic provider research](docs/provider-resilience-research.md).\n'
readme.write_text(text)
notes='''## v1.4.0

### Automatic sources and fault isolation

- Removed the manual Athens GIS switch from setup and options in all 14 languages. Usable official polygons are selected automatically only around Athens, ignoring obsolete manual flags.
- Validate projection, polygon structure, closed rings, finite coordinates, geographic bounds and inventory completeness before accepting GIS data. An unavailable or invalid feed contributes no layer and never implies parking permission or vacancy.
- Isolate optional-provider imports, construction, eligibility checks, fetch deadlines, result parsing and merging. Malformed records do not discard other healthy results.
- Added source-local retry backoff, rate-limit-aware equivalent endpoint fallback and credential-safe diagnostic source status. Failed-source occupancy is never replayed.
- Athens WFS routes and Toulouse Opendatasoft formats are equivalent primary/fallback access, not duplicated providers. Complementary overlapping sources retain their coverage and best-source deduplication.
- Added the Toulouse Metropole BNLS static facility adapter; renewed official-source research for Bordeaux, Galway and Greece.
- Shortened English, Greek and German category-chip labels. Existing categories, restrictions, credentials, four-step setup and card appearance are retained.
- Added fault-injection tests against the actual coordinator, source supervisor, GIS validator and endpoint fallback.

### Testing limits

Public endpoint probes report only the test runner's point-in-time observations, not guaranteed availability from every Home Assistant network. The user's live installation is not modified by release testing.

'''
p=ROOT/'CHANGELOG.md';p.write_text(p.read_text().replace('# Changelog\n\n','# Changelog\n\n'+notes,1))
edit(ROOT/'tools/card/build.py',"VERSION = '1.3.1'","VERSION = '1.4.0'")
edit(ROOT/'tools/card/explorer.js','<span class="version">v1.3.1</span>','<span class="version">v1.4.0</span>')
subprocess.run([sys.executable,str(ROOT/'tools/card/build.py')],cwd=ROOT,check=True)
print('AUTO_PROVIDERS_PREPARED=1.4.0')
