# Arès

Local-first, **verifiable** autonomous AI pentester — a hard-fork of
[Strix](https://github.com/usestrix/strix) (Apache-2.0).

What Arès adds over Strix:
- 🔒 **Signed & verifiable reports** — every finding is cryptographically signed (Ed25519).
- 🏠 **Local-first** — guided local-LLM setup, runs fully offline.
- 🛡️ **Safety guardrails** — scope enforcement + human approval gates (roadmap).

See [ROADMAP.md](ROADMAP.md) for the full differentiation plan.

## `ares watch` — live A-to-Z visibility

Run alongside a scan to see the agent swarm work in real time — every agent
spawn, tool action and finding, then the report being generated and signed:

```bash
python3 ares_watch.py            # auto-detect the latest run under ./strix_runs
python3 ares_watch.py --follow   # keep tailing after completion
```

Colour-codes each agent, streams findings as they land (severity-coloured), and
on completion shows the report generation + Ed25519 signature.

## Honest positioning — local ≠ frontier accuracy

Arès is **local-first: private, offline, no API cost, no data leaving your machine.**
That is its point. But be clear-eyed about the trade-off learned from real runs:

- **Local models are for privacy and offline work, not maximum precision.** Small
  quantized models can answer security questions well yet miss or hallucinate
  findings when driving an autonomous agent loop.
- For **high-stakes accuracy**, enable the hosted **escalate** tier (frontier model
  on the validation agents only) — or at minimum, trust the **confidence gate**:
  a 🔴 LOW result means "re-run stronger", not "the target is clean".
- Every report is **signed and verifiable**, so its authenticity never rests on
  trusting the model — you can always tell a real result from a bailed one.

## Demo mode — show it in 45 seconds

```bash
ares demo
```
Replays a full OWASP Juice Shop engagement through the real Arès watch console:
live agent swarm with cascade routing, findings landing as they're validated,
then confidence gate → Ed25519 signature → verify. Scripted for speed (no LLM/
cloud) — it showcases the pipeline and UX, not a live autonomous scan.

## Just run `ares`

One interactive hub — banner, live status, and every tool in one place:

```bash
ares            # opens the hub (dashboard, setup, eval, console, run, watch…)
ares dashboard  # or jump straight to any tool
ares eval qwen3.5:latest
ares console
```

Install the shortcut once: `alias ares="/Users/z/Desktop/ares/ares"` in your shell rc.

## Dashboard — hardware + models at a glance

```bash
python3 -m ares_setup.dashboard          # hardware + local model catalog
python3 -m ares_setup.dashboard --eval   # + live STRIX-READY badges per model
```

One boxed view: your hardware (usable memory, GPU), every local model with a fit
indicator, and — with `--eval` — whether each is actually usable as a Strix agent.

## Reliability tools (from the real-run findings)

```bash
# Is a model actually usable as a Strix agent? (tool-calling is the blocker)
python3 -m ares_setup.model_eval ares-cascade-triage-qwen3-5

# Can you trust a finished scan's result? (real "clean" vs a bailed/empty report)
python3 -m ares_setup.confidence strix_runs/<run> --annotate
```

- `model_eval` scores tool-calling, vuln recall and speed → **STRIX-READY** or not.
- `confidence` marks a run 🟢HIGH / 🟡OK / 🔴LOW from what the agents actually did;
  `ares_watch` annotates it into the report **before signing**, so a bailed
  "0 findings" can't masquerade as a clean result.
- Local agents also get a mandatory "read + test before concluding" directive
  (`ARES_LOCAL_REINFORCE`, on by default) to counter the bailing seen in testing.

## Profiles — standard + offensive

Arès runs two engine profiles side by side:

| profile | env file | model | use |
|---|---|---|---|
| `default` | `ares.env` | Qwen3.6 (standard) | best general quality |
| `offensive` | `ares-offensive.env` | Qwen3.6-27B **OBLITERATED** | uncensored, no refusals |

```bash
python3 -m ares_setup --profile offensive --model hf.co/OBLITERATUS/Qwen3.6-27B-OBLITERATED:Q4_K_M -y
python3 ares_console.py --profile offensive          # launch on the offensive engine
# or switch live inside the console:  /profile offensive
```

## `ares_console.py` — the branded local console

A zero-dependency, streaming terminal UI for talking to the local engine:
fire-gradient banner, an air-gapped status badge, a thinking spinner, and a
live typewriter answer straight from Ollama.

```bash
python3 ares_console.py                 # interactive REPL
python3 ares_console.py --once "First recon step for a web pentest?"
```

## `ares init` — guided local setup (shipped)

Zero-config local LLM setup. Detects your hardware, recommends and pulls a model,
and bakes your chosen resource level into a ready-to-run config.

```bash
# see the plan for your machine without changing anything
python3 -m ares_setup --dry-run

# set up on the recommended model at full power
python3 -m ares_setup --level max -y

# then run Arès fully local, no API cost
source ares.env
strix --target ./your-app
```

### Air-gapped mode

```bash
python3 -m ares_setup --offline --level balanced -y   # zero-egress config
python3 -m ares_setup.offline ares.env                # independently audit any env
```

`--offline` disables telemetry, empties the web-search key, and refuses any
non-local model — the audit **blocks** a cloud config. For a kernel-enforced air
gap, run the Strix container with `--network none` (printed by the wizard).

The **resource dial** (`--level eco|balanced|max` or `0-100`) maps to context
size, parallel agents, GPU offload and reasoning effort — all capped to your free
memory, and baked into a derived Ollama model so the settings actually apply.

## `ares-provenance` — signed, verifiable reports (shipped)

```bash
# 1. one-time: create your Arès signing key (keep the private key secret)
python3 -m ares_provenance keygen

# 2. sign a finished scan directory
python3 -m ares_provenance sign ./run-2026-08-21 --model qwen3.6-27b-obliterated --local

# 3. anyone can verify authenticity + integrity
python3 -m ares_provenance verify ./run-2026-08-21
```

Verify exits `0` if authentic, `1` if tampered/forged — CI-friendly.

**Guarantee:** we don't claim the marker can't be *removed* (no local file can).
We guarantee it can't be removed or altered **and still pass verification** —
tampering is always detectable, forging requires the private key.

## Dev

```bash
python3 -m pytest tests/ -v
```

## License
Fork of Strix © OmniSecure Inc. (2025), Apache-2.0. Attribution retained.
