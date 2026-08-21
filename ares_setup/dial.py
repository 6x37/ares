"""The Arès resource dial: one "power" level -> concrete engine parameters.

A single 0-100 dial (or a named preset) is mapped to the knobs that actually
govern local inference cost/throughput:

  num_ctx      context window (tokens)      -> memory + how much the agent can see
  num_parallel concurrent requests to Ollama-> how many agents run at once
  num_gpu      GPU layers offloaded         -> speed (all on Apple Silicon)
  reasoning    STRIX_REASONING_EFFORT       -> depth of agent thinking
  max_tool_calls_per_turn                   -> throttle on per-turn work

Higher context and parallelism cost memory, so we cap them against the machine's
usable memory and the chosen model's footprint. The dial never promises more
than the hardware can deliver.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

PRESETS = {"eco": 20, "balanced": 55, "max": 90}


@dataclass
class EngineConfig:
    level: int              # 0-100
    num_ctx: int
    num_parallel: int
    num_gpu: int            # -1 = offload all layers
    reasoning_effort: str   # low | medium | high
    max_tool_calls_per_turn: int

    def as_dict(self) -> dict:
        return asdict(self)


def _lerp(lo: float, hi: float, t: float) -> float:
    return lo + (hi - lo) * t


def resolve_level(level: "int | str") -> int:
    if isinstance(level, str):
        key = level.strip().lower()
        if key in PRESETS:
            return PRESETS[key]
        level = int(key)
    return max(0, min(100, int(level)))


def compute(
    level: "int | str",
    *,
    usable_gb: float,
    model_footprint_gb: float,
    apple_silicon: bool,
) -> EngineConfig:
    lvl = resolve_level(level)
    t = lvl / 100.0

    # Memory left for context/KV cache after the model weights.
    headroom_gb = max(usable_gb - model_footprint_gb, 1.0)

    # Context: 4k (eco) -> 32k (max), but capped by headroom.
    # Rough cost: a 32k context for a mid-size model is a few GB; budget ~4GB at
    # 32k and scale linearly, so ctx_cap ~ headroom/4 * 32k.
    ctx_target = int(_lerp(4096, 32768, t))
    ctx_cap = int(max(4096, min(32768, (headroom_gb / 4.0) * 32768)))
    num_ctx = min(ctx_target, ctx_cap)
    num_ctx = max(2048, (num_ctx // 1024) * 1024)  # snap to 1k

    # Parallel agents: 1 (eco) -> 4 (max), capped by headroom (each concurrent
    # request needs its own KV cache).
    par_target = int(round(_lerp(1, 4, t)))
    par_cap = max(1, int(headroom_gb // 4))  # ~4GB per extra parallel slot
    num_parallel = max(1, min(par_target, par_cap))

    # GPU layers: Apple Silicon offloads everything (-1). On other GPUs, scale
    # layers with the dial so a big model can partially offload on small VRAM.
    num_gpu = -1 if apple_silicon else (-1 if t >= 0.66 else 20 if t >= 0.33 else 8)

    reasoning = "low" if t < 0.34 else ("medium" if t < 0.67 else "high")
    max_calls = int(round(_lerp(12, 48, t)))

    return EngineConfig(
        level=lvl,
        num_ctx=num_ctx,
        num_parallel=num_parallel,
        num_gpu=num_gpu,
        reasoning_effort=reasoning,
        max_tool_calls_per_turn=max_calls,
    )
