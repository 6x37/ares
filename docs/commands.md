# Command reference

Every command below is grounded in the actual code: the `ares` launcher script
(repo root), the interactive hub in `ares_setup/home.py`, and each module's own
CLI. Where a command is a thin dispatch to a Python module, the exact `python3`
form is shown too — that form always works from the repo, regardless of which
`ares` is on your `PATH` (see the note below).

## The two `ares` entry points

- **Launcher script** (`./ares`, repo root) — a small bash dispatcher. It maps
  `ares <subcommand>` to the right module. This is the interface the rest of this
  page documents.
- **Console command** (`ares`, installed by `pip`) — the `[project.scripts]` entry
  `ares = ares_setup.home:home`. It opens the **interactive hub** and does not
  parse subcommands.

If `ares <subcommand>` opens the hub instead of running the subcommand, you are
using the console entry. Use `./ares <subcommand>` from the repo, or the `python3`
form listed for each command.

The launcher recognizes: `home`/`hub`, `dashboard`/`dash`, `init`, `eval`,
`confidence`/`conf`, `offline`, `console`/`chat`, `demo`, `watch`,
`sign`/`verify`/`keygen`, and `help`.

---

## `ares` — interactive hub

```bash
ares                 # (launcher: `ares home`; module: python3 -m ares_setup.home)
```

Opens a full-screen menu that reaches every tool. It shows a live status line
(detected chip, usable inference memory, whether Ollama is running and how many
models are installed) and the default engine profile, then this menu:

| Key | Item | Action |
|---|---|---|
| 1 | Dashboard | hardware + local model catalog |
| 2 | Setup | guided local-LLM install (`ares init`) |
| 3 | Eval a model | live STRIX-READY test of a model |
| 4 | Console | chat with the local engine |
| 5 | Run a scan | launch a pentest on a target |
| 6 | Watch | live agent activity of a running scan |
| 7 | Confidence | trust score of a finished scan |
| 8 | Verify report | check an Arès signature |
| 9 | Profiles | list engine profiles & cascade |
| q | Quit | |

"Run a scan" (item 5) prompts for a target, a profile (`cascade` ★, `fast`, or
`offensive`), and a max-turns count, then sources the matching `ares-*.env` and
runs the `strix` engine. It parses the env file itself and passes the target as
argv (no shell), so a target string cannot inject a command.

---

## `ares init` — guided local-LLM setup

```bash
ares init [options]          # module: python3 -m ares_setup
```

Detects hardware → checks Ollama → recommends a model → resolves the resource dial
→ pulls the model if needed → bakes a derived Ollama model with the dial settings
→ writes an env file → prints how to run. Fully scriptable for CI.

| Flag | Default | Meaning |
|---|---|---|
| `--model <tag>` | recommend for your hardware | Ollama base tag to use. An unknown tag is accepted as a raw base. |
| `--level <lvl>` | `balanced` | Resource dial: `eco` \| `balanced` \| `max`, or a number `0`–`100`. |
| `--endpoint <url>` | `http://localhost:11434` | Ollama endpoint. |
| `--profile <name>` | `default` | Named profile: `default` → `ares.env`, others → `ares-<name>.env`. |
| `--env-path <path>` | derived from `--profile` | Write the env file to an explicit path instead. |
| `-y`, `--yes` | off | Accept the recommended model without prompting. |
| `--dry-run` | off | Show the full plan without pulling, creating, or writing anything. |
| `--standard-model` | off | Do **not** prefer uncensored/abliterated models. |
| `--offline` | off | Air-gapped mode: disable telemetry and web search, require a local model, refuse any cloud egress. Aborts if it cannot guarantee offline. |

