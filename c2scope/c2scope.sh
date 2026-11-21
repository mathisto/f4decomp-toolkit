#!/bin/zsh
# c2scope for f4decomp: run a c2scope tool (NoahBPeterson/c2scope, MIT) on a Linux build host with cl 17.00 x64 (VS2012).
# usage:
#   c2scope.sh orig <address> [out.s]     write the original's code as c2scope's orig.s (VA mnemonic operands)
#   c2scope.sh <tool.py> [args...] -- <flags>
# Local files named in the args are copied to the build host and their paths rewritten; the f4check kit's shared headers
# are added as an include folder. Examples (FUN = the function's name in your source):
#   c2scope.sh c2ncol.py cand.cpp --func FUN_14039ef40 --why -- /O2 /GS- /MD /EHsc /GR
#   c2scope.sh judge.py cand.cpp --func FUN_14039ef40 --asm-vs orig.s -- /O2 /GS- /MD /EHsc /GR
# Read c2scope_guide.md for which tool answers which symptom.
set -u
base=${F4WORK:-$HOME/f4work}
host=${F4_COMPILE_HOST:-buildhost}
# The kit's include folder on the build host, as Wine sees it (Z: is /).
inc=${F4_REMOTE_KIT_INCLUDE:-/home/$USER/f4work/kit/f4check/include}
[ $# -lt 1 ] && { sed -n '2,10p' $0; exit 2; }
if [ "$1" = orig ]; then
  addr=$2; out=${3:-orig.s}
  F4CHECK_IMAGE=$base/private/Fallout4_1_10_163_unpacked.exe $base/venv/bin/python - "$addr" "$out" <<'EOF'
import json, os, sys
sys.path.insert(0, os.path.expanduser('$F4WORK/kit/f4check'))
import f4check
a = int(sys.argv[1], 16)
size = {int(f['address'], 16): f['size'] for f in json.load(open(f4check.index_path()))['functions']}[a]
pe = f4check.image(); md = f4check.capstone64()
with open(sys.argv[2], 'w') as f:
    for ins in md.disasm(pe.read(a, size), a):
        f.write('%x %s %s\n' % (ins.address, ins.mnemonic, ins.op_str))
print('wrote', sys.argv[2], size, 'bytes')
EOF
  exit
fi
tool=$1; shift
rw=projects/c2scope-env/work/f4-$$-$RANDOM
ssh -o BatchMode=yes $host "mkdir -p ~/$rw" || exit 1
args=()
for a in "$@"; do
  if [ -f "$a" ]; then
    scp -q -o BatchMode=yes "$a" "$host:$rw/${a:t}" || exit 1
    args+=("\$HOME/$rw/${a:t}")
  else
    args+=("${(q)a}")
  fi
done
case " $* " in *" -- "*) args+=("/IZ:$inc");; esac
ssh -o BatchMode=yes $host "cd ~/projects/c2scope && export PATH=/usr/lib/llvm-18/bin:\$HOME/.local/bin:\$PATH WINEDEBUG=-all C2_BUILD=\${C2_BUILD:-17.00} && uv run tools/$tool ${args[*]}; rc=\$?; rm -rf ~/$rw; exit \$rc"
