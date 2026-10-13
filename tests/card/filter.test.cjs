const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('custom_components/osm_parking/frontend/osm-parking-map-card.js','utf8');
const context = vm.createContext({HTMLElement:class{},customElements:{get:()=>undefined,define:()=>{}},window:{},console,URL});
vm.runInContext(source+'\nglobalThis.f={osmNumber,osmKind,osmFree,osmVisible,osmCleanPrefs,OsmParkingExplorerCard,OSM_EXPLORER_I18N};',context);
const f=context.f;
const items=[
 {name:'Alpha',category:'underground',fee:'yes',availability_kind:'live',free_capacity:8,capacity:100,distance_m:150,provider:'city'},
 {name:'Bravo',category:'street',fee:'unknown',availability_kind:'static',distance_m:20,provider:'osm'},
 {name:'Charlie',category:'park_and_ride',fee:'no',availability_kind:'reported',free_capacity:25,capacity:60,distance_m:300,provider:'other'},
 {name:'Delta',category:'multi_storey',fee:'yes',availability_kind:'live',free_capacity:0,capacity:20,distance_m:null,provider:'city'},
 {name:'Echo',category:'open',fee:'unknown',availability_kind:'estimated',free_capacity:999,distance_m:220,provider:'estimate'}
].map(Object.freeze);
Object.freeze(items);
const view=changes=>f.osmVisible(items,f.osmCleanPrefs(changes),'en').map(i=>i.name).join(',');
test('numeric unknowns do not become zero',()=>{for(const v of [null,undefined,'',true,false,[],{},'nan',Infinity])assert.equal(f.osmNumber(v),null);assert.equal(f.osmNumber('0'),0);});
test('distance ascending with missing values last',()=>assert.equal(view({sort:'distance'}),'Bravo,Alpha,Echo,Charlie,Delta'));
test('free-first never treats unknown fees as free',()=>assert.equal(view({sort:'free_first'}),'Charlie,Alpha,Delta,Bravo,Echo'));
test('availability retains reported label and rejects estimates as counts',()=>assert.equal(view({sort:'availability'}),'Charlie,Alpha,Delta,Bravo,Echo'));
test('quality ordering prioritizes live rather than highest reported count',()=>assert.equal(view({sort:'data_quality'}),'Alpha,Delta,Charlie,Echo,Bravo'));
test('available-only requires positive live counts',()=>assert.equal(view({available:true}),'Alpha'));
test('closed facilities excluded from available-only',()=>{const row={...items[0],opening_status:'closed'};assert.equal(f.osmVisible([row],f.osmCleanPrefs({available:true})).length,0);});
test('multiple parking types combine with logical OR',()=>assert.equal(view({types:['street','underground']}),'Bravo,Alpha'));
test('cost unknown filter',()=>assert.equal(view({cost:'unknown'}),'Bravo,Echo'));
test('source filter uses winning provider',()=>assert.equal(view({source:'city'}),'Alpha,Delta'));
test('quality filter',()=>assert.equal(view({quality:'reported'}),'Charlie'));
test('distance filter excludes unknown distances',()=>assert.equal(view({maxDistance:200}),'Bravo,Alpha'));
test('text search is case insensitive',()=>assert.equal(view({query:'ALPHA'}),'Alpha'));
test('Greek accent-insensitive search',()=>{const row={...items[0],name:'Κέντρο'};assert.equal(f.osmVisible([row],f.osmCleanPrefs({query:'κεντρο'}),'el').length,1);});
test('filters do not modify backend objects',()=>{const before=JSON.stringify(items);view({sort:'type',types:['street']});assert.equal(JSON.stringify(items),before);});
test('invalid counts never become valid availability',()=>{for(const count of [-1,101,1.5,null,'',true])assert.equal(f.osmFree({...items[0],free_capacity:count}),null);});
test('preference validation prevents unknown types and duplicate chips',()=>{const ui=f.osmCleanPrefs({types:['street','bogus','street'],quality:'fake',sort:'wrong'});assert.equal(ui.types.join(','),'street');assert.equal(ui.quality,'all');assert.equal(ui.sort,'distance');});
test('dangerous URL schemes are rejected',()=>{const url=f.OsmParkingExplorerCard.prototype._url;for(const v of ['javascript:alert(1)','data:text/html,test','not-a-url'])assert.equal(url(v),'');assert.equal(url('https://example.com'),'https://example.com/');});
test('all 14 languages include every presentation label',()=>{const dict=f.OSM_EXPLORER_I18N;assert.equal(Object.keys(dict).length,14);const keys=Object.keys(dict.en).sort().join(',');for(const row of Object.values(dict)){assert.equal(Object.keys(row).sort().join(','),keys);assert.ok(Object.values(row).every(v=>typeof v==='string'&&v.length>0));}});
test('same custom card type remains registered',()=>assert.ok(source.includes("customElements.define('osm-parking-map-card', OsmParkingExplorerCard)")));
