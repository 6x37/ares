"""Arès onboarding dashboard — hardware + local model catalog, magnitude-style.

One boxed view that answers "what can THIS machine run, and which models are
actually usable as agents?" Combines hardware detection, the model catalog with
fit indicators, and (optional) live STRIX-READY eval badges.
"""

from __future__ import annotations

import sys

from . import hardware, models, ollama, ui

_BOX_W = 62


def _line(c: ui.C, text: str = "", pad: str = " ") -> str:
    # visible length ignoring ANSI — approximate by stripping escapes
    import re
    visible = re.sub(r"\033\[[0-9;]*m", "", text)
    fill = max(0, _BOX_W - 2 - len(visible))
    return c.gray("│ ") + text + pad * fill + c.gray(" │")


def _rule(c: ui.C, ch: str = "─") -> str:
    return c.gray("├" + ch * _BOX_W + "┤")


def _bar(frac: float, width: int, c: ui.C, color=None) -> str:
    frac = max(0.0, min(1.0, frac))
    filled = int(width * frac)
    color = color or c.green
    return color("█" * filled) + c.gray("░" * (width - filled))


def render(evaluate: bool = False, endpoint: str = "http://localhost:11434/v1") -> None:
    c = ui.C(on=sys.stdout.isatty())
    hw = hardware.detect()
    st = ollama.status()
    installed = set(st.models)
    ranked = models.recommend(hw.usable_inference_gb, installed_tags=installed)
    best = ranked[0].ollama_tag if ranked else None

    top = c.gray("╭" + "─" * _BOX_W + "╮")
    bot = c.gray("╰" + "─" * _BOX_W + "╯")
    print()
    print(top)
    print(_line(c, c.red(c.bold("  ARÈS")) + c.gray("  ·  local engine dashboard")))
    print(_rule(c))

    # hardware
    print(_line(c, c.bold("  HARDWARE")))
    print(_line(c, f"  {hw.chip}  ·  {hw.os}/{hw.arch}"))
    ram_frac = min(hw.usable_inference_gb / max(hw.total_ram_gb, 1), 1.0)
    print(_line(c, "  memory   " + _bar(ram_frac, 22, c) +
                f"  {hw.usable_inference_gb:.0f}/{hw.total_ram_gb:.0f} GB usable"))
    gpu = {"apple-metal": "Apple GPU (Metal)", "nvidia": f"NVIDIA {hw.gpu_vram_gb or ''}GB",
           "none": "CPU only"}[hw.gpu]
    print(_line(c, f"  gpu      {gpu}"))
    rt = c.green("● running") if st.running else c.red("● offline")
    print(_line(c, f"  runtime  Ollama {rt}  ·  {len(installed)} models"))
    print(_rule(c))

    # models
    print(_line(c, c.bold("  LOCAL MODELS") + c.gray("   fit · size · agent-ready")))
    shown = 0
    for m in models.CATALOG:
        if shown >= 6:
            break
        fits = models.fits(m, hw.usable_inference_gb)
        here = ollama.has_model(m.ollama_tag, st)
        star = c.gold("★") if m.ollama_tag == best else " "
        fit_icon = c.green("✓") if fits else c.red("✗")
        inst = c.green("●") if here else c.gray("○")
        name = (m.display[:26]).ljust(26)
        size = f"{m.approx_gb:>4.0f}GB"
        badge = ""
        if evaluate and here and fits:
            from .model_eval import probe_tool_calls
            with ui.Spinner(c, f"eval {m.display}…", on=c.on):
                ok, _ = probe_tool_calls(m.ollama_tag, endpoint.rstrip("/"))
            badge = c.green(" STRIX-READY") if ok else c.red(" no-tools")
        elif m.uncensored:
            badge = c.gray(" uncensored")
        print(_line(c, f" {star}{fit_icon} {inst} {c.cyan(name)} {size}{badge}"))
        shown += 1

    print(_rule(c))
    if best:
        print(_line(c, c.gray("  ★ recommended  ") + c.cyan(best.split('/')[-1])))
    print(_line(c, c.gray("  ● installed  ○ available  ✓ fits  ✗ too big")))
    print(bot)
    print()


def _main(argv=None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    render(evaluate="--eval" in args)
    return 0


if __name__ == "__main__":
    sys.exit(_main())
