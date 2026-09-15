#!/usr/bin/env python3
"""ares demo — a fast, scripted showcase of the full Arès chain (~45s).

Replays a realistic OWASP Juice Shop engagement through the REAL Arès watch
console: live agent feed (cascade routing shown), findings landing as cards,
then report generation → confidence gate → Ed25519 signature → verify.

Scripted backend so it runs in seconds with no LLM or cloud — it demonstrates
the pipeline and UX, it is not a live autonomous scan. Marked as a demo run.
"""
from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
from pathlib import Path

HOME = Path(__file__).resolve().parent
RUN = HOME / "strix_runs" / "_demo_live"

# (delay before, agent, tier, log line)
SCRIPT = [
    (0.4, "root", "validate", "Bringing up sandbox session for scan _demo_live"),
    (0.6, "root", "validate", "Sandbox ready for scan _demo_live"),
    (0.5, "root", "validate", "root agent decomposing target http://host.docker.internal:3000"),
    (0.7, "root", "validate", "spawning sub-agent: Recon Agent (a1)"),
    (0.6, "a1", "triage", "browser crawl on http://host.docker.internal:3000"),
    (0.6, "a1", "triage", "discovered: /rest/user/login /rest/products/search /#/administration"),
    (0.7, "root", "validate", "spawning sub-agent: SQLi Validation Agent (a2)"),
    (0.7, "a2", "validate", "testing SQL injection on /rest/user/login"),
    (0.8, "a2", "validate", "payload confirmed: authentication bypass via SQLi"),
    ("VULN", {"id": "VULN-001", "title": "SQL Injection on /rest/user/login (auth bypass)",
              "severity": "critical", "endpoint": "/rest/user/login"}),
    (0.6, "a2", "validate", "create_vulnerability_report VULN-001 (with PoC)"),
    (0.7, "root", "validate", "spawning sub-agent: XSS Agent (a3)"),
    (0.6, "a3", "validate", "testing reflected XSS on /#/search?q="),
    (0.7, "a3", "validate", "confirmed: reflected XSS in search results"),
    ("VULN", {"id": "VULN-002", "title": "Reflected XSS via search q parameter",
              "severity": "high", "endpoint": "/#/search"}),
    (0.6, "a3", "validate", "create_vulnerability_report VULN-002"),
    (0.7, "root", "validate", "spawning sub-agent: Access Control Agent (a4)"),
    (0.7, "a4", "triage", "probing /#/administration without admin role"),
    (0.7, "a4", "validate", "confirmed: admin section reachable (broken access control)"),
    ("VULN", {"id": "VULN-003", "title": "Broken access control — admin section exposed",
              "severity": "high", "endpoint": "/#/administration"}),
    (0.6, "a4", "validate", "create_vulnerability_report VULN-003"),
    (0.8, "root", "validate", "Strix scan _demo_live done"),
]


def _writer():
    RUN.mkdir(parents=True, exist_ok=True)
    (RUN / "vulnerabilities").mkdir(exist_ok=True)
    log = RUN / "strix.log"
    log.write_text("", encoding="utf-8")
    (RUN / "run.json").write_text(json.dumps(
        {"status": "running", "target": "http://host.docker.internal:3000",
         "run_name": "_demo_live", "note": "DEMO replay"}), encoding="utf-8")
    (RUN / "vulnerabilities.json").write_text("[]", encoding="utf-8")
    vulns = []
    turn = 0
    for step in SCRIPT:
        if step[0] == "VULN":
            vulns.append({**step[1], "target": "http://host.docker.internal:3000",
                          "timestamp": "t"})
            (RUN / "vulnerabilities.json").write_text(json.dumps(vulns), encoding="utf-8")
            continue
        delay, agent, tier, msg = step
        time.sleep(delay)
        turn += 1
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        with log.open("a", encoding="utf-8") as f:
            f.write(f"{ts}.100 INFO    _demo_live {agent} strix.core.runner: Starting turn {turn}\n")
            f.write(f"{ts}.101 INFO    _demo_live {agent} strix.agents.factory: "
                    f"Ares cascade: agent '{agent}' -> "
                    f"openai/ares-cascade-{tier}\n")
            f.write(f"{ts}.102 INFO    _demo_live {agent} strix.tools: {msg}\n")
            f.write(f"{ts}.103 INFO    _demo_live {agent} strix.tools: Tool http_request completed\n")
    # report + complete
    (RUN / "penetration_test_report.md").write_text(
        "# Security Penetration Test Report\n\n"
        "> DEMO replay — OWASP Juice Shop.\n\n"
        "## Executive Summary\n3 findings (1 critical, 2 high).\n", encoding="utf-8")
    (RUN / "run.json").write_text(json.dumps(
        {"status": "completed", "target": "http://host.docker.internal:3000",
         "run_name": "_demo_live"}), encoding="utf-8")


def main() -> int:
    import shutil
    if RUN.exists():
        shutil.rmtree(RUN)
    t = threading.Thread(target=_writer, daemon=True)
    t.start()
    time.sleep(0.6)  # let the run dir appear
    rc = subprocess.run([sys.executable, str(HOME / "ares_watch.py"),
                         "--run", str(RUN), "--poll", "0.4"]).returncode
    t.join(timeout=2)
    _print_links()
    return rc


import os as _os
# Optional shareable web report; set ARES_DEMO_URL to enable. Empty = local only.
DEMO_URL = _os.getenv("ARES_DEMO_URL", "")


def _print_links() -> None:
    from ares_setup import ui
    c = ui.C(on=sys.stdout.isatty())
    md_report = (RUN / "penetration_test_report.md").resolve()
    html_report = (HOME / "ares_report.html").resolve()
    print("\n" + c.orange(c.bold("── cascade ──")))
    print("  " + c.gray("triage   ") + c.cyan("Qwen3.5 (14B)") + c.gray("            recon · crawl · map"))
    print("  " + c.gray("validate ") + c.cyan("Qwen3.6-27B-OBLITERATED") + c.gray("  confirm · PoC · report"))
    print("\n" + c.orange(c.bold("── rapport ──")))
    print("  " + c.bold("📄 rapport  ") + c.cyan(str(html_report)) + c.gray("  (beau, local, hors-ligne)"))
    print("  " + c.gray("   markdown : ") + c.cyan(str(md_report)))
    print("  " + c.bold("🔍 vérifier ") + c.gray(f" ares verify {RUN}"))
    print("  " + c.gray("   (lien web partageable : ") + c.gray(DEMO_URL + ")"))
    # offer to open the LOCAL html report (no cloud, no login) when interactive
    if sys.stdout.isatty():
        try:
            ans = input(c.orange("\n  ouvrir le rapport maintenant ? [Y/n] ")).strip().lower()
        except (EOFError, KeyboardInterrupt):
            ans = "n"
        if ans in ("", "y", "yes", "o", "oui"):
            import subprocess as _sp
            opener = "open" if sys.platform == "darwin" else "xdg-open"
            target = html_report if html_report.exists() else md_report
            _sp.run([opener, str(target)], check=False)


if __name__ == "__main__":
    sys.exit(main())
