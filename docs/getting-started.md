# Getting started

This walks you from a clean machine to a first end-to-end demo. It is grounded in
the repo's [`../README.md`](../README.md) and the setup code in `ares_setup/`.

## Prerequisites

| Requirement | Why | Notes |
|---|---|---|
| **Python 3.12+** | Arès and the vendored engine require it (`requires-python = ">=3.12"` in [`../pyproject.toml`](../pyproject.toml)). | On macOS, a `uv`-managed 3.12 works well even if the system Python is older. |
| **[Ollama](https://ollama.com)** | Serves your local model over an OpenAI-compatible endpoint at `http://localhost:11434/v1`. | `ares init` detects it and pulls a model for you. |
| **Docker** | Strix runs each scan inside a sandbox container. | Required to run real scans; the `ares demo` replay does **not** need it. |

`ares init` itself drives Ollama (detect, pull, build a derived model). Docker is
needed when you launch an actual scan, because the engine executes tools inside a
sandbox container.

## Install

```bash
# clone and install the toolkit + the engine's runtime dependencies
git clone https://github.com/6x37/ares && cd ares
pip install -e ".[engine]"          # or: uv pip install -e ".[engine]"
```

What this installs:

- The Arès toolkit — the `ares_setup` and `ares_provenance` packages and the
  `ares_console` / `ares_watch` / `ares_demo` modules — plus the `ares` command.
- The `[engine]` extra: the third-party runtime dependencies the vendored Strix
  engine needs (litellm, the OpenAI Agents SDK, docker, pydantic, reportlab, and
  so on — see [`../pyproject.toml`](../pyproject.toml)).

The base install (`pip install -e .`, no extra) pulls only `cryptography`, which
is enough to use the provenance tools (`sign` / `verify` / `keygen`), the setup
wizard, and the console.

> **Two commands named `ares`.** The repo ships an `ares` **launcher script** (at
> the repo root) that dispatches subcommands like `ares init` and `ares demo`. The
> `pip install` also registers an `ares` **console command** that opens the
> interactive hub (`ares_setup.home:home`) and ignores extra arguments. If typing
> `ares demo` opens the hub instead of running the demo, you are using the console
> entry — run `./ares demo` from the repo, or use the `python3 …` form shown for
> each command in [commands.md](commands.md).

## Guided setup: `ares init`

`ares init` is a guided wizard: it detects your hardware, recommends a local model
that fits, pulls it if needed, bakes a *derived* Ollama model with resource
settings baked in, and writes an `ares.env` you source before a run.

```bash
ares init                     # detect hardware, recommend + pull a model, write ares.env
ares init --dry-run           # show the whole plan without pulling or writing anything
ares init --level max         # resource dial: eco | balanced | max, or a 0-100 number
ares init --offline           # air-gapped: local model only, telemetry + web search off
```

The wizard will stop with a clear message if Ollama is not installed or not
running (`ollama serve`). See [commands.md](commands.md#ares-init--guided-local-llm-setup) for every flag.

Why a *derived* model? Strix's agent prompts are large (~40k tokens), so Arès
bakes a context floor of 49,152 tokens (and your GPU/parallelism settings) into a
new Ollama model via a generated `Modelfile`. Baking guarantees the settings
apply regardless of how the agent framework forwards per-request options. Details
in [reliability.md](reliability.md) and [troubleshooting.md](troubleshooting.md#context-window-too-small).

After it finishes, inspect what your machine can run:

```bash
ares dashboard                # hardware + local model catalog, with fit indicators
ares dashboard --eval         # also live-test installed models for STRIX-READY tool-calling
```

## First run: `ares demo`

The fastest way to see the whole chain — live agent feed, findings landing,
report generation, confidence gate, Ed25519 signature — is the demo:

```bash
ares demo
```

`ares demo` is a **scripted replay** of an OWASP Juice Shop engagement through the
real `ares watch` console. It runs in ~45 seconds with **no LLM and no cloud**, so
it demonstrates the pipeline and UX — it is **not** a live autonomous scan and its
findings are canned. (This honesty matters; see
[reliability.md](reliability.md#the-demo-is-a-replay).) It writes a signed run
under `strix_runs/_demo_live/` and offers to open a local HTML report.

## Verify a report

Every completed run (including the demo) is signed. Check it:

```bash
ares verify strix_runs/_demo_live
```

You should see a `VERIFIED` or `INTACT` line. The difference — and what each
verdict does and does not prove — is explained in [provenance.md](provenance.md).

## Run a real scan

Real scans are executed by the vendored `strix` engine inside a Docker sandbox.
The interactive hub can build and launch one for you:

```bash
ares                          # open the hub, choose [5] Run a scan
```

Under the hood the hub sources a profile (see [`../PROFILES.md`](../PROFILES.md))
and runs the engine roughly as:

```bash
source ares-cascade.env
strix -t ./test-target -m quick -n --max-turns 15
```

Open `ares watch` in a second terminal to follow the agents live and auto-sign the
report on completion. Be aware that a full local scan with a strong model can take
hours; see [troubleshooting.md](troubleshooting.md#inference-is-very-slow) and the
[cascade](cascade.md) for how Arès manages the cost/quality trade-off.

## Where things live

```
ares.env, ares-*.env      engine profiles you source before a run
strix_runs/<run>/         per-scan output (report, findings, log, signature)
~/.ares/keys/             your signing keypair (created by `ares keygen`)
~/.ares/trusted/          extra public keys you choose to trust when verifying
keys/ares-release.pub.pem the shipped Arès release public key
```

## Next steps

- [commands.md](commands.md) — the full command reference.
- [cascade.md](cascade.md) — routing work across a fast and a strong model.
- [reliability.md](reliability.md) — vetting a model and reading the confidence gate.
- [provenance.md](provenance.md) — the signing and verification model.
