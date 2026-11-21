#!/usr/bin/env python3
"""Write a local pack.json (the pool's standard flags, no claim) and disasm.txt for one address.
usage: prep_big.py <address> <folder>"""
import glob, json, os, subprocess, sys
from pathlib import Path

base = Path(os.environ.get('F4WORK', Path.home() / 'f4work'))
addr, folder = sys.argv[1], Path(sys.argv[2])
idx = json.load(open(base / 'kit' / 'f4check' / 'function_index.json'))['functions']
size = next(f['size'] for f in idx if int(f['address'], 16) == int(addr, 16))
# Copy the flags, accepted alternatives and standards version from the newest real pack we have.
packs = sorted(glob.glob(str(base / 'workers' / '*' / 'packs' / '*' / 'pack.json')), key=os.path.getmtime)
ref = json.load(open(packs[-1]))
pack = {'address': addr, 'size': size, 'name': 'FUN_%s' % addr[2:], 'flags': ref['flags'],
        'accept_also': ref['accept_also'], 'callees': [], 'owner': None,
        'standards_version': ref['standards_version'], 'headers': ref.get('headers', []),
        'note': 'local offline pack: claim the function and re-check against its real pack before submitting'}
folder.mkdir(parents=True, exist_ok=True)
json.dump(pack, open(folder / 'pack.json', 'w'), indent=1)
env = dict(os.environ, F4CHECK_IMAGE=str(base / 'private' / 'Fallout4_1_10_163_unpacked.exe'))
out = subprocess.run([str(base / 'venv' / 'bin' / 'python'), str(base / 'kit' / 'f4check' / 'f4check.py'),
                      '--disasm', addr], capture_output=True, text=True, env=env)
(folder / 'disasm.txt').write_text(out.stdout + out.stderr)
print(addr)