The resource dial maps one level to concrete knobs — context window, parallel
agents (`OLLAMA_NUM_PARALLEL`), GPU layers, reasoning effort, and a per-turn
tool-call cap — each capped against your machine's free memory. The derived model
is always built with at least a 49,152-token context (Strix's prompts are ~40k),
even at a low dial level.

---

## `ares dashboard` — hardware + model catalog

```bash
ares dashboard               # module: python3 -m ares_setup.dashboard
ares dashboard --eval        # also run a live tool-calling probe on installed, fitting models
```

Prints one boxed view: your chip/OS/arch, usable inference memory versus total
RAM, GPU type, Ollama runtime status, and a catalog of curated local models with
fit indicators (`✓ fits` / `✗ too big`, `● installed` / `○ available`, and a `★`
on the recommended one). With `--eval`, each installed model that fits is probed
live for structured tool-calling and badged `STRIX-READY` or `no-tools`.

`--eval` runs the same tool-calling probe as `ares eval`; see
[reliability.md](reliability.md#model-eval-is-this-model-usable-as-an-agent).

---

## `ares eval <model>` — is this model usable as an agent?

```bash
ares eval qwen3.5:latest                 # module: python3 -m ares_setup.model_eval qwen3.5:latest
ares eval qwen3.5:latest mistral:latest  # evaluate several
ares eval qwen3.5:latest --plain         # non-animated, plain-text report
```

Probes a model on the three things that decide agent fitness:

1. **Structured tool-calling** — does it emit OpenAI `tool_calls`, not tool calls
   as free text? This is the **blocker**: pass it and the model is `STRIX-READY`;
   fail it and the agent loop cannot parse the model, whatever else it knows.
2. **Vulnerability recall** — shown obviously vulnerable code, does it name the
   bug classes (SQL / command injection / path traversal)? Quality signal.
3. **Speed** — prompt-eval throughput, to predict per-turn latency.

Only tool-calling gates the `STRIX-READY` verdict; recall and speed are reported
for context. Arguments that are not installed Ollama models are ignored (so a
stray shell token like a `#` comment is skipped). Exit code is `0` only if every
evaluated model is `STRIX-READY`.

---

## `ares console` — streaming local chat

```bash
ares console                       # module: python3 ares_console.py
ares console --once "explain CSRF" # one-shot, print and exit
ares console --profile offensive   # load ares-offensive.env instead of ares.env
```

A branded, stdlib-only REPL that streams tokens from Ollama's OpenAI-compatible
endpoint, with a spinner while a reasoning model thinks. This is the right place
for a model that is great at security knowledge but not usable as an agent (for
example one that emits tool calls as text — see [cascade.md](cascade.md#what-is-deliberately-not-a-tier)).

| Flag | Meaning |
|---|---|
| `--once <prompt>` | Send one prompt, print the answer, exit. |
| `--env <path>` | Load a specific env file. |
| `--profile <name>` | Load `ares.env` (`default`) or `ares-<name>.env`. |
| `--no-color` | Disable ANSI styling. |

Slash-commands inside the REPL include: `/help`, `/status`, `/offline` (audit the
loaded env for egress), `/model [tag]`, `/think` (toggle showing reasoning),
`/verify <dir>`, `/sign <dir>`, `/profile <name>`, `/save <file>`, `/clear`,
`/quit`.

---

## `ares demo` — 45-second scripted showcase

```bash
ares demo                    # module: python3 ares_demo.py
```

Replays a realistic OWASP Juice Shop engagement through the real `ares watch`
console: live agent feed with cascade routing shown, three findings landing as
cards, then report → confidence gate → Ed25519 signature. It runs in seconds with
**no LLM and no cloud**, writing a signed run to `strix_runs/_demo_live/`.

It is a **scripted replay to show the pipeline and UX — not a live scan**. The
optional env var `ARES_DEMO_URL` adds a shareable web-report link to the printed
output; unset, everything stays local.

---

## `ares watch` — live agent activity

```bash
ares watch                             # module: python3 ares_watch.py; auto-detects the latest run
ares watch --run strix_runs/my-run     # watch a specific run
ares watch --follow                    # keep tailing after completion
ares watch --no-sign                   # do not auto-sign on completion
ares watch --poll 0.4                  # polling interval in seconds (default 0.7)
```

Runs alongside a scan and tails what the engine writes to `strix_runs/<run>/`:
`strix.log` (per-agent lifecycle + tool activity, color-coded), `vulnerabilities.json`
(findings shown the moment they land), and `run.json` (status). When the run
reaches a terminal status, watch waits for the report, runs the **confidence gate**
and annotates the report with the verdict, then **signs** the run with
`ares_provenance` (unless `--no-sign`). So the whole chain — recon → exploit →
report → confidence → signature — is visible in one console.

---

## `ares verify <run>` — check a report's signature

```bash
ares verify strix_runs/my-run                 # module: python3 -m ares_provenance verify <run>
ares verify strix_runs/my-run --pubkey k.pem  # additionally pin an expected public key
ares --key-dir ~/.ares/keys verify <run>      # the launcher passes global flags through
```

Verifies the Ed25519 signature over the run's artifact manifest, re-hashes every
signed artifact, and checks nothing was dropped or added. It prints one of three
verdicts — `VERIFIED`, `INTACT`, or `FAILED` — and exits `0` only when the result
is trustworthy. The precise meaning of each verdict, the default trust set, and
key pinning are covered in [provenance.md](provenance.md).

---

## `ares sign <run>` — sign a run

```bash
ares sign strix_runs/my-run                        # module: python3 -m ares_provenance sign <run>
ares sign strix_runs/my-run --model qwen3.6-27b    # record which engine produced it
ares sign strix_runs/my-run --local                # mark the scan as locally executed
```

Builds the signed manifest (`ares.provenance.json`) over the run's artifacts and
injects a verifiable footer into `penetration_test_report.md`. `ares watch` and
`ares demo` sign automatically, so you rarely call this by hand. Signing uses the
private key in `--key-dir` (default `~/.ares/keys/`); create one with `ares keygen`.

| Flag | Meaning |
|---|---|
| `--model <name>` | Record the engine model in the provenance. |
| `--local` | Mark the run as locally executed. |
| `--key-dir <dir>` | Directory holding the signing keypair (global flag). |

---

## `ares keygen` — create a signing keypair

```bash
ares keygen                          # module: python3 -m ares_provenance keygen
ares --key-dir ~/.ares/keys keygen   # choose the key directory (default ~/.ares/keys)
```

Generates an Ed25519 keypair, writes the private key (`0600`) and public key as
PEM, and prints the public-key **fingerprint** (`ARES-XXXX-XXXX-XXXX-XXXX`).
Keep the private key secret; distribute the public key and fingerprint so anyone
can verify your reports. See [provenance.md](provenance.md#keys-and-fingerprints).

---

## `ares offline <env>` — air-gap audit

```bash
ares offline ares.env        # module: python3 -m ares_setup.offline ares.env
```

Audits an env file for outbound egress risk: it checks that the LLM endpoint is
loopback/private, that `STRIX_LLM` is not a cloud provider, that telemetry is off,
and that no cloud API-key variables are set. It prints each passed check, each
auto-fixable warning, and each hard blocker, and exits non-zero if egress is
possible. This is **config-level** enforcement, not a firewall — for a hard
air-gap, run the sandbox with no external network. See
[architecture.md](architecture.md#offline-and-air-gapped-mode).

---

## `ares confidence <run>` — trust score of a finished scan

```bash
ares confidence strix_runs/my-run              # module: python3 -m ares_setup.confidence <run>
ares confidence strix_runs/my-run --annotate   # also append the assessment to the report
```

Grades a finished run 🟢 HIGH / 🟡 OK / 🔴 LOW based on what the agents actually
did — findings, tool actions, files read, turns, and give-up signals — so a bailed
empty report cannot pass as a real "clean". `ares watch` runs this automatically
before signing. Exit code is non-zero on a LOW verdict. Full semantics in
[reliability.md](reliability.md#the-confidence-gate-high--ok--low).

---

## `ares help`

```bash
ares help                    # or: ares -h / ares --help
```

Prints the launcher's short usage summary.

---

## Related modules without a launcher alias

These are part of the product (`ares_setup/`) but are invoked directly with
`python3 -m`, not through the `ares` launcher:

```bash
python3 -m ares_setup.compliance <run>          # map findings to PCI-DSS / ISO 27001 / SOC 2 / NIST CSF
python3 -m ares_setup.diff <old_run> <new_run>  # what's new / fixed / still present between two runs
python3 -m ares_setup.guardrails check <target> [--internal]   # scope preflight (allowlist, private/metadata IP block)
python3 -m ares_setup.guardrails kill | resume  # arm / clear the kill-switch sentinel (~/.ares/KILL)
```

The guardrails module provides a scope preflight, a kill-switch sentinel file, and
a destructive-action approval gate (`ARES_SAFE_MODE`). These are **cooperative**
mechanisms an Arès wrapper checks, not a hard block wired into every engine tool
call — described honestly in [architecture.md](architecture.md#guardrails).
