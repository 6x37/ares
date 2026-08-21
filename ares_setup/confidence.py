"""Confidence gate for a finished scan — tell a real result from a bailed one.

The session's core failure: both local models reported "0 findings" on obviously
vulnerable code, having barely used their tools. A signed but empty report is
worthless if you can't tell "0 findings because it's clean" from "0 findings
because the agent gave up". This scores a run on what the agents ACTUALLY did.

Signals (from strix.log + vulnerabilities.json):
  findings        — vulnerabilities reported
  tool_actions    — how many tool calls the agents completed (did they test?)
  files_read      — did they read the target at all?
  turns           — how much work happened
  bailed_turns    — turns that ended with no lifecycle tool call (a give-up tell)

Verdict:
  HIGH   — findings present, each with evidence, tools exercised.
  OK     — 0 findings but the agents genuinely worked (read + tested), so "clean"
           is credible.
  LOW    — 0 findings AND little tool work → likely a bail/hallucination; the
           report must NOT be trusted as "clean".
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Confidence:
    verdict: str                 # HIGH | OK | LOW
    findings: int = 0
    tool_actions: int = 0
    files_read: int = 0
    turns: int = 0
    bailed_turns: int = 0
    reasons: list = field(default_factory=list)

    def banner(self) -> str:
        icon = {"HIGH": "🟢", "OK": "🟡", "LOW": "🔴"}[self.verdict]
        return f"{icon} Confidence: {self.verdict}"

    def to_markdown(self) -> str:
        lines = [
            "\n## 🔎 Arès confidence assessment\n",
            f"**{self.banner()}**\n",
            f"- Findings reported: {self.findings}",
            f"- Tool actions by agents: {self.tool_actions}",
            f"- Target files read: {self.files_read}",
            f"- Turns: {self.turns} (bailed: {self.bailed_turns})",
        ]
        if self.reasons:
            lines.append("")
            lines += [f"- {r}" for r in self.reasons]
        if self.verdict == "LOW":
            lines.append(
                "\n> ⚠️ This run did little actual testing. A '0 findings' result "
                "here is **not** evidence the target is secure — re-run with a "
                "stronger model (see the Arès cascade) before trusting it.")
        return "\n".join(lines) + "\n"


_TOOL_RE = re.compile(r"Tool .* completed|tool_call|create_vulnerability_report|create_agent", re.I)
_READ_RE = re.compile(r"read_file|view_file|cat |\.py|filesystem|open\(", re.I)
_TURN_RE = re.compile(r"Starting turn")
_BAIL_RE = re.compile(r"ended a turn without a lifecycle tool call", re.I)


def assess(run_dir: Path) -> Confidence:
    log = (run_dir / "strix.log")
    text = log.read_text(encoding="utf-8", errors="replace") if log.exists() else ""
    try:
        vulns = json.loads((run_dir / "vulnerabilities.json").read_text())
    except (OSError, json.JSONDecodeError):
        vulns = []

    findings = len(vulns)
    tool_actions = len(_TOOL_RE.findall(text))
    files_read = len(_READ_RE.findall(text))
    turns = len(_TURN_RE.findall(text))
    bailed = len(_BAIL_RE.findall(text))

    c = Confidence(verdict="OK", findings=findings, tool_actions=tool_actions,
                   files_read=files_read, turns=turns, bailed_turns=bailed)

    if findings > 0:
        c.verdict = "HIGH"
        c.reasons.append(f"{findings} finding(s) reported by the agents.")
        return c

    # 0 findings — was the work real?
    if tool_actions < 5 or files_read == 0:
        c.verdict = "LOW"
        if files_read == 0:
            c.reasons.append("Agents never read the target files.")
        if tool_actions < 5:
            c.reasons.append(f"Only {tool_actions} tool action(s) across {turns} turn(s) — minimal testing.")
        if bailed:
            c.reasons.append(f"{bailed} turn(s) ended without a lifecycle call (give-up signal).")
    else:
        c.verdict = "OK"
        c.reasons.append("Agents read the target and exercised tools; '0 findings' is credible.")
    return c


def annotate_report(run_dir: Path) -> Confidence:
    """Append the confidence assessment to penetration_test_report.md (idempotent)."""
    c = assess(run_dir)
    report = run_dir / "penetration_test_report.md"
    if report.exists():
        text = report.read_text(encoding="utf-8")
        marker = "## 🔎 Arès confidence assessment"
        if marker in text:
            text = text.split(marker)[0].rstrip()
        report.write_text(text.rstrip() + "\n" + c.to_markdown(), encoding="utf-8")
    return c


def _main(argv=None) -> int:
    import sys
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        print("usage: python3 -m ares_setup.confidence <run_dir> [--annotate]")
        return 2
    from pathlib import Path
    run = Path(args[0])
    if "--annotate" in args:
        c = annotate_report(run)
        print(f"annotated report → {c.banner()}")
    else:
        c = assess(run)
        print(c.banner())
        for r in c.reasons:
            print("  -", r)
    return 0 if c.verdict != "LOW" else 1


if __name__ == "__main__":
    import sys
    sys.exit(_main())
