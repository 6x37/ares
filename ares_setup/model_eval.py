"""Evaluate a local model for Strix/Arès agent use BEFORE wasting a scan on it.

The session's lesson: a model can be great at security Q&A yet unusable as an
agent (WhiteRabbitNeo emits tool calls as text; qwen3.5 hallucinated findings).
This harness probes the three things that actually decide fitness:

  1. tool_calls    — does it emit STRUCTURED OpenAI tool_calls (not text)?  [BLOCKER]
  2. vuln_recall   — shown obviously vulnerable code, does it name the bugs? [quality]
  3. speed         — prompt-eval throughput, to predict per-turn latency.    [practical]

Verdict: STRIX-READY only if tool_calls pass. The rest scores quality/speed.
"""

from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass, field

DEFAULT_ENDPOINT = "http://localhost:11434/v1"

_VULN_SNIPPET = (
    "q = \"SELECT * FROM users WHERE name = '\" + request.args.get('u') + \"'\"\n"
    "os.system('ping ' + request.args.get('host'))\n"
    "open('/data/' + request.args.get('f'))"
)
_TOOL = {
    "type": "function",
    "function": {
        "name": "http_request",
        "description": "send an HTTP request to test an endpoint",
        "parameters": {
            "type": "object",
            "properties": {"url": {"type": "string"}, "payload": {"type": "string"}},
            "required": ["url"],
        },
    },
}


@dataclass
class EvalResult:
    model: str
    tool_calls_ok: bool = False
    tool_calls_detail: str = ""
    vuln_recall: float = 0.0            # 0..1 fraction of expected vulns named
    vulns_found: list = field(default_factory=list)
    eval_tok_s: float = 0.0
    errors: list = field(default_factory=list)

    @property
    def strix_ready(self) -> bool:
        return self.tool_calls_ok

    def report(self) -> str:
        rd = "✅ STRIX-READY" if self.strix_ready else "❌ NOT usable as a Strix agent"
        lines = [
            f"Model: {self.model}   {rd}",
            f"  tool-calling (structured) : {'✅ yes' if self.tool_calls_ok else '❌ no — ' + self.tool_calls_detail}",
            f"  vuln recall               : {self.vuln_recall*100:.0f}%  {self.vulns_found}",
            f"  speed (eval)              : {self.eval_tok_s:.0f} tok/s",
        ]
        for e in self.errors:
            lines.append(f"  ⚠ {e}")
        return "\n".join(lines)


def _post(url: str, body: dict, timeout: int = 120) -> dict:
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def evaluate(model: str, endpoint: str = DEFAULT_ENDPOINT) -> EvalResult:
    res = EvalResult(model=model)
    base = endpoint.rstrip("/")

    # 1. structured tool-calling (the blocker)
    try:
        d = _post(f"{base}/chat/completions", {
            "model": model,
            "messages": [{"role": "user",
                          "content": "Test /login for SQL injection. Call the http_request tool."}],
            "tools": [_TOOL], "stream": False, "max_tokens": 600,
        })
        msg = d["choices"][0]["message"]
        tc = msg.get("tool_calls")
        if tc and isinstance(tc, list) and tc[0].get("function", {}).get("name"):
            res.tool_calls_ok = True
            res.tool_calls_detail = tc[0]["function"]["name"]
        else:
            content = (msg.get("content") or "")[:80]
            res.tool_calls_ok = False
            res.tool_calls_detail = f"emitted text, not tool_calls ({content!r})"
    except Exception as e:  # noqa: BLE001
        res.errors.append(f"tool-call probe failed: {e}")

    # 2. vuln recall
    try:
        d = _post(f"{base}/chat/completions", {
            "model": model,
            "messages": [{"role": "user", "content":
                          "Name the vulnerability CLASSES in this code, comma-separated, "
                          "no explanation:\n" + _VULN_SNIPPET}],
            "stream": False, "max_tokens": 800,
        })
        txt = (d["choices"][0]["message"].get("content") or "").lower()
        expected = {"sql": ["sql", "sqli"], "command": ["command inj", "os command", "rce", "command injection"],
                    "traversal": ["traversal", "path traversal", "lfi", "directory traversal"]}
        found = [k for k, kws in expected.items() if any(w in txt for w in kws)]
        res.vulns_found = found
        res.vuln_recall = len(found) / len(expected)
    except Exception as e:  # noqa: BLE001
        res.errors.append(f"vuln-recall probe failed: {e}")

    # 3. speed
    try:
        import time
        t0 = time.time()
        d = _post(f"{base.replace('/v1','')}/api/generate", {
            "model": model, "prompt": "Say: ready", "stream": False,
            "options": {"num_predict": 16},
        })
        el = time.time() - t0
        ec = d.get("eval_count", 0); ed = d.get("eval_duration", 0)
        res.eval_tok_s = (ec / (ed / 1e9)) if ed else (16 / el if el else 0)
    except Exception as e:  # noqa: BLE001
        res.errors.append(f"speed probe skipped: {e}")

    return res



