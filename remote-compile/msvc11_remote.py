#!/usr/bin/env python3
"""Drop-in replacement for f4check's msvc11.py that compiles on another host over SSH (a light machine -> a Linux build host running the compiler under Wine).

The candidate source and every /I folder go over in a tar stream; remote_cl.py on the compile host runs the kit's own
msvc11.run there (Wine) and sends the object file and the compiler output back. Same interface: run(args, cwd).
F4_COMPILE_HOST picks the host (default: buildhost, an SSH alias). Install: keep the kit's msvc11.py as msvc11_local.py, put this
file in its place.
"""
import io, json, os, subprocess, sys, tarfile
from pathlib import Path

HOST = os.environ.get('F4_COMPILE_HOST', 'buildhost')
REMOTE = os.environ.get('F4_COMPILE_CMD', 'python3 ~/f4work/remote_cl.py')
OPTS = ('/I', '/Fo', '/Fa')


def run(args, cwd=None):
    buf = io.BytesIO()
    conv, outs, k = [], [], 0
    with tarfile.open(fileobj=buf, mode='w') as t:
        for a in args:
            opt = next((o for o in OPTS if a.startswith(o) and len(a) > len(o)), None)
            if opt == '/I':
                name = 'inc%d' % k; k += 1
                t.add(a[2:], name); conv.append('/I@/' + name)
            elif opt:
                p = a[len(opt):]; name = Path(p).name
                conv.append(opt + '@/' + name); outs.append((name, p))
            elif not a.startswith('/') or os.path.isfile(a):
                if os.path.isfile(a):
                    name = Path(a).name; t.add(a, name); conv.append('@/' + name)
                else:
                    conv.append(a)
            else:
                conv.append(a)
        data = json.dumps(conv).encode()
        info = tarfile.TarInfo('__args.json'); info.size = len(data); t.addfile(info, io.BytesIO(data))
    r = subprocess.run(['ssh', '-o', 'BatchMode=yes', HOST, REMOTE], input=buf.getvalue(), capture_output=True)
    if r.returncode != 0 and not r.stdout:
        return 1, 'remote compile failed: ' + r.stderr.decode('utf-8', 'replace')[-2000:]
    res = {'rc': 1, 'out': 'no result from compile host'}
    with tarfile.open(fileobj=io.BytesIO(r.stdout), mode='r') as t:
        for m in t.getmembers():
            f = t.extractfile(m)
            if f is None:
                continue
            if m.name == '__result.json':
                res = json.loads(f.read())
            else:
                for name, dest in outs:
                    if m.name == name:
                        Path(dest).write_bytes(f.read())
    return res['rc'], res['out']


if __name__ == '__main__':
    rc, text = run(sys.argv[1:])
    sys.stdout.write(text)
    raise SystemExit(rc)
