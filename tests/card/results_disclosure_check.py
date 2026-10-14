"""Actual bundled card + real MapLibre; synthetic HA states and a local map.

Tests map-first disclosure inside a scrolling dashboard and shadow root.
No actual Home Assistant server, credentials or external parking data is used.
"""
from functools import partial
import http.server
import json
import os
from pathlib import Path
import threading
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'card-evidence'
OUT.mkdir(exist_ok=True)

class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass

server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), partial(Quiet, directory=str(ROOT)))
threading.Thread(target=server.serve_forever, daemon=True).start()
report = {'actual_bundled_card': True, 'actual_maplibre': True, 'sample_data': True,
          'scenarios': [], 'errors': []}

def checked(name):
    report['scenarios'].append(name)
    print('DISCLOSURE_PASS=' + name, flush=True)

with sync_playwright() as p:
    options = {'headless': True, 'args': ['--no-sandbox', '--use-angle=swiftshader', '--enable-unsafe-swiftshader']}
    if os.environ.get('CHROMIUM_PATH'):
        options['executable_path'] = os.environ['CHROMIUM_PATH']
    browser = p.chromium.launch(**options)
    page = browser.new_page(viewport={'width': 390, 'height': 720}, device_scale_factor=1)
    page.on('pageerror', lambda error: report['errors'].append(str(error)))
    def local_style(route):
        style = {'version': 8, 'sources': {}, 'layers': [{'id': 'background', 'type': 'background',
                 'paint': {'background-color': '#14222d' if 'dark' in route.request.url else '#edf1f3'}}]}
        route.fulfill(status=200, content_type='application/json', body=json.dumps(style))
    page.route('https://tiles.openfreemap.org/styles/**', local_style)
    def ready():
        page.wait_for_function('window.card?._map?.loaded() && window.card?._pins?.size===5', timeout=30000)
        page.wait_for_timeout(450)
    def instrument():
        page.evaluate('''() => {
          window.revealCalls=[];
          const original=Element.prototype.scrollIntoView;
          Element.prototype.scrollIntoView=function(options) {
            if(this.classList.contains('result-card')) window.revealCalls.push({key:this.dataset.key,options});
            return original.call(this,options);
          };
          window.lastKey=()=>osmKey(window.card._visible.at(-1));
          window.clickLast=()=>window.card._pins.get(window.lastKey()).button.click();
          window.fold=()=>window.card._setResultsExpanded(false);
          window.replaceState=()=>{window.ha.states['sensor.parking_suggestions']={state:'ok',attributes:window.attributes};window.card.hass=window.ha;};
        }''')
    def no_extra_scroll(count):
        page.wait_for_timeout(180)
        assert page.evaluate('revealCalls.length') == count
    try:
        page.goto(f'http://127.0.0.1:{server.server_port}/tests/card/preview.html')
        ready(); instrument()
        assert page.locator('.results-toggle').get_attribute('aria-expanded') == 'false'
        assert not page.locator('.results-panel').is_visible()
        assert page.locator('.osm-park-marker').count() == 5
        assert page.locator('.search').is_visible()
        assert page.locator('.sort').is_visible()
        assert page.evaluate('window.serviceCalls.length') == 0
        checked('fresh load is folded; map markers and filters/sorting remain usable')
        page.screenshot(path=str(OUT/'results-folded-mobile.png'), full_page=True)

        page.evaluate('''() => {
          const scroller=document.createElement('main');scroller.id='dashboard-scroll';
          scroller.style.cssText='height:100vh;overflow-y:auto;padding:12px;box-sizing:border-box';
          const footer=document.createElement('div');footer.style.height='900px';
          const host=document.getElementById('host');document.body.append(scroller);
          scroller.append(document.querySelector('.preview-label'),host,footer);
          document.body.style.padding='0';document.body.style.margin='0';
        }''')
        before = page.evaluate('window.card._map.getCenter().toArray().concat(window.card._map.getZoom())')
        key = page.evaluate('lastKey()')
        page.locator('.osm-park-marker').last.click()
        page.wait_for_function('window.revealCalls.length===1')
        assert page.locator('.results-panel').is_visible()
        assert page.locator('.result-card.selected').get_attribute('data-key') == key
        assert page.locator('.osm-park-marker.selected').count() == 1
        assert page.evaluate('revealCalls[0].key') == key
        page.wait_for_function('''() => {
          const r=window.card._rows.get(window.card._selected).getBoundingClientRect();
          return r.top>=0 && r.bottom<=innerHeight+1;
        }''')
        assert page.locator('#dashboard-scroll').evaluate('(e)=>e.scrollTop') > 0
        assert page.evaluate('window.card._map.getCenter().toArray().concat(window.card._map.getZoom())') == before
        assert not page.locator('.result-details').last.evaluate('(e)=>e.open')
        checked('pointer marker click opens, highlights and scrolls exact row in nested dashboard without moving map')
        page.screenshot(path=str(OUT/'results-marker-revealed-mobile.png'), full_page=True)

        page.locator('.results-toggle').click()
        assert not page.locator('.results-panel').is_visible()
        page.locator('.results-toggle').focus()
        page.keyboard.press('Enter')
        assert page.locator('.results-panel').is_visible()
        page.keyboard.press('Space')
        assert not page.locator('.results-panel').is_visible()
        no_extra_scroll(1)
        checked('manual show/hide supports Enter and Space without automatic scrolling')

        for mode in ('name', 'free_first', 'distance'):
            page.evaluate('fold()')
            page.locator('.sort').select_option(mode)
            target = page.evaluate('lastKey()')
            previous = page.evaluate('revealCalls.length')
            page.locator('.osm-park-marker').last.click()
            page.wait_for_function('(n)=>revealCalls.length===n', arg=previous+1)
            assert page.locator('.result-card.selected').get_attribute('data-key') == target
        checked('marker-to-row reveal remains correct after sorting')
        previous = page.evaluate('revealCalls.length')
        page.evaluate('fold()')
        page.locator('.search').fill('City Centre')
        assert not page.locator('.results-panel').is_visible()
        assert page.locator('.osm-park-marker').count() == 1
        page.locator('.osm-park-marker').click()
        page.wait_for_function('(n)=>revealCalls.length===n', arg=previous+1)
        assert 'City Centre' in page.locator('.result-card.selected').inner_text()
        page.locator('.reset-filters').click()
        checked('filtering preserves collapsed state until its matching marker is selected')

        previous = page.evaluate('revealCalls.length')
        page.evaluate("window.attributes={...window.attributes,suggestions:window.sampleItems.map((v,i)=>i?v:{...v,free_capacity:29})};replaceState();window.applyTheme(false)")
        page.wait_for_function("window.card.dataset.mode==='light' && window.card._map.isStyleLoaded()")
        assert page.locator('.results-panel').is_visible()
        page.locator('.sort').select_option('source')
        no_extra_scroll(previous)
        page.evaluate('fold();window.applyTheme(true);replaceState()')
        assert not page.locator('.results-panel').is_visible()
        no_extra_scroll(previous)
        checked('live updates, sorting and theme changes preserve fold choice and never re-scroll')

        page.emulate_media(reduced_motion='reduce')
        page.locator('.osm-park-marker').last.focus()
        page.keyboard.press('Enter')
        page.wait_for_function('(n)=>revealCalls.length===n', arg=previous+1)
        assert page.evaluate('revealCalls.at(-1).options.behavior') == 'instant'
        assert page.locator('.result-card.selected .result-focus').evaluate('(e)=>e.getRootNode().activeElement===e')
        checked('keyboard marker activation focuses revealed row; reduced motion uses instant scrolling')
        page.emulate_media(reduced_motion='no-preference')

        previous = page.evaluate('revealCalls.length')
        page.evaluate('clickLast();fold()')
        no_extra_scroll(previous)
        assert not page.locator('.results-panel').is_visible()
        page.evaluate('''() => {
          const keys=window.card._visible.map(osmKey);
          window.card._pins.get(keys[0]).button.click();
          window.card._pins.get(keys.at(-1)).button.click();
        }''')
        page.wait_for_function('(n)=>revealCalls.length===n', arg=previous+1)
        assert page.evaluate('revealCalls.at(-1).key===lastKey()')
        checked('collapse cancels pending reveal; rapid marker clicks reveal only final selection')

        previous = page.evaluate('revealCalls.length')
        page.evaluate("clickLast();window.card._ui.query='zz-none';window.card._filterChanged()")
        no_extra_scroll(previous)
        assert page.locator('.filter-empty').is_visible()
        page.locator('.filter-empty button').click()
        previous = page.evaluate('revealCalls.length')
        page.locator('.result-focus').first.click()
        no_extra_scroll(previous)
        assert page.locator('.osm-park-marker.selected').count() == 1
        checked('filtered targets cannot trigger stale scrolling; list-to-map selection is preserved')

        previous = page.evaluate('revealCalls.length')
        page.evaluate('clickLast();window.card.remove()')
        no_extra_scroll(previous)
        assert page.evaluate('window.card._revealFrame===null')
        page.evaluate("document.getElementById('host').shadowRoot.append(window.card)")
        ready()
        assert page.locator('canvas.maplibregl-canvas').count() == 1
        checked('disconnect cancels pending scroll and reconnect creates one map')

        page.evaluate("window.card.setConfig({entity:'sensor.parking_suggestions',map_height:220,show_list:false,remember_filters:false});window.card.hass=window.ha")
        ready(); previous = page.evaluate('revealCalls.length')
        page.locator('.osm-park-marker').last.click()
        no_extra_scroll(previous)
        assert not page.locator('.results-toggle').is_visible()
        assert not page.locator('.results-panel').is_visible()
        assert page.locator('.maplibregl-popup').count() == 1
        checked('show_list false stays map-only and retains marker popup')

        page.evaluate("window.card.setConfig({entity:'sensor.parking_suggestions',map_height:220,show_filters:false,remember_filters:false});window.card.hass=window.ha")
        ready()
        assert page.locator('.results-toggle').is_visible()
        assert not page.locator('.search').is_visible()
        page.locator('.results-toggle').click()
        assert page.locator('.results-panel').is_visible()
        checked('results disclosure remains usable with filter controls hidden')

        page.evaluate("window.card.setConfig({entity:'sensor.parking_suggestions',map_height:220});window.card.hass=window.ha")
        ready()
        for width in (320, 390, 900):
            page.set_viewport_size({'width': width, 'height': 900})
            for locale in ('en','el','de','es','fr','it','nl','pl','pt','pt-BR','ru','tr','zh-Hans','ja'):
                page.evaluate('(locale)=>{window.ha={...window.ha,language:locale};window.card.hass=window.ha}', locale)
                label=page.locator('.results-toggle-label').inner_text()
                assert label and not label.startswith('show_results')
                assert not page.locator('.results-panel').is_visible()
                assert page.locator('.parking-explorer').evaluate('(e)=>e.scrollWidth<=e.clientWidth+1')
                page.locator('.results-toggle').click()
                assert page.locator('.results-toggle-label').inner_text()!=label
                page.locator('.results-toggle').click()
        checked('14 localized show/hide labels without overflow at 320, 390 and 900px')

        page.evaluate("window.card._mapFailure(new Error('Test tile outage'))")
        page.locator('.results-toggle').click()
        assert page.locator('.result-card').first.is_visible()
        assert page.locator('.navigate').first.get_attribute('href').startswith('https:')
        checked('tile failure leaves manual expansion and navigation usable')
        assert page.evaluate('window.serviceCalls.length') == 0
        page.reload(); ready()
        assert not page.locator('.results-panel').is_visible()
        page.locator('.results-toggle').click()
        page.evaluate("window.ha={...window.ha,user:{id:'other'}};window.card.hass=window.ha")
        assert not page.locator('.results-panel').is_visible()
        checked('reload and user change start folded; expansion is not persisted')
        assert not report['errors'], report['errors']
        report['passed']=True
    except Exception as exc:
        report['passed']=False;report['failure']=repr(exc)
        page.screenshot(path=str(OUT/'results-disclosure-failure.png'), full_page=True)
        raise
    finally:
        (OUT/'results-disclosure-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
        browser.close();server.shutdown()
print('RESULTS_DISCLOSURE_SCENARIOS='+str(len(report['scenarios'])))
