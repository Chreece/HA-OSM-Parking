"""Checked one-time presentation update on top of the pending provider work."""
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
UI=ROOT/'tools/card'


def replace(path,old,new):
    text=path.read_text(encoding='utf-8')
    if text.count(old)!=1:raise RuntimeError(f'Expected one target in {path}: {old[:80]}')
    path.write_text(text.replace(old,new),encoding='utf-8')


js=UI/'explorer.js'
replace(js,'class OsmParkingExplorerCard extends OsmParkingMapCardV070 {','let osmResultsPanelSequence = 0;\n\nclass OsmParkingExplorerCard extends OsmParkingMapCardV070 {')
replace(js,'    this._originalConfig = {...config};','    this._originalConfig = {...config};\n    this._resultsExpanded=false; this._contentVisible=false;')
replace(js,'    cancelAnimationFrame(this._resizeFrame); cancelAnimationFrame(this._renderFrame);','    cancelAnimationFrame(this._resizeFrame); cancelAnimationFrame(this._renderFrame);\n    this._cancelResultReveal();')
replace(js,'    this._prefKey=key;','    this._prefKey=key;\n    // New entity/user starts folded; ordinary data refreshes keep the choice.\n    this._resultsExpanded=false; this._selected=null; this._cancelResultReveal();')
replace(js,"    const empty=document.createElement('div');empty.className='filter-empty';empty.hidden=true;this._els.list.before(empty);",'''    const list=this._els.list, panel=document.createElement('section');
    panel.className='results-panel';panel.id=`osm-results-${++osmResultsPanelSequence}`;panel.hidden=true;
    const toggle=document.createElement('button');toggle.type='button';toggle.className='results-toggle';
    toggle.id=panel.id+'-toggle';toggle.setAttribute('aria-expanded','false');toggle.setAttribute('aria-controls',panel.id);
    toggle.innerHTML='<span class="results-toggle-label"></span><span class="results-chevron" aria-hidden="true">⌄</span>';
    panel.setAttribute('role','region');panel.setAttribute('aria-labelledby',toggle.id);
    list.before(toggle,panel);panel.append(list);list.hidden=true;
    this._els.resultsPanel=panel;this._els.resultsToggle=toggle;
    toggle.addEventListener('click',()=>this._setResultsExpanded(!this._resultsExpanded));
    // Keep empty/error recovery outside the folded list so it remains visible.
    const empty=document.createElement('div');empty.className='filter-empty';empty.hidden=true;panel.before(empty);''')
replace(js,"  _resetFilters() { const sort=this._ui.sort;this._ui=osmCleanPrefs({sort});this._filterChanged(); }",'''  _cancelResultReveal() {
    cancelAnimationFrame(this._revealFrame);this._revealFrame=null;
  }
  _syncResultsDisclosure() {
    const e=this._els;if(!e?.resultsPanel) return;
    const allowed=this._contentVisible && this.config.show_list!==false;
    const count=this._visible?.length || 0;
    const expanded=allowed && this._resultsExpanded && count>0;
    e.resultsToggle.hidden=!allowed;e.resultsToggle.disabled=!count;
    e.resultsToggle.setAttribute('aria-expanded',String(expanded));
    e.resultsToggle.querySelector('.results-toggle-label').textContent=`${this._xt(expanded?'hide_results':'show_results')} · ${count}`;
    e.resultsPanel.hidden=!expanded;e.list.hidden=!expanded;
  }
  _setResultsExpanded(expanded) {
    if(this.config.show_list===false || !this._contentVisible) return;
    this._resultsExpanded=!!expanded;
    if(!expanded) {
      this._cancelResultReveal();
      // Do not leave keyboard focus inside a newly hidden region.
      if(this._els.resultsPanel.matches(':focus-within')) this._els.resultsToggle.focus({preventScroll:true});
    }
    this._syncResultsDisclosure();
  }
  _revealResult(key, keyboard=false) {
    this._cancelResultReveal();
    if(this.config.show_list===false || !this._contentVisible) return;
    this._setResultsExpanded(true);
    const epoch=this._epoch;
    // Wait for the formerly hidden region's layout. Resolve the keyed row
    // again after refresh/sort, rather than capturing an obsolete DOM node.
    this._revealFrame=requestAnimationFrame(()=>{
      this._revealFrame=requestAnimationFrame(()=>{
        this._revealFrame=null;
        if(!this.isConnected || epoch!==this._epoch || !this._resultsExpanded
           || key!==this._selected || this._els.resultsPanel.hidden) return;
        const row=this._rows.get(key);
        if(!row?.isConnected || !this._visible.some(item=>osmKey(item)===key)) return;
        if(keyboard) row.querySelector('.result-focus')?.focus({preventScroll:true});
        row.scrollIntoView({block:'nearest',inline:'nearest',
          behavior:window.matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'});
      });
    });
  }
  _resetFilters() { const sort=this._ui.sort;this._ui=osmCleanPrefs({sort});this._filterChanged(); }''')
