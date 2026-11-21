#!/usr/bin/env python3
"""Submit offline matches to f4decomp.com without a model: one process owns every claim and submit for the queues.

Queues (largest function first, since the daily cap binds and bytes per submission is what counts):
  big/ready/<addr>/         matches made by the Codex large-function lanes
  big/ports/ready/<addr>/   twin ports from twins.py
Each folder holds candidate.cpp and pack.json; model.txt (who wrote the source) is optional.

Per item: claim just in time -> packet -> download the real pack with the key -> f4check against it ->
submit on MATCH, else give up with the source as best_code. Every claim ends at once (submitted or released), so no
claim lapses. Outcomes move the folder to submitted/, tried/ or lost/ beside its queue.

Account safety: reads status every loop; keeps 50 under the daily cap and 200 under the pending cap; pauses (writes
big/SUBMITTER_PAUSED) when strikes grow, a recent verdict is not 'verified', or 5 unexpected errors happen in a row.
Remove that file to resume. Stop: touch big/SUBMITTER_STOP. State line: big/submitter.status.

usage: venv/bin/python submitter.py            run until stopped
       venv/bin/python submitter.py --dry N    check the N largest items against their local packs; claims nothing
Run in $F4WORK. Key: workers/w1/key.txt (never printed).
"""
import json, os, shutil, subprocess, sys, tarfile, tempfile, threading, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

BASE = Path(os.environ.get('F4WORK', Path.home() / 'f4work'))
BIG = BASE / 'big'
KEY = (BASE / 'workers' / 'w1' / 'key.txt').read_text().strip()
PY = str(BASE / 'venv' / 'bin' / 'python')
F4CHECK = str(BASE / 'kit' / 'f4check' / 'f4check.py')
API = 'https://f4decomp.com/api/v1/'
QUEUES = [(BIG / 'ready', BIG, 'codex-cli'), (BIG / 'ports' / 'ready', BIG / 'ports', 'twin-port')]
PAUSED, STOP, STATUS, LOG = BIG / 'SUBMITTER_PAUSED', BIG / 'SUBMITTER_STOP', BIG / 'submitter.status', BIG / 'submitter.log'
WORKERS, BATCH = 4, 60
ENV = dict(os.environ, F4CHECK_IMAGE=str(BASE / 'private' / 'Fallout4_1_10_163_unpacked.exe'))

log_lock = threading.Lock()


def log(msg):
    with log_lock, open(LOG, 'a') as f:
        f.write('%s %s\n' % (time.strftime('%Y-%m-%dT%H:%M:%S'), msg))


def api(tool, body, timeout=120):
    try:
        r = subprocess.run(['curl', '-s', '-m', str(timeout), '-o', '-', '-w', '\n%{http_code}', '-X', 'POST', API + tool,
                            '-H', 'Authorization: Bearer ' + KEY, '-H', 'Content-Type: application/json',
                            '--data-binary', '@-'], input=json.dumps(body), capture_output=True, text=True,
                           timeout=timeout + 30)
        text, _, code = r.stdout.rpartition('\n')
        code = int(code or 599)
    except Exception as e:
        return 599, {'error': str(e)}
    try:
        return code, json.loads(text)
    except Exception:
        return code, {'error': text[:300]}


def download(url, dest):
    r = subprocess.run(['curl', '-s', '-f', '-m', '120', '-o', str(dest), '-H', 'Authorization: Bearer ' + KEY, url])
    return r.returncode == 0 and dest.exists() and dest.stat().st_size > 200


def safe_extract(tgz, into):
    with tarfile.open(tgz) as t:
        for m in t.getmembers():
            if m.issym() or m.islnk() or m.name.startswith('/') or '..' in Path(m.name).parts:
                raise ValueError('unsafe tar member ' + m.name)
        t.extractall(into)


def f4check(cand, pack):
    r = subprocess.run([PY, F4CHECK, str(cand), '--pack', str(pack), '--json'], capture_output=True, text=True,
                       env=ENV, timeout=600)
    try:
        return json.loads(r.stdout[r.stdout.index('{'):])
    except Exception:
        return {'status': 'no json', 'tail': (r.stdout + r.stderr)[-300:]}


