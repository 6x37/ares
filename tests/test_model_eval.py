"""Structural tests for the model eval harness (no live model needed)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ares_setup.model_eval import EvalResult


def test_strix_ready_requires_tool_calls():
    r = EvalResult(model="x", tool_calls_ok=False, vuln_recall=1.0, eval_tok_s=100)
    assert not r.strix_ready          # great recall+speed but no tools => not ready
    r2 = EvalResult(model="y", tool_calls_ok=True)
    assert r2.strix_ready


def test_report_shows_verdict():
    r = EvalResult(model="m", tool_calls_ok=True, vuln_recall=0.66, eval_tok_s=40)
    txt = r.report()
    assert "STRIX-READY" in txt and "tool-calling" in txt
