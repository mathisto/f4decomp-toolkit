#!/bin/zsh
# Take the next free address of a large-function lane and prepare its offline work folder.
# usage: next_big.sh <big|mid>   prints the address (folder big/work/<address>/ holds pack.json and disasm.txt)
set -eu
lane=$1
base=${F4WORK:-$HOME/f4work}
big=$base/big
mkdir -p $big/work $big/ready $big/tried $big/submitted $big/lost
while read -r a; do
  [ -n "$a" ] || continue
  for s in ready tried submitted lost; do [ -e $big/$s/$a ] && continue 2; done
  mkdir $big/work/$a 2>/dev/null || continue          # another worker has it
  $base/venv/bin/python $base/prep_big.py $a $big/work/$a >/dev/null
  echo $a
  exit 0
done < $big/queue/$lane.txt
