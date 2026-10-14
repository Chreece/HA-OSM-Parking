const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'), vm=require('node:vm');
const source=fs.readFileSync('custom_components/osm_parking/frontend/osm-parking-map-card.js','utf8');
const context=vm.createContext({HTMLElement:class{},customElements:{get:()=>undefined,define:()=>{}},window:{},console,URL});
vm.runInContext(source+'\nglobalThis.api={OSM_PARKING_GLYPHS,osmIconType,osmTypeIconMarkup,osmKey,osmVisible,osmCleanPrefs,OsmParkingExplorerCard};',context);
const f=context.api;
test('all seven parking categories have distinct fixed vector glyphs',()=>{
  assert.equal(Object.keys(f.OSM_PARKING_GLYPHS).join(','),'paid,open,street,underground,multi_storey,park_and_ride,other');
  assert.equal(new Set(Object.values(f.OSM_PARKING_GLYPHS).map(g=>g.path)).size,7);
  for(const [type,g] of Object.entries(f.OSM_PARKING_GLYPHS)) {
    const html=f.osmTypeIconMarkup({category:type});
    assert.ok(html.includes(`data-icon="${g.name}"`));
    assert.match(html,/viewBox="0 0 24 24"/);assert.match(html,/fill="currentColor"/);
    assert.match(html,/aria-hidden="true"/);assert.match(html,/focusable="false"/);
    assert.doesNotMatch(html,/<text|<image|href=|https:\/\//);
  }
});
test('unknown null and malformed category fall back to the other-parking glyph',()=>{
  for(const category of [null,undefined,{},[],7,'future','__proto__','constructor','toString']) {
    assert.equal(f.osmIconType({category}),'other');
    assert.equal(f.osmTypeIconMarkup({category}),f.osmTypeIconMarkup({category:'other'}));
  }
  assert.equal(f.osmIconType(null),'other');
});
test('provider names or category strings cannot inject icon HTML',()=>{
  const html=f.osmTypeIconMarkup({category:'"><script>alert(1)</script>',name:'<img src=x onerror=alert(1)>'});
  assert.doesNotMatch(html,/script|onerror|<img/);
});
test('physical category is not overwritten merely because the site is paid',()=>{
  assert.equal(f.osmIconType({category:'underground',fee:'yes'}),'underground');
  assert.equal(f.osmIconType({category:'park_and_ride',fee:'yes'}),'park_and_ride');
});
test('same type and same name do not become the same internal parking identity',()=>{
  const a={category:'multi_storey',provider:'city',provider_id:'A',name:'Central'},b={...a,provider_id:'B'};
  assert.equal(f.osmTypeIconMarkup(a),f.osmTypeIconMarkup(b));
  assert.notEqual(f.osmKey(a),f.osmKey(b));
});
test('changing sort order never changes icon or stable key',()=>{
  const rows=Object.freeze([{provider:'a',provider_id:'1',category:'paid',name:'Zeta',distance_m:100},{provider:'a',provider_id:'2',category:'street',name:'Alpha',distance_m:400}].map(Object.freeze));
  const signatures=new Map(rows.map(r=>[f.osmKey(r),f.osmTypeIconMarkup(r)]));
  for(const sort of ['name','distance','source','type','free_first','availability','data_quality'])
    for(const r of f.osmVisible(rows,f.osmCleanPrefs({sort}))) assert.equal(f.osmTypeIconMarkup(r),signatures.get(f.osmKey(r)));
});
test('safe popup fallback is a translated parking name not a display ordinal',()=>{
  const fn=f.OsmParkingExplorerCard.prototype._safeItem;
  const original=Object.freeze({name:'',category:'other'});
  const result=fn.call({_t:()=> 'Πάρκινγκ',_url:()=>''},original);
  assert.equal(result.name,'Πάρκινγκ');assert.equal(original.name,'');
});
