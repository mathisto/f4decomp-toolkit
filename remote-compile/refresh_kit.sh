#!/bin/zsh -l
# Refresh the f4check kit and shared files on this machine (and the kit copy on the build host) from f4decomp.com.
# Keeps our remote-compile shim: the kit's own msvc11.py becomes msvc11_local.py here; the build host gets the original.
# usage: refresh_kit.sh   (uses workers/w1/key.txt; safe to run while workers are idle or between compiles)
set -eu
base=${F4WORK:-$HOME/f4work}
kit=$base/kit/f4check
key=$(cat $base/workers/w1/key.txt)
tmp=$(mktemp -d)
get() { curl -sf -H "Authorization: Bearer $key" -o "$2" "https://f4decomp.com/pack-data/$1"; }
get f4check.tar.gz $tmp/f4check.tar.gz
get f4decomp_symbols.json $tmp/f4decomp_symbols.json
get function_index.json $tmp/function_index.json
get compiler_tips.md $tmp/compiler_tips.md
get large_functions.md $tmp/large_functions.md
mkdir $tmp/x && tar xzf $tmp/f4check.tar.gz -C $tmp/x
src=$(dirname $(find $tmp/x -name f4check.py | head -1))
cp $kit/msvc11.py $tmp/msvc11_remote_shim.py
rsync -a --exclude msvc11.py $src/ $kit/
cp $src/msvc11.py $kit/msvc11_local.py
cp $tmp/msvc11_remote_shim.py $kit/msvc11.py
cp $tmp/f4decomp_symbols.json $tmp/function_index.json $kit/
cp $tmp/compiler_tips.md $tmp/large_functions.md $base/
# the build host compiles with the kit's own msvc11.py
rsync -a $src/ ${F4_COMPILE_HOST:-buildhost}:f4work/kit/f4check/
cd $tmp && shasum -a 256 f4check.tar.gz f4decomp_symbols.json function_index.json
rm -rf $tmp
echo "kit refreshed $(date -u +%FT%TZ)"