def probe_tool_calls(model: str, base: str) -> tuple:
    try:
        d = _post(f"{base}/chat/completions", {
            "model": model,
            "messages": [{"role": "user",
                          "content": "Test /login for SQL injection. Call the http_request tool."}],
            "tools": [_TOOL], "stream": False, "max_tokens": 600})
        msg = d["choices"][0]["message"]; tc = msg.get("tool_calls")
        if tc and tc[0].get("function", {}).get("name"):
            return True, tc[0]["function"]["name"]
        return False, f"text not tool_calls ({(msg.get('content') or '')[:50]!r})"
    except Exception as e:  # noqa: BLE001
        return False, f"error: {e}"


def probe_vuln_recall(model: str, base: str) -> tuple:
    try:
        d = _post(f"{base}/chat/completions", {
            "model": model,
            "messages": [{"role": "user", "content":
                          "List the vulnerability class names in this code (SQL, command, "
                          "traversal, etc). Answer with the class names only:\n" + _VULN_SNIPPET}],
            "stream": False, "max_tokens": 1600})
        m = d["choices"][0]["message"]
        txt = ((m.get("content") or "") + " " + (m.get("reasoning") or "")).lower()
        exp = {"sql": ["sql"], "command": ["command inj", "os command", "rce", "command injection"],
               "traversal": ["traversal", "lfi"]}
        found = [k for k, kws in exp.items() if any(w in txt for w in kws)]
        return len(found) / len(exp), found
    except Exception as e:  # noqa: BLE001
        return 0.0, [f"error: {e}"]


def probe_speed(model: str, base: str) -> float:
    try:
        import time
        t0 = time.time()
        d = _post(f"{base.replace('/v1','')}/api/generate",
                  {"model": model, "prompt": "Say: ready", "stream": False,
                   "options": {"num_predict": 16}})
        ec, ed = d.get("eval_count", 0), d.get("eval_duration", 0)
        return (ec / (ed / 1e9)) if ed else 0.0
    except Exception:  # noqa: BLE001
        return 0.0


def evaluate_live(model: str, endpoint: str = DEFAULT_ENDPOINT) -> "EvalResult":
    """Run the eval with a live, animated CLI display (Arès styling)."""
    from . import ui
    import sys
    c = ui.C(on=sys.stdout.isatty())
    base = endpoint.rstrip("/")
    res = EvalResult(model=model)
    print(c.orange(c.bold(f"\n  ⚡ Arès model eval — {model}\n")))

    with ui.Spinner(c, "structured tool-calling (blocker)…", on=c.on):
        ok, detail = probe_tool_calls(model, base)
    res.tool_calls_ok, res.tool_calls_detail = ok, detail
    print("  " + (c.green("✅ tool-calling   ") if ok else c.red("❌ tool-calling   ")) +
          c.gray(detail if not ok else f"emits tool_calls ({detail})"))

    with ui.Spinner(c, "vulnerability recall…", on=c.on):
        recall, found = probe_vuln_recall(model, base)
    res.vuln_recall, res.vulns_found = recall, found
    bar = ui.bar(int(recall * 3), 3, width=12, c=c)
    print("  " + c.cyan("● vuln recall     ") + bar + c.gray(f"  {found}"))

    with ui.Spinner(c, "speed (prompt eval)…", on=c.on):
        speed = probe_speed(model, base)
    res.eval_tok_s = speed
    tag = c.green("fast") if speed >= 40 else c.gold("ok") if speed >= 20 else c.red("slow")
    print("  " + c.cyan("● speed           ") + f"{speed:.0f} tok/s  " + tag)

    verdict = c.green(c.bold("  ╭─ ✅ STRIX-READY ─╮")) if res.strix_ready else c.red(c.bold("  ╭─ ❌ NOT agent-usable ─╮"))
    print("\n" + verdict)
    if not res.strix_ready:
        print(c.gray("  │ no structured tool-calling → the agent loop can't parse it"))
    print(c.green("  ╰" + "─" * 18 + "╯") if res.strix_ready else c.red("  ╰" + "─" * 22 + "╯"))
    return res

def _main(argv=None) -> int:
    import sys
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        print("usage: python3 -m ares_setup.model_eval <model> [<model> ...]")
        return 2
    live = "--plain" not in args
    candidates = [a for a in args if not a.startswith("--")]
    # keep only real installed models (skip stray shell tokens like a '#' comment)
    try:
        import subprocess
        installed = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=10).stdout
        known = {ln.split()[0] for ln in installed.splitlines()[1:] if ln.split()}
        known |= {k.split(":")[0] for k in known}
    except Exception:
        known = set()
    models = [m for m in candidates if not known or m in known or m.split(":")[0] in known]
    skipped = [m for m in candidates if m not in models]
    if skipped:
        print(f"(ignoré, pas un modèle installé: {', '.join(skipped)})")
    if not models:
        print("Aucun modèle valide. usage: python3 -m ares_setup.model_eval <model> [--plain]")
        return 2
    ok_all = True
    for m in models:
        r = evaluate_live(m) if live else evaluate(m)
        if not live:
            print(r.report()); print()
        ok_all = ok_all and r.strix_ready
    return 0 if ok_all else 1


if __name__ == "__main__":
    import sys
    sys.exit(_main())
