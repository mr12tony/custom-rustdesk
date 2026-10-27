#!/usr/bin/env python3
"""Apply Windows branding to the pinned RustDesk 1.5.0 tree (AGPL-3.0)."""
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

# Preserve upstream copyright notices; customize product identity only.
change('flutter/windows/runner/Runner.rc', '"FileDescription", "RustDesk Remote Desktop"',
       '"FileDescription", "MagendaSupport Remote Desktop"')
change('flutter/windows/runner/Runner.rc', '"ProductName", "RustDesk"',
       '"ProductName", "MagendaSupport"')
change('flutter/windows/runner/Runner.rc', '"CompanyName", "Purslane Tech Pte. Ltd."',
       '"CompanyName", "MagendaMD"')
change('flutter/windows/runner/Runner.rc', '"OriginalFilename", "rustdesk.exe"',
       '"OriginalFilename", "MagendaSupport.exe"')
change('flutter/windows/runner/Runner.rc', '"InternalName", "rustdesk"',
       '"InternalName", "MagendaSupport"')
change('libs/portable/build.rs', 'let mut res = winres::WindowsResource::new();',
       'let mut res = winres::WindowsResource::new();\n'
       '        res.set("ProductName", "MagendaSupport");\n'
       '        res.set("FileDescription", "MagendaSupport Remote Desktop");\n'
       '        res.set("CompanyName", "MagendaMD");\n'
       '        res.set("OriginalFilename", "MagendaSupport.exe");\n'
       '        res.set("InternalName", "MagendaSupport");')

from PIL import Image
logo = assets / 'magenda-support-logo.png'
for name in ('res/icon.png', 'flutter/assets/logo.png', 'flutter/assets/logo_light.png',
             'flutter/assets/logo_dark.png', 'flutter/assets/icon.png'):
    target = root / name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(logo, target)
with Image.open(logo) as original:
    icon = original.convert('RGBA')
    for name in ('res/icon.ico', 'flutter/windows/runner/resources/app_icon.ico',
                 'flutter/assets/icon.ico'):
        icon.save(root / name, format='ICO', sizes=[(n,n) for n in (16,24,32,48,64,128,256)])
print('Applied Windows product identity, assets, server defaults and peer name.')
