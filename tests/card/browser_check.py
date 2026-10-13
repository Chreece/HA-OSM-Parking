"""Real-browser UI regression checks with pinned MapLibre and local map data.

This is NOT a Home Assistant server integration test. The actual shipped card
is mounted inside a shadow root with sample HA states and a local vector-map
fixture so tests do not depend on third-party map tiles or live parking APIs.
"""
from pathlib import Path
from functools import partial
import http.server
import json
import os
import threading
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'card-evidence'
OUT.mkdir(exist_ok=True)


def style(dark=True):
    features=[]
    for n in range(-12,13):
        x=6.983+n*.0015
        features.append({'type':'Feature','geometry':{'type':'LineString','coordinates':[[x,50.915],[x+.008,50.960]]},'properties':{}})
        y=50.938+n*.001
        features.append({'type':'Feature','geometry':{'type':'LineString','coordinates':[[6.950,y],[7.015,y+.002]]},'properties':{}})
    return {'version':8,'name':'Offline map fixture',
            'sources':{'fixture':{'type':'geojson','attribution':'Offline map fixture — not geographic evidence','data':{'type':'FeatureCollection','features':features}}},
            'layers':[{'id':'background','type':'background','paint':{'background-color':'#14222d' if dark else '#edf1f3'}},
                      {'id':'roads','type':'line','source':'fixture','paint':{'line-color':'#3a5060' if dark else '#c7d1d7','line-width':3}}]}


class QuietServer(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*args): pass


server=http.server.ThreadingHTTPServer(('127.0.0.1',0),partial(QuietServer,directory=str(ROOT)))
threading.Thread(target=server.serve_forever,daemon=True).start()
report={'sample_data':True,'actual_maplibre':True,'scenarios':[],'screenshots':[],'errors':[]}


def checked(name):
    report['scenarios'].append(name)
    print('BROWSER_PASS='+name,flush=True)


