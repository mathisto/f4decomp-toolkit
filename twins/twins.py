#!/usr/bin/env python3
"""Port our matched sources to their same-shape twins and check every port offline (no model involved).

Idea from another f4decomp account's notes (weak-twin porting): two functions whose instruction lists are equal once
every call, jump and RIP-relative target outside the function is masked have the same shape; the source of one, with
its FUN_/DAT_ placeholders renamed one-to-one, often compiles to the other.

  twins.py shapes          build big/twins/shapes.json: {addr: [size, strong, weak]} for every indexed function
  twins.py open            write big/twins/open.txt: every open, unheld address (all bands)
  twins.py port [--limit N] [--jobs J] [--dry]
                           for every template (our submitted sources), check each open weak twin offline; a MATCH goes
                           to big/ports/ready/<addr>/ (candidate.cpp, pack.json, model.txt, origin.txt)

Run in $F4WORK with venv/bin/python. Templates are workers/*/packs/<addr>/ folders that hold submit.json and
candidate.cpp. A template whose target carries a real name is skipped (every twin would reuse the name: Q6).
"""
import glob, hashlib, json, os, re, shutil, subprocess, sys, tempfile, threading
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from pathlib import Path

BASE = Path(os.environ.get('F4WORK', Path.home() / 'f4work'))
KIT = BASE / 'kit' / 'f4check'
sys.path.insert(0, str(KIT))
os.environ.setdefault('F4CHECK_IMAGE', str(BASE / 'private' / 'Fallout4_1_10_163_unpacked.exe'))
import f4check  # noqa: E402

OUT = BASE / 'big' / 'twins'
PORTS = BASE / 'big' / 'ports'
PY = str(BASE / 'venv' / 'bin' / 'python')

_env = {}


def env():
    if not _env:
        pe = f4check.image()
        sizes = {int(f['address'], 16): f['size'] for f in json.load(open(f4check.index_path()))['functions']}
        _env.update(pe=pe, sizes=sizes, name_of=f4check.names_for(pe, sizes, f4check.symbols(None)))
    return _env


LABEL = re.compile(r'\[rip -> ([^\]]+)\]')


def rows_of(a):
    e = env()
    return f4check.disasm(e['pe'], a, e['sizes'][a], e['name_of'])


def targets(rows):
    """Relocation-bound operands in instruction order: FUN_/DAT_ placeholders, symbol names, string previews."""
    t = []
    for _, m, o in rows:
        t += LABEL.findall(o)
        if m in ('call', 'jmp') and not o.startswith('+0x') and not o.startswith(('q', 'r', 'e', '[')):
            t.append(o)
    return t


def keys(rows):
    strong = '\n'.join('%s %s' % (m, o) for _, m, o in rows)
    weak = []
    for _, m, o in rows:
        o = LABEL.sub('[rip -> X]', o)
        if m in ('call', 'jmp') and not o.startswith('+0x') and not o.startswith(('q', 'r', 'e', '[')):
            o = 'X'
        weak.append('%s %s' % (m, o))
    h = lambda s: hashlib.sha1(s.encode()).hexdigest()[:16]
    return h(strong), h('\n'.join(weak))


def _shape_chunk(addrs):
    out = {}
    for a in addrs:
        try:
            s, w = keys(rows_of(a))
            out['%x' % a] = [env()['sizes'][a], s, w]
        except Exception:
            pass
    return out


def cmd_shapes():
    addrs = sorted(a for a, n in env()['sizes'].items() if n >= 8)
    chunks = [addrs[i:i + 2000] for i in range(0, len(addrs), 2000)]
    table = {}
    with ProcessPoolExecutor(8) as ex:
        for part in ex.map(_shape_chunk, chunks):
            table.update(part)
    OUT.mkdir(parents=True, exist_ok=True)
    json.dump(table, open(OUT / 'shapes.json', 'w'))
    groups = {}
    for a, (_, _, w) in table.items():
        groups.setdefault(w, []).append(a)
    multi = [g for g in groups.values() if len(g) > 1]
    print('functions', len(table), 'weak groups with twins', len(multi), 'functions in them', sum(map(len, multi)))


