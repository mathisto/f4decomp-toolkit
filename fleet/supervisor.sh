#!/bin/zsh -l
# Keep a set of f4decomp Codex workers busy until a deadline, with no other agent involved.
# usage: nohup caffeinate -i $F4WORK/supervisor.sh <days> >/dev/null 2>&1 &
# Stop: touch $F4WORK/STOP   (running workers finish their current batch; none are restarted)
# Each worker is restarted with a fresh context after every batch, alternating models. A worker that stops early
# (STOPPED.txt, or a batch under 3 minutes: quota or service trouble) waits 30 minutes before its next try.
set -u
base=${F4WORK:-$HOME/f4work}
days=${1:-7}
end=$(( $(date +%s) + days * 86400 ))
batch=25
models=(gpt-6.2-astra gpt-6.2-astra)   # 6.2 Sol declined this task (2026-11-21); Astra only
typeset -A started backoff runs fails lanes
lanes=(w1 big w2 big w3 mid w4 mid)   # offline-first large functions; empty lane = the small-function brief
i=0
while [ $(date +%s) -lt $end ] && [ ! -e $base/STOP ]; do
  # The model-free submitter owns every claim and submit for big/ready and big/ports/ready (submitter.py).
  pgrep -f "submitter.py"  >/dev/null || [ -e $base/big/SUBMITTER_STOP ] ||     (cd $base && nohup venv/bin/python submitter.py >>big/submitter.out 2>&1 &)
  for w in w1 w2 w3 w4; do
    dir=$base/workers/$w
    [ -s $dir/key.txt ] || continue
    pgrep -f "run_worker.sh $w " >/dev/null && continue
    now=$(date +%s)
    [ $now -lt ${backoff[$w]:-0} ] && continue
    if [ -n "${started[$w]:-}" ]; then           # a batch just ended: archive it, decide on a back-off
      ts=$(date -u +%Y%m%dT%H%M%SZ)
      mkdir -p $dir/runs
      [ -f $dir/SUMMARY.md ] && mv $dir/SUMMARY.md $dir/runs/SUMMARY-$ts.md
      [ -f $dir/codex.out ] && tail -c 20000 $dir/codex.out > $dir/runs/codex-$ts.tail && rm -f $dir/codex.out
      if [ -f $dir/STOPPED.txt ] || [ $(( now - ${started[$w]} )) -lt 180 ]; then
        [ -f $dir/STOPPED.txt ] && mv $dir/STOPPED.txt $dir/runs/STOPPED-$ts.txt
        fails[$w]=$(( ${fails[$w]:-0} + 1 )); backoff[$w]=$(( now + 1800 )); unset "started[$w]"
        [ ${fails[$w]} -ge 3 ] && backoff[$w]=$end      # three early stops in a row: retire this worker
        continue
      fi
      fails[$w]=0; unset "started[$w]"
    fi
    m=${models[$(( i % 2 + 1 ))]}; i=$(( i + 1 ))
    started[$w]=$now; runs[$w]=$(( ${runs[$w]:-0} + 1 ))
    lane=${lanes[$w]:-}; n=$batch
    [ "$lane" = big ] && n=4; [ "$lane" = mid ] && n=8
    (cd $base && nohup ./run_worker.sh $w $m $n $lane >/dev/null 2>&1 &)
  done
  {
    echo "updated $(date -u +%FT%TZ)  deadline $(date -u -r $end +%FT%TZ)"
    for w in w1 w2 w3 w4; do
      d=$base/workers/$w
      sub=$(cat $d/log.tsv 2>/dev/null | grep -c 'submitted')
      gave=$(cat $d/log.tsv 2>/dev/null | grep -c 'gave up')
      run=$(pgrep -f "run_worker.sh $w " >/dev/null && echo running || echo idle)
      echo "$w $run batches=${runs[$w]:-0} submitted=$sub gave_up=$gave backoff_until=${backoff[$w]:-0} early_stops=${fails[$w]:-0}"
    done
    echo "big: $(for s in work ready submitted tried lost; do printf '%s=%s ' $s $(ls $base/big/$s 2>/dev/null | wc -l | tr -d ' '); done)"
    echo "submitter: $(cat $base/big/submitter.status 2>/dev/null || echo starting)$( [ -e $base/big/SUBMITTER_PAUSED ] && echo ' PAUSED')"
    echo "ports: ready=$(ls $base/big/ports/ready 2>/dev/null | wc -l | tr -d ' ') submitted=$(ls $base/big/ports/submitted 2>/dev/null | wc -l | tr -d ' ')"
    echo "build host load: $(ssh -o BatchMode=yes -o ConnectTimeout=10 ${F4_COMPILE_HOST:-buildhost} cat /proc/loadavg 2>/dev/null || echo unreachable)"
  } > $base/status.txt
  sleep 60
done
echo "supervisor ended $(date -u +%FT%TZ)" >> $base/status.txt
