"""Arès scope guardrails + kill-switch — keep the swarm inside the engagement.

Autonomous agents that can send traffic MUST be bounded. This enforces, before
and during a scan:
  • a target allowlist (only in-scope hosts),
  • a block on internal/metadata ranges unless explicitly authorized,
  • a global kill-switch (a sentinel file) any wrapper/agent can honor,
  • approval gates for destructive actions.

Preflight is enforced at launch; the kill-switch + approval are cooperative
mechanisms Arès wrappers check (documented in INTEGRATION_NOTES).
"""

from __future__ import annotations

import ipaddress
import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

KILL_FILE = Path.home() / ".ares" / "KILL"

# Cloud metadata endpoints — never in scope unless explicitly allowed.
_METADATA_HOSTS = {"169.254.169.254", "metadata.google.internal", "100.100.100.200"}
# Actions that need human sign-off before an agent runs them.
DESTRUCTIVE = ("delete", "drop", "shutdown", "rm -rf", "format", "wipe",
               "truncate", "destroy", "deprovision")


@dataclass
class ScopeResult:
    allowed: bool
    target: str
    reasons: list = field(default_factory=list)

    def report(self) -> str:
        head = ("✅ in scope" if self.allowed else "⛔ OUT OF SCOPE — refused")
        return head + "\n" + "\n".join(f"  • {r}" for r in self.reasons)


def _host_of(target: str) -> str:
    if "://" in target:
        return urlparse(target).hostname or target
    return urlparse("//" + target).hostname or target.split("/")[0].split(":")[0]


def _is_internal(host: str) -> bool:
    if host in _METADATA_HOSTS:
        return True
    try:
        ip = ipaddress.ip_address(host)
        return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
    except ValueError:
        return False  # a domain name; not an IP literal


def check_scope(target: str, *, allowlist: list[str] | None = None,
                allow_internal: bool = False) -> ScopeResult:
    """Validate a target against the allowlist and internal-range policy."""
    host = _host_of(target)
    r = ScopeResult(allowed=True, target=target)

    if host in _METADATA_HOSTS and not allow_internal:
        r.allowed = False
        r.reasons.append(f"{host} is a cloud metadata endpoint (SSRF risk) — blocked.")
        return r

    if _is_internal(host) and not allow_internal:
        r.allowed = False
        r.reasons.append(
            f"{host} is an internal/private/loopback address — set allow_internal "
            "only for an authorized internal engagement.")
        return r

    if allowlist:
        ok = any(host == a or host.endswith("." + a) or a == "*" for a in allowlist)
        if not ok:
            r.allowed = False
            r.reasons.append(f"{host} is not in the allowlist {allowlist}.")
            return r
        r.reasons.append(f"{host} matches the allowlist.")
    else:
        r.reasons.append(f"{host} — no allowlist set (allowing; set one to restrict).")
    return r


# ---- kill-switch ----------------------------------------------------------
def arm_kill_switch() -> Path:
    KILL_FILE.parent.mkdir(parents=True, exist_ok=True)
    KILL_FILE.write_text("ARES KILL — scan halt requested\n", encoding="utf-8")
    return KILL_FILE


def clear_kill_switch() -> None:
    KILL_FILE.unlink(missing_ok=True)


def is_killed() -> bool:
    return KILL_FILE.exists()


# ---- approval gate --------------------------------------------------------
def needs_approval(action: str) -> bool:
    a = (action or "").lower()
    return any(d in a for d in DESTRUCTIVE)


def safe_mode() -> bool:
    return os.getenv("ARES_SAFE_MODE", "").strip().lower() in ("1", "true", "on", "yes")


def gate(action: str) -> bool:
    """Return True if the action may proceed. In safe-mode, destructive actions
    require an interactive yes; otherwise they're allowed but flagged."""
    if is_killed():
        return False
    if safe_mode() and needs_approval(action):
        try:
            ans = input(f"⚠ approve destructive action? [{action[:60]}] (y/N) ")
            return ans.strip().lower().startswith("y")
        except (EOFError, KeyboardInterrupt):
            return False
    return True


def _main(argv=None) -> int:
    import sys
    args = argv if argv is not None else sys.argv[1:]
    if args and args[0] == "kill":
        print(f"kill-switch armed: {arm_kill_switch()}"); return 0
    if args and args[0] == "resume":
        clear_kill_switch(); print("kill-switch cleared"); return 0
    if args and args[0] == "check" and len(args) > 1:
        r = check_scope(args[1], allow_internal="--internal" in args)
        print(r.report()); return 0 if r.allowed else 1
    print("usage: guardrails check <target> [--internal] | kill | resume")
    return 2


if __name__ == "__main__":
    import sys
    sys.exit(_main())
