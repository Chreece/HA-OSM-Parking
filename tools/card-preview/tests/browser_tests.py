"""Interaction tests of the real UI extension using the offline MapLibre double.
Not a Home Assistant integration or external-tile connectivity test.
Run: python tests/browser_tests.py (Playwright + Chromium required).
"""
from pathlib import Path
import os, shutil
import json
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'preview'
results=[]
def check(name, ok):
    if not ok: raise AssertionError(name)
    results.append(name)

with sync_playwright() as p:
    browser=p.chromium.launch(executable_path=shutil.which('chromium') or None,headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])
    context=browser.new_context(viewport={'width':1060,'height':1200},device_scale_factor=1)
    page=context.new_page();errors=[]
    page.on('pageerror',lambda e: errors.append(str(e)))
    html=(OUT/'index.html').read_text()
    bundle = os.environ.get('OSM_BETA_BUNDLE')
    if bundle:
        # Exercise the complete release module, not the old-method adapter.
        html = html.replace('<script src="legacy-adapter.js"></script>', '')
        html = html.replace('<script src="../modern-card-extension.js"></script>',
            '<script>' + Path(bundle).read_text() + '</script>')
        html = html.replace("customElements.define('osm-parking-map-card',OsmParkingMapCardCompact);", '')
        # Only the transport/map are mocked. All legacy card methods are real.
        html = html.replace('<script src="mock-map.js"></script>',
            '<script>' + (OUT/'mock-map.js').read_text() + '</script>')
        html = html.replace('const card=document.querySelector',
            "OsmParkingMapCardCompact.prototype._ensureMapLibre = async function() { "
            "if(window.MOCK_DELAY) await new Promise(r=>setTimeout(r,window.MOCK_DELAY)); "
            "if(window.MOCK_MAP_FAIL) throw new Error('offline simulated failure'); }; "
            'const card=document.querySelector')
    else:
        for src in ['legacy-adapter.js','mock-map.js','../modern-card-extension.js']:
            html=html.replace(f'<script src="{src}"></script>', '<script>'+(OUT/src).resolve().read_text()+'</script>')
    # Offline rendering on about:blank: no external navigation is required.
    # Storage is a test double because opaque origins deny sessionStorage.
    html=html.replace('<script>', '<script>window.__store=new Map();Object.defineProperty(window,"sessionStorage",{value:{getItem:k=>__store.get(k)||null,setItem:(k,v)=>__store.set(k,v)}});</script><script>', 1)
    page.set_content(html)
    page.wait_for_function('window.card && card._mapReady')
    check('initial render without JavaScript error',not errors)
    check('all five samples visible',page.locator('.parking-row').count()==5)
    check('compact default map is 250 px',page.locator('.map').evaluate('(e)=>e.clientHeight')==250)
    check('automatic dark map style',page.evaluate("card._mapStyle.endsWith('/dark')"))
    check('default nearest-first order',page.locator('.row-title').first.inner_text()=='Rheinpark Garage')
    page.screenshot(path=str(OUT/'desktop-dark.png'),full_page=True)
    page.locator('#toggle').click();page.wait_for_function("card._mapReady && card._mapStyle.endsWith('/positron')")
    page.screenshot(path=str(OUT/'desktop-light.png'),full_page=True)
    page.locator('#toggle').click();page.wait_for_function("card._mapReady && card._mapStyle.endsWith('/dark')")
    page.locator('.filter-button').click()
    page.locator('.filter-type').select_option('street')
    check('type filter narrows results',page.locator('.parking-row').count()==1 and page.locator('.row-title').inner_text()=='Deutzer Freiheit')
    check('filtered markers and rows match',page.evaluate("card._markers.filter(m=>m._itemKey).length===card._view.length"))
    check('visible row and marker use same number',page.locator('.number').inner_text()=='1' and page.locator('.osm-park-marker').inner_text()=='1')
    page.locator('.clear').click()
    page.locator('.filter-fee').select_option('no')
    check('free filter excludes unknown and paid',page.locator('.parking-row').count()==1)
    page.locator('.clear').click()
    page.locator('.filter-distance').select_option('500')
    check('distance filter',page.locator('.parking-row').count()==2)
    page.locator('.clear').click()
    page.locator('.filter-data').select_option('live')
    check('verified-live filter excludes reported/estimated',page.locator('.parking-row').count()==1)
    page.locator('.clear').click()
    page.locator('.sort').select_option('availability')
    check('availability sort uses real reported counts, no estimates',page.locator('.row-title').first.inner_text()=='Messe / Deutz P+R')
    check('marker labels follow sorted list',page.locator('.osm-park-marker').all_text_contents()==['1','2','3','4','5'])
    page.locator('.sort').select_option('distance_desc')
    check('farthest-first sort',page.locator('.row-title').first.inner_text()=='Riverside Surface Parking')
    page.locator('.sort').select_option('name')
    check('name sort',page.locator('.row-title').first.inner_text()=='Deutzer Freiheit')
    page.locator('.sort').select_option('type')
    check('type sort retains all results',page.locator('.parking-row').count()==5)
    page.locator('.sort').select_option('distance')
    page.locator('.search').fill('arena')
    page.wait_for_timeout(180)
    check('text search',page.locator('.parking-row').count()==1 and page.locator('.row-title').inner_text()=='Lanxess Arena P2')
    fits=page.evaluate('MAP_STATS.fit'); created=page.evaluate('MAP_STATS.created')
    page.evaluate("card.hass=makeHass([...sample.map(s=>({...s})),{...sample[0],provider_id:'new',name:'New Garage',distance_m:1200}])")
    check('data update retains filters',page.locator('.search').input_value()=='arena' and page.locator('.parking-row').count()==1)
    check('data update neither remounts nor recentres map',page.evaluate('MAP_STATS.created')==created and page.evaluate('MAP_STATS.fit')==fits)
    page.locator('.search').fill('no such parking');page.wait_for_timeout(180)
    check('empty filtered state has reset action',page.locator('.reset').is_visible() and page.locator('.parking-row').count()==0)
    page.locator('.reset').click();page.evaluate('pushHass()')
    page.locator('.filter-button').click()
    page.locator('.row-select').first.click()
    check('select result highlights same marker',page.locator('.parking-row.selected').count()==1 and page.locator('.osm-park-marker.active').count()==1)
    page.locator('.row-bottom summary').first.click()
    page.locator('.osm-park-marker').nth(1).click()
    check('map selection highlights its corresponding row',page.locator('.osm-park-marker.active').inner_text()=='2' and page.locator('.parking-row.selected .row-title').inner_text()=='Deutzer Freiheit')
    check('source details disclosed on demand',page.locator('details[open] .detail-content').is_visible())
    page.evaluate('card.hass=makeHass(sample.map(s=>({...s,extra:1})))')
    check('opened source details remain open during updates',page.locator('.row-bottom details[open]').count()==1)
    check('navigation URL retained',page.locator('.navigate').first.get_attribute('href').startswith('https://www.google.com/maps/dir/'))
    page.locator('.refresh').click()
    check('explicit refresh calls correct HA service',page.evaluate("serviceCalls[0][0]==='homeassistant' && serviceCalls[0][1]==='update_entity'"))
    check('unsafe navigation URLs are rejected',page.evaluate("osmUiSafeUrl('javascript:alert(1)')==='' && osmUiSafeUrl('data:text/html,hi')===''"))
    check('null counts are never zero free spaces',page.evaluate("osmUiFree({availability_kind:'live',free_capacity:null})===null"))
    check('unknown distance sorts last',page.evaluate("osmUiSelect([{name:'Unknown',distance_m:null},{name:'Known',distance_m:20}],OSM_UI_DEFAULTS,'en',i=>i.category)[1].name==='Unknown'"))
    check('closed parking does not rank as available',page.evaluate("osmUiFree({availability_kind:'live',opening_status:'closed',free_capacity:22})===null"))
    check('negative / fractional / beyond capacity not shown as free',page.evaluate("[-1,1.5,101].every(n=>osmUiFree({availability_kind:'reported',free_capacity:n,capacity:100})===null)"))
    check('type filter also matches known physical type on paid facility',page.evaluate("osmUiTypes({category:'paid',parking_type:'underground'}).has('underground')"))
    check('filter and sort do not mutate backend list',page.evaluate('JSON.stringify(sample)===originalSamples'))
    check('all 14 new-label translations are complete',page.evaluate("Object.keys(OSM_PARKING_UI_LABEL_VALUES).length===14 && Object.values(OSM_PARKING_UI_LABEL_VALUES).every(v=>v.length===OSM_PARKING_UI_LABEL_KEYS.length && v.every(s=>typeof s==='string'&&s.length))"))
    # User can pan without refresh or filter implicitly undoing their camera.
    page.locator('.fit').click();check('recenter happens on explicit button',page.evaluate('MAP_STATS.fit')>fits)
    page.locator('.expand').click();check('map expands on demand',page.locator('.map').evaluate('(e)=>e.clientHeight')==440)
    page.locator('.expand').click();check('map compacts on demand',page.locator('.map').evaluate('(e)=>e.clientHeight')==250)
    # Restore polygons across style changes and prove handlers don't duplicate.
    page.evaluate("""window.zones=[{type:'Feature',geometry:{type:'Polygon',coordinates:[[[6.98,50.937],[6.983,50.937],[6.983,50.94],[6.98,50.937]]]},properties:{record_type:'zone',name:'Sample zone'}}];var h=makeHass();h.states['sensor.parking_suggestions'].attributes.parking_zones=zones;card.hass=h;""")
    check('zone layer is independent of parking results',page.evaluate("!!card._map.getSource('osm-parking-controlled-zones') && card._view.length===5"))
    for mode in ['light','dark','light','dark']:
        page.locator('.theme').select_option(mode);page.wait_for_function('card._mapReady')
    check('zone layers restored after theme changes',page.evaluate("card._map.getSource('osm-parking-controlled-zones').data.features.length===1"))
    check('style switches do not accumulate zone event handlers',page.evaluate("card._map.handlers.click.filter(h=>h[0]==='osm-parking-controlled-zones-fill').length===1"))
    page.locator('.theme').select_option('auto');page.wait_for_function('card._mapReady')
    page.locator('#toggle').click();page.wait_for_function("card._mapStyle.endsWith('/positron') && card._mapReady")
    check('HA light theme swaps to light base map',page.locator('osm-parking-map-card').get_attribute('data-dark')=='false')
    page.locator('.row-bottom details[open] summary').click()
    page.evaluate('pushHass()')
    # Partial data remains usable; a map failure also leaves list interactive.
    page.evaluate("var h=makeHass();h.states['sensor.parking_suggestions'].attributes.partial_data=true;h.states['sensor.parking_suggestions'].attributes.provider_errors={example:'unavailable'};card.hass=h")
    check('partial-source warning keeps map and result list visible',page.locator('.status-panel').is_visible() and page.locator('.parking-row').count()==5)
    page.evaluate("var h=makeHass();h.states['sensor.parking_suggestions'].state='error';card.hass=h")
    check('backend error clears stale markers and visible suggestions',page.locator('.results-section').is_hidden() and page.evaluate('card._markers.length')==0)
    page.evaluate('pushHass()');check('same good payload recovers from error',page.locator('.parking-row').count()==5)
    page.evaluate('window.MOCK_MAP_FAIL=true;card._disposeMap();card._ensureCompactMap()')
    page.wait_for_function('card._mapIssue')
    check('map failure preserves usable results',page.locator('.parking-row').count()==5 and page.locator('.retry-map').is_visible())
    page.evaluate('window.MOCK_MAP_FAIL=false');page.locator('.retry-map').click();page.wait_for_function('card._mapReady')
    check('map can retry without page reload',not page.locator('.map-message').is_visible())
    # Rapid destination updates during asynchronous startup do not display old data.
    page.evaluate("window.MOCK_DELAY=80;card._disposeMap();card._ensureCompactMap();var h=makeHass();h.states['sensor.parking_suggestions'].attributes.destination_longitude=7.01;h.states['sensor.parking_suggestions'].attributes.suggestions=[];card.hass=h;")
    page.wait_for_function('card._mapReady')
    check('late map load uses newest destination/data',page.evaluate('card._map.c.center[0]===7.01 && card._view.length===0 && card._markers.length===1'))
    page.evaluate('window.MOCK_DELAY=0;pushHass()')
    # Disconnection removes WebGL/listeners and reconnect creates one map.
    before=page.evaluate('MAP_STATS.removed')
    page.evaluate('card.remove()');check('disconnect frees map resources',page.evaluate('MAP_STATS.removed')==before+1)
    page.evaluate("document.querySelector('main').append(card)");page.wait_for_function('card._mapReady')
    check('reconnect restores card',page.locator('.parking-row').count()==5)
    # Native focus/keyboard controls, shadow containment, no automatic page jump.
    page.locator('.filter-button').focus();page.keyboard.press('Enter')
    check('filter drawer is keyboard-operable',page.locator('#filter-panel').is_visible())
    page.locator('.filter-button').click()
    check('scoped stylesheet cannot affect neighboring titles/lists',page.evaluate("document.querySelector('.test-sibling .title').getRootNode()===document && card.shadowRoot.querySelector('style')!==null && card.children.length===0"))
    page.set_viewport_size({'width':390,'height':1100});page.locator('#toggle').click();page.wait_for_function('card._mapReady')
    page.locator('#language').select_option('el')
    check('Greek new controls are localized',page.locator('.search').get_attribute('placeholder')=='Αναζήτηση στάθμευσης')
    check('mobile card fits within viewport',page.evaluate('document.documentElement.scrollWidth<=390'))
    check('long Greek row labels stay within card',page.evaluate("[...card.shadowRoot.querySelectorAll('.parking-row')].every(e=>e.scrollWidth<=e.clientWidth+1)"))
    page.screenshot(path=str(OUT/'mobile-greek-dark.png'),full_page=True)
    page.set_viewport_size({'width':320,'height':1000})
    page.evaluate("card.hass=makeHass(sample.map((s,i)=>i===0?{...s,name:'Πολύ μεγάλο όνομα χώρου στάθμευσης για έλεγχο αναδίπλωσης',price:'€2.50 / hour · €15 / day'}:s))")
    check('320px long Greek labels do not overflow',page.evaluate("document.documentElement.scrollWidth<=320 && [...card.shadowRoot.querySelectorAll('.parking-row')].every(e=>e.scrollWidth<=e.clientWidth+1)"))
    page.set_viewport_size({'width':390,'height':1100});page.evaluate('pushHass()')
    page.locator('.filter-button').click();page.screenshot(path=str(OUT/'mobile-greek-filters.png'),full_page=True)
    # Persist filter choice across re-creation/reload, scoped by user.
    page.locator('.filter-fee').select_option('no')
    page.evaluate("const cfg={...card.config};card.setConfig(cfg);card.hass=makeHass()");page.wait_for_function('card._mapReady')
    check('tab-scoped filter restoration after card recreation (storage double)',page.locator('.parking-row').count()==1 and page.evaluate("card._filters.fee==='no'"))
    page.evaluate("var h=makeHass();h.user.id='other-user';card.hass=h")
    check('persisted filters scoped to HA user',page.locator('.parking-row').count()==5)
    # Graphical editor emits config changes without stripping unknown options.
    check('visual editor offered',page.evaluate("!!OsmParkingMapCardCompact.getConfigElement()"))
    page.evaluate("window.editor=OsmParkingMapCardCompact.getConfigElement();document.body.append(editor);editor.hass=makeHass();editor.setConfig({entity:'sensor.parking_suggestions',show_zones:false,custom_option:42});editor.addEventListener('config-changed',e=>window.editResult=e.detail.config)")
    page.locator('osm-parking-compact-editor input[name=map_height]').fill('220');page.locator('osm-parking-compact-editor input[name=map_height]').dispatch_event('change')
    check('editor preserves unrelated settings',page.evaluate('editResult.map_height===220 && editResult.show_zones===false && editResult.custom_option===42'))
    check('no unhandled JavaScript errors throughout',not errors)
    (OUT/'test-report.json').write_text(json.dumps({'passed':len(results),'tests':results,'page_errors':errors,'method':('Complete release JavaScript + synthetic HA state, storage and MapLibre doubles; not full HA runtime or external tiles' if bundle else 'Preview extension with inherited-method, storage and MapLibre doubles')},indent=2))
    print(json.dumps({'passed':len(results),'page_errors':errors,'screenshots':[p.name for p in OUT.glob('*.png')]},indent=2))
    browser.close()
