# Changelog

## 0.1.0 — initial
First public cut of Arès, a local-first, verifiable hard-fork of Strix v1.5.3.

- Local-first: guided `ares init`, resource dial, offline/air-gap mode.
- Verifiable provenance: Ed25519-signed reports; `ares verify` (INTACT vs VERIFIED).
- Reliability: model-eval (STRIX-READY), confidence gate (HIGH/OK/LOW), local reinforcement.
- Model cascade: per-agent-role routing (triage / validate / opt-in escalate).
- Guardrails: scope allowlist, SSRF/private-IP block, kill-switch, safe-mode gates.
- Docker: `ares-*` naming, entrypoint & Caido reliability fixes.
- Tooling: interactive hub, dashboard, streaming console, live watch, 45s demo.
- Fork hygiene: vendored engine + `update.sh` upstream-sync with conflict reporting.
