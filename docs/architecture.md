# Architecture

Arès is three layers: a **product layer** it owns, a **signing layer** it owns, and
the **engine** it vendors from Strix. The product and signing layers are original
work; the engine is a modified copy of Strix that Arès controls directly.

Grounded in the Architecture section of [`../README.md`](../README.md),
[`../ares_engine/VENDORED.md`](../ares_engine/VENDORED.md), and the modules
themselves.

```
ares_setup/        the Arès product — init, dial, dashboard, cascade config,
                   model-eval, confidence, offline, guardrails, compliance, diff, hub
ares_provenance/   Ed25519 signing & verification (only external dep: cryptography)
ares_console.py    streaming local console (stdlib only)
ares_watch.py      live agent-activity feed + confidence gate + auto-sign
ares_demo.py       scripted 45s showcase of the whole chain
ares_engine/       the vendored, modified Strix engine (owned, not live-patched)
```

## Layer 1 — `ares_setup/` (the product)

Everything that makes a local, guided, reliable experience:

- **Setup**: `hardware.py` (detect usable inference memory on macOS/Linux),
  `models.py` (curated local-model catalog + recommendation), `ollama.py` (drive
  the local Ollama CLI/daemon), `dial.py` (map one 0–100 "power" level to concrete
  engine knobs), `config.py` (bake a derived Ollama model + write the `ares.env`),
  `wizard.py` + `__main__.py` (the `ares init` flow).
- **Inspection**: `dashboard.py` (hardware + model catalog), `model_eval.py`
  (STRIX-READY tool-calling probe — see [reliability.md](reliability.md)).
- **Routing**: `cascade.py` (the triage / validate / escalate tier definitions —
  see [cascade.md](cascade.md)).
- **Reliability**: `confidence.py` (grade a finished run HIGH/OK/LOW).
- **Safety & privacy**: `offline.py` (air-gap audit/harden), `guardrails.py` (scope
  preflight, kill-switch, approval gate).
- **Reporting extras**: `compliance.py` (map findings to PCI-DSS / ISO 27001 /
  SOC 2 / NIST CSF), `diff.py` (compare two runs).
- **Hub**: `home.py` (the interactive `ares` menu), `ui.py` (shared styling).

This layer's only heavy assumption is a local Ollama; it has no dependency on
cloud services.

## Layer 2 — `ares_provenance/` (signing)

A small, self-contained package with **one** external dependency, `cryptography`.
It produces and checks the Ed25519-signed manifest that makes reports
tamper-evident and attributable: `keys.py` (keypairs + fingerprints), `sign.py`
(build + sign the artifact manifest, inject the report footer), `verify.py` (the
three-verdict verifier), `canonical.py` (deterministic JSON + SHA-256).

Full details in [provenance.md](provenance.md). Because it is dependency-light and
standalone, it can sign/verify even in the base install without the engine extra.

## Layer 3 — `ares_engine/` (the vendored Strix engine)

`ares_engine/strix/` is a **full, version-controlled copy** of the Strix engine —
the agent swarm, tools, and vulnerability coverage — pinned at the tag in
[`../ares_engine/BASELINE`](../ares_engine/BASELINE) (**v1.5.3**) with the Arès
modifications baked in. Arès **owns** this copy; it is not a live patch of an
external install, so there is a single source of truth.

### How Arès wraps Strix — a minimal, localized diff

Per [`../ares_engine/VENDORED.md`](../ares_engine/VENDORED.md), only **8 files**
(~220 lines) differ from pristine upstream:

