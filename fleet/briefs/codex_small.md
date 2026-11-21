# f4decomp worker brief: small functions, offline, local model

You match functions of Fallout4.exe 1.10.163 (x64, Visual C++ 2012) in C++ for f4decomp.com, one at a time, on this
machine only. You make no network calls and claim nothing: matches you produce are submitted later by another worker.

## Tools

- Checker: `$F4WORK/venv/bin/python $F4WORK/kit/f4check/f4check.py <file.cpp> --pack <folder>`.
  It compiles your file (a few seconds) and prints MATCH or the differences against the original. Do not change the kit.
- Rules worth reading once: `$F4WORK/kit/f4check/STANDARDS.md`; compiler habits:
  `$F4WORK/compiler_tips.md`. Shared headers you may `#include`: `$F4WORK/kit/f4check/include/`.

## Loop (repeat until your launch count is reached)

1. `$F4WORK/next_big.sh small` prints an address and creates `$F4WORK/big/work/<address>/` with
   `pack.json` and `disasm.txt`. If it prints nothing, stop.
2. Read `disasm.txt`. Write `candidate.cpp` in that folder: declare the types and callees you need, name the function
   `FUN_<address>` unless the disassembly shows a real name, and write plain C++ that does what the code does.
3. Run the checker with `--pack` set to that folder. Fix the first reported difference, run again. Keep a short
   `notes.md` there: each attempt and what changed.
4. On MATCH: write your model name into `model.txt` in the folder, then
   `mv $F4WORK/big/work/<address> $F4WORK/big/ready/`.
5. No match after 15 minutes or 8 attempts without progress: write the remaining difference into `notes.md`, then
   `mv $F4WORK/big/work/<address> $F4WORK/big/tried/`.

## Hard rules

- Real, readable C++: no inline assembly, no raw bytes, no `#pragma`, no `volatile` locals, no invented helpers that
  exist only to steer the compiler.
- Disassembly and anything else from the game stays on this machine. No model, tool or path names in code comments.
- If the code references Havok (`hk...`), Scaleform/GFx, zlib, libpng, Bink or `IAllocatorFunctor`, do not work it:
  write one line in `notes.md` and move the folder to `big/tried/`.
- Do not touch git, install anything, or change files outside your working folder and `$F4WORK/big/`.

## Log

Append one line per function to `log.tsv` in your working folder: time, address, size, verdict (ready / tried),
minutes, attempts, a few words on why. At the end write `SUMMARY.md` with the counts.
