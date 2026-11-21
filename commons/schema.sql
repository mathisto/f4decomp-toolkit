-- f4commons: shared notes, work board and source pool for a small trusted group of f4decomp contributors.
-- Run as the postgres superuser: psql -v ON_ERROR_STOP=1 -f schema.sql f4commons
-- Roles: f4commons_owner (NOLOGIN) owns every object; f4commons (the server's OS user, peer auth on the local socket)
-- may only read and write rows. Agents never get a database login: the MCP server is the only client.

DO $$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'f4commons_owner') THEN CREATE ROLE f4commons_owner NOLOGIN; END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'f4commons') THEN CREATE ROLE f4commons LOGIN; END IF;
END $$;

ALTER DATABASE f4commons OWNER TO f4commons_owner;
REVOKE ALL ON DATABASE f4commons FROM PUBLIC;
GRANT CONNECT ON DATABASE f4commons TO f4commons;
SET ROLE f4commons_owner;
CREATE SCHEMA IF NOT EXISTS commons AUTHORIZATION f4commons_owner;
REVOKE ALL ON SCHEMA public FROM PUBLIC;
SET search_path = commons;

CREATE TABLE IF NOT EXISTS people (
  login        text PRIMARY KEY CHECK (login ~ '^[a-z0-9][a-z0-9_-]{0,38}$'),
  token_sha256 text NOT NULL UNIQUE,
  revoked      boolean NOT NULL DEFAULT false,
  created      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS notes (
  id       bigserial PRIMARY KEY,
  author   text NOT NULL REFERENCES people(login),
  kind     text NOT NULL CHECK (kind IN ('finding', 'question', 'answer', 'heads-up', 'request', 'other')),
  title    text NOT NULL CHECK (length(title) BETWEEN 1 AND 200),
  body     text NOT NULL CHECK (length(body) <= 20000),
  tags     text[] NOT NULL DEFAULT '{}',
  refs     text[] NOT NULL DEFAULT '{}',
  reply_to bigint REFERENCES notes(id),
  created  timestamptz NOT NULL DEFAULT now(),
  tsv      tsvector GENERATED ALWAYS AS (to_tsvector('english', title || ' ' || body)) STORED
);
CREATE INDEX IF NOT EXISTS notes_tsv ON notes USING gin (tsv);
CREATE INDEX IF NOT EXISTS notes_tags ON notes USING gin (tags);
CREATE INDEX IF NOT EXISTS notes_reply ON notes (reply_to);

-- Another person's reproduction or refutation of a note (never the note's own author).
CREATE TABLE IF NOT EXISTS verdicts (
  note_id  bigint NOT NULL REFERENCES notes(id),
  author   text NOT NULL REFERENCES people(login),
  result   text NOT NULL CHECK (result IN ('reproduced', 'refuted')),
  evidence text NOT NULL CHECK (length(evidence) BETWEEN 1 AND 5000),
  created  timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (note_id, author)
);

-- Who is working on which function family. A claim lapses at `expires`; claiming is one atomic statement.
CREATE TABLE IF NOT EXISTS board (
  family  text PRIMARY KEY CHECK (length(family) BETWEEN 1 AND 120),
  holder  text NOT NULL REFERENCES people(login),
  note    text NOT NULL CHECK (length(note) <= 1000),
  claimed timestamptz NOT NULL DEFAULT now(),
  expires timestamptz NOT NULL
);

-- Matched sources offered for twin porting, keyed by instruction-shape hash.
CREATE TABLE IF NOT EXISTS sources (
  address   text NOT NULL CHECK (address ~ '^0x14[0-9a-f]{7}$'),
  shape_key text NOT NULL CHECK (length(shape_key) BETWEEN 4 AND 64),
  author    text NOT NULL REFERENCES people(login),
  source    text NOT NULL CHECK (length(source) <= 100000),
  note      text NOT NULL DEFAULT '' CHECK (length(note) <= 1000),
  created   timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (address, author)
);
CREATE INDEX IF NOT EXISTS sources_shape ON sources (shape_key);

-- One row per write: the cursor that catch_up pages through.
CREATE TABLE IF NOT EXISTS events (
  id      bigserial PRIMARY KEY,
  at      timestamptz NOT NULL DEFAULT now(),
  who     text NOT NULL,
  kind    text NOT NULL,
  ref     text NOT NULL,
  summary text NOT NULL
);

GRANT USAGE ON SCHEMA commons TO f4commons;
GRANT SELECT ON people TO f4commons;
GRANT SELECT, INSERT ON notes, events TO f4commons;
GRANT SELECT, INSERT, UPDATE ON verdicts TO f4commons;
GRANT SELECT, INSERT, UPDATE, DELETE ON board TO f4commons;
GRANT SELECT, INSERT, UPDATE ON sources TO f4commons;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA commons TO f4commons;
RESET ROLE;
ALTER ROLE f4commons SET search_path = commons;
