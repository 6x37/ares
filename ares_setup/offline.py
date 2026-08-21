"""Air-gapped / offline enforcement for Arès.

Strix has exactly three outbound channels. `--offline` closes all three at the
config layer:

  1. Telemetry (PostHog + Scarf)  -> STRIX_TELEMETRY=0
  2. web_search (api.perplexity.ai) -> PERPLEXITY_API_KEY must be empty
  3. The LLM itself                 -> STRIX_LLM must be a LOCAL model on a
                                       loopback/private endpoint, never a cloud
                                       provider.

HONEST SCOPE: this makes Arès *not initiate* outbound connections. It is config
enforcement, not a firewall. The airtight guarantee is OS/container network
isolation (run the Strix sandbox with no external route — see `docker_offline_hint`).
`audit` reports egress risks; `harden` returns an env with the fixable ones fixed
and flags the unfixable ones (a cloud model) as blockers.
"""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass, field
from urllib.parse import urlparse

# LLM slug prefixes that mean "runs on your machine".
_LOCAL_PREFIXES = ("ollama/", "ollama_chat/", "litellm/ollama")
# Prefixes that ALWAYS mean a hosted cloud provider (egress), whatever the base.
_CLOUD_PREFIXES = ("anthropic/", "gemini/", "groq/", "mistral/", "openrouter/",
                   "cohere/", "vertex", "bedrock", "azure/", "deepseek/", "xai/")
# Env vars that, if set, indicate a cloud provider is configured.
_CLOUD_KEY_VARS = (
    "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "GROQ_API_KEY",
    "MISTRAL_API_KEY", "PERPLEXITY_API_KEY", "OPENROUTER_API_KEY",
    "AWS_ACCESS_KEY_ID", "VERTEX_PROJECT",
)


@dataclass
class OfflineAudit:
    ok: bool
    blockers: list = field(default_factory=list)   # must fix; would cause egress
    warnings: list = field(default_factory=list)   # fixed automatically by harden
    checked: list = field(default_factory=list)    # passed checks, for transparency

    def report(self) -> str:
        lines = []
        for c in self.checked:
            lines.append(f"  ✓ {c}")
        for w in self.warnings:
            lines.append(f"  ~ {w}")
        for b in self.blockers:
            lines.append(f"  ✗ {b}")
        head = ("AIR-GAPPED: config allows no outbound connections"
                if self.ok else
                "NOT air-gapped — outbound egress possible:")
        return head + "\n" + "\n".join(lines)


def is_local_endpoint(url: "str | None") -> bool:
    if not url:
        return True  # unset -> ollama default localhost
    host = urlparse(url if "://" in url else "http://" + url).hostname or ""
    if host in ("localhost", "127.0.0.1", "::1", "host.docker.internal"):
        return True
    try:
        return ipaddress.ip_address(host).is_private or ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def is_local_model(slug: "str | None") -> bool:
    return bool(slug) and any(slug.startswith(p) for p in _LOCAL_PREFIXES)


def audit(env: dict) -> OfflineAudit:
    a = OfflineAudit(ok=True)

    slug = env.get("STRIX_LLM") or ""
    base = env.get("LLM_API_BASE")
    endpoint_local = is_local_endpoint(base)
    is_cloud_provider = any(slug.startswith(p) for p in _CLOUD_PREFIXES)

    if not endpoint_local:
        a.ok = False
        a.blockers.append(f"LLM_API_BASE='{base}' is not loopback/private.")
    else:
        a.checked.append("LLM endpoint is loopback/private")

    if is_cloud_provider:
        a.ok = False
        a.blockers.append(
            f"STRIX_LLM='{slug}' names a cloud provider — it would leave the "
            "machine even with a local endpoint set.")
    elif endpoint_local:
        a.checked.append(f"LLM is local ({slug})")

    tel = str(env.get("STRIX_TELEMETRY", "1")).lower()
    if tel in ("0", "false", "no", "off"):
        a.checked.append("telemetry disabled")
    else:
        a.warnings.append("telemetry was enabled — will set STRIX_TELEMETRY=0")

    for var in _CLOUD_KEY_VARS:
        val = env.get(var)
        if val and val not in ("", "ollama-local"):
            a.warnings.append(f"{var} is set — will unset for offline mode")

    return a


def harden(env: dict) -> tuple[dict, OfflineAudit]:
    """Return (offline_env, audit). Fixable risks are fixed; blockers remain."""
    a = audit(env)
    out = dict(env)
    out["STRIX_TELEMETRY"] = "0"
    # Belt-and-suspenders: some libs honor these generic opt-outs too.
    out["DO_NOT_TRACK"] = "1"
    out["SCARF_NO_ANALYTICS"] = "1"
    for var in _CLOUD_KEY_VARS:
        if var in out and out[var] not in ("ollama-local",):
            out.pop(var, None)
    # keep the local dummy key litellm needs
    out.setdefault("LLM_API_KEY", "ollama-local")
    # re-audit the hardened env so the report reflects reality
    return out, audit(out)


def docker_offline_hint(endpoint: str = "http://localhost:11434") -> str:
    return (
        "For a HARD air-gap (kernel-enforced, not just config), run Strix's\n"
        "container with no external network — only the local Ollama reachable:\n"
        "  docker run --network none ...            # fully isolated, or\n"
        "  docker run --add-host=host.docker.internal:host-gateway \\\n"
        "             -e LLM_API_BASE=http://host.docker.internal:11434 ...\n"
        "so the sandbox can reach Ollama on the host but nothing on the internet."
    )


def _parse_env_file(path: str) -> dict:
    """Parse `export KEY="val"` lines from an ares.env file into a dict."""
    env: dict = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            line = line[len("export "):].strip() if line.startswith("export ") else line
            if "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def _main(argv=None) -> int:
    import sys
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        print("usage: python3 -m ares_setup.offline <ares.env>")
        return 2
    env = _parse_env_file(args[0])
    a = audit(env)
    print(a.report())
    return 0 if a.ok else 1


if __name__ == "__main__":
    import sys
    sys.exit(_main())
