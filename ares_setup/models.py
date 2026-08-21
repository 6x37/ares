"""Local-model catalog + recommendation for Arès.

We recommend the *largest capable model that fits* in the machine's usable
inference memory, leaving headroom for the context/KV cache. For pentesting we
prefer models that won't refuse security tasks (uncensored / abliterated), since
refusals cripple an offensive agent. Already-installed models are preferred so
the user doesn't re-download gigabytes.

Footprints are approximate (GGUF-style quantization) and marked as such — they
guide selection, they are not exact.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ModelSpec:
    ollama_tag: str        # what `ollama pull` expects
    display: str
    params_b: float        # billions of parameters
    approx_gb: float       # approx memory footprint at its default quant
    uncensored: bool       # won't refuse security tasks
    agentic: str           # tool-use quality: "strong" | "ok" | "weak"
    note: str


# Curated for security/agentic use. Footprints approximate.
CATALOG: list[ModelSpec] = [
    ModelSpec("qwen3.6:latest", "Qwen3.6 (27B-class)", 27, 23,
              False, "strong", "Best all-round agentic reasoning; heavy."),
    ModelSpec("hf.co/OBLITERATUS/Qwen3.6-27B-OBLITERATED:Q4_K_M", "Qwen3.6 27B OBLITERATED",
              27, 16, True, "strong",
              "Uncensored Qwen3.6 (Q4_K_M) — no refusals, ideal for offensive tasks."),
    ModelSpec("qwen3.5:latest", "Qwen3.5", 14, 6.6,
              False, "strong", "Great balance of quality and footprint."),
    ModelSpec("mistral:latest", "Mistral 7B", 7, 4.4,
              False, "ok", "Light, fast, decent general model."),
    ModelSpec("smollm2:1.7b", "SmolLM2 1.7B", 1.7, 1.8,
              False, "weak", "Tiny — triage/smoke-test only, not for real scans."),
]

# Fraction of usable memory a model may occupy; the rest is context/KV headroom.
_FOOTPRINT_BUDGET = 0.80
# Below this many GB usable, warn that real scans will be painful.
MIN_SERIOUS_GB = 8.0


def by_tag(tag: str) -> ModelSpec | None:
    for m in CATALOG:
        if m.ollama_tag == tag:
            return m
    return None


def fits(spec: ModelSpec, usable_gb: float) -> bool:
    return spec.approx_gb <= usable_gb * _FOOTPRINT_BUDGET


def recommend(
    usable_gb: float,
    *,
    installed_tags: set[str] | None = None,
    prefer_uncensored: bool = True,
) -> list[ModelSpec]:
    """Return candidate models best-first for this machine.

    Ranking: fits-in-memory, then already-installed, then (optionally)
    uncensored, then more parameters, then smaller footprint as tiebreak.
    """
    installed = installed_tags or set()

    def score(m: ModelSpec) -> tuple:
        return (
            fits(m, usable_gb),                       # must fit
            m.ollama_tag in installed,                # no re-download
            prefer_uncensored and m.uncensored,       # pentest-friendly
            {"strong": 2, "ok": 1, "weak": 0}[m.agentic],
            m.params_b,                               # bigger = smarter
            -m.approx_gb,                             # lighter tiebreak
        )

    ranked = sorted(CATALOG, key=score, reverse=True)
    return [m for m in ranked if fits(m, usable_gb)] or ranked
