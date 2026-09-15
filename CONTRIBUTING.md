# Contributing

Thanks for your interest. Arès is a hard-fork of
[Strix](https://github.com/usestrix/strix) (Apache-2.0).

## Layout
- `ares_setup/`, `ares_provenance/`, `ares_*.py` — the Arès product (original work).
- `ares_engine/strix/` — the **vendored** Strix engine, pinned in `ares_engine/BASELINE`,
  modified only in the 8 files listed in `patches/MODIFIED_FILES`.

## Rules of thumb
- Keep engine changes **minimal and localized** — every edited engine file is a
  future merge conflict. Prefer adding Arès logic in `ares_setup/` where possible.
- Engine bug fixes that aren't Arès-specific should go **upstream to Strix** as a
  PR, not stay in our diff.
- Run the tests before opening a PR: `python3 -m pytest tests/ -q`.

## Syncing the engine with upstream
```bash
bash ares_engine/update.sh            # latest upstream tag
```
It re-applies the Arès patches and flags conflicts to re-port by hand.

## Commit style
Small, focused commits with a clear subject line.