def is_match(j):
    return j.get('status') == 'match' and not (j.get('lint') or {}).get('refused')


def items():
    out = []
    for q, home, harness in QUEUES:
        for d in q.glob('0x*'):
            if (d / '.taking').exists() or not (d / 'candidate.cpp').exists():
                continue
            try:
                size = int(json.load(open(d / 'pack.json'))['size'])
            except Exception:
                continue
            out.append((size, d, home, harness))
    out.sort(key=lambda t: -t[0])
    return out


def move(d, home, state):
    (home / state).mkdir(parents=True, exist_ok=True)
    shutil.rmtree(d / '.taking', ignore_errors=True)
    dest = home / state / d.name
    if dest.exists():
        shutil.rmtree(dest)
    shutil.move(str(d), str(dest))


class Backoff(Exception):
    pass


retry_at = {}       # address -> time before which it is not tried again (in this process)


def process(size, d, home, harness, open_claims):
    addr = d.name
    src = (d / 'candidate.cpp').read_text()
    model = (d / 'model.txt').read_text().strip() if (d / 'model.txt').exists() else 'gpt-6.2-astra'
    code, c = api('claim', {'address': addr, 'model': model, 'harness': harness})
    cid = c.get('claim_id') if code == 200 else None
    if not cid:
        err = json.dumps(c)[:300]
        if code == 409 and 'waiting for the verification' in err:
            retry_at[addr] = time.time() + 3 * 3600; return 'later', err
        if code in (409, 500, 502, 504, 599) and addr in open_claims:
            cid = open_claims[addr]
        elif code in (409, 404):
            json.dump(c, open(d / 'claim-refused.json', 'w')); move(d, home, 'lost'); return 'lost', err
        elif code in (429, 503):
            raise Backoff(err)
        else:
            retry_at[addr] = time.time() + 300; return 'error', '%s %s' % (code, err)
    json.dump({'claim_id': cid, 'model': model, 'harness': harness}, open(d / 'claim.json', 'w'))
    with tempfile.TemporaryDirectory(prefix='sub-') as t:
        code, p = api('packet', {'claim_id': cid})
        url = p.get('pack_url')
        pack = Path(t) / 'pack'
        ok = bool(url) and download(url, Path(t) / 'pack.tgz')
        if ok:
            try:
                pack.mkdir(); safe_extract(Path(t) / 'pack.tgz', pack)
            except Exception:
                ok = False
        j = f4check(d / 'candidate.cpp', pack) if ok else {'status': 'no pack'}
    if is_match(j):
        code, s = api('submit', {'claim_id': cid, 'source': src, 'model': model})
        if code == 409 and 'expired' in json.dumps(s):
            code, c2 = api('claim', {'address': addr, 'model': model, 'harness': harness})
            if code == 200 and c2.get('claim_id'):
                code, s = api('submit', {'claim_id': c2['claim_id'], 'source': src, 'model': model})
        if code == 200 and s.get('submission_id'):
            json.dump(s, open(d / 'submit.json', 'w')); move(d, home, 'submitted'); return 'submitted', s['submission_id']
        if code in (429, 503) or 'limit' in json.dumps(s).lower():
            api('giveup', {'claim_id': cid, 'category': 'other', 'tried': 'submit refused by a limit',
                           'still_differs': 'nothing: it matched', 'suspected_cause': 'daily or pending limit',
                           'best_code': src})
            raise Backoff('submit limit: %s %s' % (code, json.dumps(s)[:200]))
        why = 'submit failed %s %s' % (code, json.dumps(s)[:200])
    else:
        why = 'real pack: %s' % j.get('status')
    code, g = api('giveup', {'claim_id': cid, 'category': 'codegen',
                             'tried': 'matched offline under the pool flags; re-checked against this claim\'s pack',
                             'still_differs': str(j.get('status')) + ' against the real pack',
                             'suspected_cause': 'the real pack differs from the offline one (flags, names or headers)',
                             'best_code': src})
    json.dump({'reason': why, 'check': {k: j.get(k) for k in ('status', 'errors', 'differing_instructions')},
               'giveup': g}, open(d / 'giveup.json', 'w'))
    move(d, home, 'tried')
    return 'released', why


