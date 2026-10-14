"""One-time narrow presentation patch on the verified v1.4.0 release."""
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]


def replace(relative,old,new):
    path=ROOT/relative
    text=path.read_text(encoding='utf-8')
    if text.count(old)!=1:
        raise RuntimeError(f'Expected one patch target in {relative}: {old[:90]}')
    path.write_text(text.replace(old,new),encoding='utf-8')


replace('tools/card/explorer.js',"const OSM_EXPLORER_ICONS = {paid:'mdi:cash',open:'mdi:parking',street:'mdi:road-variant',underground:'mdi:car-lifted-pickup',multi_storey:'mdi:office-building',park_and_ride:'mdi:train-car',other:'mdi:parking'};\n",'')
replace('tools/card/explorer.js',"  _safeItem(item) {const copy={...item};for(const k of ['navigation_url','provider_url','osm_url','geo_uri']) copy[k]=this._url(copy[k]);return copy;}","  _safeItem(item) {const copy={...item,name:String(item.name || '').trim() || this._t('parking')};for(const k of ['navigation_url','provider_url','osm_url','geo_uri']) copy[k]=this._url(copy[k]);return copy;}")
replace('tools/card/explorer.js','<span class="result-number"></span>','<span class="result-icon" aria-hidden="true">${osmTypeIconMarkup(item)}</span>')
replace('tools/card/explorer.js','<ha-icon icon="${OSM_EXPLORER_ICONS[item.category] || \'mdi:parking\'}"></ha-icon>','')
replace('tools/card/explorer.js',"      row.querySelector('.result-number').textContent=String(index+1);","      // Display order is internal metadata. Selection uses the stable key.\n      row.dataset.index=String(index);row.dataset.type=osmIconType(item);")
replace('tools/card/explorer.js',"      pin.marker.setLngLat([ilon,ilat]);pin.button.textContent=String(index+1);pin.button.title=String(item.name || this._t('parking'));\n      pin.button.setAttribute('aria-label',`${index+1}. ${pin.button.title}`);pin.button.classList.toggle('selected',key===this._selected);",'''      const type=osmIconType(item);
      pin.marker.setLngLat([ilon,ilat]);
      // Reuse the actual button so type changes cannot lose keyboard focus.
      if(pin.button.dataset.type!==type) {
        pin.button.innerHTML=osmTypeIconMarkup(item);pin.button.dataset.type=type;
      }
      pin.button.dataset.key=key;pin.button.dataset.index=String(index);
      pin.marker._osmSuggestionIndex=index;
      const label=this._translations().categories[type] || this._t('parking');
      pin.button.title=`${label} · ${String(item.name || '').trim() || this._t('parking')}`;
      pin.button.setAttribute('aria-label',pin.button.title);
      pin.button.setAttribute('aria-pressed',String(key===this._selected));
      pin.button.classList.toggle('selected',key===this._selected);''')
p=ROOT/'tools/card/explorer.css'
css=p.read_text().replace('.result-number','.result-icon')
css+='''
/* Real type glyphs, not list ordinals. Buttons own focus/labels; SVGs decorate. */
osm-parking-map-card[data-explorer] .parking-type-glyph {display:block;width:22px;height:22px;flex:none;fill:currentColor;pointer-events:none;}
osm-parking-map-card[data-explorer] .parking-type-glyph * {pointer-events:none;}
osm-parking-map-card[data-explorer] .osm-park-marker {display:grid;place-items:center;width:36px;height:36px;min-width:36px;min-height:36px;padding:0;line-height:1;}
osm-parking-map-card[data-explorer] .result-icon .parking-type-glyph {width:22px;height:22px;}
'''
p.write_text(css,encoding='utf-8')
replace('tools/card/build.py',"    js = (UI / 'explorer.js').read_text(encoding='utf-8')","    js = (UI / 'type_icons.js').read_text(encoding='utf-8') + '\\n' + (UI / 'explorer.js').read_text(encoding='utf-8')")
replace('tools/card/build.py',"VERSION = '1.4.0'","VERSION = '1.4.1'")
replace('tools/card/explorer.js','<span class="version">v1.4.0</span>','<span class="version">v1.4.1</span>')
replace('tests/card/browser_check.py',"        assert page.locator('.osm-park-marker').inner_text()=='1'","        assert page.locator('.osm-park-marker').inner_text().strip()==''\n        assert page.locator('.osm-park-marker .parking-type-glyph').count()==1\n        assert page.evaluate(\"window.card._pins.get(osmKey(window.card._visible[0])).button.dataset.key===osmKey(window.card._visible[0])\")")
replace('tests/card/browser_check.py',"checked('type filter synchronizes marker and row numbering')","checked('type filter synchronizes marker icons and internal facility identity')")
replace('tests/card/browser_check.py',"pairs=page.evaluate('window.card._visible.map((i,n)=>[window.card._pins.get(osmKey(i)).button.textContent,String(n+1)])')","pairs=page.evaluate('window.card._visible.map((i,n)=>[window.card._pins.get(osmKey(i)).button.dataset.index,String(n)])')")
replace('tests/card/browser_check.py',"checked('all seven sorts retain marker-to-result numbering')","checked('all seven sorts retain internal marker-to-result index and identity')")
replace('.github/workflows/card-visual.yml','          node --test tests/card/filter.test.cjs','          node --test tests/card/filter.test.cjs tests/card/type_icons.test.cjs')
replace('.github/workflows/card-visual.yml','          python3 tests/card/results_disclosure_check.py','          python3 tests/card/results_disclosure_check.py\n          python3 tests/card/type_icons_check.py')
# Gallery screenshots deliberately show expanded results, while the runtime
# still starts folded. The actual marker/row icons need no preview substitutes.
replace('tools/card/readme_screenshots.py','                    if filters:\n','                    page.locator(".results-toggle").click()\n                    if filters:\n')
replace('tools/card/readme_screenshots.py','        "preview_icon_substitutes": True,','        "preview_icon_substitutes": True,\n        "parking_type_glyphs": "Exact packaged SVG paths, not substitutes",')

