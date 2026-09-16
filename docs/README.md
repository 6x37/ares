# Arès documentation

**Arès** is a local-first, verifiable, autonomous AI pentester — a hard-fork of
[Strix](https://github.com/usestrix/strix) (© 2025 OmniSecure Inc., Apache-2.0).
Strix supplies the multi-agent engine; Arès rebuilds the layer around it for
**privacy, trust, and reliability**: it runs on your own machine, signs every
report, and tells you when a run should not be trusted.

This folder documents what Arès actually does today. It is written to be honest:
where a capability is partial, opt-in, or off by default, the docs say so.

## Contents

| Doc | What it covers |
|---|---|
| [getting-started.md](getting-started.md) | Prerequisites (Python 3.12+, Ollama, Docker), install, guided `ares init`, and a first `ares demo`. |
| [commands.md](commands.md) | Reference for every `ares` subcommand — init, dashboard, eval, console, demo, watch, verify (plus confidence, offline, sign, keygen) — and the interactive hub. |
| [provenance.md](provenance.md) | The Ed25519 signing and verification model: the artifact manifest, the `VERIFIED` / `INTACT` / `FAILED` verdicts, key fingerprints, and the default trust set. |
| [cascade.md](cascade.md) | The model cascade: triage / validate / escalate tiers, per-agent-role routing, and why escalate (hosted) is opt-in and off by default. |
| [reliability.md](reliability.md) | The honesty layer: model-eval (can a model drive the agent loop?) and the confidence gate (HIGH / OK / LOW), and why a LOW run is "re-run stronger", not "the target is clean". |
| [architecture.md](architecture.md) | The three layers (`ares_setup/`, `ares_provenance/`, `ares_engine/`), how Arès wraps Strix, local-first routing through Ollama, and offline mode. |
| [troubleshooting.md](troubleshooting.md) | Common issues and fixes: Ollama/LLM connection, context-window sizing, Docker/Caido startup, slow inference, and 0-findings (model-quality) situations. |

## The honest pitch (in one paragraph)

Local models are chosen for **privacy**, not maximum precision. A small model can
answer a security question well yet miss or hallucinate a finding when driving an
autonomous agent loop. So Arès does not ask you to trust the model: it **grades
every run** (a 🔴 LOW verdict means "re-run stronger", not "the target is clean"),
**signs every report** (authenticity never rests on trust), and can **escalate**
the hardest calls to a stronger model — locally by default, cloud only if you opt
in. Signing proves a report's **integrity and authenticity**, not that the
findings inside it are correct.

## See also (repo root)

- [`../README.md`](../README.md) — project overview and quickstart.
- [`../INTEGRATION_NOTES.md`](../INTEGRATION_NOTES.md) — the real blockers hit
  running Strix against a local LLM, with root causes and fixes.
- [`../ares_engine/VENDORED.md`](../ares_engine/VENDORED.md) — the exact engine
  diff versus upstream Strix.
- [`../PROFILES.md`](../PROFILES.md) — the shipped engine profiles.
- [`../ROADMAP.md`](../ROADMAP.md) — what is shipped versus planned.

## Credit

Arès is a derivative work of **Strix** — the open-source multi-agent AI pentester
by OmniSecure. The agent swarm, tools, and vulnerability coverage are Strix's. The
name "Strix" is used only to describe the origin of this work, per Apache-2.0 §4.
See [`../NOTICE`](../NOTICE).
