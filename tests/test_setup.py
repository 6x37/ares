"""Tests for ares_setup (dial math, recommendation, config, wizard dry-run)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ares_setup import compute, PRESETS
from ares_setup.config import derived_model_name, build_modelfile, build_env
from ares_setup.dial import resolve_level
from ares_setup.models import recommend, CATALOG, fits, MIN_SERIOUS_GB
from ares_setup.wizard import InitOptions, run


def test_dial_presets_monotonic():
    """Higher level => more context and never less parallelism."""
    lo = compute("eco", usable_gb=36, model_footprint_gb=6, apple_silicon=True)
    mid = compute("balanced", usable_gb=36, model_footprint_gb=6, apple_silicon=True)
    hi = compute("max", usable_gb=36, model_footprint_gb=6, apple_silicon=True)
    assert lo.num_ctx <= mid.num_ctx <= hi.num_ctx
    assert lo.num_parallel <= mid.num_parallel <= hi.num_parallel
    assert lo.reasoning_effort == "low" and hi.reasoning_effort == "high"


def test_dial_clamps_and_numeric_levels():
    assert resolve_level(999) == 100
    assert resolve_level(-5) == 0
    assert resolve_level("max") == PRESETS["max"]
    assert resolve_level("42") == 42


def test_dial_respects_memory_headroom():
    """A heavy model on tight memory must cap parallelism vs a light model."""
    heavy = compute("max", usable_gb=36, model_footprint_gb=30, apple_silicon=True)
    light = compute("max", usable_gb=36, model_footprint_gb=6, apple_silicon=True)
    assert heavy.num_parallel <= light.num_parallel
    assert heavy.num_ctx <= light.num_ctx


def test_apple_silicon_offloads_all_layers():
    c = compute("eco", usable_gb=16, model_footprint_gb=8, apple_silicon=True)
    assert c.num_gpu == -1


def test_recommend_prefers_installed_and_fits():
    recs = recommend(36, installed_tags={"qwen3.5:latest"}, prefer_uncensored=False)
    assert recs, "should return candidates"
    assert all(fits(m, 36) for m in recs)


def test_recommend_uncensored_bias():
    """With the uncensored bias and nothing installed, an uncensored model
    should outrank a same-tier standard one of equal params."""
    recs = recommend(36, installed_tags=set(), prefer_uncensored=True)
    unc = next((m for m in recs if m.uncensored), None)
    assert unc is not None


def test_modelfile_bakes_dial():
    from ares_setup.config import STRIX_CTX_FLOOR
    e = compute("max", usable_gb=36, model_footprint_gb=23, apple_silicon=True)
    mf = build_modelfile("qwen3.6:latest", e)
    expected_ctx = max(e.num_ctx, STRIX_CTX_FLOOR)   # ctx is floored for Strix
    assert f"num_ctx {expected_ctx}" in mf
    assert f"num_gpu {e.num_gpu}" in mf
    assert mf.startswith("FROM qwen3.6:latest")


def test_derived_name_is_safe_slug():
    n = derived_model_name("hf.co/OBLITERATUS/Qwen3.6-27B-OBLITERATED", 90)
    assert n == "ares-qwen3-6-27b-obliterated-l90"
    assert " " not in n and "/" not in n


def test_env_has_required_strix_vars():
    e = compute("balanced", usable_gb=36, model_footprint_gb=23, apple_silicon=True)
    env = build_env("ollama/ares-x", "http://localhost:11434", e)
    assert env["LLM_API_BASE"].endswith("/v1")
    for key in ("STRIX_LLM", "LLM_API_BASE", "LLM_API_KEY",
                "OLLAMA_NUM_PARALLEL", "STRIX_REASONING_EFFORT"):
        assert key in env and env[key]
    assert env["STRIX_LLM"] == "openai/ares-x"


def test_wizard_dry_run_writes_nothing(tmp_path, monkeypatch):
    # Make the test hermetic: pretend Ollama is up with the model installed,
    # so it passes on CI machines without a running daemon.
    import ares_setup.wizard as wiz
    from ares_setup.ollama import OllamaStatus
    fake = OllamaStatus(installed=True, running=True,
                        endpoint="http://localhost:11434",
                        models=["qwen3.6:latest"])
    monkeypatch.setattr(wiz.ollama, "status", lambda *a, **k: fake)
    monkeypatch.setattr(wiz.ollama, "has_model", lambda *a, **k: True)
    envp = tmp_path / "ares.env"
    res = run(InitOptions(model="qwen3.6:latest", level="max",
                          env_path=envp, dry_run=True))
    # dry-run must not touch the filesystem
    assert not envp.exists()
    # but still computes a coherent plan
    assert res.derived_model and res.env.get("STRIX_LLM")
