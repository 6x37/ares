"""Shared terminal styling for the Arès CLI (banner, colors, spinner, bars).

Zero-dependency ANSI. All rendering degrades to plain text when stdout is not a
TTY or --no-color is set, so piping/CI output stays clean and the wizard stays
testable (tests drive `run()` with a plain log callback, never this module).
"""

from __future__ import annotations

import itertools
import sys
import threading
import time

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


class C:
    RESET = "\033[0m"; BOLD = "\033[1m"; DIM = "\033[2m"
    def __init__(self, on: bool): self.on = on
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


def render_banner(c: C) -> None:
    ramp = [52, 88, 124, 160, 196, 196]
    lines = BANNER.split("\n")
    solid = [l for l in lines if l.strip()]; n = max(len(solid), 1); idx = 0
    for ln in lines:
        if ln.strip():
            code = ramp[min(int(idx / max(n - 1, 1) * (len(ramp) - 1)), len(ramp) - 1)]
            print(c.c256(code, ln)); idx += 1
        else:
            print(ln)
    print("  " + c.gray("autonomous · local · signed") + "\n")


def styled_log(c: C):
    """Return a log(msg) that colorizes the wizard's known line shapes."""
    def log(msg: str) -> None:
        for line in str(msg).split("\n"):
            s = line.strip()
            if s.startswith("──") and s.endswith("──"):
                print("\n" + c.orange(c.bold(line)))
            elif s.startswith("✓"):
                print(c.green(line))
            elif s.startswith("✗"):
                print(c.red(line))
            elif s.startswith("⚠") or s.startswith("~"):
                print(c.gold(line))
            elif s.startswith("→") or s.startswith("↓"):
                print(c.cyan(line))
            elif s.startswith("●") or "AIR-GAPPED" in s:
                print(c.green(line))
            else:
                print(line)
    return log


class Spinner:
    FRAMES = ["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"]
    def __init__(self, c: C, label: str, on: bool = True):
        self.c = c; self.label = label; self.on = on
        self._stop = threading.Event(); self._t = None; self.start = time.time()
    def _run(self):
        for fr in itertools.cycle(self.FRAMES):
            if self._stop.is_set(): break
            el = time.time() - self.start
            sys.stdout.write("\r" + self.c.gold(fr) + " " + self.c.dim(f"{self.label} {el:4.1f}s"))
            sys.stdout.flush(); time.sleep(0.08)
    def __enter__(self):
        if self.on:
            self._t = threading.Thread(target=self._run, daemon=True); self._t.start()
        return self
    def __exit__(self, *a):
        self._stop.set()
        if self._t: self._t.join()
        if self.on:
            sys.stdout.write("\r\033[K"); sys.stdout.flush()


def bar(done: int, total: int, width: int = 28, c: "C | None" = None) -> str:
    total = max(total, 1); filled = int(width * done / total)
    b = "█" * filled + "░" * (width - filled)
    pct = f"{100*done//total:3d}%"
    return (c.green(b) + " " + c.gray(pct)) if c else f"{b} {pct}"