replace(js,"    this._els.list.hidden=!visible || this.config.show_list===false;", "    this._contentVisible=visible;this._syncResultsDisclosure();\n    if(!visible) this._cancelResultReveal();")
replace(js,"if(this._selected && !this._visible.some(i=>osmKey(i)===this._selected)) {this._selected=null;this._popup?.remove();}","if(this._selected && !this._visible.some(i=>osmKey(i)===this._selected)) {this._selected=null;this._popup?.remove();this._cancelResultReveal();}")
replace(js,"    this._renderList(this._visible);\n  }\n  _qualityText", "    this._renderList(this._visible);this._syncResultsDisclosure();\n  }\n  _qualityText")
replace(js,'''  _focusItem(key) {
    this._selected=key;
    this._renderList(this._visible);this._syncMarkers();
    const item=this._visible.find(i=>osmKey(i)===key),pin=this._pins.get(key);
''','''  _focusItem(key, {fromMap=false,keyboard=false}={}) {
    const item=this._visible.find(i=>osmKey(i)===key);
    if(!item) return;
    this._cancelResultReveal();this._selected=key;
    this._renderList(this._visible);this._syncMarkers();
    if(fromMap) this._revealResult(key,keyboard);
    const pin=this._pins.get(key);
''')
replace(js,"button.onclick=()=>this._focusItem(key);", "button.onclick=event=>{event.stopPropagation();this._focusItem(key,{fromMap:true,keyboard:event.detail===0});};")
css='''
/* Fold the results, never the matching map markers or recovery messages. */
osm-parking-map-card[data-explorer] .results-toggle {display:flex;align-items:center;justify-content:space-between;gap:10px;min-height:44px;width:calc(100% - 28px);margin:0 14px 14px;padding:10px 13px;border:1px solid var(--ex-line);border-radius:12px;background:var(--ex-surface);color:var(--ex-fg);font-size:.84rem;font-weight:650;text-align:start;}
osm-parking-map-card[data-explorer] .results-toggle:disabled {cursor:default;opacity:.6;}
osm-parking-map-card[data-explorer] .results-toggle-label {min-width:0;overflow-wrap:anywhere;}
osm-parking-map-card[data-explorer] .results-chevron {flex:none;font-size:20px;line-height:1;}
osm-parking-map-card[data-explorer] .results-toggle[aria-expanded=true] .results-chevron {transform:rotate(180deg);}
osm-parking-map-card[data-explorer] .results-panel {min-width:0;}
osm-parking-map-card[data-explorer] .result-card {scroll-margin-block:72px 16px;}
@media(max-width:450px) {osm-parking-map-card[data-explorer] .results-toggle {width:calc(100% - 20px);margin-left:10px;margin-right:10px;}}
'''
p=UI/'explorer.css';p.write_text(p.read_text()+css,encoding='utf-8')
labels={
'en':['Show results','Hide results'],'el':['Εμφάνιση αποτελεσμάτων','Απόκρυψη αποτελεσμάτων'],
'de':['Ergebnisse anzeigen','Ergebnisse ausblenden'],'fr':['Afficher les résultats','Masquer les résultats'],
'es':['Mostrar resultados','Ocultar resultados'],'it':['Mostra risultati','Nascondi risultati'],
'nl':['Resultaten tonen','Resultaten verbergen'],'pl':['Pokaż wyniki','Ukryj wyniki'],
'pt':['Mostrar resultados','Ocultar resultados'],'pt-BR':['Mostrar resultados','Ocultar resultados'],
'ru':['Показать результаты','Скрыть результаты'],'tr':['Sonuçları göster','Sonuçları gizle'],
'zh-Hans':['显示结果','隐藏结果'],'ja':['結果を表示','結果を非表示'],
}
replace(UI/'locales.py','def translations():','FOLD_LABELS = '+repr(labels)+'\n\ndef translations():')
replace(UI/'locales.py','        out[locale]=dict(zip(KEYS,values))',"        out[locale]=dict(zip(KEYS,values))\n        out[locale].update(zip(('show_results','hide_results'),FOLD_LABELS[locale]))")
browser=ROOT/'tests/card/browser_check.py'
replace(browser,"        assert page.locator('.result-card').count()==5\n        assert page.locator('.map').evaluate", "        assert page.locator('.results-toggle').get_attribute('aria-expanded')=='false'\n        assert not page.locator('.result-card').first.is_visible()\n        page.locator('.results-toggle').click()\n        assert page.locator('.result-card').count()==5\n        assert page.locator('.map').evaluate")
replace(browser,"        checked('browser-local filters survive reload without HA service calls')", "        checked('browser-local filters survive reload without HA service calls')\n        assert page.locator('.results-toggle').get_attribute('aria-expanded')=='false'")
replace(browser,"        page.locator('.result-focus').first.click()", "        page.locator('.results-toggle').click()\n        page.locator('.result-focus').first.click()")
replace(UI/'readme_screenshots.py','                    if filters:\n','                    page.locator(".results-toggle").click()\n                    if filters:\n')
replace(ROOT/'.github/workflows/card-visual.yml','          python3 tests/card/map_controls_check.py','          python3 tests/card/map_controls_check.py\n          python3 tests/card/fold_results_check.py')
documentation='''
### Folded results and map selection

The card loads with the **results list collapsed** while every matching map marker stays visible. Use **Show results** to browse the list manually. Clicking or keyboard-activating a parking marker opens the list, highlights the corresponding row and scrolls it into view after the layout updates. The row is matched by facility identity, not its position before a filter or sort.

Folding does not change the search, filters, sorting, parking data or provider requests. Ordinary data/theme updates retain your current open/closed state and do not scroll the page. A newly loaded card starts folded again; fold state is not saved with filter preferences. **Hide results** collapses the list again. Explicit `show_list: false` still means map-only; markers keep their existing popup without opening a disabled list. An empty-results recovery message remains accessible without expanding the list. Keyboard controls expose their expanded state, and reduced-motion settings disable animated scrolling.
'''
for p in (ROOT/'README.md',UI/'guide.md'):p.write_text(p.read_text()+'\n'+documentation,encoding='utf-8')
replace(ROOT/'CHANGELOG.md','## v1.4.0\n','''## v1.4.0

### Folded map results

- Start with the result list collapsed without hiding matching map markers. Add a localized Show/Hide results control in all 14 card languages.
- Selecting a parking marker expands the list, highlights its matching result and scrolls it into view; filter/sort order and stable facility identity stay aligned.
- Keep the open/closed state during ordinary updates without unsolicited scrolling. Cancel pending reveal work on removal, collapse, stale selection or user change; respect reduced-motion preferences and explicit map-only cards.
- Added real-MapLibre browser checks for default folding, marker click and keyboard reveal, actual viewport scrolling, sort/filter changes, multiple cards and lifecycle safety.
''')
subprocess.run([sys.executable,str(UI/'build.py')],cwd=ROOT,check=True)
print('FOLDED_RESULTS_PREPARED=PASS')
