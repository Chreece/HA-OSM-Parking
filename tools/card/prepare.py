"""One-time visual/lifecycle correction; removed after verified build commit."""
from pathlib import Path
root=Path(__file__).resolve().parent
css=root/'explorer.css'
text=css.read_text(encoding='utf-8')
fix='''
/* MapLibre's document stylesheet does not cross Home Assistant shadow roots.
   Explicit sizing stops the zoom group inheriting the attribution's width. */
osm-parking-map-card[data-explorer] .map .maplibregl-ctrl-group {display:flex;flex-direction:column;align-items:center;width:34px;max-width:34px;height:auto;margin:0 10px 8px auto;float:right;clear:both;}
osm-parking-map-card[data-explorer] .map .maplibregl-ctrl-group button {display:block;flex:0 0 32px;width:32px;height:32px;min-width:32px;min-height:32px;padding:0;line-height:32px;position:relative;}
osm-parking-map-card[data-explorer] .map .maplibregl-ctrl-zoom-out {border-top:1px solid var(--ex-line);}
osm-parking-map-card[data-explorer] .map .maplibregl-ctrl-attrib {clear:both;float:right;max-width:100%;}
'''
if fix not in text:
    css.write_text(text+fix,encoding='utf-8')
source=root/'explorer.js'
text=source.read_text(encoding='utf-8')
old="    const map=this._map;if(!map?.isStyleLoaded()) return;"
new='''    const map=this._map;if(!map) return;
    // style.load can arrive while GeoJSON sources are still loading. Retry
    // once at idle instead of losing overlays or repeatedly calling setData.
    if(!map.isStyleLoaded()) {
      if(!this._zoneIdlePending) {
        this._zoneIdlePending=true;
        map.once('idle',()=>{
          this._zoneIdlePending=false;
          if(map===this._map) this._updateZoneOverlay(this._stateObj?.attributes?.parking_zones || []);
        });
      }
      return;
    }'''
if old in text:
    assert text.count(old)==1
    text=text.replace(old,new)
else:
    assert new in text
old='this._pins?.clear(); this._zoneEvents=false; this._fitSignature=null;'
new='this._pins?.clear(); this._zoneEvents=false; this._zoneIdlePending=false; this._fitSignature=null;'
if old in text:text=text.replace(old,new)
else:assert new in text
source.write_text(text,encoding='utf-8')
print('MAP_CONTROLS_AND_STYLE_LIFECYCLE_CORRECTED')