def dry(n):
    for size, d, home, harness in items()[:n]:
        j = f4check(d / 'candidate.cpp', d)
        print(size, d.relative_to(BIG), j.get('status'), (j.get('lint') or {}).get('refused'))


def main():
    base_strikes, errors_in_row, counts = None, 0, {}
    while not STOP.exists():
        code, st = api('status', {})
        if code != 200:
            state = 'status %s' % code; time.sleep(120)
        else:
            lim = st.get('limits', {})
            strikes = st.get('strikes_last_7_days', 0)
            base_strikes = strikes if base_strikes is None else base_strikes
            bad = [r for r in st.get('recent', []) if any(w in str(r.get('verdict', '')).lower()
                                                          for w in ('fail', 'reject', 'refus', 'strike'))]
            if strikes > base_strikes or bad:
                PAUSED.write_text('strikes %s (were %s); bad verdicts: %s\n' % (strikes, base_strikes, json.dumps(bad)[:800]))
            room = min(lim.get('subsPerDay', 0) - 50 - st.get('submissions_today', 0),
                       lim.get('pending', 0) - 200 - st.get('awaiting_verification', 0), BATCH)
            open_claims = {}
            for oc in st.get('open_claims', []):
                if isinstance(oc, dict) and oc.get('address') and oc.get('claim_id'):
                    open_claims[oc['address']] = oc['claim_id']
            todo = [i for i in items() if retry_at.get(i[1].name, 0) <= time.time()]
            if PAUSED.exists():
                state = 'paused (see SUBMITTER_PAUSED)'
            elif not todo:
                state = 'idle'
            elif room <= 0:
                state = 'daily cap' if st.get('submissions_today', 0) >= lim.get('subsPerDay', 0) - 50 else 'waiting (pending)'
            else:
                state = 'working'
                batch = []
                for it in todo[:room]:
                    try:
                        os.mkdir(it[1] / '.taking'); batch.append(it)
                    except FileExistsError:
                        pass
                backoff = threading.Event()

                def run(it):
                    if backoff.is_set():
                        shutil.rmtree(it[1] / '.taking', ignore_errors=True); return 'skipped', ''
                    try:
                        return process(*it, open_claims)
                    except Backoff as e:
                        backoff.set(); shutil.rmtree(it[1] / '.taking', ignore_errors=True); return 'backoff', str(e)
                    except Exception as e:
                        shutil.rmtree(it[1] / '.taking', ignore_errors=True); return 'error', repr(e)[:300]

                with ThreadPoolExecutor(WORKERS) as ex:
                    for it, (out, detail) in zip(batch, ex.map(run, batch)):
                        counts[out] = counts.get(out, 0) + 1
                        log('%s %s %d %s %s' % (out, it[1].name, it[0], it[2].name, detail))
                        errors_in_row = errors_in_row + 1 if out == 'error' else 0
                        if errors_in_row >= 5 and not PAUSED.exists():
                            PAUSED.write_text('5 unexpected errors in a row; last: %s\n' % detail)
                if backoff.is_set():
                    time.sleep(120)
            STATUS.write_text('%s | %s | today %s/%s awaiting %s strikes %s | queue %d | this run %s\n' % (
                time.strftime('%FT%T'), state, st.get('submissions_today'), lim.get('subsPerDay'),
                st.get('awaiting_verification'), strikes, len(todo), json.dumps(counts)))
            if state != 'working':
                time.sleep(300 if state == 'daily cap' else 60)
    STOP.unlink(missing_ok=True)
    STATUS.write_text(STATUS.read_text() + 'stopped %s\n' % time.strftime('%FT%T') if STATUS.exists() else 'stopped\n')


if __name__ == '__main__':
    if sys.argv[1:2] == ['--dry']:
        dry(int(sys.argv[2]) if len(sys.argv) > 2 else 5)
    else:
        main()