license_text=Path('/usr/share/common-licenses/Apache-2.0').read_text()
notice='''Parking-type glyphs use unchanged Material Design Icons SVG path data.
Upstream: https://github.com/Templarian/MaterialDesign-SVG
Pictogrammers Free License: icons distributed under Apache License 2.0.
No fonts are bundled. Only fixed paths are embedded into the single JS card.

Upstream source blobs inspected for this release:
parking.svg             6337794e5052b864f6531a8f4deb672324ebb045
cash.svg                0157c73753ba53abdcbf51e58bff77a6c5e0ae7d
road-variant.svg        3e2c07b00c246a527d1cba0a0219e59c9122ac33
tunnel.svg              d583cc106a2f43e20006438ba385aa847df46cce
office-building.svg     7ac753d7015e5c81281652154e3baafd300fc432
train-car.svg           4e4706a6fe08963da27e6a485a1dc3c2cfe7ca57
map-marker-question.svg 680fbee45e345441f088dad892a79bfe3f2dc844

'''
p=ROOT/'custom_components/osm_parking/frontend/licenses/material-design-icons.txt'
p.parent.mkdir(parents=True,exist_ok=True);p.write_text(notice+license_text,encoding='utf-8')

guide='''### Parking-type map icons

Parking markers use type icons instead of sequential numbers: a banknote for paid parking, P for surface parking, a road for street parking, a tunnel for underground parking, a building for multi-storey parking, a train/car for Park & Ride, and a question-mark location pin for other or unknown types. The same glyph is shown beside the matching result. Hover text and accessible button names include the translated parking type and facility name.

Numbers and ordering remain internal metadata. Matching uses the existing stable facility key, not icon appearance or row order, so two garages with identical icons and names still open their own results after sorting/filtering. Marker activation retains the folded-list behavior: expand, highlight and scroll to the correct row without changing the map camera. Ordinary updates do not scroll again. The glyphs are embedded in the card; no image service, icon font or extra browser dependency is required.

'''
for path in (ROOT/'README.md',ROOT/'tools/card/guide.md'):
    text=path.read_text()
    text=text.replace('Map markers and rows share the same visible numbering.','Map markers and rows share the same parking-type icons; their facility IDs and display indices remain internal.')
    path.write_text(text+'\n'+guide,encoding='utf-8')
notes='''## v1.4.1

### Parking-type icons

- Replaced visible ordinal numbers on the map and result badges with matching parking-type SVG icons for all seven categories. Unknown types have a safe generic fallback.
- Kept stable facility keys and display indices internally, including distinct facilities sharing the same name and type. Filter/sort changes never match by icon appearance.
- Preserved marker-driven list expansion, highlight and scroll, keyboard activation, reduced motion, map-only popups and camera position.
- Added translated type/name hover and accessibility labels. Unnamed facilities no longer acquire a visible ordinal fallback name.
- Embedded licensed vector glyphs so markers do not wait for remote image, font or lazy-loaded icon requests. Refreshes reuse marker buttons and unchanged icon nodes.
- Added icon/identity unit and real-browser regression coverage. Refreshed the README gallery with sample-data screenshots of the shipped card.

### Compatibility

Provider backends, API credentials, automatic Athens GIS, failure isolation, source-quality deduplication and the four-step setup are unchanged. No configuration migration or new YAML setting is required. Browser tests use the complete card, real MapLibre and local sample data, not the user's live Home Assistant.

'''
p=ROOT/'CHANGELOG.md';p.write_text(p.read_text().replace('# Changelog\n\n','# Changelog\n\n'+notes,1),encoding='utf-8')
subprocess.run([sys.executable,str(ROOT/'tools/card/build.py')],cwd=ROOT,check=True)
print('PARKING_TYPE_ICONS_PREPARED=1.4.1')
