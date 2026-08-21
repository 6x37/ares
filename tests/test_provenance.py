"""Tests for Arès provenance signing. Run: python3 -m pytest tests/ -v"""
import json
import shutil
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ares_provenance import (
    generate_keypair, save_keypair, load_private_key, load_public_key,
    sign_run, verify_run,
)
from ares_provenance.keys import PRIV_NAME, PUB_NAME


@pytest.fixture
def signed_run(tmp_path):
    run = tmp_path / "run"
    (run / "vulnerabilities").mkdir(parents=True)
    (run / "penetration_test_report.md").write_text(
        "# Security Penetration Test Report\n\n1 critical SQLi.\n", encoding="utf-8")
    (run / "vulnerabilities" / "VULN-001.md").write_text(
        "# SQLi\n**Severity:** CRITICAL\n", encoding="utf-8")
    (run / "vulnerabilities.json").write_text(
        json.dumps([{"id": "VULN-001"}]), encoding="utf-8")
    keys = tmp_path / "keys"
    save_keypair(generate_keypair(), key_dir=keys)
    priv = load_private_key(keys / PRIV_NAME)
    pub = load_public_key(keys / PUB_NAME)
    sign_run(run, priv, engine={"model": "qwen3.6-27b", "execution": "local"})
    return run, pub, keys


def test_fresh_signature_verifies(signed_run):
    run, pub, _ = signed_run
    assert verify_run(run, expected_public_key=pub).ok


def test_content_tamper_detected(signed_run):
    run, pub, _ = signed_run
    f = run / "vulnerabilities" / "VULN-001.md"
    f.write_text(f.read_text().replace("CRITICAL", "LOW"), encoding="utf-8")
    r = verify_run(run, expected_public_key=pub)
    assert not r.ok
    assert "vulnerabilities/VULN-001.md" in r.tampered


def test_footer_removal_detected(signed_run):
    run, pub, _ = signed_run
    rep = run / "penetration_test_report.md"
    rep.write_text(rep.read_text().split("<!-- ARES-PROVENANCE:BEGIN -->")[0],
                   encoding="utf-8")
    r = verify_run(run, expected_public_key=pub)
    assert not r.ok
    assert "penetration_test_report.md" in r.tampered


def test_missing_file_detected(signed_run):
    run, pub, _ = signed_run
    (run / "vulnerabilities" / "VULN-001.md").unlink()
    r = verify_run(run, expected_public_key=pub)
    assert not r.ok
    assert "vulnerabilities/VULN-001.md" in r.missing


def test_unsigned_extra_file_detected(signed_run):
    run, pub, _ = signed_run
    (run / "vulnerabilities" / "VULN-999.md").write_text("injected", encoding="utf-8")
    r = verify_run(run, expected_public_key=pub)
    assert not r.ok
    assert "vulnerabilities/VULN-999.md" in r.unsigned


def test_forged_key_rejected(signed_run, tmp_path):
    run, pub, _ = signed_run
    evil_dir = tmp_path / "evil"
    save_keypair(generate_keypair(), key_dir=evil_dir)
    evil = load_private_key(evil_dir / PRIV_NAME)
    (run / "penetration_test_report.md").write_text("# lies\n", encoding="utf-8")
    sign_run(run, evil)  # attacker re-signs with their own key
    r = verify_run(run, expected_public_key=pub)
    assert not r.ok
    assert r.trusted_key is False


def test_unsigned_run_fails(tmp_path):
    run = tmp_path / "run"
    run.mkdir()
    (run / "penetration_test_report.md").write_text("# report\n", encoding="utf-8")
    assert not verify_run(run).ok
