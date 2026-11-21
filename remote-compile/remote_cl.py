#!/usr/bin/env python3
"""Compile-host half of msvc11_remote.py: reads a tar (sources, include folders, __args.json) on stdin, runs the f4check
kit's msvc11.run under Wine in a private temp folder, and writes a tar of the outputs plus __result.json to stdout."""
import io, json, os, sys, tarfile, tempfile

BASE = os.path.expanduser('~/f4work')
sys.path.insert(0, os.path.join(BASE, 'kit', 'f4check'))
os.environ.setdefault('F4_MSVC_ROOT', os.path.join(BASE, 'vs2012'))
os.environ.setdefault('F4_MSVC_PREFIX', os.path.join(BASE, 'wine-vs2012'))
import msvc11  # noqa: E402

with tempfile.TemporaryDirectory() as d:
    with tarfile.open(fileobj=sys.stdin.buffer, mode='r|') as t:
        t.extractall(d, filter='data')
    args = [a.replace('@/', d + '/') for a in json.load(open(os.path.join(d, '__args.json')))]
    rc, out = msvc11.run(args, cwd=d)
    out = out.replace(d + '/', '')
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode='w') as t:
        for name in os.listdir(d):
            if name.endswith(('.obj', '.asm', '.cod')):
                t.add(os.path.join(d, name), name)
        data = json.dumps({'rc': rc, 'out': out}).encode()
        info = tarfile.TarInfo('__result.json'); info.size = len(data); t.addfile(info, io.BytesIO(data))
    sys.stdout.buffer.write(buf.getvalue())
