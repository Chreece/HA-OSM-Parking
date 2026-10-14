"""One-time transformation; preserve provider resilience and the rebuilt card."""
from pathlib import Path
import subprocess
import sys
ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / 'tools/card'


def replace(path, old, new):
    content = path.read_text(encoding='utf-8')
    if content.count(old) != 1:
        raise RuntimeError(f'Expected exactly one target in {path}: {old[:100]}')
    path.write_text(content.replace(old, new), encoding='utf-8')


js = UI / 'explorer.js'
replace(js, 'class OsmParkingExplorerCard extends OsmParkingMapCardV070 {', '''let osmResultsRegionId = 0;

class OsmParkingExplorerCard extends OsmParkingMapCardV070 {''')
replace(js, '    this._originalConfig = {...config};', '''    this._originalConfig = {...config};
    // Expansion is view state, not a saved preference: every new card starts folded.
    this._resultsExpanded=false; this._contentVisible=false;''')
replace(js, '    clearTimeout(this._styleTimer);\n', '''    clearTimeout(this._styleTimer);
    this._cancelResultReveal();
''')
replace(js, '    this._prefKey=key;', '''    this._prefKey=key;
    this._resultsExpanded=false; this._cancelResultReveal();
    this._selected=null; this._popup?.remove();''')
replace(js, '    this._els.frame=frame;this._els.tools=tools;this._els.note=note;this._els.empty=empty;', '''    const results=document.createElement('section');results.className='results-panel';
    results.id=`osm-parking-results-${++osmResultsRegionId}`;results.hidden=true;
    const toggle=document.createElement('button');toggle.type='button';toggle.className='results-toggle';
    toggle.setAttribute('aria-controls',results.id);toggle.setAttribute('aria-expanded','false');
    const caption=document.createElement('span');caption.className='results-toggle-label';
    const chevron=document.createElement('span');chevron.className='results-chevron';chevron.setAttribute('aria-hidden','true');chevron.textContent='⌄';
    toggle.append(caption,chevron);empty.before(toggle,results);results.append(empty,this._els.list);
    this._els.results=results;this._els['results-toggle']=toggle;
    toggle.addEventListener('click',()=>this._setResultsExpanded(!this._resultsExpanded));
    this._els.frame=frame;this._els.tools=tools;this._els.note=note;this._els.empty=empty;''')
replace(js, '  _setContentVisible(visible) {', '''  _cancelResultReveal() {
    cancelAnimationFrame(this._revealFrame);this._revealFrame=null;
  }
  _syncResultsDisclosure() {
    const e=this._els;if(!e?.results) return;
    const allowed=this._contentVisible && this.config.show_list!==false;
    e.results.hidden=!allowed || !this._resultsExpanded;
    e['results-toggle'].hidden=!allowed;
    e['results-toggle'].setAttribute('aria-expanded',String(allowed && this._resultsExpanded));
    e['results-toggle'].querySelector('.results-toggle-label').textContent=
      `${this._xt(this._resultsExpanded?'hide_results':'show_results')} (${this._visible?.length || 0})`;
    e.results.setAttribute('aria-label',this._t('suggestions'));
  }
  _setResultsExpanded(expanded) {
    this._resultsExpanded=expanded && this.config.show_list!==false;
    if(!this._resultsExpanded) {
      this._cancelResultReveal();
      // Avoid leaving keyboard focus inside a section we are about to hide.
      const active=this.getRootNode().activeElement;
      if(active && this._els.results.contains(active)) this._els['results-toggle'].focus({preventScroll:true});
    }
    this._syncResultsDisclosure();
  }
  _revealResult(key, keyboard=false) {
    this._cancelResultReveal();
    if(this.config.show_list===false || !this._contentVisible) return;
    this._setResultsExpanded(true);
    const epoch=this._epoch;
    // Resolve by stable facility key, not marker number: sorting may change
    // before the formerly hidden panel participates in layout.
    this._revealFrame=requestAnimationFrame(()=>{
      this._revealFrame=null;
      if(epoch!==this._epoch || !this.isConnected || !this._contentVisible || !this._resultsExpanded || this._selected!==key) return;
      const row=this._rows.get(key);
      if(!row?.isConnected || !this._visible.some(item=>osmKey(item)===key)) return;
      if(keyboard) row.querySelector('.result-focus')?.focus({preventScroll:true});
      row.scrollIntoView({block:'nearest',inline:'nearest',behavior:
        window.matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'});
    });
  }
  _setContentVisible(visible) {''')
