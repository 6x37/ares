# The model cascade

No single local model is at once fast, reliable at tool-calling, and accurate at
findings. So Arès ships a **cascade**: a cheap model for breadth, a strong model
for the calls that matter, and an optional hosted model for the hardest step. Each
agent is routed to the right tier by its role.

Source: `ares_setup/cascade.py` (the tier definitions), `ares_setup/config.py`
(how a model choice becomes engine config), the engine router in
`ares_engine/strix/agents/factory.py::_ares_route_model`, and the shipped profiles
[`../ares-cascade.yaml`](../ares-cascade.yaml) / [`../ares-cascade.env`](../ares-cascade.env).

## The tiers

| Tier | Role | Default model | Context | Reasoning | Default |
|---|---|---|---|---|---|
| **triage** | recon, crawl, map, enumerate, cheap triage | `qwen3.5:latest` (fast 14B) | 49,152 | low | on |
| **validate** | confirm a vuln, build the PoC, write the report | `hf.co/OBLITERATUS/Qwen3.6-27B-OBLITERATED:Q4_K_M` (strong 27B, uncensored) | 49,152 | medium | on |
| **escalate** | the hardest calls a local model is unsure about | a hosted frontier model (configured default `anthropic/claude-sonnet-5`) | 200,000 | high | **off (opt-in)** |

Both local tiers are built at a **49,152-token context floor**, because Strix's
agent prompts (system prompt plus all tool schemas) run to ~40k tokens; anything
smaller overflows on the first real turn. The two local tiers are ordinary local
models on the **same** Ollama endpoint — only the model **name** changes between
them, so switching tiers costs nothing but a model swap.

## How routing works

Routing lives in the engine's agent factory and is driven by environment
variables. It is **off by default**: with `ARES_CASCADE` unset, every agent uses
the single `STRIX_LLM` model (upstream Strix behavior, fully backwards
compatible).

When `ARES_CASCADE` is enabled, each agent is classified by role:

- An agent is routed to the **strong (validate)** tier if it is the **root** agent
  (it coordinates strategy and decides what to spawn, so quality matters most
  there) **or** its name contains one of the decisive markers:
  `valid`, `exploit`, `poc`, `report`, `confirm`, `verif`, `inject`.
- Every other (breadth-first) agent — recon, crawl, mapping, enumeration — is
  routed to the fast **triage** tier.

Each routing decision is logged, so `ares watch` shows lines like
`Ares cascade: agent 'SQLi Validation Agent' -> openai/ares-cascade-validate-…`.

### Environment variables

The cascade profile ([`../ares-cascade.env`](../ares-cascade.env)) sets these:

| Variable | Purpose | Default |
|---|---|---|
| `ARES_CASCADE` | Master switch for per-role routing. | off (unset) |
| `ARES_CASCADE_TRIAGE` | Triage-tier model slug. | `openai/ares-cascade-triage-qwen3-5` |
| `ARES_CASCADE_VALIDATE` | Validate-tier model slug. | `openai/ares-cascade-validate-qwen3-6-27b-obliterated` |
| `ARES_CASCADE_ESCALATE` | Opt in to hosted escalation. | off (unset) |
| `ARES_CASCADE_ESCALATE_MODEL` | The hosted model for escalation. | `anthropic/claude-sonnet-5` |
| `STRIX_LLM` | The default model used when cascade is off or a role doesn't match a tier. | triage model in the cascade profile |

The tier model slugs use the derived model names Arès builds during setup (for
example `ares-cascade-triage-qwen3-5`), served through the OpenAI-compatible path
(`openai/…`), which is the routing Arès uses for reliability (see
[troubleshooting.md](troubleshooting.md#the-llm-connection-retry-storms-or-times-out)).

## The escalate tier is opt-in and off by default

Escalation exists for the honest reason that quantized local models do not
reliably drive Strix's demanding multi-agent tool protocol on the hardest steps
(see [reliability.md](reliability.md) and [`../INTEGRATION_NOTES.md`](../INTEGRATION_NOTES.md)).
But because it calls a **hosted** provider, it **leaves your machine**, so it is
disabled unless you turn it on:

```bash
# on top of the cascade profile
export ARES_CASCADE_ESCALATE=1
export ANTHROPIC_API_KEY=...          # a key for whatever hosted model you configure
```

When enabled, only the highest-stakes agents (those whose names match
`valid` / `exploit` / `report` / `confirm`) are candidates for the hosted model;
everything else stays on the local tiers.

**Honest limitation.** The current engine forces a single global `api_base` for a
run, so true *per-agent* "local for breadth, hosted for one step" routing is not
fully realized: escalate is effectively a run-level choice. In practice, with a
local `api_base`, escalate-marked agents fall back to the local strong (validate)
tier. For a genuinely hosted run, set `STRIX_LLM` to a hosted model directly — the
engine recognizes cloud-provider prefixes (e.g. `anthropic/`) and routes them to
their own hosted endpoint instead of the local one. Treat per-agent hosted
escalation as **partial** today, not a finished feature.

## What is deliberately *not* a tier

Some models are excellent security oracles but unusable as agents. The canonical
example is **WhiteRabbitNeo V3 7B**: strong security knowledge and payloads, but it
emits tool calls as raw text (`<toolcall>…</toolcall>`) instead of the structured
`tool_calls` field the agent loop needs, so it breaks the loop. It is excluded
from the cascade on purpose — use it in [`ares console`](commands.md#ares-console--streaming-local-chat)
as a knowledge oracle, never as an agent engine. This is exactly what
[`ares eval`](reliability.md#model-eval-is-this-model-usable-as-an-agent) checks
for before you commit a model to a scan.

## Choosing a profile

The cascade is one of several shipped profiles ([`../PROFILES.md`](../PROFILES.md)):

| Profile | File | Engine | Use |
|---|---|---|---|
| default | `ares.env` | Qwen3.6-27B-OBLITERATED (local) | general local runs |
| **cascade** ★ | `ares-cascade.env` | root + validate → 27B, breadth → 14B | recommended local balance |
| fast | `ares-fast.env` | qwen3.5 14B | quick, lower accuracy |
| offensive | `ares-offensive.env` | Qwen3.6-27B-OBLITERATED | slow, strong |

Source a profile before a scan (`source ares-cascade.env`), or let the hub's
"Run a scan" pick one for you.

## See also

- [reliability.md](reliability.md) — why the cascade exists: vetting a model and
  grading a run.
- [architecture.md](architecture.md) — where routing sits in the vendored engine.
- [`../ares-cascade.yaml`](../ares-cascade.yaml) — the annotated cascade definition.
