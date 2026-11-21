#!/bin/zsh -l
# Launch one Codex worker for f4decomp.
# usage: run_worker.sh <name> <model> <functions> [lane]   (key in workers/<name>/key.txt)
# lane: empty = small functions (codex_worker.md); big or mid = offline-first large functions (codex_big.md);
#       small = offline 96-255 B functions on a local LM Studio model (codex_small.md; <model> is the LM Studio id)
set -eu
name=$1; model=$2; count=$3; lane=${4:-}
base=${F4WORK:-$HOME/f4work}
dir=$base/workers/$name
mkdir -p "$dir"
[ "$lane" = small ] || [ -s "$dir/key.txt" ] || { echo "no key in $dir/key.txt"; exit 1; }
cd "$dir"
export F4CHECK_IMAGE=$base/private/Fallout4_1_10_163_unpacked.exe
provider=()
if [ "$lane" = small ]; then
  brief=$(cat $base/codex_small.md)
  launch="Launch line: you are worker '$name', model '$model'. Finish $count functions (ready or tried), then write SUMMARY.md and stop."
  effort=(); provider=(--oss --local-provider lmstudio)
elif [ -n "$lane" ]; then
  brief=$(cat $base/codex_big.md)
  launch="Launch line: you are worker '$name', model '$model', lane '$lane'. Do Phase 1, then finish $count functions in Phase 2 (ready or tried), then write SUMMARY.md and stop."
  effort=(-c model_reasoning_effort=high)
else
  brief=$(cat $base/codex_worker.md)
  launch="Launch line: you are worker '$name', model '$model'. Finish $count functions (submitted or given up), then write SUMMARY.md and stop."
  effort=()
fi
/opt/homebrew/bin/codex exec --skip-git-repo-check $provider -m "$model" $effort \
  -s workspace-write -c sandbox_workspace_write.network_access=true \
  -c 'sandbox_workspace_write.writable_roots=["'$base/big'"]' \
  "$brief

$launch" \
  < /dev/null > codex.out 2>&1
