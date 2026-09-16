# Troubleshooting

Practical fixes for the issues you are most likely to hit running Arès locally.
Most of these come from real blockers documented in
[`../INTEGRATION_NOTES.md`](../INTEGRATION_NOTES.md) — that file has the full root
causes; this page is the quick reference.

## Ollama isn't detected or reachable

**Symptoms:** `ares init` stops with "Ollama is not installed" or "installed but
not running"; `ares console` / `ares eval` error out reaching the model.

**Fixes:**

```bash
# install Ollama
#   macOS:  brew install ollama   (or https://ollama.com/download)
#   Linux:  curl -fsSL https://ollama.com/install.sh | sh

ollama serve          # start the daemon
ollama list           # confirm it responds and shows your models
```

Arès talks to Ollama's **OpenAI-compatible** endpoint (default
`http://localhost:11434/v1`). If you moved Ollama to another host/port, pass it
through `ares init --endpoint http://host:port` (which writes `LLM_API_BASE`), or
edit `LLM_API_BASE` in your `ares.env`.

## The LLM connection retry-storms or times out

**Symptom:** streamed tool calls fail repeatedly and the run appears to loop or
retry-storm.

**Cause & fix:** the native Ollama routing (`ollama_chat/…`, litellm's native API
path) failed every streamed tool call in testing. Arès routes through the
**OpenAI-compatible** path instead. A working profile has:

```bash
export STRIX_LLM="openai/ares-<model>"          # openai/ prefix, NOT ollama/
export LLM_API_BASE="http://localhost:11434/v1" # note the /v1
export LLM_API_KEY="ollama-local"               # dummy key litellm needs
```

`ares init` writes this for you. If you hand-edited a profile, make sure
`STRIX_LLM` uses the `openai/` prefix and `LLM_API_BASE` ends in `/v1`. You can
sanity-check the endpoint independently:

```bash
curl -s http://localhost:11434/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"<your-model>","messages":[{"role":"user","content":"say ready"}]}'
```

## Context window too small

**Symptom:** the first real agent turn dies with something like
`request (40604 tokens) exceeds context size (19456)`.

**Cause:** Strix's agent prompts (system prompt + all tool schemas) are ~40k
tokens. A model built at a small default context overflows immediately.

**Fix:** Arès **bakes a 49,152-token context floor** into every derived model, so
re-running the guided setup fixes this:

```bash
ares init            # bakes num_ctx >= 49152 into the derived Ollama model
```

If you built a model by hand, rebuild it with `num_ctx` at 49,152 or more. Note
that the resource dial's own maximum context target (32k) is below the Strix floor
on purpose — `config.py` raises it to 49,152 when it bakes the model, so the floor
always wins regardless of dial level.

## Docker or the Caido proxy won't start

**Symptom:** every scan fails at turn 0 with `loginAsGuest failed after N
attempts`, or nothing is listening on the proxy port inside the sandbox.

**Checks & fixes:**

- **Docker must be running.** Real scans execute inside a sandbox container; start
  Docker Desktop / the daemon first. (The `ares demo` replay does not need Docker.)
- **Use the Arès sandbox image.** The default is `ares-sandbox:1.3.0`, selected via
  `ARES_IMAGE` / `STRIX_IMAGE`. Make sure that image exists locally; the engine's
  image pull is tolerant of local-only tags so it won't hard-abort on them.
- **The Caido root cause (already fixed in the vendored engine):** a newer Agents
  SDK created the sandbox with `entrypoint=["tail"]`, which overrode the image's
  own entrypoint — the script that launches `caido-cli`. Arès stops overriding the
  entrypoint (passes `command=["tail","-f","/dev/null"]` and lets the image
  ENTRYPOINT run) and raised Caido readiness attempts from 10 to 30. If you still
  see Caido failures, inspect the sandbox container's logs:

```bash
docker ps -a --filter label=ares.managed=true
docker logs <ares-sandbox-container>
```

Arès names its Docker objects `ares-*` and labels them `ares.managed=true` /
`ares.run-id`, which makes them easy to find and clean up.

## Inference is very slow

**Symptom:** on a laptop, a strong (e.g. 27B) reasoning model takes several minutes
per turn — enough to exceed a stream-idle timeout, after which the run abandons the
turn and loops.

**Mitigations** (the generated profiles already apply the first two):

