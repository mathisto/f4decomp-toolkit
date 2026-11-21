# f4decomp worker brief: large functions, offline first (Codex)

You are one of several workers contributing matched functions to f4decomp.com for your human.
This brief is for the **large-function lanes**: functions of 512 bytes and up that need real reasoning. Small functions
are left to other contributors. Work on your own until you have finished the number of functions in your launch line.

## Read first

1. `$F4WORK/agents.md`: the project's agent guide. It outranks this brief where they differ.
2. `$F4WORK/kit/f4check/STANDARDS.md` and `README.md`.
3. `$F4WORK/community_insights.md` and `$F4WORK/our_insights.md`: measured compiler rules for this
   exact compiler and game (R-numbers and M-numbers). Look up the relevant rule before guessing.
4. `$F4WORK/compiler_tips.md` and `$F4WORK/large_functions.md` (the site's own advice).
5. `$F4WORK/c2scope_guide.md`: the compiler tracer. When a near miss stalls (a few instructions or registers
   off), run `icount` before trying more spellings: it names the source line and compiler pass behind each
   difference. Use it before giving up on any function whose remaining difference is small.

## Setup (already done; do not redo it)

- API key: `key.txt` in your working folder, sent as `Authorization: Bearer <key>`. Never print or copy it.
- REST with curl only (Python's urllib is blocked): `curl -s -X POST https://f4decomp.com/api/v1/<tool>
  -H "Authorization: Bearer $(cat key.txt)" -H "Content-Type: application/json" -d '<json>'`.
- Checker: `$F4WORK/venv/bin/python $F4WORK/kit/f4check/f4check.py`, with `F4CHECK_IMAGE` already
  set. Compiles run on another machine automatically and take a few seconds. Do not change the kit.
- Shared folder for this lane: `$F4WORK/big/` (`queue/`, `work/`, `ready/`, `tried/`, `submitted/`, `lost/`).

## Phase 1, every launch: near misses (only when the account has capacity)

Do not claim or submit anything in `big/ready/`: a separate submitter process does that for every ready folder,
largest first, once the account has capacity. Call `status`. If `submissions_today` is below the daily allowance
(5,000 unless status says otherwise), then near misses: for each folder in `big/tried/` whose `notes.md` reports a small remaining difference (under
about 5% of the bytes) and that has no `giveup.json`, take it the same way (`mkdir .taking`), claim it, check
`candidate.cpp` against the real pack, and `giveup` with `category`, `tried`, `still_differs`, `suspected_cause` and
`best_code` (the candidate): the site's solver works on close give-ups and credits us when it finishes one. Save the
answer as `giveup.json`. At most 10 per launch.
If the account is at its daily limit, skip Phase 1 entirely. Never claim anything you are not about to submit or
give up at once.

## Phase 2: match new functions offline, without a claim

Repeat until your launch count is reached:
0. Retry first: if a folder in `big/tried/` contains a file `RETRY` and no `.taking`, take it (`mkdir .taking`), read its `notes.md`, run `icount` as `c2scope_guide.md` shows, and spend up to
   30 minutes on what it names. On MATCH move it to `big/ready/` (remove `RETRY` and `.taking`); otherwise add what you
   learned to `notes.md` and remove `RETRY`.
1. `$F4WORK/next_big.sh <lane>` prints the next free address of your lane and creates its folder
   `big/work/<address>/` with `pack.json` and `disasm.txt` (or prints nothing when the queue is empty: then stop).
2. Read `disasm.txt`. Write the function in `big/work/<address>/candidate.cpp` and check it with
   `f4check big/work/<address>/candidate.cpp --pack big/work/<address>`. The `pack.json` there is built locally from the
   pool's standard flags; it carries no owner or callee list, so name the target `FUN_<address>` unless the symbol map
   or the disassembly gives a real name, and declare the types you need.
3. Fix the first difference first. Work by measured differences (size, then call order, then frame size, then stack
   slots, then registers). Keep `notes.md` in the folder: what you tried, what changed, the closest result.
4. **MATCH:** move the folder to `big/ready/<address>/` (the submitter process claims and submits it once the
   account has capacity). Log it.
5. **No match:** stop by the clock: about 60 minutes for the `big` lane (30 for `mid`), or 20 minutes with only
   register or block-order differences left, or 30 minutes without a measured gain. Write the remaining difference
   and the closest code into `notes.md`, move the folder to `big/tried/`, log it. Nothing is claimed, so nothing lapses
   and no give-up is needed.

## Hard rules

- Submit only what f4check reports as MATCH against that claim's own pack.
- Real, readable C++: no inline assembly, no raw bytes, no steering (pragmas, barriers, volatile locals, invented
  helpers). A `volatile` member of an engine type is allowed where the community notes show it (R1510).
- The game executable and anything derived from it (disassembly, dumps) stay on this machine. Never paste them into a
  submission, a give-up note, a comment or anywhere off this machine.
- No model, tool or path names and no e-mail addresses in code comments (standards Q10).
- Skip, do not work, any function that references `IAllocatorFunctor` (R1450) or Havok, Scaleform, zlib or libpng
  code: move it to `big/tried/` with one line of notes.
- Do not touch git, install anything, or change files outside your working folder and `big/`.
- On HTTP 429 or 503 from claim or submit, stop Phase 1 for this launch and continue with Phase 2.

## Log

Append one line per function to `log.tsv` in your working folder: time, address, size, verdict (ready / submitted /
tried / lost), minutes spent, attempts, a few words on what made it match or not. At the end write `SUMMARY.md`:
counts, the compiler patterns you learned (with the function address as evidence), and anything that surprised you.
Those notes feed the shared insights.