replace(js, '    this._els.frame.hidden=!visible;', '''    this._contentVisible=visible;
    if(!visible) this._cancelResultReveal();
    this._syncResultsDisclosure();
    this._els.frame.hidden=!visible;''')
replace(js, '    this._renderList(this._visible);\n  }', '''    this._renderList(this._visible);
    this._syncResultsDisclosure();
  }''')
replace(js, '''  _focusItem(key) {
    this._selected=key;
    this._renderList(this._visible);this._syncMarkers();
    const item=this._visible.find(i=>osmKey(i)===key),pin=this._pins.get(key);
    if(!item || !this._map || !pin) return;''', '''  _focusItem(key, {fromMap=false, keyboard=false}={}) {
    const item=this._visible.find(i=>osmKey(i)===key);
    if(!item) return;
    this._cancelResultReveal();this._selected=key;
    this._renderList(this._visible);this._syncMarkers();
    const pin=this._pins.get(key);
    if(fromMap && this.config.show_list!==false) {
      // Marker selection reveals the list, without competing popup/camera
      // movement. List selection retains the existing map-focus action.
      this._popup?.remove();this._popup=null;
      this._revealResult(key,keyboard);return;
    }
    if(!this._map || !pin) return;''')
replace(js, 'button.onclick=()=>this._focusItem(key);', 'button.onclick=event=>{event.stopPropagation();this._focusItem(key,{fromMap:true,keyboard:event.detail===0});};')
replace(js, "new maplibregl.Popup({offset:20,maxWidth:'280px'})", "new maplibregl.Popup({offset:20,maxWidth:'280px',focusAfterOpen:false})")
with (UI / 'explorer.css').open('a', encoding='utf-8') as f:
    f.write('''
/* Map-first disclosure. No height animation: scrolling uses final layout. */
osm-parking-map-card[data-explorer] .results-toggle {display:flex;align-items:center;justify-content:space-between;gap:12px;width:calc(100% - 28px);min-height:44px;margin:6px 14px 14px;padding:10px 12px;border:1px solid var(--ex-line);border-radius:12px;background:var(--ex-surface);color:var(--ex-fg);font-size:.82rem;font-weight:600;text-align:start;}
osm-parking-map-card[data-explorer] .results-toggle-label {min-width:0;overflow-wrap:anywhere;}
osm-parking-map-card[data-explorer] .results-toggle:hover,osm-parking-map-card[data-explorer] .results-toggle[aria-expanded=true] {border-color:var(--ex-accent);color:var(--ex-accent);}
osm-parking-map-card[data-explorer] .results-chevron {flex:none;font-size:20px;line-height:1;}
osm-parking-map-card[data-explorer] .results-toggle[aria-expanded=true] .results-chevron {transform:rotate(180deg);}
osm-parking-map-card[data-explorer] .results-panel {min-width:0;}
osm-parking-map-card[data-explorer] .result-card {scroll-margin-top:calc(var(--header-height,56px) + 16px);scroll-margin-bottom:16px;}
@media(max-width:450px) {osm-parking-map-card[data-explorer] .results-toggle {width:calc(100% - 20px);margin-left:10px;margin-right:10px;}}
''')
labels = {
    'en': ['Show results', 'Hide results'],
    'el': ['Εμφάνιση αποτελεσμάτων', 'Απόκρυψη αποτελεσμάτων'],
    'de': ['Ergebnisse anzeigen', 'Ergebnisse ausblenden'],
    'es': ['Mostrar resultados', 'Ocultar resultados'],
    'fr': ['Afficher les résultats', 'Masquer les résultats'],
    'it': ['Mostra risultati', 'Nascondi risultati'],
    'nl': ['Resultaten tonen', 'Resultaten verbergen'],
    'pl': ['Pokaż wyniki', 'Ukryj wyniki'],
    'pt': ['Mostrar resultados', 'Ocultar resultados'],
    'pt-BR': ['Mostrar resultados', 'Ocultar resultados'],
    'ru': ['Показать результаты', 'Скрыть результаты'],
    'tr': ['Sonuçları göster', 'Sonuçları gizle'],
    'zh-Hans': ['显示结果', '隐藏结果'],
    'ja': ['結果を表示', '結果を非表示'],
}
replace(UI/'locales.py', 'def translations():', 'DISCLOSURE_LABELS = '+repr(labels)+'\n\ndef translations():')
replace(UI/'locales.py', '        out[locale]=dict(zip(KEYS,values))', '''        out[locale]=dict(zip(KEYS,values))
        out[locale].update(zip(('show_results','hide_results'),DISCLOSURE_LABELS[locale]))''')