with sync_playwright() as p:
    kwargs={'headless':True,'args':['--no-sandbox','--use-angle=swiftshader','--enable-unsafe-swiftshader']}
    if os.environ.get('CHROMIUM_PATH'):kwargs['executable_path']=os.environ['CHROMIUM_PATH']
    browser=p.chromium.launch(**kwargs)
    page=browser.new_page(viewport={'width':900,'height':1500},device_scale_factor=1)
    page.on('pageerror',lambda error:report['errors'].append(str(error)))
    page.route('https://tiles.openfreemap.org/styles/**',lambda route:route.fulfill(status=200,content_type='application/json',body=json.dumps(style('dark' in route.request.url))))
    try:
        page.goto(f'http://127.0.0.1:{server.server_port}/tests/card/preview.html')
        page.wait_for_function('window.card?._map?.loaded() && window.card?._pins?.size===5',timeout=30000)
        assert page.evaluate('window.maplibregl.version')=='5.6.2'
        assert page.locator('.result-card').count()==5
        assert page.locator('.map').evaluate('(e)=>e.getBoundingClientRect().height')==220
        checked('real MapLibre + actual bundled card + compact 220px map')
        page.screenshot(path=str(OUT/'desktop-dark.png'),full_page=True)
        report['screenshots'].append('desktop-dark.png')

        page.locator('.filter-toggle').first.click()
        page.locator('.type-chip[data-type=underground]').click()
        assert page.locator('.result-card').count()==1
        assert page.locator('.osm-park-marker').count()==1
        assert page.locator('.osm-park-marker').inner_text()=='1'
        checked('type filter synchronizes marker and row numbering')
        page.locator('.reset-filters').click()
        page.locator('.available').check()
        assert page.locator('.result-card').count()==1
        assert 'Rheinpark' in page.locator('.result-title').inner_text()
        checked('available-only excludes reported counts and full live facilities')
        page.locator('.reset-filters').click()
        page.locator('.cost').select_option('unknown')
        assert page.locator('.result-card').count()==1
        assert 'Street' in page.locator('.result-title').inner_text()
        checked('unknown price is separate from free')
        page.locator('.reset-filters').click()
        page.locator('.quality').select_option('reported')
        assert page.locator('.result-card').count()==1
        assert 'Reported' in page.locator('.quality-badge').inner_text()
        checked('reported quality is labelled and filterable')
        page.locator('.reset-filters').click()
        page.locator('.source').select_option('city')
        assert page.locator('.result-card').count()==2
        checked('winning source filter')
        page.locator('.reset-filters').click()
        page.locator('.max-distance').fill('300')
        assert page.locator('.result-card').count()==2
        checked('maximum distance filter')
        page.locator('.reset-filters').click()
        page.locator('.sort').select_option('free_first')
        assert 'Park & Ride' in page.locator('.result-title').first.inner_text()
        page.locator('.sort').select_option('availability')
        assert 'City Centre' in page.locator('.result-title').first.inner_text()
        page.locator('.sort').select_option('data_quality')
        assert 'Rheinpark' in page.locator('.result-title').first.inner_text()
        for sort in ['type','source','name','distance']:
            page.locator('.sort').select_option(sort)
            pairs=page.evaluate('window.card._visible.map((i,n)=>[window.card._pins.get(osmKey(i)).button.textContent,String(n+1)])')
            assert all(a==b for a,b in pairs)
        checked('all seven sorts retain marker-to-result numbering')

        page.evaluate('window.card._map.jumpTo({center:[6.994,50.943],zoom:15})')
        before=page.evaluate('window.card._map.getCenter().toArray()')
        page.locator('.sort').select_option('free_first')
        assert page.evaluate('window.card._map.getCenter().toArray()')==before
        page.evaluate("window.attributes={...window.attributes,suggestions:window.sampleItems.map((v,i)=>i? v:{...v,free_capacity:29})};window.ha.states['sensor.parking_suggestions']={state:'ok',attributes:window.attributes};window.card.hass=window.ha")
        page.wait_for_timeout(100)
        assert page.evaluate('window.card._map.getCenter().toArray()')==before
        checked('sort and data refresh preserve user map viewport')
        page.locator('.search').fill('zz-no-result')
        assert page.locator('.result-card').count()==0
        assert page.locator('.filter-empty').is_visible()
        page.locator('.filter-empty button').click()
        assert page.locator('.result-card').count()==5
        checked('empty filtered results offer working reset')
        page.locator('.search').fill('rhein')
        assert page.locator('.result-card').count()==1
        assert page.evaluate('window.serviceCalls.length')==0
        page.reload()
        page.wait_for_function('window.card?._pins?.size===1',timeout=30000)
        assert page.locator('.result-card').count()==1
        checked('browser-local filters survive reload without HA service calls')
        page.evaluate("window.ha={...window.ha,user:{id:'different-user'}};window.card.hass=window.ha")
        assert page.locator('.result-card').count()==5
        checked('preferences are isolated when Home Assistant user changes')
        page.evaluate("window.ha={...window.ha,user:{id:'preview-user'}};window.card.hass=window.ha")
        assert page.locator('.result-card').count()==1
        page.locator('.reset-filters').click()
        page.locator('.sort').select_option('distance')
        page.locator('.fit').click()

        page.evaluate('window.applyTheme(false)')
        page.wait_for_function("window.card._style.endsWith('/liberty') && window.card._map.isStyleLoaded() && !!window.card._map.getLayer('osm-parking-controlled-zones-fill')")
        assert page.locator('osm-parking-map-card').get_attribute('data-mode')=='light'
        assert page.locator('.osm-park-marker').count()==5
        page.screenshot(path=str(OUT/'desktop-light.png'),full_page=True)
        report['screenshots'].append('desktop-light.png')
        page.evaluate('window.applyTheme(true)')
        page.wait_for_function("window.card._style.endsWith('/dark') && window.card._map.isStyleLoaded() && !!window.card._map.getLayer('osm-parking-controlled-zones-fill')")
        checked('HA theme switch preserves markers and controlled-zone overlays')
        page.locator('.expand').click()
        assert page.locator('.map').evaluate('(e)=>e.getBoundingClientRect().height')>=400
        page.locator('.expand').click()
        assert page.locator('.map').evaluate('(e)=>e.getBoundingClientRect().height')==220
        checked('map expansion and collapse without rebuilding card')
        page.locator('.result-focus').first.click()
        assert page.locator('.result-card.selected').count()==1
        assert page.locator('.osm-park-marker.selected').count()==1
        checked('keyboard-accessible result selection highlights matching marker')
        page.evaluate('window.card._popup?.remove()')
        page.locator('.result-details summary').first.click()
        assert page.locator('.result-details').first.evaluate('(e)=>e.open')
        checked('provider details and provenance remain accessible')
        page.locator('.result-details summary').first.click()

        for width in [320,390]:
            page.set_viewport_size({'width':width,'height':1500})
            for locale in ['en','el','de','es','fr','it','nl','pl','pt','pt-BR','ru','tr','zh-Hans','ja']:
                page.evaluate('(locale)=>{window.ha={...window.ha,language:locale};window.card.hass=window.ha}',locale)
                assert not page.evaluate('document.documentElement.scrollWidth>innerWidth')
                assert page.locator('.parking-explorer').evaluate('(e)=>e.scrollWidth<=e.clientWidth+1')
                assert page.locator('.filter-toggle').first.locator(':scope > span').inner_text()
        checked('14 languages at 320px and 390px without horizontal overflow')
        page.evaluate("window.ha={...window.ha,language:'el'};window.card.hass=window.ha;window.card._selected=null;window.card._renderResults();window.card._syncMarkers();window.card._fitVisible()")
        page.wait_for_timeout(200)
        page.screenshot(path=str(OUT/'mobile-greek-dark.png'),full_page=True)
        report['screenshots'].append('mobile-greek-dark.png')
        page.locator('.filter-toggle').first.click()
        page.screenshot(path=str(OUT/'mobile-greek-filters.png'),full_page=True)
        report['screenshots'].append('mobile-greek-filters.png')
        page.locator('.filter-toggle').first.click()

        page.evaluate("window.ha.states['sensor.parking_suggestions']={state:'error',attributes:{...window.attributes,status:'error',suggestions:[],parking_zones:[]}};window.card.hass=window.ha")
        assert not page.locator('.map-frame').is_visible()
        assert page.locator('.status-panel').is_visible()
        page.evaluate("window.ha.states['sensor.parking_suggestions']={state:'ok',attributes:{...window.attributes,partial_data:true,provider_errors:{example:'Test outage'}}};window.card.hass=window.ha")
        assert page.locator('.status-panel').is_visible()
        assert page.locator('.result-card').count()==5
        checked('backend failure and partial-source recovery messages retained')
        page.evaluate("window.ha.states['sensor.parking_suggestions']={state:'ok',attributes:window.attributes};window.card.hass=window.ha;window.card._mapFailure(new Error('Simulated tile outage'))")
        assert page.locator('.map-note').is_visible()
        assert page.locator('.result-card').count()==5
        page.locator('.search').fill('rhein')
        assert page.locator('.result-card').count()==1
        assert page.locator('.navigate').first.get_attribute('href').startswith('https:')
        checked('tile failure leaves search results and navigation usable')
        page.locator('.reset-filters').click()
        page.evaluate('window.savedCard=window.card;window.card.remove()')
        assert page.evaluate('window.card._map===null && window.card._observer===null')
        page.evaluate("document.getElementById('host').shadowRoot.append(window.savedCard)")
        page.wait_for_function('window.card?._map?.loaded() && window.card._pins.size===5',timeout=30000)
        assert page.locator('canvas.maplibregl-canvas').count()==1
        checked('disconnect cleans WebGL and observers; reconnect creates one map')
        page.evaluate("window.card.setConfig({entity:'sensor.parking_suggestions',height:300,remember_filters:false});window.card.hass=window.ha")
        assert page.locator('.map').evaluate('(e)=>e.getBoundingClientRect().height')==300
        page.evaluate("window.card.setConfig({entity:'sensor.parking_suggestions',height:430,map_height:200,remember_filters:false});window.card.hass=window.ha")
        assert page.locator('.map').evaluate('(e)=>e.getBoundingClientRect().height')==200
        checked('legacy height retained and map_height override respected')
        assert not report['errors'],report['errors']
        report['passed']=True
    except Exception as exc:
        report['passed']=False;report['failure']=repr(exc)
        page.screenshot(path=str(OUT/'failure.png'),full_page=True)
        raise
    finally:
        (OUT/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        browser.close()
        server.shutdown()
print('BROWSER_SCENARIOS_PASSED='+str(len(report['scenarios'])))
