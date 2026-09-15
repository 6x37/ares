# Vendored engine — Strix, modified & owned

`strix/` here is the Strix engine source, **pinned at the tag in `BASELINE`**
(currently `v1.5.3`), with the Arès modifications overlaid. Arès owns this copy —
it is not a live patch of an external install.

## The Arès diff — 8 files, ~220 lines

Only these files differ from pristine upstream (see `../patches/`):

| File | Change |
|------|--------|
| `interface/main.py` | ethical-use notice replaces the model-quality warning |
| `interface/environment.py` | tolerant image pull (local-only tags don't 404-abort) |
| `interface/tui/backend/controller.py` | drop the model-quality warning (TUI) |
| `config/settings.py` | default sandbox image `ares-sandbox:1.3.0` |
| `config/models.py` | cloud-prefixed models bypass the local api_base (escalate tier) |
| `runtime/docker_client.py` | `ares-*` Docker naming + preserve the image ENTRYPOINT |
| `runtime/caido_bootstrap.py` | Caido readiness attempts 10 → 30 |
| `agents/factory.py` | cascade per-role model routing + local reinforcement directive |

## Staying in sync with upstream

Upstream ships fast (already past this baseline). New engine capabilities —
tools, vuln coverage, agent-graph work — live *inside* the engine, so bumping the
baseline inherits them; Arès's own layer (signing, confidence, cascade) sits on
top and doesn't change.

```bash
bash ares_engine/update.sh            # sync to the latest upstream tag
bash ares_engine/update.sh v1.6.2     # or a specific one
```

The script does a 3-way check per Arès-modified file:
- upstream left the file untouched → the Arès patch re-applies cleanly;
- upstream changed the file → **conflict**: it stops, keeps the upstream version,
  and tells you exactly which patch to re-port by hand (with the two diffs to
  compare). Nothing is pushed — you review, run tests, and commit.

`patches/baseline/` holds the pristine version each patch was made against;
`patches/ares/` holds the Arès version. That pair is what makes conflicts precise.
