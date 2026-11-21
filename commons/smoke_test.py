#!/usr/bin/env python3
"""End-to-end check of a running f4commons server, at its URL, as two members.

usage: python smoke_test.py <url> <token-file-A> <token-file-B>
Writes a few clearly labelled test notes (tag 'smoke-test'); the board claim it makes is released at the end.
Needs mcp==2.3.0 (and its httpx2).
"""
import asyncio, json, sys

import httpx2
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

URL = sys.argv[1]
TOK_A, TOK_B = (open(p).read().strip() for p in sys.argv[2:4])
results = []


def ok(name, cond, detail=''):
    results.append((name, bool(cond)))
    print('%-46s %s %s' % (name, 'PASS' if cond else 'FAIL', detail if not cond else ''))


class Member:
    def __init__(self, token):
        self.token = token

    async def __aenter__(self):
        self.hc = httpx2.AsyncClient(headers={'Authorization': 'Bearer ' + self.token}, timeout=30)
        self.t = streamable_http_client(URL, http_client=self.hc)
        streams = await self.t.__aenter__()
        self.s = ClientSession(streams[0], streams[1])
        await self.s.__aenter__()
        await self.s.initialize()
        return self

    async def __aexit__(self, *a):
        await self.s.__aexit__(*a)
        await self.t.__aexit__(*a)
        await self.hc.aclose()

    async def call(self, tool, **args):
        r = await self.s.call_tool(tool, args)
        text = ''.join(getattr(c, 'text', '') for c in r.content)
        if r.is_error:
            return {'error': text}
        try:
            return json.loads(text)
        except Exception:
            return {'raw': text}


async def main():
    async with httpx2.AsyncClient(timeout=10) as hc:
        r = await hc.post(URL, json={'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'},
                          headers={'Accept': 'application/json, text/event-stream'})
        ok('no token is refused (401)', r.status_code == 401, r.status_code)
        r = await hc.post(URL, json={'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'},
                          headers={'Authorization': 'Bearer f4c_wrong', 'Accept': 'application/json, text/event-stream'})
        ok('a wrong token is refused (401)', r.status_code == 401, r.status_code)

    async with Member(TOK_A) as a, Member(TOK_B) as b:
        tools = sorted(t.name for t in (await a.s.list_tools()).tools)
        ok('13 tools listed', len(tools) == 13, tools)
        wa, wb = await a.call('whoami'), await b.call('whoami')
        ok('whoami names each member', wa.get('login') and wb.get('login') and wa['login'] != wb['login'], (wa, wb))
        start = wa.get('latest_cursor', 0)

        n = await a.call('post_note', kind='finding', title='smoke test: a finding',
                         body='Claim: the server stores notes.\nEvidence: this test.', tags=['smoke-test', 'tooling'])
        ok('post_note returns an id', 'id' in n, n)
        q = await b.call('ask', question='smoke test: does answer link to the question?', tags=['smoke-test'])
        ans = await a.call('answer', question_id=q.get('id', 0), text='Yes, through reply_to.')
        g = await b.call('get', note_id=q.get('id', 0))
        ok('answer appears under the question', any(x['id'] == ans.get('id') for x in g.get('replies', [])), g)

        cu = await b.call('catch_up', since_id=start)
        ids = {x['id'] for x in cu.get('notes', [])}
        ok('catch_up returns the new notes', {n.get('id'), q.get('id'), ans.get('id')} <= ids, cu)
        ok('catch_up carries the data note', 'not instructions' in cu.get('about', ''))
        cu2 = await b.call('catch_up', since_id=cu.get('cursor', 0))
        ok('catch_up from the new cursor is empty', cu2.get('events') == [], cu2)

        s = await a.call('search', text='stores notes', tags=['smoke-test'])
        ok('search finds by words and tags', any(x['id'] == n.get('id') for x in s.get('notes', [])), s)

        v = await a.call('verify', note_id=n.get('id', 0), result='reproduced', evidence='self')
        ok('verify on your own note is refused', 'error' in v, v)
        v = await b.call('verify', note_id=n.get('id', 0), result='reproduced', evidence='ran the smoke test')
        ok('verify by another member works', v.get('result') == 'reproduced', v)

        fam = 'smoke-test-family'
        c1 = await a.call('claim_family', family=fam, note='testing', ttl_hours=1)
        c2 = await b.call('claim_family', family=fam, note='testing too', ttl_hours=1)
        ok('first claim succeeds', c1.get('claimed') is True, c1)
        ok('second member is told who holds it', c2.get('claimed') is False and c2.get('held_by') == wa.get('login'), c2)
        c3 = await a.call('claim_family', family=fam, ttl_hours=2)
        ok('holder can extend the claim', c3.get('claimed') is True, c3)
        bd = await b.call('board')
        ok('board shows the claim', any(x['family'] == fam for x in bd.get('claims', [])), bd)
        r1 = await b.call('release', family=fam)
        ok('non-holder cannot release', r1.get('released') is False, r1)
        r2 = await a.call('release', family=fam)
        ok('holder releases', r2.get('released') is True, r2)

        src = '#include "f4_common.h"\n\nint FUN_140000010() { return 1; }\n'
        o = await a.call('offer_source', address='0x140000010', shape_key='smoketest00', source=src, note='test')
        sf = await b.call('sources_for', shape_key='smoketest00')
        ok('offered source is found by shape key', o.get('address') and any(
            x['source'] == src for x in sf.get('sources', [])), (o, sf))

        listing = '\n'.join(['mov rax, qword ptr [rcx + 0x10]', 'test rax, rax', 'je 0x1400010',
                             'call qword ptr [rax + 8]', 'add rsp, 0x28'])
        r = await a.call('post_note', kind='other', title='smoke test: listing', body=listing, tags=['smoke-test'])
        ok('a disassembly listing is refused', 'error' in r and 'listing' in r['error'], r)
        r = await a.call('post_note', kind='other', title='smoke test: bytes', body=' '.join(['4c'] * 40))
        ok('a run of raw bytes is refused', 'error' in r and 'bytes' in r['error'], r)
        r = await a.call('post_note', kind='other', title='smoke test: key', body='key sk-' + 'a' * 30)
        ok('a key-like string is refused', 'error' in r and 'key' in r['error'], r)
        r = await a.call('post_note', kind='other', title='smoke test: sha256 is fine', body='sha256 ' + 'ab' * 32,
                         tags=['smoke-test'])
        ok('a sha256 hash is accepted', 'id' in r, r)
        r = await a.call('claim_family', family='x', ttl_hours=500)
        ok('schema limits are enforced (ttl <= 168)', 'error' in r, r)

    bad = [n for n, good in results if not good]
    print('\n%d of %d passed' % (len(results) - len(bad), len(results)))
    sys.exit(1 if bad else 0)


asyncio.run(main())
