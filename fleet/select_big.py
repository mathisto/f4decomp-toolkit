#!/usr/bin/env python3
"""Build the offline work queues for large functions (no model involved).

Pages f4decomp's list_functions for the 512-1K, 1K-4K and 4K+ bands (open functions not held by anyone), reads each
one from the local image with the kit's disassembler, drops the ones we should not spend effort on, ranks the rest and
writes big/queue/<lane>.txt (one address per line, best first) plus big/candidates.json with the features.

usage: venv/bin/python select_big.py [small]   (run in $F4WORK; uses workers/w1/key.txt for read-only calls)
  small: instead build big/queue/small.txt from the open functions of the <=255 band from 96 bytes up,
         for the local-model lane.
"""
import json, os, re, subprocess, sys
from pathlib import Path

BASE = Path(os.environ.get('F4WORK', Path.home() / 'f4work'))
sys.path.insert(0, str(BASE / 'kit' / 'f4check'))
os.environ.setdefault('F4CHECK_IMAGE', str(BASE / 'private' / 'Fallout4_1_10_163_unpacked.exe'))
import f4check  # noqa: E402

KEY = (BASE / 'workers' / 'w1' / 'key.txt').read_text().strip()
OUT = BASE / 'big'


def api(tool, body):
    r = subprocess.run(['curl', '-s', '-X', 'POST', 'https://f4decomp.com/api/v1/' + tool,
                        '-H', 'Authorization: Bearer ' + KEY, '-H', 'Content-Type: application/json',
                        '-d', json.dumps(body)], capture_output=True, text=True, timeout=120)
    return json.loads(r.stdout)


def open_functions(band, max_pages=None):
    out, cur, pages = [], None, 0
    while max_pages is None or pages < max_pages:
        pages += 1
        body = {'band': band, 'limit': 500, 'include_held': False}
        if cur: body['cursor'] = cur
        d = api('list_functions', body)
        out += d.get('functions', [])
        cur = d.get('next')
        if not cur or not d.get('functions'): return out
    return out


# Third-party code we must not hand-write: vendored public libraries come from their own sources, Havok and
# Scaleform are off-limits. Detected by strings they load.
THIRD_PARTY = re.compile(r'"(?:[^"]*(?:hk[A-Z]|Havok|Scaleform|GFx|zlib|inflate|deflate|png_|libpng|Bink)[^"]*)"')


def main():
    pe = f4check.image()
    idx = json.load(open(f4check.index_path()))['functions']
    sizes = {int(f['address'], 16): f['size'] for f in idx}
    frag = {int(f['address'], 16): f.get('pdata_entries', 1) for f in idx}
    syms = f4check.symbols(None)
    name_of = f4check.names_for(pe, sizes, syms)
    small = sys.argv[1:] == ['small']
    cands = []
    for band in (('<=255',) if small else ('512-1K', '1K-4K', '4K+')):
        fns = open_functions(band)
        if small: fns = [f for f in fns if f['size'] >= 96]
        print(band, len(fns), 'open', flush=True)
        for f in fns:
            a = int(f['address'], 16)
            try:
                rows = f4check.disasm(pe, a, f['size'], name_of)
            except Exception:
                continue
            text = '\n'.join('%s %s' % (m, o) for _, m, o in rows)
            calls = [o for _, m, o in rows if m in ('call', 'jmp') and not o.startswith('+0x')]
            reasons = []
            if 'IAllocatorFunctor' in text: reasons.append('allocator-functor store (R1450)')
            if THIRD_PARTY.search(text): reasons.append('third-party library')
            if re.search(r'call (?:qword ptr )?\[', text) is None and not calls: pass
            named_callees = sum(1 for c in set(calls) if not c.startswith('FUN_'))
            strings = len(set(re.findall(r'"[^"]{4,}"', text)))
            eh = '-2' in text and 'qword ptr [rsp' in text and bool(re.search(r'mov qword ptr \[rsp \+ 0x[0-9a-f]+\], -2', text))
            rec = {'address': f['address'], 'size': f['size'], 'band': band, 'self_name': name_of(a),
                   'earlier_claims': f.get('earlier_claims', 0), 'give_ups': f.get('give_ups', 0),
                   'near_misses': f.get('near_misses', 0), 'instructions': len(rows),
                   'distinct_callees': len(set(calls)), 'named_callees': named_callees, 'strings': strings,
                   'eh_frame': eh, 'fragments': frag.get(a, 1), 'skip': reasons}
            cands.append(rec)
    keep = [c for c in cands if not c['skip']]

    # Rank: untouched first (nobody else is close, nobody failed on it), then real names and strings (twins, readable
    # intent), then fewer distinct callees per KB (less to declare), then smaller.
    def score(c):
        s = 0.0
        if c['earlier_claims'] == 0: s += 3
        s -= 1.5 * c['give_ups']
        if c['self_name'] and not c['self_name'].startswith('FUN_'): s += 2
        s += min(c['strings'], 4) * 0.5 + min(c['named_callees'], 6) * 0.3
        s -= 4.0 * c['distinct_callees'] / max(c['size'] / 1024, 0.5) / 10
        if c['fragments'] > 1: s -= 1
        return -s
    if small:
        lanes = {'small': keep}
    else:
        lanes = {'big': [c for c in keep if c['size'] >= 1024], 'mid': [c for c in keep if c['size'] < 1024]}
    (OUT / 'queue').mkdir(parents=True, exist_ok=True)
    for lane, lst in lanes.items():
        lst.sort(key=lambda c: (score(c), c['size']))
        (OUT / 'queue' / (lane + '.txt')).write_text(''.join(c['address'] + '\n' for c in lst))
        print(lane, len(lst), 'queued')
    json.dump(cands, open(OUT / ('candidates_small.json' if small else 'candidates.json'), 'w'), indent=0)
    print('skipped', len(cands) - len(keep), 'of', len(cands))


if __name__ == '__main__':
    main()
