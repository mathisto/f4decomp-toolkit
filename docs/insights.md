# f4decomp insights from team mathisto: Visual C++ 2012 x64, Fallout 4 PC 1.10.163

Facts we measured while preparing a private match tree (43,834 functions byte-exact, relocations verified) and then
contributing on f4decomp (5,004 verified submissions on 2026-11-21). It is written to sit next to the community
insights file. It holds no account data, no local paths and no game bytes. Addresses are 1.10.163 virtual addresses.
Last updated 2026-11-21.

**Rule IDs** are `M` + number, so they never collide with the community file's `R` IDs. Evidence tags as there:
**[M]** measured against the game image, **[probe]** small standalone unit, **[I]** inference, not confirmed.

---

## Compiler and flags

### M100. The game is built without C++ exceptions, although the packs list /EHsc

**[M, whole image]** Only 3,557 of 291,080 unwind entries name `__CxxFrameHandler3` (another 957 + 453 name two
other handlers; `__C_specific_handler` is SEH). With `/EHsc`, an inlined constructor body or a destructor chain gets
an EH frame (`mov qword ptr [rsp+N],-2`, a `nop` after calls) that the game's functions do not have.
- Our private tree builds everything with `/O2 /GS- /Gy /MD` (no `/EHsc`). Every earlier match still matched after
  dropping `/EHsc`, and a `throw()` we had added to destructors only to suppress that frame became unnecessary.
- A few units do use EH: 59 static setting initialisers carry the frame, so they need `/EHsc` per unit.
- Fits the community lead R1450: 0x142497600 "also needed building without /EHsc to lose the exception frame".
  If your candidate shows `mov qword ptr [rsp+N],-2` and the game does not, the cause is the flag, not your source.

### M110. VS2012 RTM, Update 2 and Update 4 generate identical code; the game's CRT is RTM's

**[M, 43,947 functions]** Built with cl 17.00.50727.1 (RTM), 17.00.60315.1 (Update 2) and 17.00.61030 (Update 4),
every function of our tree compiled to the same bytes (the same 43,834 matched, the same misses). So the kit's
Update 5 compiler and an RTM one are interchangeable for matching.
- The static CRT linked into the game matches RTM's x64 `msvcrt.lib` byte-exact (Windows-app `__tmainCRTStartup`
  482 B, `__security_init_cookie` 184 B, 48 CRT functions in all). Updates 2 and 4 ship a rebuilt `msvcrt.lib`
  (dated 5 Nov 2012) whose versions are 483 and 172 B and appear nowhere in the game. So the game was linked
  against RTM libraries.

### M120. The image's VC_FEATURE debug record counts 4,147 C/C++ objects

**[M PE debug directory, type 12]** 1 pre-VC11 object, 4,147 C/C++ objects, 494 built with `/GS`, 0 with `/sdl`.
That is roughly the translation-unit count, and most units are `/GS-`. The RTM linker writes this record too, so it
does not date the linker.

### M130. Static settings are about 15,000 functions in two generated forms

**[M 14,937 functions]** Each `SettingT<Collection> x("key:Section", value)` yields a dynamic initialiser `??__E`
(ensure the collection singleton, `Add`, then `atexit`) and an atexit destructor `??__F` (the inlined `~SettingT`:
`Remove`, then `Setting::~Setting`). The vtable, key and value are constant-folded into `.data`, so the key string
read from the image names the setting.
- The `??__E` runs inside a thread-local memory-context id at `.tls+0x9c0`. Both of these spellings are in the game:
  an RAII scope object gives `mov esi,0x9c0 ; [rdi+rsi]` (4,972 functions); an explicit save and restore gives
  `mov edx,0x9c0 ; add rdi,rdx` (2,491).
- Static initialisers can share one section: a function's bytes run from its symbol to the next symbol in that
  section, so tools that take "the whole section" give false diffs.

### M140. A pointer-to-member global of a multiple-inheritance class is a 16-byte copy

**[M 1,611 functions]** `void (C::*g)() = &C::f;` where `C` has multiple inheritance compiles to a dynamic
initialiser that builds a 16-byte temporary: `mov dword [rsp+8],0 ; mov rax,[rsp+8]` then two stores.

