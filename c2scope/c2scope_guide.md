# c2scope on f4decomp (cl 17.00 x64): which tool for which symptom

c2scope (NoahBPeterson/c2scope, MIT) traces Visual C++'s back end (c2.dll) while it compiles your candidate, so it
can say why the compiler made a choice, not only that it differs. Our compiler is exactly the build it was ported to
(c2.dll 17.00.61030). Run every tool through `$F4WORK/c2scope.sh`; it copies your files to the trace host,
adds the kit headers and selects 17.00. A traced compile takes a few seconds.

First write the original's code in c2scope's format, once per function:

    $F4WORK/c2scope.sh orig 0x14039ef40 orig.s

Flags always go last, after `--`, exactly as the pack lists them: `-- /O2 /GS- /MD /EHsc /GR`.
`--func` takes the function's name as in your source (`FUN_14039ef40`) or part of its decorated name.

| Your candidate differs by | Run | What you get |
|---|---|---|
| Extra or missing instructions (a widening, a reload, a compare, a move) | `icount.py cand.cpp --func F --asm-vs orig.s -- FLAGS` | each extra/missing instruction with its source line, the compiler pass that made or removed it, and a verdict class. Start here for almost everything. |
| Registers only (same instructions, other registers) | `c2ncol.py cand.cpp --func F --why -- FLAGS` | every value in priority order with the register it got; `--why` gives the priority formula per block. The allocator follows appearances weighted by free registers per block. |
| Which edit would give value V register R | `c2ncol.py cand.cpp --func F --export run.json -- FLAGS`, then `ncolsim.py whatif run.json --func F +app:V:B:N` | the predicted registers after adding/removing N appearances of V in block B (about 95% of choices right): a hypothesis, confirm with one compile |
| Instruction order inside a block | `c2sched17.py cand.cpp --func F --ready -- FLAGS` | the scheduler's issue order and why (priority fields, pairing); compares and their jcc stay together |
| Stack slots of locals in other places | `c2trace.py slots cand.cpp --func F -- FLAGS` | the frame packer's colours and final offsets |
| Operand order of a commutative operation | `symkeys.py sites cand.cpp --func F -- FLAGS` | the keys that order operands; `whatif` predicts edits |
| You want to try several spellings at once | `tsweep.py tmpl.cpp --func F --asm-vs orig.s -- FLAGS` with `{{a<|>b<|>c}}` alternatives in the file | every combination compiled and ranked against the original |
| What the IL looks like after a pass | `c2trace.py il cand.cpp --func F -- FLAGS` | the compiler's intermediate code with source lines |

Not ported to x64 yet (they print a warning or give wrong answers): `judge.py`, `regs`/`scratch`/`regmap`,
`rasim`, `realize.py`, `rwsweep.py`, `helpersweep.py`. Ignore the two "events are not ported" warnings.

Trust order: f4check's byte comparison, then a traced compile, then a model prediction. Every model answer is a
hypothesis until one compile confirms it.

Example (0x14039ef40, 2,239 bytes): icount showed the only difference was at `land->height(quadrant, vertex)`, where
the original sign-extends `vertex` from r8d (the third argument register) before the multiply while ours merged it
into a `cdqe` on eax: the widening belongs inside the accessor on its parameter, not at the call site.
