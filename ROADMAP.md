# Arès — Roadmap & Differentiation

> Arès is a hard-fork of [Strix](https://github.com/usestrix/strix) (Apache-2.0),
> an autonomous multi-agent AI pentester. Arès keeps Strix's agent swarm and adds
> a **local-first, verifiable, safety-guardrailed** experience.

## Positioning (grounded in the 2026 market)

| Tool | Model | Local LLM | Signed/verifiable reports | Safety guardrails | License |
|------|-------|-----------|---------------------------|-------------------|---------|
| **XBOW** | cloud, closed | ❌ | ❌ | n/a | commercial |
| **PentestGPT** | local capable | ✅ (raw) | ❌ | ❌ | open |
| **Strix** | cloud/local via litellm | ⚠️ possible, no UX | ❌ | partial (scope) | Apache-2.0 |
| **Arès** | **local-first** | ✅ **guided + optimized** | ✅ **Ed25519 signed** | ✅ **scope + approval gates** | Apache-2.0 |

The white space: **trust & reproducibility**. Research (e.g. the 400-run LLM-pentest
consistency study) shows autonomous agents are inconsistent and hard to audit.
Nobody in open source ships **cryptographically verifiable** pentest output. Arès does.

---

## Tier 0 & Tier-1 core — SHIPPED ✅

### Verifiable provenance (`ares_provenance/`)
Every scan run is signed with an Ed25519 key. `ares-provenance verify <run>` proves:
- **Authenticity** — only the Arès private key can produce a valid signature.
- **Integrity** — every artifact's SHA-256 is in the signed manifest; one edited byte fails verification.
- **Completeness** — dropped or injected files are detected.
- **Provenance of engine** — records which local model produced the report.

Detects all four attack classes (content edit, marker removal, file drop/inject,
forged re-sign). 7/7 tests pass. This is the honest version of "the Arès marker
can't be faked" — not "can't be removed", but "can't be removed and still look genuine".

---

## Tier 1 — Quick wins (high impact, low effort)

1. **`ares init` — guided local-LLM installer.** ✅ **SHIPPED** — `ares_setup/`.
   Detects RAM/GPU/Apple-Silicon → recommends a model (prefers installed +
   uncensored-for-offense) → pulls via Ollama → **bakes a derived model** with the
   dial params → writes `ares.env`. Verified end-to-end on Apple M4 Pro / 48 GB.

2. **Resource dial (the "% power" idea, done right).** ✅ **SHIPPED** — `ares_setup/dial.py`.
   One `eco|balanced|max` (or 0-100) level maps to real knobs: context window,
   parallel agents (`OLLAMA_NUM_PARALLEL`), GPU layers (`num_gpu`), reasoning
   effort, per-turn tool-call cap — all capped against actual free memory. The
   settings are *baked into a derived Ollama model*, so they genuinely apply.

3. **Air-gapped / zero-telemetry mode.** ✅ **SHIPPED** — `ares_setup/offline.py`.
   `--offline` closes Strix's three egress channels: telemetry (`STRIX_TELEMETRY=0`),
   web_search (empties `PERPLEXITY_API_KEY`), and the LLM (refuses any non-local
   model/endpoint). An independent `python3 -m ares_setup.offline <env>` audit
   blocks cloud configs. Honest scope: config-level enforcement; documents the
   `docker --network none` hard air-gap for kernel-level isolation.

## Tier 2 — Flagship differentiators

4. **Scope guardrails + kill-switch.** Hard target allowlist enforced at the tool
   layer (not just prompt-level): block RFC1918/metadata IPs unless explicitly in
   scope, refuse out-of-scope hosts, global stop. The swarm *cannot* wander off
   scope — a legal/safety moat autonomous tools badly need.

5. **Human-in-the-loop approval gates.** `--safe-mode` pauses before destructive or
   exploit-sending actions and asks for approval. Bridges "fully autonomous" and
   "auditable", which regulated buyers require.

6. **Model cascade (cost/quality router).** Cheap local model does recon/triage;
   escalate a hard exploit-validation step to a bigger local model (or, opt-in, a
   cloud model) only when confidence is low. Best of both without paying per agent.

7. **Signed + replayable audit trail.** Record every agent action deterministically;
   `ares replay <run>` re-plays the engagement. Combined with Tier-0 signing =
   court/audit-admissible evidence. Directly answers the reproducibility research gap.

8. **Compliance mapping.** Auto-map findings to PCI-DSS, ISO 27001:2022, SOC 2,
   NIST CSF 2.0 and emit auditor-ready evidence. (Leverages existing GRC playbooks.)

## Tier 3 — Moonshots

9. **Diff / regression mode.** "What's new since last scan" across signed runs —
   track fixes and regressions over time.
10. **Local RAG over past engagements.** Arès learns from your own prior findings,
    fully offline.
11. **Public XBOW-style benchmark harness.** Measure Arès on standardized challenges
    so every capability claim is backed by a reproducible score (also great content).

---

## Suggested first public milestone (for launch/LinkedIn)
Ship **Tier 0 (done) + Tier 1** and demo: *"An autonomous AI pentester that runs
100% offline on your own machine and signs every report so findings can't be
silently forged."* That single sentence is the differentiator neither XBOW nor
PentestGPT can claim.

## Attribution / license
Fork of Strix (© OmniSecure Inc., 2025, Apache-2.0). `LICENSE` and `NOTICE`
retained; modified files marked per Apache-2.0 §4. "Strix" used only to describe origin.
