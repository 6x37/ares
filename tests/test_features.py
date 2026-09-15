"""Tests for the Tier-2 features: guardrails, diff, compliance."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ares_setup.guardrails import check_scope, needs_approval, arm_kill_switch, clear_kill_switch, is_killed
from ares_setup.diff import diff_runs
from ares_setup.compliance import map_run, to_markdown


def test_scope_blocks_metadata():
    assert not check_scope("http://169.254.169.254/latest/").allowed

def test_scope_blocks_private_ip():
    assert not check_scope("http://192.168.1.10:8080").allowed

def test_scope_allows_public():
    assert check_scope("https://testphp.vulnweb.com").allowed

def test_scope_allowlist():
    assert check_scope("https://a.vulnweb.com", allowlist=["vulnweb.com"]).allowed
    assert not check_scope("https://evil.com", allowlist=["vulnweb.com"]).allowed

def test_internal_allowed_when_authorized():
    assert check_scope("http://10.0.0.5", allow_internal=True).allowed

def test_approval_gate_flags_destructive():
    assert needs_approval("rm -rf /data")
    assert needs_approval("DROP TABLE users")
    assert not needs_approval("read /etc/passwd")

def test_kill_switch(tmp_path, monkeypatch):
    import ares_setup.guardrails as g
    monkeypatch.setattr(g, "KILL_FILE", tmp_path / "KILL")
    assert not g.is_killed()
    g.arm_kill_switch(); assert g.is_killed()
    g.clear_kill_switch(); assert not g.is_killed()

def _run(tmp, vulns):
    r = tmp; r.mkdir(exist_ok=True)
    (r / "vulnerabilities.json").write_text(json.dumps(vulns))
    return r

def test_diff_new_and_fixed(tmp_path):
    old = _run(tmp_path / "old", [{"title": "SQLi", "endpoint": "/login", "severity": "high"}])
    new = _run(tmp_path / "new", [{"title": "XSS", "endpoint": "/search", "severity": "medium"}])
    d = diff_runs(old, new)
    assert len(d.new) == 1 and len(d.fixed) == 1

def test_compliance_maps_sqli(tmp_path):
    run = _run(tmp_path / "r", [{"title": "SQL Injection on login", "severity": "high"}])
    rows = map_run(run)
    assert rows and rows[0]["controls"].get("PCI-DSS")
    assert "PCI-DSS" in to_markdown(run)


def test_scope_blocks_hostname_resolving_internal():
    # localhost / host.docker.internal resolve to loopback → must be blocked
    assert not check_scope("http://localhost:3000").allowed
    assert not check_scope("http://host.docker.internal:3000").allowed
    # ...unless explicitly authorized for an internal engagement
    assert check_scope("http://localhost:3000", allow_internal=True).allowed


def test_verify_message_distinguishes_trust(tmp_path):
    """Unpinned verify says INTACT (integrity), pinned says VERIFIED (authentic)."""
    import json
    from ares_provenance import (generate_keypair, save_keypair, load_private_key,
                                  load_public_key, sign_run, verify_run)
    from ares_provenance.keys import PRIV_NAME, PUB_NAME
    run = tmp_path / "run"; (run / "vulnerabilities").mkdir(parents=True)
    (run / "penetration_test_report.md").write_text("# r\n", encoding="utf-8")
    (run / "vulnerabilities.json").write_text("[]", encoding="utf-8")
    keys = tmp_path / "k"; save_keypair(generate_keypair(), key_dir=keys)
    sign_run(run, load_private_key(keys / PRIV_NAME))
    assert "INTACT" in verify_run(run).summary()
    pinned = verify_run(run, expected_public_key=load_public_key(keys / PUB_NAME))
    assert "VERIFIED" in pinned.summary() and pinned.ok
