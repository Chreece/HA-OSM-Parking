"""Type glyphs and stable map/result identity on the actual bundled card.

Real Chromium + pinned MapLibre; synthetic HA state and local map fixture.
Parking SVGs are the exact packaged paths, not preview/icon substitutes.
"""
from pathlib import Path
from functools import partial
import http.server
import json
import os
import threading
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'card-evidence';OUT.mkdir(exist_ok=True)
class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*args):pass
server=http.server.ThreadingHTTPServer(('127.0.0.1',0),partial(Quiet,directory=str(ROOT)))
threading.Thread(target=server.serve_forever,daemon=True).start()
style={'version':8,'sources':{},'layers':[{'id':'local-background','type':'background','paint':{'background-color':'#233b4a'}}]}
report={'actual_bundled_card':True,'actual_maplibre':True,'packaged_svg_paths':True,'sample_data':True,'scenarios':[],'errors':[]}
def passed(name):report['scenarios'].append(name);print('TYPE_ICONS_PASS='+name,flush=True)
with sync_playwright() as p:
    options={'headless':True,'args':['--no-sandbox','--use-angle=swiftshader','--enable-unsafe-swiftshader']}
    if os.environ.get('CHROMIUM_PATH'):options['executable_path']=os.environ['CHROMIUM_PATH']
    browser=p.chromium.launch(**options)
    page=browser.new_page(viewport={'width':390,'height':900})
    page.on('pageerror',lambda e:report['errors'].append(str(e)))
    page.route('https://tiles.openfreemap.org/styles/**',lambda r:r.fulfill(status=200,content_type='application/json',body=json.dumps(style)))
    try:
        page.goto(f'http://127.0.0.1:{server.server_port}/tests/card/preview.html')
        page.wait_for_function('window.card?._map?.loaded() && window.card._pins?.size===5',timeout=30000)
        assert page.evaluate('maplibregl.getVersion()')=='5.6.2'
        assert not page.locator('.result-card').first.is_visible()
        assert page.locator('.osm-park-marker .parking-type-glyph').count()==5
        assert page.locator('.osm-park-marker').all_text_contents()==['']*5
        assert page.locator('.result-number').count()==0
        passed('folded map loads exact SVG type glyphs without visible ordinals')
        page.evaluate('''()=>{
          window.demo=OSM_EXPLORER_TYPES.map((category,n)=>({
            provider:'example',provider_id:'category-'+n,category,name:'Sample '+category,
            latitude:50.934+(n%3)*.003,longitude:6.976+Math.floor(n/3)*.007,
            distance_m:100+n*100,availability_kind:'static',fee:'unknown',
            navigation_url:'https://example.com/navigation',data_sources:['example']
          }));
          window.demo.push({...window.demo[4],provider_id:'same-type-second',name:window.demo[4].name,latitude:50.943,longitude:6.994});
          window.showDemo=()=>{window.ha.states['sensor.parking_suggestions']={state:'ok',attributes:{...window.attributes,suggestions:window.demo}};window.card.hass=window.ha};
          window.card.setConfig({entity:'sensor.parking_suggestions',remember_filters:false,map_height:220});window.showDemo();
        }''')
        page.wait_for_function('window.card._map?.loaded() && window.card._pins.size===8',timeout=30000)
        glyphs=page.evaluate('''()=>window.card._visible.map(item=>{
          const key=osmKey(item),button=window.card._pins.get(key).button,svg=button.querySelector('svg'),path=svg.querySelector('path'),bbox=path.getBBox();
          return {type:item.category,key,internalKey:button.dataset.key,glyph:svg.dataset.icon,d:path.getAttribute('d'),expected:OSM_PARKING_GLYPHS[item.category].path,width:svg.getBoundingClientRect().width,geometry:bbox.width*bbox.height,label:button.getAttribute('aria-label'),text:button.textContent};
        })''')
        assert len({x['d'] for x in glyphs})==7
        assert all(x['d']==x['expected'] and x['geometry']>0 and x['width']==22 and x['key']==x['internalKey'] and x['text']=='' and x['label'] for x in glyphs)
        passed('all seven types draw distinct bounded glyphs including paid surface and other')
        page.evaluate("window.targetKey=osmKey(window.demo[7]);window.card._pins.get(window.targetKey).button.click()")
        page.wait_for_function("window.card._resultsExpanded && window.card._revealFrame===null")
        assert page.evaluate("window.card.querySelector('.result-card.selected').dataset.key===window.targetKey")
        assert page.locator('.osm-park-marker[aria-pressed=true]').count()==1
        assert page.evaluate("window.card._pins.get(osmKey(window.demo[4])).button.getAttribute('aria-pressed')==='false'")
        passed('two facilities with identical name and type reveal different stable result keys')
        for sort in ('distance','name','type','source','availability','free_first','data_quality'):
            page.locator('.sort').select_option(sort)
            assert page.evaluate('''()=>window.card._visible.every((item,index)=>{
              const key=osmKey(item),button=window.card._pins.get(key).button,row=window.card._rows.get(key);
              return button.dataset.key===key && button.dataset.index===String(index) && row.dataset.index===String(index)
                && button.querySelector('path').getAttribute('d')===row.querySelector('.result-icon path').getAttribute('d');
            })''')
        passed('all seven sorts keep hidden indices and stable keys aligned with row glyphs')
        page.locator('.filter-toggle').first.click()
        page.locator('.type-chip[data-type=multi_storey]').click()
        assert page.locator('.osm-park-marker').count()==2
        page.evaluate('window.card._setResultsExpanded(false)')
        before=page.evaluate('window.card._map.getCenter().toArray().concat(window.card._map.getZoom())')
        page.locator('.osm-park-marker').first.click()
        page.wait_for_function('window.card._resultsExpanded && window.card._revealFrame===null')
        assert page.locator('.result-card.selected').count()==1
        assert page.evaluate('window.card._map.getCenter().toArray().concat(window.card._map.getZoom())')==before
        passed('actual pointer click on an icon reveals filtered row without changing camera')
        page.locator('.reset-filters').click()
        page.evaluate('''()=>{const key=osmKey(window.demo[0]);window.keptButton=window.card._pins.get(key).button;window.keptSvg=window.keptButton.firstElementChild;window.keptKey=key;window.demo[0]={...window.demo[0],distance_m:37};window.showDemo()}''')
        assert page.evaluate('window.card._pins.get(window.keptKey).button===window.keptButton && window.keptButton.firstElementChild===window.keptSvg')
        page.evaluate("window.demo[0]={...window.demo[0],category:'underground'};window.showDemo()")
        assert page.evaluate("window.card._pins.get(window.keptKey).button===window.keptButton && window.keptButton.querySelector('svg').dataset.icon==='tunnel'")
        assert page.evaluate("window.card._rows.get(window.keptKey).querySelector('svg').dataset.icon==='tunnel'")
        passed('refresh reuses marker and glyph; changed category updates both views in place')
        page.evaluate("window.demo[0]={...window.demo[0],category:'unrecognized',name:''};window.showDemo()")
        assert page.evaluate("window.keptButton.querySelector('svg').dataset.icon==='map-marker-question'")
        assert page.evaluate("window.card._rows.get(window.keptKey).querySelector('.popup-title').textContent===window.card._t('parking')")
        passed('unknown category and unnamed facility have safe icon and no numbered fallback name')
        page.emulate_media(reduced_motion='reduce')
        page.evaluate('window.card._setResultsExpanded(false)')
        button=page.locator('.osm-park-marker').first
        button.focus();button.press('Enter')
        page.wait_for_function('window.card._resultsExpanded && window.card._revealFrame===null')
        assert page.locator('.result-card.selected .result-focus').evaluate('(e)=>e.getRootNode().activeElement===e')
        assert page.locator('.osm-park-marker svg').first.get_attribute('aria-hidden')=='true'
        assert page.locator('.osm-park-marker svg').first.get_attribute('focusable')=='false'
        passed('native marker buttons retain keyboard reveal and glyphs are not extra focus targets')
        for dark in (False,True):
            page.evaluate('(dark)=>window.applyTheme(dark)',dark)
            page.wait_for_function('window.card._map.isStyleLoaded()')
            for locale in ('en','el','de','fr','es','it','nl','pl','pt','pt-BR','ru','tr','zh-Hans','ja'):
                page.evaluate('(language)=>{window.ha={...window.ha,language};window.card.hass=window.ha}',locale)
                assert page.evaluate('''()=>window.card._visible.every(item=>{
                  const b=window.card._pins.get(osmKey(item)).button,category=window.card._translations().categories[osmIconType(item)];
                  return b.title.startsWith(category+' · ') && b.getAttribute('aria-label')===b.title && b.textContent==='';
                })''')
                assert not page.evaluate('document.documentElement.scrollWidth>innerWidth')
        passed('both themes and 14 languages have type-and-name labels instead of ordinal labels')
        page.evaluate("window.ha={...window.ha,language:'el'};window.demo[0]={...window.demo[0],category:'paid',name:'Sample paid'};window.showDemo();window.card._setResultsExpanded(false);window.card._fitVisible()")
        page.wait_for_timeout(200)
        page.screenshot(path=str(OUT/'type-icons-folded-greek.png'),full_page=True)
        page.evaluate('window.card._pins.get(osmKey(window.demo[3])).button.click()')
        page.wait_for_function('window.card._revealFrame===null')
        page.screenshot(path=str(OUT/'type-icons-selected-greek.png'),full_page=True)
        page.evaluate("window.card.setConfig({entity:'sensor.parking_suggestions',show_list:false,remember_filters:false});window.showDemo()")
        page.wait_for_function('window.card._map?.loaded() && window.card._pins.size===8')
        page.locator('.osm-park-marker').first.click()
        assert page.locator('.maplibregl-popup').is_visible()
        assert not page.locator('.results-toggle').is_visible()
        passed('explicit map-only configuration still opens the icon marker popup')
        assert page.evaluate('window.serviceCalls.length')==0
        assert not report['errors'],report['errors']
        report['passed']=True
    except Exception as exc:
        report.update(passed=False,failure=repr(exc));page.screenshot(path=str(OUT/'type-icons-failure.png'),full_page=True);raise
    finally:
        (OUT/'type-icons-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        browser.close();server.shutdown();server.server_close()
print('TYPE_ICONS_SCENARIOS='+str(len(report['scenarios'])))