### M150. Adjustor thunks come from one function overriding the same virtual in two bases

**[M]** MSVC emits `sub rcx,N ; jmp` when one function overrides the same virtual in two bases (the second at
offset N). Overriding only the second base's virtual emits no thunk. Thunks have the mangled prefix `?f@C@...@@W`;
look them up by exact decorated name, because a qualified name also matches the `@@U` function itself.

### M160. A by-value result read once is a named local of a type with a constructor

**[M 2,887-function family]** `R r = f(); return r.p;` matched where `return f().p;` did not, and only when `R` has
a user constructor (so it comes back through a hidden pointer). Release-and-null of a global nulls it inside the
`if`, not after it.

### M170. Small literal traps

- **[M]** `%.9g` of `FLT_MAX` rounds above the float range (C2177 "constant too big"). Write `3.402823466e+38f`.
- **[M]** Fixed-string static initialisers end in a tail `jmp` to the atexit registration, although it returns
  `int` and the initialiser returns `void`.

### M180. `push rbp ; sub rsp,N ; mov rbp,rdx ; ...` is an EH funclet, not a function

**[M]** Those starts are unwind funclets of their parent functions. There is no source to write for them on their
own.

### M190. Open: BSTArray capacity calls through a functor keep `this` in rcx; ours copy it to rax

**[M about 1,800 functions, in shapes of 1,230, 320 and 220]** The game keeps `this` in `rcx` (`add rcx,0x18`
after storing it in the functor). Every spelling we tried (the array as bases or as members, a template, the functor
as a named local or a by-reference temporary) copies it to `rax` first and is 3 bytes longer. Update 4 reproduces
the miss byte for byte, so the cause is in the source, not the compiler build.
- **[I]** Possibly the same family as R1450 (the IAllocatorFunctor destructor store). Not yet tried with a functor
  destructor plus no `/EHsc`.

### M195. Open: 210 field reads whose temporary sits in a different home slot

**[M]** The game's temporary is at `[rsp+0x40]`, ours at `[rsp+0x30]`. Adding parameters did not move it.

---

## Names and structure, before any compiling

### M300. RTTI gives most class names and 40,000 named virtual functions

**[M]** RTTI yields 10,112 classes, 11,914 vtables and 120,993 virtual slots, which reach 40,498 distinct functions,
with base-class chains (for example `PlayerCharacter > Actor > TESObjectREFR > TESForm`).

### M310. Leaf functions have no `.pdata` entry, so `.pdata` alone misses thousands

**[M]** `.pdata` lists 199,088 functions. Leaf functions have no unwind entry (`ret 0` stubs, `jmp` thunks,
`xor eax,eax ; ret`): 15,554 of the RTTI- and F4SE-named functions are such leaves. `.pdata` plus RTTI plus F4SE
gives 214,642 function starts before any disassembler pass.

### M320. Fallout 3 twins through shared strings are few

**[M]** Of 10,406 Fallout 4 functions that load a string and 14,868 Fallout 3 functions that push one, only 322 share
a string that is unique on both sides (Fallout 4 rewrote most of the engine). Chaining through a Fallout 3 to
New Vegas twin map names 133 of them. The community's multi-feature scoring (R1700) finds more; use both.

---

## Tooling

### M400. Relocation-verifying comparison on x64

**[M]** f3_decomp's comparer (CC0) resolves every relocation to an original address instead of masking it. Porting
it to AMD64 needs: `REL32` and `REL32_1..5` add 4 + k to the field address; `ADDR64` is 8 bytes; `ADDR32NB` is
image-relative. With placeholder externs bound to their addresses, float and string literals verify by content.

### M410. Bindings cross-check each other

**[M]** Binding every referenced target took our verified matches from 14,921 to 24,637 and exposed 9 "static
initialisers" that never reach `atexit` (they had passed while targets were masked). A target that thousands of
functions share (`atexit` at 0x142936bcc, used by 2,500 initialisers) is a consensus check on every binding.

