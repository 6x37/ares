"""Diff two Arès runs — what's new, fixed, or still present since last scan."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


def _load(run: Path) -> dict:
    try:
        vulns = json.loads((run / "vulnerabilities.json").read_text())
    except (OSError, json.JSONDecodeError):
        vulns = []
    return {(v.get("title", ""), v.get("endpoint") or v.get("target") or ""): v
            for v in vulns}


@dataclass
class Diff:
    new: list = field(default_factory=list)
    fixed: list = field(default_factory=list)
    persisting: list = field(default_factory=list)

    def report(self) -> str:
        def fmt(v):
            return f"{v.get('severity','?').upper()} {v.get('title','')}"
        lines = ["## Scan diff\n"]
        lines.append(f"🆕 new: {len(self.new)}")
        lines += [f"  + {fmt(v)}" for v in self.new]
        lines.append(f"✅ fixed: {len(self.fixed)}")
        lines += [f"  - {fmt(v)}" for v in self.fixed]
        lines.append(f"➖ still present: {len(self.persisting)}")
        return "\n".join(lines)


def diff_runs(old: Path, new: Path) -> Diff:
    a, b = _load(old), _load(new)
    d = Diff()
    d.new = [b[k] for k in b if k not in a]
    d.fixed = [a[k] for k in a if k not in b]
    d.persisting = [b[k] for k in b if k in a]
    return d


def _main(argv=None) -> int:
    import sys
    args = argv if argv is not None else sys.argv[1:]
    if len(args) < 2:
        print("usage: diff <old_run_dir> <new_run_dir>"); return 2
    print(diff_runs(Path(args[0]), Path(args[1])).report())
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(_main())
