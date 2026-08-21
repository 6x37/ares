# Arès × Strix — Integration Notes & Fixes

Running Strix (the upstream engine Arès forks) end-to-end against a **local LLM**
on an Apple M4 Pro surfaced six real blockers. Each is documented here with root
cause and fix — this is the hard-won knowledge that makes Arès actually run
locally, and the raw material for write-ups.

## Environment
- Python 3.12 via `uv` (system Python stays 3.9), Strix 1.5.3, Docker Desktop.
- Local engine: Ollama, OpenAI-compatible endpoint at `http://localhost:11434/v1`.
- Sandbox image re-tagged `ares-sandbox:1.3.0`.

## The six blockers

### 1. Model "quality warning" gate
Strix warns (and in TUI, nags) that a non-frontier model "is not recommended".
**Arès change:** removed the warning, replaced with an **ethical-use disclaimer**
("authorized testing only; no liability for misuse"). Arès is model-agnostic —
"works with any LLM, local or hosted". Files: `interface/main.py`,
`interface/tui/backend/controller.py`.

### 2. LLM connection — retry storm
`ollama/<model>` routing (litellm `ollama_chat/` → native API) failed every
streamed tool call and retry-stormed. **Fix:** route through the OpenAI-compatible
path instead — `STRIX_LLM=openai/<model>` + `LLM_API_BASE=…:11434/v1`. Proven with
a direct curl (tools + streaming both work). Result: 0 retries.

### 3. Install from source broke dependencies
Installing the fork from the git clone re-resolved `openai-agents` to a build that
raised `KeyError: 'agents'` / `ModuleNotFoundError: strix.llm.warmup` (the clone's
`main` is ahead of the 1.5.3 PyPI release). **Fix:** install the clean PyPI package,
then overlay only the specific edited files — keep known-good deps.

### 4. Caido proxy never started (the deep one)
Every scan failed at turn 0: `loginAsGuest failed after N attempts` — nothing
listening on `:48080` inside the sandbox. Caido starts fine in a manual
`docker run` of the same image, but not under Strix.
**Root cause:** the installed `openai-agents` **0.19** SDK creates the sandbox with
`entrypoint=["tail"]`, overriding the image's `docker-entrypoint.sh` — the script
that launches `caido-cli`. Strix's own override targets the SDK 0.14.6 method and
is dead code on 0.19. **Fix:** stop overriding the entrypoint — pass
`command=["tail","-f","/dev/null"]` and let the image ENTRYPOINT run. Caido then
binds immediately (0 login retries).

### 5. Context overflow
First real agent turn: `request (40604 tokens) exceeds context size (19456)`.
Strix's agent prompts (system + all tool schemas) are **~40k tokens**. Our derived
model was baked at the resource-dial default (19,456) — even the dial's max (32k)
is too small. **Fix + product rule:** the Arès resource dial must guarantee a
**≥48k context floor** for Strix agents. Rebuilt the model at `num_ctx=65536`.

### 6. Local inference speed
A 27B reasoning model must ingest the ~40k-token prompt every turn — **5-10 min/turn**
on the M4 Pro, exceeding the 300s stream-idle timeout (it abandons and loops).
**Mitigations:** pre-warm the model (weights resident), raise
`STRIX_STREAM_IDLE_TIMEOUT`/`LLM_TIMEOUT` to 1800s, drop `OLLAMA_NUM_PARALLEL` to 1
(no KV-cache multiplication at large context). Turns then complete — but a full
scan is still hours on a 27B locally.

## Docker naming (Arès convention)
- Image: `ares-sandbox:1.3.0` (default via `ARES_IMAGE`/`STRIX_IMAGE`).
- Labels: `ares.managed=true`, `ares.run-id`.
- Anonymous volumes → `ares-<run>-<target>-<short-uuid>` (no bare 64-hex hashes).
- Container name: `ares-sandbox-<run>-<short-uuid>`.

## The model-quality finding (the real lesson)
Same pipeline, three engines, one deliberately-vulnerable `app.py` (SQLi + command
injection + path traversal):
- **qwen3.5 14B (fast):** completed 25 turns in minutes → but did only ~3 tool
  actions and **hallucinated** "no vulnerable code / stub print()". Fast, wrong.
- **Qwen3.6-27B-OBLITERATED:** methodical, was progressing (6+ turns) → but too slow
  to finish a full scan in a sitting.
- **WhiteRabbitNeo V3 7B (cyber-specialist):** fast and produces excellent
  security payloads (e.g. `admin'||'1=0--` for SQLi) — but emits tool calls as
  raw text (`<toolcall>{…}</toolcall>`), NOT the OpenAI `tool_calls` field the
  agent loop needs. **Not usable as a Strix agent engine** (great for the console
  though). Confirms: cyber-tuned ≠ agentic-tool-tuned.

**Conclusion:** Arès's integration is solid and produces **signed, verifiable**
reports end-to-end (which XBOW/PentestGPT don't). But model choice is decisive:
small general models hallucinate findings; big models are accurate but slow
locally. This is the concrete case for Arès's **model-cascade** (light model for
triage, strong model for validation) and for shipping **verifiable provenance** so
a report's authenticity never rests on trust.


## Refined finding: the local-agent-protocol gap (mount is NOT the issue)
Verified directly: mounting `test-target` into the sandbox exposes the **real
vulnerable `app.py`** (full Flask + sqlite3 + os + request) at
`/workspace/test-target/app.py`. So the code was genuinely available to both runs.

Yet BOTH local models drove Strix's agent loop and returned **0 findings**,
converging on the same false "no vulnerable code / stub" conclusion:
- qwen3.5 14B: ~3 tool actions in 25 turns, then confabulated a stub.
- Qwen3.6-27B-OBLITERATED: finished at turn 6 having done almost no tool work
  ("ended a turn without a lifecycle tool call"), then reported nothing.

The bottleneck is therefore NOT the mount, NOT the network, NOT context size — it
is that **quantized local models do not reliably execute Strix's demanding
multi-agent tool protocol**. They can answer a security question perfectly in the
console, but they don't methodically run read → test → validate → report as
autonomous agents. This is the real ceiling for local autonomous pentesting today,
and the strongest argument for: (a) the hosted **escalate** tier in the cascade,
(b) Arès-tuned, shorter agent prompts for local models, and (c) verifiable
provenance so an empty/"no findings" report can be told apart from a real one.
