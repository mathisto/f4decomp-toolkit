# Provenance

Everything in this repository was written for it by its author's own setup, except where noted.

- **Weak-twin porting** (`twins/`): the idea of porting a matched source to functions with the same masked instruction
  shape comes from another f4decomp contributor's published tooling notes (2026-11-21). The code and the literal-swap
  and address-based renames are ours.
- **Offline screening with a synthesized `pack.json`**, and claiming only what already matched, follow practice shared
  by the f4decomp community (its insights file, rule R880).
- **c2scope** (`c2scope/`): the wrapper and guide are ours; c2scope itself is NoahBPeterson/c2scope (MIT) and is not
  included.
- **f4check** is f4decomp.com's checker kit. It is not included; `remote-compile/` replaces only its compiler call.
- No game bytes, disassembly listings, Microsoft files, keys or third-party code are in this repository.
