"""Finalize theme lifecycle and evidence capture; removed by preview commit."""
from pathlib import Path
root=Path(__file__).resolve().parents[2]
path=root/'tests/card/browser_check.py'
text=path.read_text(encoding='utf-8')
old="return {'version':8,'name':'Offline map fixture',"
new="return {'version':8,'name':'Offline map fixture - '+('dark' if dark else 'light'),"
assert text.count(old)==1
text=text.replace(old,new)
for suffix,mode in (('liberty','light'),('dark','dark')):
    old=f'''page.wait_for_function("window.card._style.endsWith('/{suffix}') && window.card._map.isStyleLoaded() && !!window.card._map.getLayer('osm-parking-controlled-zones-fill')")'''
    new=f'''page.wait_for_function("window.card._style.endsWith('/{suffix}') && window.card._map.getStyle()?.name==='Offline map fixture - {mode}' && window.card._map.isStyleLoaded() && !!window.card._map.getLayer('osm-parking-controlled-zones-fill')")
        page.evaluate("() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))")'''
    assert text.count(old)==1,suffix
    text=text.replace(old,new)
path.write_text(text,encoding='utf-8')
path=root/'tools/card/explorer.js'
text=path.read_text(encoding='utf-8')
old='this._map.setStyle(style); // Camera and HTML markers are intentionally retained.'
new='''// A style diff can omit style.load while removing our custom zone layer.
    // Rebuild the stylesheet only, retaining the map, camera and HTML markers;
    // the existing style.load handler then restores zone sources reliably.
    this._map.setStyle(style, {diff:false});'''
assert text.count(old)==1
path.write_text(text.replace(old,new),encoding='utf-8')
print('THEME_LIFECYCLE_AND_RENDER_CAPTURE_FIXED')
