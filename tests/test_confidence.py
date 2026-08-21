"""Tests for the Arès confidence gate (anti-hallucination)."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ares_setup.confidence import assess, annotate_report


def _mk(tmp, log, vulns):
    run = tmp / "run"; run.mkdir()
    (run / "strix.log").write_text(log, encoding="utf-8")
    (run / "vulnerabilities.json").write_text(json.dumps(vulns), encoding="utf-8")
    (run / "penetration_test_report.md").write_text("# Report\n", encoding="utf-8")
    return run


def test_findings_present_is_high(tmp_path):
    run = _mk(tmp_path, "Starting turn 1\nTool read_file completed\n", [{"id": "V1"}])
    assert assess(run).verdict == "HIGH"


def test_zero_findings_no_work_is_low(tmp_path):
    log = "Starting turn 1\n" * 6 + "ended a turn without a lifecycle tool call\n"
    run = _mk(tmp_path, log, [])
    c = assess(run)
    assert c.verdict == "LOW"
    assert c.files_read == 0


def test_zero_findings_real_work_is_ok(tmp_path):
    log = ("Starting turn 1\n" +
           "Tool read_file completed\n" * 3 +
           "read_file app.py\n" +
           "Tool http_request completed\n" * 4)
    run = _mk(tmp_path, log, [])
    c = assess(run)
    assert c.verdict == "OK"
    assert c.tool_actions >= 5 and c.files_read >= 1


def test_annotate_is_idempotent(tmp_path):
    run = _mk(tmp_path, "Starting turn 1\n", [])
    annotate_report(run); annotate_report(run)
    text = (run / "penetration_test_report.md").read_text()
    assert text.count("Arès confidence assessment") == 1


def test_low_confidence_warning_in_markdown(tmp_path):
    run = _mk(tmp_path, "Starting turn 1\n", [])
    md = assess(run).to_markdown()
    assert "not" in md.lower() and "🔴" in md
