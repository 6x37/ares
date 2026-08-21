"""Arès home — one interactive hub. Run `ares`, reach everything from here."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from . import ui

HOME = Path(__file__).resolve().parents[1]

def _default_profile() -> str:
    env = HOME / "ares.env"
    if not env.exists():
        return ""
    for line in env.read_text().splitlines():
        if "STRIX_LLM" in line:
            return line.split("=", 1)[1].strip().strip('"').split("/")[-1]
    return ""


MENU = [
    ("1", "Dashboard",   "hardware + local model catalog"),
    ("2", "Setup",       "guided local-LLM install (ares init)"),
    ("3", "Eval a model", "live STRIX-READY test of a model"),
    ("4", "Console",     "chat with the local engine"),
    ("5", "Run a scan",  "launch a pentest on a target"),
    ("6", "Watch",       "live agent activity of a running scan"),
    ("7", "Confidence",  "trust score of a finished scan"),
    ("8", "Verify report", "check an Arès signature"),
    ("9", "Profiles",    "list engine profiles & cascade"),
    ("q", "Quit",        ""),
]


def _run(cmd: list[str]) -> None:
    try:
        subprocess.run(cmd, cwd=str(HOME))
    except KeyboardInterrupt:
        pass


def _profiles(c: ui.C) -> None:
    print("\n" + c.orange(c.bold("  Profiles / cascade")))
    for f in sorted(HOME.glob("ares*.env")):
        model = ""
        for line in f.read_text().splitlines():
            if "STRIX_LLM" in line:
                model = line.split("=", 1)[1].strip().strip('"')
        star = c.gold(" ★") if f.name == "ares-cascade.env" else ""
        print("  " + c.cyan(f"{f.name:22}") + c.gray(model) + star)
    cascade = HOME / "ares-cascade.yaml"
    if cascade.exists():
        print("  " + c.gray("cascade config: ") + c.cyan("ares-cascade.yaml"))
    print()


def _ask(c: ui.C, prompt: str, default: str = "") -> str:
    try:
        v = input(c.orange("  " + prompt + (f" [{default}]" if default else "") + " ")).strip()
    except (EOFError, KeyboardInterrupt):
        return default
    return v or default


def _run_scan(c: ui.C) -> None:
    target = _ask(c, "target (path/url):", "./test-target")
    print("  profils: " + c.cyan("cascade") + c.gold(" ★recommandé") + c.gray(" · ") + c.cyan("fast") + c.gray("(qwen3.5) · ") + c.cyan("offensive") + c.gray("(27B)"))
    prof = _ask(c, "profile:", "cascade")
    env = {"fast": "ares-fast.env", "offensive": "ares-run.env",
           "cascade": "ares-cascade.env"}.get(prof, "ares-fast.env")
    turns = _ask(c, "max turns:", "15")
    print(c.gray(f"\n  → source {env} && strix -t {target} -m quick -n --max-turns {turns}"))
    print(c.gray("  (astuce: ouvre `ares watch` dans un autre terminal pour suivre en live)\n"))
    if _ask(c, "lancer ? (y/n):", "y").lower().startswith("y"):
        _run(["bash", "-lc",
               f"set -a; source {env}; set +a; "
               f"$HOME/.local/bin/strix -t {target} -m quick -n --max-turns {turns}"])


def home() -> int:
    c = ui.C(on=sys.stdout.isatty())
    while True:
        if c.on:
            sys.stdout.write("\033[2J\033[H")  # clear screen for a clean redraw
        ui.render_banner(c)
        # rich status line: hardware + runtime + default profile
        try:
            from . import hardware, ollama
            hw = hardware.detect(); st = ollama.status()
            rt = c.green("●") if st.running else c.red("●")
            load = hw.usable_inference_gb / max(hw.total_ram_gb, 1)
            memc = c.green if load > 0.4 else c.gold
            mem = memc(f"{hw.usable_inference_gb:.0f}GB usable")
            print("  " + c.gray(f"{hw.chip} · ") + mem +
                  c.gray(f" · Ollama {rt} {len(st.models)} models"))
        except Exception:
            pass
        prof = _default_profile()
        if prof:
            print("  " + c.gray("engine  ") + c.cyan(prof))
        else:
            print("  " + c.red("⚠ pas de config — commence par [2] Setup"))
        print()
        for key, name, desc in MENU:
            print("  " + c.gold(f"[{key}]") + " " + c.bold(f"{name:16}") + c.gray(desc))
        choice = _ask(c, "\n  ⟩", "").lower()
        print()
        if choice in ("q", "quit", "exit"):
            print(c.gray("  bye.\n")); return 0
        elif choice == "1":
            from .dashboard import render; render()
        elif choice == "2":
            _run([sys.executable, "-m", "ares_setup"])
        elif choice == "3":
            m = _ask(c, "model:", "qwen3.5:latest")
            _run([sys.executable, "-m", "ares_setup.model_eval", m])
        elif choice == "4":
            _run([sys.executable, "ares_console.py"])
        elif choice == "5":
            _run_scan(c)
        elif choice == "6":
            _run([sys.executable, "ares_watch.py"])
        elif choice == "7":
            r = _ask(c, "run dir:", "")
            if r:
                _run([sys.executable, "-m", "ares_setup.confidence", r])
        elif choice == "8":
            r = _ask(c, "run dir:", "")
            if r:
                _run([sys.executable, "-m", "ares_provenance", "verify", r])
        elif choice == "9":
            _profiles(c)
        else:
            print(c.gray("  choix inconnu.\n"))
        try:
            input(c.gray("  — entrée pour revenir au menu —"))
        except (EOFError, KeyboardInterrupt):
            print(); return 0


if __name__ == "__main__":
    sys.exit(home())