| Engine file | Arès change |
|---|---|
| `interface/main.py` | ethical-use notice replaces the model-quality warning |
| `interface/environment.py` | tolerant image pull (local-only tags don't 404-abort) |
| `interface/tui/backend/controller.py` | drop the model-quality warning (TUI) |
| `config/settings.py` | default sandbox image `ares-sandbox:1.3.0` |
| `config/models.py` | cloud-prefixed models bypass the local `api_base` (escalate tier) |
| `runtime/docker_client.py` | `ares-*` Docker naming + preserve the image ENTRYPOINT |
| `runtime/caido_bootstrap.py` | Caido readiness attempts 10 → 30 |
| `agents/factory.py` | cascade per-role model routing + local-reinforcement directive |

The philosophy (see [`../CONTRIBUTING.md`](../CONTRIBUTING.md)): keep engine
changes minimal and localized because every edited engine file is a future merge
conflict; put new logic in `ares_setup/` where possible; send non-Arès-specific
fixes upstream. New engine capabilities are inherited by bumping the baseline
(`bash ares_engine/update.sh`), which re-applies the Arès patches and flags any
conflicts to re-port by hand. `patches/baseline/` and `patches/ares/` hold the
before/after of each patch so conflicts are precise.

### The local-reinforcement directive

Beyond routing, `agents/factory.py` adds a reliability nudge for local models
(`ARES_LOCAL_REINFORCE`, on by default): it appends a short "mandatory discipline"
block to the agent's system prompt — read every in-scope file before concluding,
attempt a concrete test/PoC for each suspected issue, and never conclude "no
vulnerabilities" from reasoning alone. This is a direct countermeasure to the
hallucinated-"stub" failure mode (see [reliability.md](reliability.md)). Set
`ARES_LOCAL_REINFORCE=0` to disable it.

## Local-first routing

Arès talks to models through **Ollama's OpenAI-compatible endpoint**, not the
native Ollama API path. A generated profile therefore sets, roughly:

```bash
export STRIX_LLM="openai/ares-<model>"          # note the openai/ prefix
export LLM_API_BASE="http://localhost:11434/v1" # the /v1 (OpenAI-compatible) path
export LLM_API_KEY="ollama-local"               # a dummy key litellm requires
```

The `openai/…` + `/v1` routing is a deliberate reliability choice: the native
`ollama_chat/` path in litellm retry-stormed on streamed tool calls, while the
OpenAI-compatible path handles tools + streaming cleanly (see
[troubleshooting.md](troubleshooting.md#the-llm-connection-retry-storms-or-times-out)
and [`../INTEGRATION_NOTES.md`](../INTEGRATION_NOTES.md)). All local cascade tiers
share this one endpoint; only the model name changes.

## Offline and air-gapped mode

Generated profiles are private by default — telemetry off (`STRIX_TELEMETRY=0`,
`DO_NOT_TRACK=1`). `ares init --offline` and `ares_setup/offline.py` go further and
close all three of Strix's outbound channels:

1. **Telemetry** (PostHog + Scarf) → `STRIX_TELEMETRY=0`.
2. **web_search** (Perplexity) → the API key must be empty.
3. **The LLM itself** → `STRIX_LLM` must be a local model on a loopback/private
   endpoint, never a cloud provider.

This is **config-level** enforcement — it makes Arès *not initiate* outbound
connections. It is honestly documented as **not a firewall**: for a hard,
kernel-enforced air-gap, run the engine's sandbox container with no external route
(for example `docker run --network none …`, reaching only the host's Ollama). The
`ares offline <env>` audit reports any residual egress risk and exits non-zero if
egress is possible.

## Guardrails

`ares_setup/guardrails.py` provides a **scope preflight** (block RFC1918 / loopback
/ link-local and cloud-metadata addresses unless an internal engagement is
explicitly authorized; match a host allowlist), a **kill-switch** sentinel file
(`~/.ares/KILL`), and a **destructive-action approval gate** (`ARES_SAFE_MODE`).

Honest scope: the preflight is meant to run at launch, and the kill-switch and
approval gate are **cooperative** mechanisms an Arès wrapper checks — they are not
(yet) a hard block wired into every individual engine tool call. Treat them as a
strong, auditable default, not an unbypassable sandbox. Hardening these into the
tool layer is on the roadmap ([`../ROADMAP.md`](../ROADMAP.md)).

## Data flow of a run

```
source ares-cascade.env
        │
        ▼
strix engine  ──►  Docker sandbox (ares-sandbox:1.3.0)   ──►  strix_runs/<run>/
 (agent swarm)      recon · exploit · validate · report        report, findings,
        │                                                        strix.log, run.json
        ▼
ares watch  ──►  confidence gate (annotate report)  ──►  ares_provenance (sign)
        │
        ▼
ares verify <run>   →   VERIFIED / INTACT / FAILED
```

## Packaging notes

[`../pyproject.toml`](../pyproject.toml) ships the toolkit (`ares_setup`,
`ares_provenance`, and the `ares_console` / `ares_watch` / `ares_demo` modules) and
registers the `ares` console command. The base dependency is just `cryptography`;
the `[engine]` extra adds the engine's third-party runtime deps (litellm, the
OpenAI Agents SDK, docker, pydantic, reportlab, …). The large, modified engine is
vendored in `ares_engine/` and used as the `strix` engine for actual scans.

## See also

- [cascade.md](cascade.md) — the per-role routing in `agents/factory.py`.
- [provenance.md](provenance.md) — the signing layer in depth.
- [`../INTEGRATION_NOTES.md`](../INTEGRATION_NOTES.md) — the real integration
  blockers and fixes that shaped these choices.
