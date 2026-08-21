"""`ares init` — the guided local-LLM setup wizard.

Flow: detect hardware -> check Ollama -> recommend a model -> pick a resource
level -> (pull if needed) -> bake a derived model with the dial baked in ->
write ares.env -> print how to run. Fully scriptable via InitOptions for
non-interactive/CI use.
"""

from __future__ import annotations

from contextlib import nullcontext
from dataclasses import dataclass
from pathlib import Path

from . import config as cfg
from . import offline as offline_mod
from . import hardware, models, ollama
from .dial import compute


@dataclass
class InitOptions:
    model: str | None = None          # ollama base tag; None -> recommend/ask
    level: "int | str" = "balanced"   # dial preset or 0-100
    endpoint: str = ollama.DEFAULT_ENDPOINT
    env_path: Path = Path("ares.env")
    assume_yes: bool = False          # don't prompt; accept top recommendation
    dry_run: bool = False             # don't pull or `ollama create`
    prefer_uncensored: bool = True
    offline: bool = False


@dataclass
class InitResult:
    ok: bool
    hardware: hardware.Hardware
    chosen_model: str | None
    derived_model: str | None
    env: dict
    messages: list
    needs_pull: bool = False

    def report(self) -> str:
        return "\n".join(self.messages)


def _pick_model(hw, st, opts, log) -> "models.ModelSpec | None":
    installed = set(st.models)
    ranked = models.recommend(
        hw.usable_inference_gb, installed_tags=installed,
        prefer_uncensored=opts.prefer_uncensored,
    )
    if opts.model:
        spec = models.by_tag(opts.model)
        if spec is None:
            # unknown tag: accept it as a raw base, synth a minimal spec
            spec = models.ModelSpec(
                opts.model, opts.model, 0, min(hw.usable_inference_gb * 0.6, 8),
                False, "ok", "user-specified model")
        return spec
    # non-interactive / assume-yes: take best recommendation
    return ranked[0] if ranked else None


def run(opts: InitOptions, log=None, spinner=None) -> InitResult:
    msgs: list[str] = []
    log = log or msgs.append

    hw = hardware.detect()
    log("── Hardware ──")
    log(hw.summary())
    if hw.usable_inference_gb < models.MIN_SERIOUS_GB:
        log(f"⚠  Only ~{hw.usable_inference_gb:.0f} GB usable — real scans will be "
            "slow; expect to use a small model.")

    st = ollama.status(opts.endpoint)
    log("\n── Runtime ──")
    if not st.installed:
        log("✗ " + ollama.install_hint())
        return InitResult(False, hw, None, None, {}, msgs)
    if not st.running:
        log("✗ Ollama is installed but not running. Start it:  ollama serve")
        return InitResult(False, hw, None, None, {}, msgs)
    log(f"✓ Ollama running at {st.endpoint} · {len(st.models)} model(s) installed")

    spec = _pick_model(hw, st, opts, log)
    if spec is None:
        log("✗ No suitable model found.")
        return InitResult(False, hw, None, None, {}, msgs)

    already = ollama.has_model(spec.ollama_tag, st)
    log("\n── Model ──")
    log(f"→ {spec.display}  (~{spec.approx_gb:.0f} GB, {spec.agentic} agentic"
        f"{', uncensored' if spec.uncensored else ''})")
    log(f"  {spec.note}")
    if not already:
        log(f"  ↓ not installed — will pull `{spec.ollama_tag}`")

    engine = compute(
        opts.level, usable_gb=hw.usable_inference_gb,
        model_footprint_gb=spec.approx_gb, apple_silicon=hw.apple_silicon,
    )
    log("\n── Resource dial ──")
    log(f"  level {engine.level}: context={engine.num_ctx} tokens · "
        f"{engine.num_parallel} parallel agent(s) · reasoning={engine.reasoning_effort}")

    if opts.dry_run:
        derived = cfg.derived_model_name(spec.ollama_tag, engine.level)
        env = cfg.build_env(f"ollama/{derived}", opts.endpoint, engine)
        if opts.offline:
            env, audit = offline_mod.harden(env)
            log("\n── Air-gapped mode (dry-run) ──")
            log(audit.report())
        log("\n(dry-run: no pull, no ollama create, no files written)")
        return InitResult(True, hw, spec.ollama_tag, derived, env, msgs,
                          needs_pull=not already)

    if not already:
        log(f"\nPulling {spec.ollama_tag} …")
        rc = ollama.pull(spec.ollama_tag)
        if rc != 0:
            log("✗ pull failed.")
            return InitResult(False, hw, spec.ollama_tag, None, {}, msgs)

    log("\nBaking derived model with dial settings …")
    _spin = spinner("baking derived model") if spinner else nullcontext()
    with _spin:
        derived = cfg.create_derived_model(spec.ollama_tag, engine)
    log(f"✓ created `{derived}`")

    env = cfg.build_env(f"ollama/{derived}", opts.endpoint, engine)
    if opts.offline:
        env, audit = offline_mod.harden(env)
        log("\n── Air-gapped mode ──")
        log(audit.report())
        if not audit.ok:
            log("✗ cannot guarantee offline mode — aborting.")
            return InitResult(False, hw, spec.ollama_tag, derived, env, msgs)
        log("\n" + offline_mod.docker_offline_hint(opts.endpoint))
    path = cfg.write_env_file(env, opts.env_path)
    log(f"✓ wrote {path}")

    log("\n── Ready ──")
    log(f"  source {opts.env_path}")
    log("  strix --target ./your-app        # runs fully local, no API cost")
    return InitResult(True, hw, spec.ollama_tag, derived, env, msgs,
                      needs_pull=False)
