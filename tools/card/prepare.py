"""One-time visual correction; removed after the verified build is committed."""
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
print('MAP_CONTROL_WIDTH_CORRECTED')