def cmd_open():
    sys.path.insert(0, str(BASE))
    from select_big import open_functions
    addrs = []
    for band in ('<=255', '256-511', '512-1K', '1K-4K', '4K+'):
        fns = open_functions(band)
        print(band, len(fns), flush=True)
        addrs += [f['address'] for f in fns]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'open.txt').write_text(''.join(a + '\n' for a in addrs))


def mapping(src_t, dst_t):
    if len(src_t) != len(dst_t):
        return None
    m = {}
    for a, b in zip(src_t, dst_t):
        if a == b:
            if m.setdefault(a, b) != b: return None
            continue
        placeholder = a[:4] in ('FUN_', 'DAT_') and a[:4] == b[:4]
        literal = a[:1] == '"' and b[:1] == '"'
        if not (placeholder or literal):
            return None        # a real symbol differs, or a literal against a placeholder: not a rename
        if m.setdefault(a, b) != b: return None
    renames = {a: b for a, b in m.items() if a != b}
    return renames if len(set(m.values())) == len(m) else None


def port(src, renames):
    """Rename placeholders by address, whatever prefix the source gives them (a source may call a .text address
    outside the index FUN_ where the disassembly says DAT_), and swap string literals that appear verbatim.
    Returns None when a literal to swap is not in the source as written."""
    by_hex, lits = {}, {}
    for a, b in renames.items():
        if a[:1] == '"':
            if a not in src or '\\' in b or '"' in b[1:-1]:
                return None
            lits[a] = b
        else:
            by_hex[a[4:]] = b[4:]
    if by_hex:
        pat = re.compile(r'\b(FUN_|DAT_)(' + '|'.join(sorted(map(re.escape, by_hex), key=len, reverse=True)) + r')\b')
        src = pat.sub(lambda mo: mo.group(1) + by_hex[mo.group(2)], src)
    for a, b in lits.items():
        src = src.replace(a, b)
    return src


def templates():
    out = {}
    for sub in glob.glob(str(BASE / 'workers' / '*' / 'packs' / '*' / 'submit.json')):
        d = Path(sub).parent
        if not (d / 'candidate.cpp').exists():
            continue
        try:
            a = int(d.name, 16)
            sid = json.load(open(sub)).get('submission_id')
        except Exception:
            continue
        if sid:
            out[a] = d
    return out


_ref = {}


def ref_pack():
    if not _ref:
        packs = sorted(glob.glob(str(BASE / 'workers' / '*' / 'packs' / '*' / 'pack.json')), key=os.path.getmtime)
        _ref.update(json.load(open(packs[-1])))
    return _ref


def write_pack(folder, a, size):
    r = ref_pack()
    pack = {'address': '0x%x' % a, 'size': size, 'name': 'FUN_%x' % a, 'flags': r['flags'],
            'accept_also': r['accept_also'], 'callees': [], 'owner': None,
            'standards_version': r['standards_version'], 'headers': r.get('headers', []),
            'note': 'local offline pack: claim the function and re-check against its real pack before submitting'}
    json.dump(pack, open(Path(folder) / 'pack.json', 'w'), indent=1)


def check(src, a, size):
    with tempfile.TemporaryDirectory(prefix='twin-') as t:
        Path(t, 'candidate.cpp').write_text(src)
        write_pack(t, a, size)
        r = subprocess.run([PY, str(KIT / 'f4check.py'), str(Path(t, 'candidate.cpp')), '--pack', t, '--json'],
                           capture_output=True, text=True, timeout=300)
        try:
            j = json.loads(r.stdout[r.stdout.index('{'):])
        except Exception:
            return {'status': 'no json', 'tail': (r.stdout + r.stderr)[-300:]}
        return j


def is_match(j):
    return j.get('status') == 'match' and not (j.get('lint') or {}).get('refused')


