"""Guard map-control geometry and icon regressions inside HA shadow roots."""
from pathlib import Path
from functools import partial
import http.server
import json
import threading
from playwright.sync_api import sync_playwright

root=Path(__file__).resolve().parents[2]
class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*args): pass
server=http.server.ThreadingHTTPServer(('127.0.0.1',0),partial(Quiet,directory=str(root)))
threading.Thread(target=server.serve_forever,daemon=True).start()
style={'version':8,'sources':{},'layers':[{'id':'background','type':'background','paint':{'background-color':'#14222d'}}]}
try:
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,args=['--no-sandbox','--use-angle=swiftshader','--enable-unsafe-swiftshader'])
        page=browser.new_page(viewport={'width':390,'height':1400})
        page.route('https://tiles.openfreemap.org/styles/**',lambda route:route.fulfill(status=200,content_type='application/json',body=json.dumps(style)))
        page.goto(f'http://127.0.0.1:{server.server_port}/tests/card/preview.html')
        page.wait_for_function('window.card?._map?.loaded() && window.card._pins.size===5',timeout=30000)
        for width in (320,390,900):
            page.set_viewport_size({'width':width,'height':1400})
            box=page.locator('.maplibregl-ctrl-group').bounding_box()
            assert box and box['width']<=40 and box['height']<=70,box
            for name in ('zoom-in','zoom-out'):
                node=page.locator('.maplibregl-ctrl-'+name)
                button=node.bounding_box()
                assert button and 30<=button['width']<=40 and 30<=button['height']<=40,button
                assert node.locator('.maplibregl-ctrl-icon').evaluate('(e)=>getComputedStyle(e).display')=='none'
                assert node.evaluate("(e)=>getComputedStyle(e,'::after').position")=='absolute'
                assert node.evaluate("(e)=>getComputedStyle(e,'::after').content") in ('"+"','"−"')
        zoom=page.evaluate('window.card._map.getZoom()')
        page.locator('.maplibregl-ctrl-zoom-in').click()
        page.wait_for_function('(previous)=>window.card._map.getZoom()>previous',arg=zoom)
        browser.close()
finally:
    server.shutdown()
print('MAP_CONTROLS=PASS (320px,390px,900px, visible glyphs and working zoom)')
