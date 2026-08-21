#!/usr/bin/env python3
"""Arès — a branded, streaming console for the local pentest engine.

Zero external deps (stdlib only). Streams tokens live from Ollama's
OpenAI-compatible endpoint, shows a spinner while a reasoning model thinks, then
types out the answer. Slash-commands bridge the provenance + offline modules.

  python3 ares_console.py                 # interactive REPL
  python3 ares_console.py --once "..."    # one-shot
"""
from __future__ import annotations

import argparse
import itertools
import json
import os
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path


class C:
    RESET = "\033[0m"; BOLD = "\033[1m"; DIM = "\033[2m"
    def __init__(self, on): self.on = on
    def _w(self, code, s): return f"{code}{s}{self.RESET}" if self.on else s
    def c256(self, code, s): return self._w(f"\033[38;5;{code}m", s)
    def red(self, s):    return self.c256(196, s)
    def orange(self, s): return self.c256(208, s)
    def gold(self, s):   return self.c256(220, s)
    def cyan(self, s):   return self.c256(44, s)
    def green(self, s):  return self.c256(42, s)
    def gray(self, s):   return self.c256(244, s)
    def bold(self, s):   return self._w(self.BOLD, s)
    def dim(self, s):    return self._w(self.DIM, s)


BANNER = r"""
     /####                                      
    /  ###                                      
       /##                                      
      /  ##                                     
      /  ##     ###  /###     /##       /###    
     /    ##     ###/ #### / / ###     / #### / 
     /    ##      ##   ###/ /   ###   ##  ###/  
    /      ##     ##       ##    ### ####       
    /########     ##       ########    ###      
   /        ##    ##       #######       ###    
   #        ##    ##       ##              ###  
  /####      ##   ##       ####    /  /###  ##  
 /   ####    ## / ###       ######/  / #### /   
/     ##      #/   ###       #####      ###/    
#                                               
 ##                                             
"""

COMMANDS = [
    ("/help",            "show this command list"),
    ("/status",          "engine, endpoint & air-gap status"),
    ("/offline",         "audit ares.env for any outbound egress"),
    ("/model [tag]",     "show or switch the local model for this session"),
    ("/think",           "toggle showing the model's reasoning live"),
    ("/verify <dir>",    "verify a signed Arès report directory"),
    ("/sign <dir>",      "sign a report directory (Ed25519)"),
    ("/profile <name>",  "switch engine profile (default | offensive | …)"),
    ("/save <file>",     "save the last answer to a file"),
    ("/clear",           "clear the screen"),
    ("/quit",            "exit the console"),
]


def profile_path(name: str) -> Path:
    return Path("ares.env") if name in ("default", "") else Path(f"ares-{name}.env")


def load_env(path: Path) -> dict:
    env = dict(os.environ)
    if path.exists():
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[7:]
            if "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    return env


class Spinner:
    FRAMES = ["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"]
    def __init__(self, c, label):
        self.c = c; self.label = label
        self._stop = threading.Event(); self._t = None; self.start = time.time()
    def _run(self):
        for fr in itertools.cycle(self.FRAMES):
            if self._stop.is_set(): break
            el = time.time() - self.start
            sys.stdout.write("\r" + self.c.gold(fr) + " " + self.c.dim(f"{self.label} {el:4.1f}s"))
            sys.stdout.flush(); time.sleep(0.08)
    def __enter__(self):
        self._t = threading.Thread(target=self._run, daemon=True); self._t.start(); return self
    def __exit__(self, *a):
        self._stop.set()
        if self._t: self._t.join()
        sys.stdout.write("\r\033[K"); sys.stdout.flush()


def stream_chat(env, prompt, c, *, model=None, show_thinking=False) -> str:
    model = model or env.get("STRIX_LLM", "ollama/qwen3.6:latest").split("/", 1)[-1]
    base = env.get("LLM_API_BASE", "http://localhost:11434").rstrip("/")
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 4096, "stream": True,
    }).encode()
    req = urllib.request.Request(f"{base}/v1/chat/completions", data=body,
                                 headers={"Content-Type": "application/json"})
    answer = []
    answered = False
    thinking_open = False
    spinner = Spinner(c, "Arès réfléchit…"); spinner.__enter__()
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            for raw in resp:
                line = raw.decode("utf-8").strip()
                if not line.startswith("data:"): continue
                data = line[5:].strip()
                if data == "[DONE]": break
                try:
                    delta = json.loads(data)["choices"][0]["delta"]
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue
                think = delta.get("reasoning") or ""
                if think and show_thinking and not answered:
                    if not thinking_open:
                        spinner.__exit__()
                        sys.stdout.write(c.gray("╭─ thinking\n") + c.gray("│ "))
                        thinking_open = True
                    sys.stdout.write(c.dim(think.replace("\n", "\n" + c.gray("│ "))))
                    sys.stdout.flush()
                chunk = delta.get("content") or ""
                if chunk:
                    if thinking_open:
                        sys.stdout.write("\n" + c.gray("╰─\n")); thinking_open = False
                    if not answered:
                        if not show_thinking: spinner.__exit__()
                        sys.stdout.write(c.green(c.bold("╭─ Arès\n")) + c.green("│ "))
                        answered = True
                    answer.append(chunk)
                    sys.stdout.write(chunk.replace("\n", "\n" + c.green("│ "))); sys.stdout.flush()
    except Exception as e:  # noqa: BLE001
        if not answered and not thinking_open: spinner.__exit__()
        print(c.red(f"\n✗ erreur: {e}")); return ""
    if not answered:
        if not thinking_open: spinner.__exit__()
        print(c.gray("(pas de contenu — budget épuisé en réflexion, réessaie)"))
    else:
        sys.stdout.write("\n" + c.green("╰─\n"))
    sys.stdout.flush()
    return "".join(answer).strip()


