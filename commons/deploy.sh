#!/bin/bash
# Install or update f4commons on its server (Ubuntu 24.04 tested). Run there as a sudoer, with server.py, schema.sql and f4commons.service
# in the current directory:  bash deploy.sh
set -euo pipefail
sudo install -o f4commons -g f4commons -m 640 server.py /opt/f4commons/server.py
sudo install -o postgres -g postgres -m 640 schema.sql /tmp/f4commons-schema.sql
if ! sudo -u postgres psql -qtAc "select 1 from pg_database where datname='f4commons'" | grep -q 1; then
  sudo -u postgres createdb f4commons
fi
sudo -u postgres psql -q -v ON_ERROR_STOP=1 -d f4commons -f /tmp/f4commons-schema.sql
sudo rm -f /tmp/f4commons-schema.sql
sudo install -o root -g root -m 644 f4commons.service /etc/systemd/system/f4commons.service
sudo systemctl daemon-reload
sudo systemctl enable --now f4commons >/dev/null 2>&1
sudo systemctl restart f4commons
sleep 5
systemctl is-active f4commons
sudo ss -ltnp | grep '127.0.0.1:4410 ' || { sudo journalctl -u f4commons -n 30 --no-pager; exit 1; }
# Nightly dump (root runs it; the dump runs as postgres).
sudo install -d -o postgres -g postgres -m 700 /srv/f4commons-backup
sudo install -d -o root -g root -m 755 /opt/f4commons-bin
sudo install -d -o root -g root -m 700 /etc/f4commons
sudo install -o root -g root -m 755 f4commons-dump.sh /opt/f4commons-bin/f4commons-dump.sh
sudo install -o root -g root -m 644 f4commons-dump.service f4commons-dump.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now f4commons-dump.timer >/dev/null 2>&1
systemctl list-timers f4commons-dump.timer --no-pager | sed -n 2p
