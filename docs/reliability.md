# Reliability: the honesty layer

Arès's whole ethos is not overclaiming. Two mechanisms make that concrete: it
**vets a model before you waste a scan on it**, and it **grades a finished run** so
an empty report can't masquerade as a clean result. Neither one makes a weak model
strong — they make weakness **visible**.

Source: `ares_setup/model_eval.py` and `ares_setup/confidence.py`. Background:
[`../INTEGRATION_NOTES.md`](../INTEGRATION_NOTES.md).

## The core problem this exists to solve

Running the pipeline against one deliberately-vulnerable `app.py` (SQL injection +
command injection + path traversal), with three local engines, produced this:

- **qwen3.5 14B (fast):** completed many turns quickly, but did almost no tool work
  and **hallucinated** a conclusion that the file was an empty "stub". Fast, wrong.
- **Qwen3.6-27B-OBLITERATED:** methodical and accurate, but too slow to finish a
  full scan in one sitting locally.
- **WhiteRabbitNeo V3 7B:** excellent security payloads, but emits tool calls as
  raw text, not the structured `tool_calls` field — so it **cannot drive the agent
  loop at all**.

The lesson: **a model can answer a security question perfectly in a chat and still
fail as an autonomous agent** — including confidently reporting "nothing found" on
code that is obviously vulnerable. Cyber-tuned ≠ agentic-tool-tuned. Both honesty
tools below come straight from that finding.

## Model-eval: is this model usable as an agent?

```bash
ares eval qwen3.5:latest
```

`ares eval` probes a model on the three things that actually decide fitness,
against the local OpenAI-compatible endpoint (`http://localhost:11434/v1`):

1. **Structured tool-calling — the blocker.** It sends a prompt with a tool
   definition and checks whether the model replies with a real OpenAI `tool_calls`
   entry (not tool syntax in the text body). If it does not, the agent loop cannot
   parse it, and the model is **not** usable as a Strix agent — full stop,
   regardless of how much security it knows.
2. **Vulnerability recall — quality.** Shown the vulnerable snippet, does it name
   the bug classes (SQL, command injection, path traversal)? Scored as the
   fraction it names. This is a **quality** signal, not a gate.
3. **Speed — practical.** Prompt-eval throughput in tokens/second, to predict
   per-turn latency (roughly: ≥40 tok/s fast, ≥20 ok, below that slow).

The verdict is `STRIX-READY` **only if tool-calling passes**; recall and speed are
reported for context but do not change it. This is the honest ordering: a model
that can't emit structured tool calls is disqualified no matter how good its
security recall is, and a model with weak recall is still `STRIX-READY` but risky —
which is exactly why the [cascade](cascade.md) pairs a fast triage model with a
stronger validation model, and why the run is graded afterward.

`ares dashboard --eval` runs the same tool-calling probe across your installed,
fitting models and badges each one.

**Honest scope.** The eval is a fast, single-shot probe. Passing it means the model
*can* speak the tool protocol; it does not guarantee the model will drive a long
autonomous engagement well. That is what the confidence gate is for.

## The confidence gate: HIGH / OK / LOW

```bash
ares confidence strix_runs/my-run
```

After a scan, Arès grades what the agents **actually did**, not just what the
report claims. It reads two files from the run directory — `strix.log` and
`vulnerabilities.json` — and extracts:

- `findings` — vulnerabilities reported;
- `tool_actions` — how many tool calls the agents completed (did they test?);
- `files_read` — did they read the target at all?;
- `turns` — how much work happened;
- `bailed_turns` — turns that ended with no lifecycle tool call (a give-up tell).

The verdict:

| Verdict | Meaning | Rule |
|---|---|---|
| 🟢 **HIGH** | Findings were reported by the agents. | `findings > 0` |
| 🟡 **OK** | 0 findings, but the agents genuinely read the target and exercised tools, so "clean" is credible. | `findings == 0` and `tool_actions ≥ 5` and `files_read > 0` |
| 🔴 **LOW** | 0 findings **and** little real work — likely a bail or hallucination. | `findings == 0` and (`tool_actions < 5` or `files_read == 0`) |

The exit code is non-zero on a LOW verdict, so it can gate automation.

### What a LOW verdict means (and does not)

A 🔴 LOW verdict means **"this run did too little testing to be trusted — re-run
with a stronger model"** (see the [cascade](cascade.md)). It **does not** mean the
target is clean. A bailed, empty report is precisely the failure mode this catches:
without the gate, "0 findings because the agent gave up" is indistinguishable from
"0 findings because the target is secure". The gate refuses to let the first
impersonate the second — the annotated report even says so in plain text.

### How it's wired into a run

`ares watch` calls the gate automatically when a scan finishes and **annotates the
report before signing**, so the verdict becomes part of the signed content — a
bailed "0 findings" cannot be hidden by editing the report afterward
([provenance.md](provenance.md)). You can also annotate by hand:

```bash
ares confidence strix_runs/my-run --annotate
```

### Honest scope

The gate is a **heuristic over log signals** (it counts tool-activity and
file-read patterns in `strix.log`), not a semantic judge of correctness. Its job is
to separate "real work happened" from "the agent bailed", cheaply and reliably. It
cannot tell you a HIGH run's findings are all correct, only that the agents did the
work; and an OK "0 findings" is *credible*, not *proven*. Combine it with the
signature (integrity + authenticity) and your own review.

## The demo is a replay

```bash
ares demo
```

`ares demo` replays a scripted OWASP Juice Shop engagement through the real
`ares watch` console so you can see the whole chain in ~45 seconds with no LLM and
no cloud. Its findings are **canned** — it demonstrates the pipeline and UX, it is
**not** a live autonomous scan and produces **no real findings**. The run is even
labeled as a demo replay in its own `run.json`. Do not read the demo's three
findings as anything an Arès scan discovered on a real target.

## Putting it together

The honest workflow Arès encourages:

1. `ares eval <model>` — confirm the model can drive the agent loop at all.
2. Run with the [cascade](cascade.md) — fast breadth, strong validation.
3. `ares watch` — grades the run (confidence) and signs it (provenance).
4. Read the verdict: a 🔴 LOW is a signal to **re-run stronger**, not a verdict on
   the target; a 🟢/🟡 with a `VERIFIED` signature is a report you can stand behind.

## See also

- [cascade.md](cascade.md) — the fast/strong routing these tools motivate.
- [provenance.md](provenance.md) — signing, and why the confidence verdict is
  signed with the report.
- [troubleshooting.md](troubleshooting.md#a-scan-returns-0-findings-on-code-you-know-is-vulnerable)
  — what to do when a run comes back empty.