# Existing list-interaction scenarios open the list explicitly where needed.
browser = ROOT / 'tests/card/browser_check.py'
replace(browser, "        assert page.locator('.result-card').count()==5\n        assert page.locator('.map').evaluate", """        assert not page.locator('.results-panel').is_visible()
        assert page.locator('.results-toggle').get_attribute('aria-expanded')=='false'
        page.locator('.results-toggle').click()
        checked('new card starts folded; manual disclosure opens results')
        assert page.locator('.result-card').count()==5
        assert page.locator('.map').evaluate""")
replace(browser, "        checked('preferences are isolated when Home Assistant user changes')", """        assert not page.locator('.results-panel').is_visible()
        checked('preferences are isolated when Home Assistant user changes')""")
replace(browser, "        page.locator('.result-focus').first.click()", """        if not page.locator('.results-panel').is_visible():
            page.locator('.results-toggle').click()
        page.locator('.result-focus').first.click()""")
replace(browser, "        page.screenshot(path=str(OUT/'desktop-light.png'),full_page=True)", """        page.locator('.results-toggle').click()
        page.screenshot(path=str(OUT/'desktop-light.png'),full_page=True)""")
replace(ROOT/'.github/workflows/card-visual.yml', '          python3 tests/card/map_controls_check.py', '''          python3 tests/card/map_controls_check.py
          python3 tests/card/results_disclosure_check.py''')
replace(ROOT/'README.md', 'Map markers and rows share the same visible numbering.', '''The results list starts **collapsed** on each new card load. The map, search, filters and sorting stay usable. Click a parking marker to expand the list, highlight that exact facility and scroll it into view. This does not reset the map camera or expand every result's details. Use **Show results / Hide results** to fold the list manually. Expansion survives ordinary data/theme/filter updates but is not persisted across a reload. Keyboard activation and reduced-motion preferences are respected. An explicit `show_list: false` retains map-only mode, without auto-expansion.

Map markers and rows share the same visible numbering.''')
replace(ROOT/'CHANGELOG.md', '## v1.4.0\n', '''## v1.4.0

### Map-first result browsing

- Results start folded on a fresh card load; the map and local filter/sort controls remain visible.
- Clicking or keyboard-activating a parking marker expands the list, highlights the matching stable facility and scrolls it into view. It does not change the map camera or request new data.
- Added a localized Show/Hide results button in all 14 card languages. Ordinary updates preserve expansion without scrolling again; reloading starts folded.
- Preserve explicit map-only mode, list-to-map focus, reduced-motion scrolling, source deduplication and the pending provider-resilience changes below.
''')
subprocess.run([sys.executable, str(UI/'build.py')], cwd=ROOT, check=True)
print('RESULTS_DISCLOSURE_PATCH=PASS')
