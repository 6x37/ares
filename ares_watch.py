#!/usr/bin/env python3
"""ares watch — live A-to-Z visibility into a running Strix/Arès pentest.

Runs as a separate process alongside a scan and tails what Strix writes to
`strix_runs/<run>/`:
  • strix.log          -> agent lifecycle + tool activity feed (per-agent color)
  • vulnerabilities.json -> findings, shown the moment they land
  • run.json           -> status / phase / elapsed

When the scan completes it shows the report being generated and then SIGNS it
with ares_provenance — so the whole chain, recon → exploit → report → signature,
is visible in one console.

  python3 ares_watch.py                    # auto-detect the latest run
  python3 ares_watch.py --run strix_runs/my-run
  python3 ares_watch.py --follow           # keep tailing after completion
  python3 ares_watch.py --no-sign          # don't auto-sign on completion
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ares_setup import ui  # noqa: E402

RUNS_DIR = "strix_runs"
LOG_RE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\.\d+\s+"
    r"(?P<level>\w+)\s+(?P<scan>\S+)\s+(?P<agent>\S+)\s+(?P<name>\S+?):\s*(?P<msg>.*)$"
)
_AGENT_COLORS = [45, 213, 220, 82, 208, 51, 141, 197, 156, 118]
SEV_COLOR = {"critical": 196, "high": 208, "medium": 220, "low": 44, "info": 244}


def latest_run(base: Path) -> "Path | None":
    d = base / RUNS_DIR
    if not d.is_dir():
        return None
    runs = [c for c in d.iterdir() if (c / "run.json").is_file()]
    if not runs:
        return None
    return max(runs, key=lambda c: (c / "run.json").stat().st_mtime)


def agent_color(agent_id: str) -> int:
    if not agent_id or agent_id in ("-", "root", "None"):
        return 196  # root/none -> Arès red
    return _AGENT_COLORS[sum(map(ord, agent_id)) % len(_AGENT_COLORS)]


def classify(msg: str) -> str:
    m = msg.lower()
    if any(k in m for k in ("sandbox", "bringing up", "tearing down")):
        return "🐳"
    if any(k in m for k in ("spawn", "child", "sub-agent", "created agent", "delegat")):
        return "🤖"
    if any(k in m for k in ("vulnerab", "finding", "exploit", "poc")):
        return "🔴"
    if any(k in m for k in ("tool", "shell", "browser", "proxy", "request")):
        return "⚙ "
    if any(k in m for k in ("done", "finished", "complete", "ready")):
        return "✓ "
    if any(k in m for k in ("error", "failed", "refused", "crash")):
        return "✗ "
    return "· "


def render_log_line(c: ui.C, d: dict) -> None:
    icon = classify(d["msg"])
    ac = agent_color(d["agent"])
    agent = d["agent"] if d["agent"] not in ("-", "None") else "root"
    lvl = d["level"].upper()
    msg = d["msg"]
    if lvl in ("ERROR", "CRITICAL"):
        msg = c.red(msg)
    elif lvl in ("WARNING", "WARN"):
        msg = c.gold(msg)
    ts = c.gray(d["ts"].split(" ")[1])  # HH:MM:SS
    tag = c.c256(ac, f"{agent:>10.10}")
    print(f"{ts} {icon} {tag} {msg}")


def show_finding(c: ui.C, v: dict) -> None:
    sev = (v.get("severity") or "info").lower()
    col = SEV_COLOR.get(sev, 244)
    bar = c.c256(col, "▌")
    title = c.bold(v.get("title", "Untitled"))
    meta = c.gray(f"{v.get('id','?')} · {v.get('endpoint') or v.get('target') or ''}".strip(" ·"))
    print(f"\n{bar} {c.c256(col, sev.upper())}  {title}\n  {meta}\n")


def load_json(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def header(c: ui.C, run: Path, rec: dict) -> None:
    ui.render_banner(c)
    tgt = rec.get("target") or (rec.get("scan_config") or {}).get("target") or "?"
    print("  " + c.bold("run     ") + c.cyan(run.name))
    print("  " + c.bold("target  ") + str(tgt))
    print("  " + c.gray("live agent activity — Ctrl-C to detach\n"))
    print(c.orange(c.bold("── activity ──")))


def sign_report(c: ui.C, run: Path) -> None:
    import subprocess
    report = run / "penetration_test_report.md"
    print("\n" + c.orange(c.bold("── report ──")))
    with ui.Spinner(c, "génération du rapport…", on=c.on):
        for _ in range(60):
            if report.exists():
                break
            time.sleep(0.5)
    if not report.exists():
        print(c.gold("  (aucun rapport généré)")); return
    print(c.green(f"  ✓ rapport généré: {report.name}"))
    # Arès confidence gate: annotate the report BEFORE signing, so the verdict
    # is part of the signed content (a bailed "0 findings" can't hide).
    try:
        from ares_setup.confidence import annotate_report
        conf = annotate_report(run)
        col = {"HIGH": c.green, "OK": c.gold, "LOW": c.red}[conf.verdict]
        print("  " + col(conf.banner()))
    except Exception as _e:  # noqa: BLE001
        print(c.gray(f"  (confidence check indisponible: {_e})"))
    with ui.Spinner(c, "signature Ed25519…", on=c.on):
        rc = subprocess.run(
            [sys.executable, "-m", "ares_provenance", "sign", str(run),
             "--local"], capture_output=True, text=True)
    if rc.returncode == 0:
        print(c.green("  🛡️  rapport signé & vérifiable (ares.provenance.json)"))
    else:
        print(c.gold(f"  signature ignorée: {rc.stderr.strip()[:80]}"))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default=None, help="run dir (default: latest under ./strix_runs)")
    ap.add_argument("--base", default=".", type=Path)
    ap.add_argument("--follow", action="store_true", help="keep tailing after completion")
    ap.add_argument("--no-sign", action="store_true")
    ap.add_argument("--poll", type=float, default=0.7)
    args = ap.parse_args(argv)

    c = ui.C(on=sys.stdout.isatty())
    run = Path(args.run) if args.run else latest_run(args.base)
    if not run or not run.exists():
        print(c.red("Aucun run trouvé. Lance un scan Strix, ou passe --run <dir>."))
        return 1

    rec = load_json(run / "run.json") or {}
    header(c, run, rec)

    log_path = run / "strix.log"
    vuln_path = run / "vulnerabilities.json"
    pos = 0
    seen_vulns: set = set()
    buf = ""
    terminal = {"completed", "failed", "stopped", "interrupted"}

    try:
        while True:
            # 1) tail strix.log
            if log_path.exists():
                with log_path.open("r", encoding="utf-8", errors="replace") as f:
                    f.seek(pos)
                    chunk = f.read()
                    pos = f.tell()
                buf += chunk
                lines = buf.split("\n")
                buf = lines.pop()  # keep partial line
                for line in lines:
                    if not line.strip():
                        continue
                    m = LOG_RE.match(line)
                    if m:
                        render_log_line(c, m.groupdict())
                    else:
                        print(c.gray("           " + line[:200]))

            # 2) new findings
            vulns = load_json(vuln_path) or []
            for v in vulns:
                if v.get("id") and v["id"] not in seen_vulns:
                    seen_vulns.add(v["id"]); show_finding(c, v)

            # 3) status
            rec = load_json(run / "run.json") or rec
            status = str(rec.get("status", "running")).lower()
            if status in terminal and not args.follow:
                badge = c.green("completed") if status == "completed" else c.gold(status)
                print("\n" + c.orange(c.bold("── status ──")) + "  " + badge +
                      c.gray(f"  · {len(seen_vulns)} finding(s)"))
                if not args.no_sign:
                    sign_report(c, run)
                print("\n" + c.green("watch terminé."))
                return 0

            time.sleep(args.poll)
    except KeyboardInterrupt:
        print(c.gray("\ndétaché (le scan continue)."))
        return 0


if __name__ == "__main__":
    sys.exit(main())
