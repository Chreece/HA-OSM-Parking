"""Bundle the explorer subclass into the existing single-file Lovelace module.

Preserves the existing 14-language dictionaries and backend recovery methods.
No new browser dependencies, imports, URLs or resource registration required.
"""
from pathlib import Path
import argparse
import json
import re
from locales import translations
ROOT = Path(__file__).resolve().parents[2]
UI = Path(__file__).resolve().parent
PACKAGE = ROOT / 'custom_components/osm_parking'
VERSION = '1.4.1'
START = '// BEGIN OSM EXPLORER BUNDLE'
END = '// END OSM EXPLORER BUNDLE'


def outputs():
    card = PACKAGE / 'frontend/osm-parking-map-card.js'
    text = card.read_text(encoding='utf-8')
    if START in text:
        before, remainder = text.split(START, 1)
        _, after = remainder.split(END, 1)
        text = before + after.lstrip('\n')
    assert text.count('class OsmParkingMapCardV070 extends HTMLElement') == 1
    anchor = "if (!customElements.get('osm-parking-map-card')) {"
    assert text.count(anchor) == 1
    css = (UI / 'explorer.css').read_text(encoding='utf-8')
    js = (UI / 'type_icons.js').read_text(encoding='utf-8') + '\n' + (UI / 'explorer.js').read_text(encoding='utf-8')
    bundle = (START + '\nconst OSM_EXPLORER_I18N = ' + json.dumps(translations(), ensure_ascii=False, separators=(',', ':'))
              + ';\nconst OSM_EXPLORER_CSS = ' + json.dumps(css, ensure_ascii=False)
              + ';\n' + js.rstrip() + '\n' + END + '\n')
    text = text.replace(anchor, bundle + anchor)
    text = text.replace("customElements.define('osm-parking-map-card', OsmParkingMapCardV070)",
                        "customElements.define('osm-parking-map-card', OsmParkingExplorerCard)")
    text = re.sub(r'<span class="version">v[^<]+</span>', f'<span class="version">v{VERSION}</span>', text)
    assert "customElements.define('osm-parking-map-card', OsmParkingExplorerCard)" in text
    out = {card: text}
    manifest = PACKAGE / 'manifest.json'
    data = json.loads(manifest.read_text(encoding='utf-8'))
    data['version'] = VERSION
    out[manifest] = json.dumps(data, ensure_ascii=False, indent=2) + '\n'
    init = PACKAGE / '__init__.py'
    init_text, count = re.subn(r'^CARD_VERSION = "[^"]+"$', f'CARD_VERSION = "{VERSION}"', init.read_text(encoding='utf-8'), flags=re.M)
    assert count == 1
    out[init] = init_text
    changelog = ROOT / 'CHANGELOG.md'
    content = changelog.read_text(encoding='utf-8')
    if f'## v{VERSION}\n' not in content:
        content = content.replace('# Changelog\n\n', '# Changelog\n\n' + (UI / 'release.md').read_text(encoding='utf-8') + '\n', 1)
    out[changelog] = content
    readme = ROOT / 'README.md'
    text = readme.read_text(encoding='utf-8')
    if '## Compact parking explorer' not in text:
        text += '\n' + (UI / 'guide.md').read_text(encoding='utf-8')
    out[readme] = text
    return out


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args=parser.parse_args()
    changed=[]
    for path,text in outputs().items():
        if path.read_text(encoding='utf-8') != text:
            changed.append(str(path.relative_to(ROOT)))
            if not args.check:
                path.write_text(text, encoding='utf-8')
    if args.check and changed:
        raise SystemExit('Rebuild tools/card/build.py: '+', '.join(changed))
    print('CARD_BUNDLE='+('PASS' if args.check else 'BUILT')+'; changed='+str(len(changed)))
