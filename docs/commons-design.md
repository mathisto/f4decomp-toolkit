# Group commons server (2026-11-21)

A small shared service for four trusted contributors' agents on f4decomp: notes, questions, a work board and a pool of
matched sources, reached through one MCP server on a small always-on box. It replaced a pull-request-based commons for our group.
Status: **running for our group since 2026-11-21.** Code and member guide: `commons/`.

## Why a database, not git

| Need | git | Postgres |
|---|---|---|
| Notes and catch-up | fine (last seen commit) | a cursor (`since_id`) |
| Claiming a function family | two pushes race | one transaction; the claim lapses on its own |
| Template pool by shape key | walk folders | indexed lookup |
| Search | grep | full-text search, tags |

Vector search is not needed at this size (hundreds to a few thousand notes). `pgvector` can be added to the same
database later if it earns a place.

## Prior art (checked 2026-11-21)

Several shared-memory MCP servers on Postgres exist: team-memory-mcp
(<https://github.com/gustavolira/team-memory-mcp>), pgmemory (<https://jeff-vincent.github.io/pgmemory/team-knowledge-hub>),
engram-team (<https://pypi.org/project/engram-team>), pg-mnemosyne-mcp (has a multi-agent coordination hub), and
mem0's OpenMemory with a community multi-user fork. They store fuzzy "memories" for recall, usually with embeddings and
an LLM step that extracts them.

- **Adopted from them:** one Postgres behind one HTTP MCP endpoint that every client shares (not a local process per
  person); contradiction handling is worth having (engram-team flags conflicting beliefs). Our equivalent: a note can
  be marked reproduced or refuted by another person.
- **Not adopted:** none of them does atomic family claims with expiry or a template pool keyed by instruction shape,
  which are the two parts that matter most here, and the LLM extraction step adds cost and a model to the write path.
  Building a thin server is smaller than bending one of these. pg-mnemosyne's coordination hub is worth a read for
  ideas before building.
- **Auth:** the MCP spec makes authorization optional; over HTTP a server acts as an OAuth 2.1 resource server, tokens
  go in the `Authorization` header and never in the URL, invalid tokens get 401
  (<https://modelcontextprotocol.io/specification/2025-06-18/basic/authorization>). The Python SDK's `TokenVerifier`
  identifies the caller per request (<https://py.sdk.modelcontextprotocol.io/run/authorization/>). For four people on a
  tailnet, static per-person bearer tokens checked by such a verifier are enough; full OAuth is not needed.

## Hosting

Postgres on localhost only; the MCP server on localhost behind an existing TLS proxy that
forwards only the endpoint, rate-limited; per-member tokens stored hashed; nightly `pg_dump`
copied off the box. See `commons/README.md`.

## Tools (each one verb, fixed schema, size limits; no SQL, shell, files or URLs)

| Area | Tools |
|---|---|
| Notes | `post_note(kind, title, body, tags, refs)`, `catch_up(since_id)`, `get(id)`, `search(text, tags)` |
| Verification | `verify(note_id, reproduced or refuted, evidence)` |
| Board | `claim_family(key, note, ttl_hours)`, `release(key)`, `board()` |
| Templates | `offer_source(address, shape_key, source)`, `sources_for(shape_key)` |
| Questions | `ask(question)`, `answer(id, text)` |

Every write records the author from the token. Every read returns other people's text as data, with its author.

## Safety, sized for trusted friends

The friends are trusted; the risk is accidents, not people. Two checks stay:
1. **On write**, the server refuses hex dumps, disassembly listings and key-like strings (a pasted listing or key is
   the realistic accident; game bytes in a database copied off-box are hard to clean up).
2. **On read**, agents treat notes as suggestions to weigh against their own owner's rules, because a note may carry
   text an agent copied from elsewhere.
No review queue, no quarantine, no merge workflow.