def cmd_port(limit=None, jobs=8, dry=False):
    table = json.load(open(OUT / 'shapes.json'))
    open_set = {int(a, 16) for a in (OUT / 'open.txt').read_text().split()}
    groups = {}
    for a, (_, _, w) in table.items():
        groups.setdefault(w, []).append(int(a, 16))
    taken = set()
    for s in ('ready', 'tried', 'submitted', 'lost', 'work'):
        taken |= {int(p.name, 16) for p in (BASE / 'big' / s).glob('0x*')}
    for s in ('ready', 'tried'):
        taken |= {int(p.name, 16) for p in (PORTS / s).glob('0x*')}
    state_p = PORTS / 'screened.json'
    PORTS.mkdir(parents=True, exist_ok=True)
    screened = json.load(open(state_p)) if state_p.exists() else {}
    tmpl = templates()
    by_group = {}
    for ta, d in sorted(tmpl.items()):
        k = table.get('%x' % ta)
        if not k:
            continue
        src = (d / 'candidate.cpp').read_text()
        if not re.search(r'\bFUN_%x\s*\(' % ta, src):
            continue    # real-named target: twins cannot reuse the name (Q6)
        by_group.setdefault(k[2], []).append((ta, d, src))
    jobs_list = []
    for w, tl in by_group.items():
        twins = sorted(b for b in groups[w] if b in open_set and b not in taken and b not in tmpl
                       and '%x' % b not in screened)
        if twins:
            jobs_list.append((env()['sizes'][twins[0]], tl, twins))
    jobs_list.sort(key=lambda j: (-j[0], -len(j[2])))     # bytes per submission first: the daily cap binds
    n = sum(len(j[2]) for j in jobs_list)
    print('templates', len(tmpl), 'groups with open twins', len(jobs_list), 'open twins', n,
          'bytes', sum(j[0] * len(j[2]) for j in jobs_list), flush=True)
    if dry:
        for size, tl, tw in jobs_list[:20]:
            print('  %4d B  %4d open twins  %d templates (0x%x)' % (size, len(tw), len(tl), tl[0][0]))
        return
    lock = threading.Lock()
    stats = {'match': 0, 'tried': 0, 'nomap': 0}

    def one(ta, d, src, b):
        size = env()['sizes'][b]
        ren = mapping(targets(rows_of(ta)), targets(rows_of(b)))
        if ren is None:
            return b, 'nomap', None
        ren['FUN_%x' % ta] = 'FUN_%x' % b
        s2 = port(src, ren)
        if s2 is None:
            return b, 'nomap', None
        j = check(s2, b, size)
        if is_match(j):
            f = PORTS / 'ready' / ('0x%x' % b)
            f.mkdir(parents=True, exist_ok=True)
            (f / 'candidate.cpp').write_text(s2)
            write_pack(f, b, size)
            (f / 'origin.txt').write_text('twin of 0x%x (%s)\n' % (ta, d))
            (f / 'model.txt').write_text(model_of(d))
            return b, 'match', None
        return b, 'tried', j.get('status')

    done = 0
    with ThreadPoolExecutor(jobs) as ex:
        for size, tl, twins in jobs_list:
            if limit and done >= limit:
                break
            # Probe: up to 3 templates on the group's first mappable twins; the first one that matches ports the group.
            win = None
            for ta, d, src in tl[:3]:
                for b in twins[:3]:
                    b, v, why = one(ta, d, src, b)
                    done += 1
                    if v == 'nomap':
                        continue
                    if v == 'match':
                        win = (ta, d, src); stats['match'] += 1; screened['%x' % b] = [hex(ta), v]
                    break
                if win:
                    break
            if not win:
                stats['tried'] += 1
                for b in twins: screened['%x' % b] = [hex(tl[0][0]), 'group-declined']
                json.dump(screened, open(state_p, 'w'))
                continue
            rest = [b for b in twins if '%x' % b not in screened]
            for b, v, why in ex.map(lambda b: one(win[0], win[1], win[2], b), rest):
                with lock:
                    stats[v] += 1; screened['%x' % b] = [hex(win[0]), v]; done += 1
            json.dump(screened, open(state_p, 'w'))
            print('%d B group via 0x%x: %d twins, totals %s' % (size, win[0], len(twins), stats), flush=True)
    json.dump(screened, open(state_p, 'w'))
    print('done', stats)


def model_of(d):
    for f in ('claim.json', 'submit.request.json'):
        try:
            m = json.load(open(d / f)).get('model')
            if m: return m + '\n'
        except Exception:
            pass
    return 'gpt-6.2-astra\n'


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else ''
    if cmd == 'shapes': cmd_shapes()
    elif cmd == 'open': cmd_open()
    elif cmd == 'port':
        a = sys.argv[2:]
        lim = int(a[a.index('--limit') + 1]) if '--limit' in a else None
        jobs = int(a[a.index('--jobs') + 1]) if '--jobs' in a else 8
        cmd_port(lim, jobs, '--dry' in a)
    else:
        print(__doc__)
