# ares_engine — the Arès engine (vendored, owned)

`strix/` here is the full engine source, owned by Arès (modified Strix 1.3/1.5.3).
This is the single source of truth — no external patching.

Run from the repo with `pip install -e .` (installs this as the `strix` package
plus the `engine` extra for third-party deps), or point PYTHONPATH here.
See VENDORED.md for the exact modifications vs upstream.