### M420. Shape generators: one template per instruction shape

**[M 43,834 functions]** Disassemble every function, normalise operands (registers kept, displacements and targets
abstracted), group by the instruction sequence, and write one source template per shape that fills in offsets,
callees and constants. Six tiers of shapes, each first verified on a sample of 8, then run whole; the only failure
mode at small sizes was a guessed member offset. Trap: capstone leaves a trailing space on operand-less instructions
(`ret `); strip it before comparing shape strings.

### M430. Compiling remotely

**[M]** The compiler only needs the source, its include folders and the arguments. A small shim that tars those (with
paths rewritten), runs the kit's compile on a Linux host under Wine over SSH, and unpacks the object, lets several
lightweight machines share one build host. A compile round trip took a few seconds.

### M440. Shell and HTTP traps

- **[M]** Git Bash on Windows rewrites arguments that start with `/` into Windows paths (MSYS path conversion):
  `--flags "/O2 ..."` silently reached the compiler as a path, giving `/Od`-like code and thousands of false misses.
  Set `MSYS_NO_PATHCONV=1`, or put flags in the source file.
- **[M]** The site's firewall refuses Python's `urllib` (Cloudflare error 1010); `curl` works.
- **[M]** When generated Python passes through a shell heredoc, `\0` can arrive as a real NUL byte. Check with
  `ast.parse` after each generated edit.

### M450. Ghidra on Apple silicon

**[M]** Ghidra 12.2 needs JDK 25; with a keg-only JDK, set `JAVA_HOME_OVERRIDE` in `support/launch.properties` or the
headless launcher stops with "no TTY". Its release has no arm64 native decompiler, and the decompiler analyzers then
crash the import ("Can't checkpoint with locked buffers"): run with a pre-script that disables them. The default 2 GB
heap runs out on this image; set `GHIDRA_HEADLESS_MAXMEM=16G`.

---

## Getting the compiler without installing Visual Studio

### M500. Express 2012 and the update ISOs are still on Microsoft's servers

**[M]** `VS2012_WDX_ENU.iso` (Express 2012 for Windows Desktop, 637 MB) is still on download.microsoft.com. Windows'
own `tar.exe` lists and extracts it; `msiexec /a <msi> /qn TARGETDIR=<folder>` (administrative extraction, no admin
rights) on `vc_compilerCore86`, `vc_compilerCore86res` and `vc_librarycore86` gives the x64 cross compiler
17.00.50727.1 with its headers.
- The update bootstrappers' package links are dead, but the Update 2 and Update 4 ISOs are still served. They are
  plain ISO 9660 (no Joliet or UDF), so HTTP range requests can read single files out of them: the compiler packages
  are about 14 MB of a 2 GB image. Check each file's SHA-1 against the `<Payload Hash=...>` in the signed
  bootstrapper's manifest (file `0` of its `.wixburn` container) before extracting.
- Updates 1, 3 and 5: no surviving Microsoft link found.

---

## Contributing at volume

### M600. A day of the swarm tier, small functions

**[M 2026-11-21]** Four parallel agent workers, each restarted with a fresh context every 25 functions, starting from
a head-start index of our private matches (rewritten to the site's names and headers): 5,004 verified submissions,
173,325 bytes, no failed verification, no strike. Most small functions matched on the first compile. The daily
limit of 5,000 submissions was reached by 08:39 UTC.

### M610. At the daily limit, status still suggests claiming

**[M 2026-11-21]** After `submit` answered HTTP 429 ("return tomorrow"), `status` kept listing open bands and
suggesting a claim. Check `submissions_today` against the allowance yourself before claiming, or a loop burns
claims it cannot submit. A claim held when the limit hits can be released with `giveup`; the matching source is kept
for the next claimant.

### M620. Average size at volume is small

**[M]** 5,004 submissions averaged 35 bytes. Open functions by band on 2026-11-21: 154,511 at 255 bytes or less,
14,857 at 256-511, 6,457 at 512-1K, 2,592 at 1K-4K, 196 above 4K. Byte for byte, about 115 functions of 1.5 KB
equal that whole day.
