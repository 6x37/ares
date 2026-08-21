"""Tests for air-gapped / --offline enforcement."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ares_setup.offline import (
    audit, harden, is_local_endpoint, is_local_model, _parse_env_file,
)

LOCAL = {
    "STRIX_LLM": "ollama/ares-qwen3-6-l55",
    "LLM_API_BASE": "http://localhost:11434",
    "LLM_API_KEY": "ollama-local",
    "STRIX_TELEMETRY": "0",
}
CLOUD = {
    "STRIX_LLM": "anthropic/claude-opus",
    "LLM_API_BASE": "https://api.anthropic.com",
    "ANTHROPIC_API_KEY": "sk-ant-xxx",
    "STRIX_TELEMETRY": "1",
}


def test_local_config_is_airgapped():
    assert audit(LOCAL).ok


def test_cloud_model_is_blocked():
    a = audit(CLOUD)
    assert not a.ok
    assert any("cloud provider" in b for b in a.blockers)


def test_cloud_endpoint_is_blocked():
    a = audit(CLOUD)
    assert any("loopback/private" in b for b in a.blockers)


def test_harden_disables_telemetry_and_strips_cloud_keys():
    dirty = {**LOCAL, "STRIX_TELEMETRY": "1", "PERPLEXITY_API_KEY": "pplx-xxx"}
    env, a = harden(dirty)
    assert env["STRIX_TELEMETRY"] == "0"
    assert "PERPLEXITY_API_KEY" not in env
    assert env.get("DO_NOT_TRACK") == "1"
    assert a.ok


def test_harden_cannot_fix_cloud_model():
    """A cloud model is an unfixable blocker — harden must not fake success."""
    _, a = harden(CLOUD)
    assert not a.ok


def test_endpoint_locality():
    assert is_local_endpoint("http://localhost:11434")
    assert is_local_endpoint("http://127.0.0.1:11434")
    assert is_local_endpoint("http://192.168.1.10:11434")   # private LAN
    assert is_local_endpoint(None)                          # unset -> local default
    assert not is_local_endpoint("https://api.openai.com")
    assert not is_local_endpoint("http://8.8.8.8:11434")


def test_model_locality():
    assert is_local_model("ollama/qwen3.6")
    assert is_local_model("ollama_chat/qwen3.6")
    assert not is_local_model("openai/gpt-5.4")
    assert not is_local_model(None)


def test_parse_env_file(tmp_path):
    p = tmp_path / "ares.env"
    p.write_text('# comment\nexport STRIX_LLM="ollama/x"\nexport STRIX_TELEMETRY="0"\n')
    env = _parse_env_file(str(p))
    assert env["STRIX_LLM"] == "ollama/x"
    assert env["STRIX_TELEMETRY"] == "0"
