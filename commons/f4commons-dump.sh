#!/bin/bash
# Nightly dump of the f4commons database into /srv/f4commons-backup (kept 7 days). Copy that folder off the box
# with whatever backs up the server (we pull /srv nightly into a borg repository at home).
# Pings Healthchecks when /etc/f4commons/hc-ping holds a ping URL (start, then 0 or fail with the error).
set -uo pipefail
dir=/srv/f4commons-backup
ping=$(cat /etc/f4commons/hc-ping 2>/dev/null || true)
hc() { [ -n "$ping" ] && curl -fsS -m 10 --retry 3 -o /dev/null --data-raw "${2:-}" "$ping$1" || true; }
hc /start
out=$dir/f4commons-$(date -u +%Y%m%dT%H%M%SZ).dump
if err=$(runuser -u postgres -- pg_dump -Fc f4commons 2>&1 >"$out.tmp") && [ -s "$out.tmp" ]; then
  mv "$out.tmp" "$out"
  find "$dir" -name 'f4commons-*.dump' -mtime +7 -delete
  hc /0 "$(ls -la "$out")"
else
  rm -f "$out.tmp"
  hc /fail "pg_dump failed: $err"
  exit 1
fi
