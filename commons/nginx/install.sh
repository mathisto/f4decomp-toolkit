#!/bin/bash
# Put f4commons behind an existing TLS site on its server (idempotent). Run on the server as a sudoer from
# this folder. Backs up the site file, includes the location snippet, and reloads only if `nginx -t` passes.
set -euo pipefail
site=${F4COMMONS_NGINX_SITE:?set to your TLS site file, for example /etc/nginx/sites-available/example}
sudo install -o root -g root -m 644 f4commons-limits.conf /etc/nginx/conf.d/f4commons-limits.conf
sudo install -o root -g root -m 644 f4commons.conf /etc/nginx/snippets/f4commons.conf
if ! sudo grep -q 'include snippets/f4commons.conf;' $site; then
  sudo cp -p $site /etc/nginx/site.bak-$(date -u +%Y%m%dT%H%M%SZ)
  # first `location / {` is in the TLS server block (the port-80 block has none)
  sudo sed -i '0,/^    location \/ {/s//    include snippets\/f4commons.conf;   # f4commons MCP (f4decomp group)\n\n    location \/ {/' $site
fi
if sudo nginx -t 2>&1 | tail -2; then
  sudo systemctl reload nginx && echo reloaded
else
  echo 'nginx -t failed: not reloaded; restore from /etc/nginx/site.bak-*' >&2; exit 1
fi