- **Generous timeouts.** `STRIX_STREAM_IDLE_TIMEOUT` and `LLM_TIMEOUT` are raised
  (e.g. to 1800s) so a slow turn isn't cut off mid-generation.
- **`OLLAMA_NUM_PARALLEL=1`** for large-context models, so concurrent requests
  don't multiply the KV cache.
- **Pre-warm the model** so its weights are resident before the scan starts.
- **Use the [cascade](cascade.md)** — keep the strong model for the decisive
  validation/report calls and let a fast model handle breadth — or drop to a
  smaller model or a lower `ares init --level`.

Be realistic: even with all of this, a full scan with a 27B model **locally** can
take hours. That trade-off (privacy and no API cost, at the price of speed) is the
honest core of local-first; the cascade and the opt-in escalate tier exist to
soften it.

## A scan returns 0 findings on code you know is vulnerable

This is the most important failure mode to understand, and it is usually **not** a
bug in Arès.

**What's happening:** quantized local models do not reliably execute Strix's
demanding multi-agent tool protocol. In testing, both local models drove the agent
loop and returned 0 findings on an obviously vulnerable target — converging on a
false "no vulnerable code / stub" conclusion — even though the code was genuinely
mounted and readable. The bottleneck was **not** the mount, the network, or the
context size; the models simply did not methodically run read → test → validate →
report as autonomous agents. A model can answer the same security question
perfectly in `ares console` and still fail as an agent.

**What to do:**

1. **Read the confidence verdict.** `ares watch` runs it automatically; or:

   ```bash
   ares confidence strix_runs/<run>
   ```

   A 🔴 **LOW** verdict means the agents did little real work — **re-run with a
   stronger model**. It does **not** mean the target is clean. (See
   [reliability.md](reliability.md#what-a-low-verdict-means-and-does-not).)

2. **Vet the model first.** Before committing to a scan:

   ```bash
   ares eval <model>          # must be STRIX-READY (structured tool-calling)
   ```

   A model that fails the tool-calling probe cannot drive the loop at all,
   whatever its security knowledge.

3. **Use the cascade or a stronger validation model** ([cascade.md](cascade.md)),
   and consider the opt-in escalate tier for the hardest calls.

4. **Keep local-reinforcement on** (`ARES_LOCAL_REINFORCE=1`, the default) — it
   instructs agents to read every in-scope file and attempt a concrete test before
   ever concluding "no vulnerabilities".

Never treat a LOW "0 findings" run as evidence a target is secure.

## `ares verify` says `INTACT` instead of `VERIFIED`

`INTACT` means the signature is valid and nothing was modified, but **no trust
anchor was available** to confirm *whose* key signed it. To get `VERIFIED`, the
signing key must be in your trust set:

- For **official Arès** reports, make sure the release key is on disk — it ships at
  [`../keys/ares-release.pub.pem`](../keys/ares-release.pub.pem) (fingerprint
  `ARES-2BC4-652E-E25F-6414`) and is trusted automatically from a repo checkout.
- For **your own** reports, sign with the key in `~/.ares/keys/` (create it with
  `ares keygen`); it's trusted automatically on your machine.
- To trust **someone else's** key, drop their `*.pem` in `~/.ares/trusted/`, or pin
  it for one check: `ares verify <run> --pubkey their.pub.pem`.

Full model in [provenance.md](provenance.md#the-three-verdicts).

## `ares verify` says `FAILED`

The report is not verifiable as genuine. The output lists why: an invalid
signature, a signer key that is present in your trust set's context but **not**
trusted (an untrusted re-sign), tampered content, a signed file now missing, or an
unsigned extra file. If you did not expect a change, treat the report as
untrustworthy. See [provenance.md](provenance.md#the-three-verdicts).

## Confirming a profile is actually offline

If you need to be sure a profile won't reach the network:

```bash
ares offline ares.env        # audits telemetry, web search, and the LLM endpoint/provider
```

It exits non-zero and lists blockers if egress is possible. Remember this is
config-level; for a hard air-gap also isolate the sandbox's network (see
[architecture.md](architecture.md#offline-and-air-gapped-mode)).

## See also

- [reliability.md](reliability.md) — the honesty tools these symptoms motivate.
- [getting-started.md](getting-started.md) — prerequisites and first run.
- [`../INTEGRATION_NOTES.md`](../INTEGRATION_NOTES.md) — full root-cause writeups.
