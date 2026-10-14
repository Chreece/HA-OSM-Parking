"""Real MapLibre/browser checks for collapsed results and marker reveal.

Uses the complete shipped module in the existing shadow-root preview. Parking
records and map style are synthetic; this does not connect to the user's HA.
"""
from pathlib import Path
from functools import partial
import http.server
import json
import os
import re
import threading
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'card-evidence';OUT.mkdir(exist_ok=True)
class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*args):pass
server=http.server.ThreadingHTTPServer(('127.0.0.1',0),partial(Quiet,directory=str(ROOT)))
threading.Thread(target=server.serve_forever,daemon=True).start()
style={'version':8,'name':'Local fold-test fixture','sources':{},'layers':[{'id':'background','type':'background','paint':{'background-color':'#14222d'}}]}
report={'actual_bundled_card':True,'actual_maplibre':True,'sample_data':True,'scenarios':[],'errors':[]}


def checked(name):
    report['scenarios'].append(name);print('FOLD_PASS='+name,flush=True)


with sync_playwright() as p:
    args={'headless':True,'args':['--no-sandbox','--use-angle=swiftshader','--enable-unsafe-swiftshader']}
    if os.environ.get('CHROMIUM_PATH'):args['executable_path']=os.environ['CHROMIUM_PATH']
    browser=p.chromium.launch(**args)
    page=browser.new_page(viewport={'width':390,'height':720},device_scale_factor=1)
    page.on('pageerror',lambda e:report['errors'].append(str(e)))
    page.route('https://tiles.openfreemap.org/styles/**',lambda r:r.fulfill(status=200,content_type='application/json',body=json.dumps(style)))
    page.add_init_script('''window.resultScrolls=[];
    const native=Element.prototype.scrollIntoView;
    Element.prototype.scrollIntoView=function(options){
      if(this.classList.contains('result-card'))window.resultScrolls.push({key:this.dataset.key,options,visible:!!this.getClientRects().length});
      return native.call(this,options);
    };''')
    def loaded():page.wait_for_function('window.card?._map?.loaded() && window.card?._pins?.size===5',timeout=30000)
    def reset(config=None):
        page.evaluate('''config=>{window.ha={...window.ha,language:'en',user:{id:'preview-user'},states:{'sensor.parking_suggestions':{state:'ok',attributes:window.attributes}}};
        window.card.setConfig({entity:'sensor.parking_suggestions',remember_filters:false,...config});window.card.hass=window.ha;}''',config or {})
        loaded()
    def count():return page.evaluate('window.resultScrolls.length')
    def wait_selected():
        page.wait_for_function('''()=>{const row=window.card.querySelector('.result-card.selected');
        if(!row)return false;const r=row.getBoundingClientRect();return r.top>=-1 && r.bottom<=innerHeight+1;}''',timeout=5000)
    try:
        page.goto(f'http://127.0.0.1:{server.server_port}/tests/card/preview.html');loaded()
        assert page.evaluate('maplibregl.getVersion()')=='5.6.2'
        assert page.locator('.osm-park-marker').count()==5
        assert page.locator('.result-card').count()==5
        assert page.locator('.result-card:visible').count()==0
        assert page.locator('.results-toggle').get_attribute('aria-expanded')=='false'
        assert page.locator('.map').is_visible()
        assert count()==0
        checked('initial folded list retains every matching marker and does not scroll')
        page.evaluate("window.ha={...window.ha,language:'el'};window.card.hass=window.ha")
        page.screenshot(path=str(OUT/'folded-mobile-greek.png'),full_page=True)

        key=page.evaluate('osmKey(window.card._visible[4])')
        page.locator('.osm-park-marker').nth(4).click()
        page.wait_for_function('window.resultScrolls.length===1');wait_selected()
        assert page.locator('.results-toggle').get_attribute('aria-expanded')=='true'
        assert page.locator('.result-card.selected').get_attribute('data-key')==key
        assert page.locator('.osm-park-marker.selected').count()==1
        assert page.locator('.result-focus[aria-pressed=true]').count()==1
        assert page.evaluate('window.resultScrolls[0].visible')
        assert page.evaluate('scrollY')>0
        checked('marker opens, highlights and actually scrolls to the last result')
        page.screenshot(path=str(OUT/'revealed-mobile-greek.png'))

        page.evaluate('window.card._setResultsExpanded(false)')
        assert page.locator('.result-card:visible').count()==0
        assert page.locator('.osm-park-marker').count()==5
        prior=count()
        page.locator('.sort').select_option('name')
        key=page.evaluate('osmKey(window.card._visible[2])')
        page.locator('.osm-park-marker').filter(has_text=re.compile(r'^3$')).click()
        page.wait_for_function('(n)=>window.resultScrolls.length===n+1',arg=prior);wait_selected()
        assert page.locator('.result-card.selected').get_attribute('data-key')==key
        assert page.locator('.result-card.selected .result-number').inner_text()=='3'
        checked('marker-to-result identity and numbering survive sorting')

        page.locator('.filter-toggle').first.click()
        page.locator('.quality').select_option('reported')
        page.evaluate('window.card._setResultsExpanded(false)')
        assert page.locator('.osm-park-marker').count()==1
        page.locator('.osm-park-marker').click()
        page.wait_for_function('window.card._revealFrame===null');wait_selected()
        assert 'City Centre' in page.locator('.result-card.selected .result-title').inner_text()
        checked('filtered marker reveals only its matching filtered row')
        page.locator('.reset-filters').click()
        prior=count()
        page.evaluate('''window.attributes={...window.attributes,suggestions:window.sampleItems.map((v,i)=>i?v:{...v,free_capacity:27})};
        window.ha.states['sensor.parking_suggestions']={state:'ok',attributes:window.attributes};window.card.hass=window.ha;window.applyTheme(false);''')
        page.wait_for_timeout(250)
        assert count()==prior
        assert page.locator('.results-toggle').get_attribute('aria-expanded')=='true'
        checked('data and theme updates keep disclosure state without unsolicited scrolling')

        page.evaluate('window.card._setResultsExpanded(false)');prior=count()
        page.evaluate('window.card._renderView()');page.wait_for_timeout(150)
        assert count()==prior and page.locator('.result-card:visible').count()==0
        page.reload();loaded()
        assert page.locator('.result-card:visible').count()==0
        checked('manual collapse survives refresh and new page load starts folded')

        reset();page.emulate_media(reduced_motion='reduce')
        page.locator('.osm-park-marker').nth(4).focus()
        page.locator('.osm-park-marker').nth(4).press('Enter')
        page.wait_for_function('window.card._revealFrame===null');wait_selected()
        assert page.evaluate("window.card.querySelector('.result-card.selected .result-focus').matches(':focus')")
        assert page.evaluate('window.resultScrolls.at(-1).options.behavior')=='instant'
        checked('keyboard marker reveal transfers focus; reduced motion disables animation')
        page.locator('.results-toggle').focus();page.locator('.results-toggle').press('Space')
        assert page.locator('.result-card:visible').count()==0
        page.locator('.results-toggle').press('Enter')
        assert page.locator('.result-card:visible').count()==5
        checked('native disclosure button supports Enter and Space')

        reset();prior=count()
        expected=page.evaluate('''()=>{const pins=[...window.card._pins.values()];pins[0].button.click();pins[4].button.click();return osmKey(window.card._visible[4]);}''')
        page.wait_for_function('(n)=>window.resultScrolls.length===n+1',arg=prior)
        assert page.evaluate('window.resultScrolls.at(-1).key')==expected
        checked('rapid marker choices only scroll the last selected facility')
        page.evaluate('window.card._setResultsExpanded(false)');prior=count()
        page.evaluate("[...window.card._pins.values()][0].button.click();window.card._ui.query='no-match-for-anything';window.card._filterChanged()")
        page.wait_for_timeout(150)
        assert count()==prior
        assert page.locator('.filter-empty').is_visible()
        assert page.locator('.results-toggle').is_disabled()
        page.locator('.filter-empty button').click()
        assert page.locator('.osm-park-marker').count()==5
        checked('removed/filtered selection cancels pending scroll; zero-results recovery stays visible')

        reset();prior=count()
        page.evaluate("[...window.card._pins.values()][0].button.click();window.card._setResultsExpanded(false)")
        page.wait_for_timeout(150);assert count()==prior
        page.evaluate("[...window.card._pins.values()][0].button.click();window.savedCard=window.card;window.card.remove()")
        page.wait_for_timeout(150);assert count()==prior
        page.evaluate("document.getElementById('host').shadowRoot.append(window.savedCard)");loaded()
        checked('collapse and card removal cancel deferred reveal safely')

        reset();page.locator('.results-toggle').click();prior=count()
        page.evaluate("window.ha={...window.ha,user:{id:'different-user'}};window.card.hass=window.ha")
        assert page.locator('.result-card:visible').count()==0
        assert count()==prior
        checked('user changes start folded without revealing another user selection')
        reset({'show_filters':False})
        assert page.locator('.results-toggle').is_visible()
        page.locator('.results-toggle').click();assert page.locator('.result-card:visible').count()==5
        checked('list can be expanded even when filter toolbar is disabled')
        reset({'show_list':False});prior=count()
        assert not page.locator('.results-toggle').is_visible()
        page.locator('.osm-park-marker').first.click();page.wait_for_timeout(150)
        assert count()==prior and page.locator('.result-card:visible').count()==0
        assert page.locator('.maplibregl-popup').is_visible()
        checked('explicit map-only configuration is respected')

        reset();page.evaluate("window.card._mapFailure(new Error('simulated tile failure'))")
        assert page.locator('.map-note').is_visible()
        page.locator('.results-toggle').click()
        assert page.locator('.result-card:visible').count()==5
        assert page.locator('.navigate').first.get_attribute('href').startswith('https:')
        checked('map failure still allows manually opening results and navigation')

        reset();page.evaluate('''()=>{const other=document.createElement('osm-parking-map-card');other.id='other-card';
        other.setConfig({entity:'sensor.parking_suggestions',remember_filters:false});window.card.parentNode.append(other);other.hass=window.ha;window.other=other;}''')
        page.wait_for_function('window.other?._pins?.size===5')
        assert page.evaluate('window.card._els.resultsPanel.id!==window.other._els.resultsPanel.id')
        page.locator('#other-card .osm-park-marker').nth(2).click();page.wait_for_timeout(200)
        assert page.evaluate('window.card._resultsExpanded') is False
        assert page.evaluate('window.other._resultsExpanded') is True
        page.evaluate('window.other.remove()')
        checked('multiple cards have independent disclosure state and unique ARIA targets')

        reset();page.evaluate('''()=>{const host=document.getElementById('host');const scroller=document.createElement('div');
        scroller.id='ha-scroll';scroller.style.cssText='height:620px;overflow-y:auto;overscroll-behavior:contain';
        host.before(scroller);scroller.append(host);const end=document.createElement('div');end.style.height='400px';scroller.append(end);}''');loaded()
        page.locator('.osm-park-marker').nth(4).click()
        page.wait_for_function('''()=>{const row=window.card.querySelector('.result-card.selected');if(!row)return false;
        const r=row.getBoundingClientRect(),v=document.getElementById('ha-scroll').getBoundingClientRect();
        return document.getElementById('ha-scroll').scrollTop>0 && r.top>=v.top-1 && r.bottom<=v.bottom+1;}''')
        checked('actual row becomes visible inside a nested Home-Assistant-style scroll container')
        page.evaluate("const outer=document.getElementById('ha-scroll');outer.before(document.getElementById('host'));outer.remove()");loaded()

        for width in (320,390,900):
            page.set_viewport_size({'width':width,'height':900})
            for lang in ('en','el','de','fr','es','it','nl','pl','pt','pt-BR','ru','tr','zh-Hans','ja'):
                page.evaluate("lang=>{window.ha={...window.ha,language:lang};window.card.hass=window.ha;window.card._setResultsExpanded(false)}",lang)
                assert page.locator('.results-toggle-label').inner_text().split(' · ')[0] not in ('show_results','hide_results','')
                assert not page.evaluate('document.documentElement.scrollWidth>innerWidth')
                page.evaluate('window.card._setResultsExpanded(true)')
                assert page.locator('.results-toggle').get_attribute('aria-expanded')=='true'
        checked('all 14 languages fit desktop and mobile disclosure controls')
        assert page.evaluate('window.serviceCalls.length')==0
        checked('folding, sorting and marker selection never request provider updates')
        assert not report['errors'],report['errors']
        report['passed']=True
    except Exception as exc:
        report.update(passed=False,failure=repr(exc));page.screenshot(path=str(OUT/'fold-failure.png'),full_page=True);raise
    finally:
        (OUT/'fold-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        browser.close();server.shutdown();server.server_close()
print('FOLD_SCENARIOS_PASSED='+str(len(report['scenarios'])))