def render_banner(c):
    ramp = [52, 88, 124, 160, 196, 196]
    lines = BANNER.split("\n")
    solid = [l for l in lines if l.strip()]; n = max(len(solid), 1); idx = 0
    for ln in lines:
        if ln.strip():
            code = ramp[min(int(idx / max(n - 1, 1) * (len(ramp) - 1)), len(ramp) - 1)]
            print(c.c256(code, ln)); idx += 1
        else:
            print(ln)


def status_block(env, c, model=None, profile=None):
    model = model or env.get("STRIX_LLM", "?").split("/", 1)[-1]
    base = env.get("LLM_API_BASE", "?")
    offline = str(env.get("STRIX_TELEMETRY", "1")).lower() in ("0", "false", "off")
    badge = c.green("● AIR-GAPPED") if offline else c.gold("○ online")
    local = base.startswith(("http://localhost", "http://127."))
    loc = c.green("local") if local else c.red("remote")
    if profile:
        tag = c.red("offensive") if profile != "default" else c.green("default")
        print("  " + c.bold("profile  ") + tag)
    print("  " + c.bold("engine   ") + c.cyan(model))
    print("  " + c.bold("endpoint ") + f"{base} ({loc})   " + badge)


def print_help(c):
    print(c.orange(c.bold("\n  commandes\n")))
    for name, desc in COMMANDS:
        print("  " + c.cyan(f"{name:<16}") + c.gray(desc))
    print(c.gray("\n  …ou tape simplement ta question.\n"))


def cmd_offline(env, c):
    try:
        from ares_setup.offline import audit
    except Exception as e:  # noqa: BLE001
        print(c.red(f"module offline indisponible: {e}")); return
    print(); print(audit(env).report()); print()


def cmd_provenance(action, arg, c):
    if not arg:
        print(c.red(f"usage: /{action} <dir>")); return
    rc = subprocess.run([sys.executable, "-m", "ares_provenance", action, arg]).returncode
    print(c.green("✓ ok") if rc == 0 else c.red(f"✗ exit {rc}"))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", default=None)
    ap.add_argument("--env", default=None, type=Path)
    ap.add_argument("--profile", default="default")
    ap.add_argument("--no-color", action="store_true")
    args = ap.parse_args(argv)
    c = C(on=not args.no_color and sys.stdout.isatty())
    env_path = args.env or profile_path(args.profile)
    env = load_env(env_path)
    profile = args.profile

    if args.once is not None:
        stream_chat(env, args.once, c); return 0

    render_banner(c)
    print("  " + c.gray("autonomous · local · signed"))
    status_block(env, c, profile=profile)
    print(c.gray("  /help pour les commandes · /quit pour sortir\n"))

    state = {"model": None, "think": False, "last": "", "profile": profile}
    while True:
        try:
            q = input(c.orange(c.bold("⟩ "))).strip()
        except (EOFError, KeyboardInterrupt):
            print(c.gray("\nbye.")); return 0
        if not q:
            continue
        if q.startswith("/"):
            parts = q.split(maxsplit=1); cmd = parts[0]; arg = parts[1] if len(parts) > 1 else ""
            if cmd in ("/quit", "/exit", "/q"):
                print(c.gray("bye.")); return 0
            elif cmd in ("/help", "/?", "/h"):
                print_help(c)
            elif cmd == "/status":
                print(); status_block(env, c, state["model"], state["profile"]); print()
            elif cmd == "/offline":
                cmd_offline(env, c)
            elif cmd == "/model":
                if arg:
                    state["model"] = arg; print(c.green(f"→ modèle: {arg}"))
                else:
                    print(c.cyan(state["model"] or env.get("STRIX_LLM", "?").split("/", 1)[-1]))
            elif cmd == "/think":
                state["think"] = not state["think"]
                print(c.gray(f"réflexion affichée: {'oui' if state['think'] else 'non'}"))
            elif cmd in ("/verify", "/sign"):
                cmd_provenance(cmd[1:], arg, c)
            elif cmd == "/profile":
                if not arg:
                    print(c.cyan(state["profile"]))
                else:
                    np = profile_path(arg)
                    if not np.exists():
                        print(c.red(f"profil introuvable: {np} — lance `ares init --profile {arg}`"))
                    else:
                        env = load_env(np); state["profile"] = arg; state["model"] = None
                        print(c.green(f"→ profil: {arg}")); status_block(env, c, profile=arg)
            elif cmd == "/save":
                if not arg:
                    print(c.red("usage: /save <fichier>"))
                elif not state["last"]:
                    print(c.red("rien à sauver — pose d'abord une question"))
                else:
                    Path(arg).write_text(state["last"], encoding="utf-8")
                    print(c.green(f"✓ écrit {arg}"))
            elif cmd == "/clear":
                sys.stdout.write("\033[2J\033[H"); render_banner(c); status_block(env, c, state["model"], state["profile"]); print()
            else:
                print(c.red(f"commande inconnue: {cmd}") + c.gray("  (/help)"))
            continue
        print()
        ans = stream_chat(env, q, c, model=state["model"], show_thinking=state["think"])
        if ans: state["last"] = ans
        print()


if __name__ == "__main__":
    sys.exit(main())
