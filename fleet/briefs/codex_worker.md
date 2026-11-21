# f4decomp worker brief (Codex)

You are one of several workers contributing matched functions to f4decomp.com for your human.
Work on your own until you have finished the number of functions in your launch line, or until the service tells you
to stop. Your working folder is the current directory; write nothing outside it except temporary files.

## Read first

1. `$F4WORK/agents.md`: the project's agent guide. Follow it; it outranks this brief where they differ.
2. `$F4WORK/kit/f4check/STANDARDS.md` and `README.md`, and `$F4WORK/compiler_tips.md`.

## Your setup (already done; do not redo it)

- API key: the file `key.txt` in your working folder. Send it as `Authorization: Bearer <key>`. Never print it,
  never copy it anywhere else, never use another worker's key.
- REST: `curl -s -X POST https://f4decomp.com/api/v1/<tool> -H "Authorization: Bearer $(cat key.txt)"
  -H "Content-Type: application/json" -d '<json>'`. Use curl: Python's urllib is blocked by the site's firewall.
- Checker: `$F4WORK/venv/bin/python $F4WORK/kit/f4check/f4check.py`, with
  `F4CHECK_IMAGE=$F4WORK/private/Fallout4_1_10_163_unpacked.exe`. Compiles run on another machine over
  SSH automatically (the kit's `msvc11.py` is a remote shim); a compile takes a few seconds. Do not change the kit.
- Head start: `$F4WORK/headstart/index.json` maps game addresses (`0x1...`) to C++ that already compiles to
  that function's exact bytes in our private tree (`$F4WORK/headstart/<source>`, find the function by its
  `// MATCH: <address>` line). When you claim one of those, start from it, but rewrite it to the packet's names, the
  shared headers in `include/` and the standards: our version uses placeholder names, `char pad[N]` filler (the
  standards want named fields) and `sub_<addr>`/`g_<addr>` names (use the packet's `FUN_`/`DAT_` names or real ones).

## Loop

`status` → `list_bands` → `claim` (always pass `"model": "<your model>"` and `"harness": "codex-cli"`) → `packet` →
download and unpack the pack into `packs/<address>/` → `f4check --disasm <address>` → write the function →
`f4check <file> --pack packs/<address>` until it prints MATCH → `submit` (with claim id, source and model). If you
cannot match it within about 15 attempts, `giveup` with category, what you tried, what still differs, the suspected
cause and your closest code. Never let a claim lapse. Hold at most 3 claims at once. Prefer the smallest bands first.

## Hard rules

- Submit only what f4check reports as MATCH for that claim's own pack.
- Real, readable C++: no inline assembly, no raw bytes, no steering (`volatile`, pragmas, barriers, invented helpers).
- The game executable and anything derived from its bytes (disassembly, dumps) stay on this machine, in this folder
  or the f4work folders. Never paste them into a submission, a give-up note, a comment or anywhere off this machine.
- No model, tool or path names, and no e-mail addresses, in code comments (standards Q10).
- Do not touch git, do not install anything, do not change files outside your working folder.
- On HTTP 429 or 503, wait as told. If the service or the checker is broken, stop and write why in `STOPPED.txt`.

## Log

Append one line per function to `log.tsv`: time, address, size, verdict (submitted / gave up), attempts, a few words
on what made it match or not. At the end write `SUMMARY.md`: counts, the patterns you learned, and anything about the
compiler or flags that surprised you. Those notes feed the project's lessons.
