#!/usr/bin/env python3
"""Apply Magenda branding to the pinned RustDesk 1.5.0 tree (AGPL-3.0)."""
import base64
import json
import shutil
import subprocess
import sys
from pathlib import Path

assets = Path(__file__).resolve().parent
root = Path(sys.argv[1]).resolve()
brand = json.loads((assets / 'brand.json').read_text())
assert len(base64.b64decode(brand['public_key'], validate=True)) == 32

def change(name, old, new, count=1):
    path = root / name
    text = path.read_text()
    if text.count(old) != count:
        raise RuntimeError(f'Upstream changed: {name}: expected {count} matches of {old!r}')
    path.write_text(text.replace(old, new))

def rust_string(value):
    return json.dumps(value, ensure_ascii=True)

def rust_map(values):
    entries = ',\n'.join(f'({rust_string(k)}.to_owned(), {rust_string(v)}.to_owned())' for k, v in values.items())
    return 'RwLock::new(HashMap::from([\n' + entries + '\n]))'

# Initializers also apply to the separate macOS service process, before config is read.
change('libs/hbb_common/src/config.rs', 'RwLock::new("RustDesk".to_owned())',
       f'RwLock::new({rust_string(brand["app_name"])}.to_owned())')
change('libs/hbb_common/src/config.rs',
       'pub static ref DEFAULT_SETTINGS: RwLock<HashMap<String, String>> = Default::default();',
       'pub static ref DEFAULT_SETTINGS: RwLock<HashMap<String, String>> = ' + rust_map({
           'custom-rendezvous-server': brand['id_server'],
           'relay-server': brand['relay_server'],
           'key': brand['public_key'],
           'api-server': brand['api_server'],
       }) + ';')
change('libs/hbb_common/src/config.rs',
       'pub static ref BUILTIN_SETTINGS: RwLock<HashMap<String, String>> = Default::default();',
       'pub static ref BUILTIN_SETTINGS: RwLock<HashMap<String, String>> = ' +
       rust_map({'display-name': brand['remote_display_name']}) + ';')
# Hostname in PeerInfo is separate from the initiating operator's display-name.
change('src/server/connection.rs', 'pi.hostname = crate::whoami_hostname();',
       f'pi.hostname = {rust_string(brand["remote_display_name"])}.to_owned();')
change('src/common.rs', 'let hostname = hostname(); // sys.hostname() return localhost on android in my test',
       f'let hostname = {rust_string(brand["remote_display_name"])}.to_owned();')

change('flutter/macos/Runner/Configs/AppInfo.xcconfig', 'PRODUCT_NAME = RustDesk',
       'PRODUCT_NAME = ' + brand['app_name'])
change('flutter/macos/Runner/Configs/AppInfo.xcconfig', 'com.carriez.flutterHbb', brand['bundle_identifier'])
change('flutter/macos/Runner.xcodeproj/project.pbxproj', 'com.carriez.rustdesk', brand['bundle_identifier'], 3)
change('flutter/macos/Runner.xcodeproj/project.pbxproj', 'RustDesk.app', brand['app_name'] + '.app', 4)
path = root / 'build.py'
text = path.read_text()
assert 'Release/RustDesk.app/Contents/MacOS/' in text
path.write_text(text.replace('RustDesk.app', brand['app_name'] + '.app'))

logo = assets / 'magenda-support-logo.png'
for name in ('res/icon.png', 'res/mac-icon.png', 'flutter/assets/logo.png',
             'flutter/assets/logo_light.png', 'flutter/assets/logo_dark.png', 'flutter/assets/icon.png'):
    target = root / name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(logo, target)

iconset = root / '.magenda-icon.iconset'
iconset.mkdir(exist_ok=True)
for size in (16, 32, 128, 256, 512):
    for scale in (1, 2):
        suffix = '@2x' if scale == 2 else ''
        pixels = str(size * scale)
        subprocess.run(['sips', '-z', pixels, pixels, str(logo), '--out',
                        str(iconset / f'icon_{size}x{size}{suffix}.png')], check=True,
                       stdout=subprocess.DEVNULL)
subprocess.run(['iconutil', '-c', 'icns', str(iconset), '-o',
                str(root / 'flutter/macos/Runner/AppIcon.icns')], check=True)
print('Applied MagendaSupport branding; no passwords or private keys embedded.')
