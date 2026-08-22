"""Arès default model-cascade: route each agent role to the right-cost engine.

The session's empirical finding: on a laptop no single local model is at once
fast, reliable at tool-calling, and accurate at findings. So Arès ships a
**cascade** — cheap model for breadth, strong model for the calls that matter,
optional hosted model for the hardest step.

Tiers (default, local-first):
  triage    -> fast 14B (qwen3.5)                 : recon, crawling, mapping,
                                                     enumeration, cheap triage.
  validate  -> strong 27B (Qwen3.6 OBLITERATED)   : confirm a vuln, build the PoC,
                                                     write the vulnerability report.
  escalate  -> hosted frontier (opt-in, OFF)      : only when validate is unsure;
                                                     disabled by default to stay local.

Every local tier is baked at a >=48k context floor (Strix agent prompts ~40k).
WhiteRabbitNeo is deliberately NOT a tier: great security knowledge but emits
tool calls as text, so it breaks the agent loop. It belongs in the console.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CascadeTier:
    name: str
    role: str                 # what this tier is for
    model_tag: str            # ollama tag (base) to build the tier model from
    num_ctx: int
    reasoning: str            # low | medium | high
    when: str                 # routing rule (human-readable)
    enabled: bool = True
    hosted: bool = False      # True => calls a cloud provider (breaks air-gap)


# Chosen defaults, from this session's model characterization.
DEFAULT_CASCADE: list[CascadeTier] = [
    CascadeTier(
        name="triage",
        role="recon / crawl / map / enumerate / cheap triage",
        model_tag="qwen3.5:latest",
        num_ctx=49152,
        reasoning="low",
        when="default for exploration and breadth-first agent work",
    ),
    CascadeTier(
        name="validate",
        role="confirm vulnerability, build working PoC, write the report",
        model_tag="hf.co/OBLITERATUS/Qwen3.6-27B-OBLITERATED:Q4_K_M",
        num_ctx=49152,
        reasoning="medium",
        when="a triage agent flags a candidate finding, or before create_vulnerability_report",
    ),
    CascadeTier(
        name="escalate",
        role="hardest calls a local model is unsure about",
        model_tag="anthropic/claude-sonnet-5",
        num_ctx=200000,
        reasoning="high",
        when="validate confidence is low; OFF by default (opt-in, leaves the machine)",
        enabled=False,
        hosted=True,
    ),
]


def derived_name(tier: CascadeTier) -> str:
    import re
    base = tier.model_tag.split("/")[-1].split(":")[0].lower()
    base = re.sub(r"[^a-z0-9]+", "-", base).strip("-")
    return f"ares-cascade-{tier.name}-{base}"


def to_config(cascade: list[CascadeTier] | None = None) -> dict:
    cascade = cascade or DEFAULT_CASCADE
    return {
        "cascade_version": "ares-cascade/1",
        "policy": "local-first: run everything local; escalate to hosted only on "
                  "explicit opt-in.",
        "tiers": [
            {
                "name": t.name,
                "role": t.role,
                "base_model": t.model_tag,
                "engine_model": derived_name(t) if not t.hosted else t.model_tag,
                "num_ctx": t.num_ctx,
                "reasoning_effort": t.reasoning,
                "route_when": t.when,
                "enabled": t.enabled,
                "hosted": t.hosted,
                "air_gapped": not t.hosted,
            }
            for t in cascade
        ],
    }
