"""CLI: `ares-init` (a.k.a. `ares init`)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import ui
from .wizard import InitOptions, run


def main(argv: "list[str] | None" = None) -> int:
    p = argparse.ArgumentParser(
        prog="ares-init",
        description="Guided setup for running Arès on a local LLM.",
    )
    p.add_argument("--model", default=None,
                   help="Ollama model tag to use (default: recommend for your hardware)")
    p.add_argument("--level", default="balanced",
                   help="resource dial: eco|balanced|max or 0-100 (default: balanced)")
    p.add_argument("--endpoint", default="http://localhost:11434")
    p.add_argument("--env-path", default=None, type=Path,
                   help="explicit env file (default: derived from --profile)")
    p.add_argument("--profile", default="default",
                   help="named profile: 'default' -> ares.env, others -> ares-<name>.env")
    p.add_argument("-y", "--yes", action="store_true",
                   help="accept the recommended model without prompting")
    p.add_argument("--dry-run", action="store_true",
                   help="show the plan without pulling, creating, or writing anything")
    p.add_argument("--standard-model", action="store_true",
                   help="don't prefer uncensored models")
    p.add_argument("--offline", action="store_true",
                   help="air-gapped mode: disable telemetry & web search, require a "
                        "local model, refuse any cloud egress")
    args = p.parse_args(argv)

    env_path = args.env_path or (
        Path("ares.env") if args.profile == "default"
        else Path(f"ares-{args.profile}.env"))
    opts = InitOptions(
        model=args.model, level=args.level, endpoint=args.endpoint,
        env_path=env_path, assume_yes=args.yes, dry_run=args.dry_run,
        prefer_uncensored=not args.standard_model,
        offline=args.offline,
    )
    import sys
    c = ui.C(on=sys.stdout.isatty())
    ui.render_banner(c)
    spinner = (lambda label: ui.Spinner(c, label, on=c.on))
    result = run(opts, log=ui.styled_log(c), spinner=spinner)
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
