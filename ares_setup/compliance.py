"""Map Arès findings to compliance controls (PCI-DSS, ISO 27001, SOC2, NIST CSF).

Mapping is by vulnerability class keyword → the control each framework touches.
Produces an auditor-friendly evidence table. Not legal advice; a starting map.
"""
from __future__ import annotations

import json
from pathlib import Path

# class keyword -> {framework: control}
_MAP = {
    "sql": {"PCI-DSS": "6.5.1", "ISO27001": "A.8.28", "SOC2": "CC6.1", "NIST-CSF": "PR.PS"},
    "xss": {"PCI-DSS": "6.5.7", "ISO27001": "A.8.28", "SOC2": "CC6.1", "NIST-CSF": "PR.PS"},
    "inject": {"PCI-DSS": "6.5.1", "ISO27001": "A.8.28", "SOC2": "CC6.1", "NIST-CSF": "PR.PS"},
    "auth": {"PCI-DSS": "8.2", "ISO27001": "A.5.17", "SOC2": "CC6.1", "NIST-CSF": "PR.AA"},
    "access": {"PCI-DSS": "7.1", "ISO27001": "A.5.15", "SOC2": "CC6.3", "NIST-CSF": "PR.AA"},
    "idor": {"PCI-DSS": "7.1", "ISO27001": "A.5.15", "SOC2": "CC6.3", "NIST-CSF": "PR.AA"},
    "traversal": {"PCI-DSS": "6.5.8", "ISO27001": "A.8.28", "SOC2": "CC6.1", "NIST-CSF": "PR.PS"},
    "crypto": {"PCI-DSS": "4.1", "ISO27001": "A.8.24", "SOC2": "CC6.7", "NIST-CSF": "PR.DS"},
    "config": {"PCI-DSS": "2.2", "ISO27001": "A.8.9", "SOC2": "CC7.1", "NIST-CSF": "PR.IP"},
}
_FRAMEWORKS = ["PCI-DSS", "ISO27001", "SOC2", "NIST-CSF"]


def _class_of(title: str) -> str:
    t = (title or "").lower()
    for key in _MAP:
        if key in t:
            return key
    return ""


def map_run(run: Path) -> list[dict]:
    try:
        vulns = json.loads((run / "vulnerabilities.json").read_text())
    except (OSError, json.JSONDecodeError):
        vulns = []
    rows = []
    for v in vulns:
        cls = _class_of(v.get("title", ""))
        controls = _MAP.get(cls, {})
        rows.append({"finding": v.get("title", ""), "severity": v.get("severity", ""),
                     "class": cls or "other", "controls": controls})
    return rows


def to_markdown(run: Path) -> str:
    rows = map_run(run)
    out = ["## Compliance mapping\n",
           "| Finding | Severity | " + " | ".join(_FRAMEWORKS) + " |",
           "|---|---|" + "---|" * len(_FRAMEWORKS)]
    for r in rows:
        cells = " | ".join(r["controls"].get(f, "—") for f in _FRAMEWORKS)
        out.append(f"| {r['finding'][:40]} | {r['severity']} | {cells} |")
    if not rows:
        out.append("| (no findings to map) | | | | | |")
    return "\n".join(out) + "\n"


def _main(argv=None) -> int:
    import sys
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        print("usage: compliance <run_dir>"); return 2
    print(to_markdown(Path(args[0])))
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(_main())
