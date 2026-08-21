"""Sign an Arès scan run: build a tamper-evident, verifiable provenance manifest.

What "signed by Arès" actually guarantees
-----------------------------------------
We do NOT claim the marker is impossible to delete — that is not achievable for
any local file. What we DO guarantee, cryptographically:

  1. Authenticity  — a valid signature can only be produced with Arès's private
                     key. Nobody can forge "signed by Arès" on their own output.
  2. Integrity     — every artifact's SHA-256 is in the signed manifest. Change
                     one byte of any report and verification FAILS.
  3. Non-repudiation of tampering — strip the marker or edit the content and the
                     signature no longer matches. Removal is detectable, not
                     silent. That is the real lock: not "can't be removed" but
                     "can't be removed *and still look genuine*."

Artifacts covered (Strix run_dir layout):
  penetration_test_report.md, vulnerabilities/*.md,
  vulnerabilities.csv, vulnerabilities.json, run.json
The manifest itself is excluded (it can't hash itself) and is signed separately.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .canonical import canonical_json_bytes, sha256_bytes, sha256_file
from .keys import Ed25519PrivateKey, key_fingerprint, public_key_pem

MANIFEST_NAME = "ares.provenance.json"
MANIFEST_VERSION = "ares-provenance/1"

# Files we never treat as scan artifacts to hash.
_EXCLUDE = {MANIFEST_NAME}

# Default set of artifacts Strix emits into a run_dir.
_ARTIFACT_GLOBS = (
    "penetration_test_report.md",
    "vulnerabilities.csv",
    "vulnerabilities.json",
    "run.json",
    "findings.sarif",
    "vulnerabilities/*.md",
)

_FOOTER_BEGIN = "<!-- ARES-PROVENANCE:BEGIN -->"
_FOOTER_END = "<!-- ARES-PROVENANCE:END -->"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def collect_artifacts(run_dir: Path) -> list[Path]:
    found: list[Path] = []
    for pattern in _ARTIFACT_GLOBS:
        for p in sorted(run_dir.glob(pattern)):
            if p.is_file() and p.name not in _EXCLUDE:
                found.append(p)
    return found


def build_manifest(
    run_dir: Path,
    private_key: Ed25519PrivateKey,
    *,
    engine: dict[str, Any] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Hash every artifact, assemble the signed payload, attach the signature.

    ``engine`` records how the scan was produced (e.g. local LLM model, quant,
    Arès version) so the provenance says *what generated this*, not just *that
    Arès signed it*.
    """
    artifacts = collect_artifacts(run_dir)
    files = [
        {
            "path": p.relative_to(run_dir).as_posix(),
            "sha256": sha256_file(p),
            "bytes": p.stat().st_size,
        }
        for p in artifacts
    ]

    pub = private_key.public_key()
    payload = {
        "manifest_version": MANIFEST_VERSION,
        "producer": "Ares",
        "signed_at": _now_iso(),
        "key_fingerprint": key_fingerprint(pub),
        "engine": engine or {},
        "files": files,
    }
    if extra:
        payload["extra"] = extra

    signed_bytes = canonical_json_bytes(payload)
    signature = private_key.sign(signed_bytes)

    return {
        # The signed payload is nested verbatim so verifiers re-canonicalize the
        # exact same object. Never move fields in/out of "payload" after release.
        "payload": payload,
        "signature": {
            "alg": "Ed25519",
            "value": signature.hex(),
            "public_key_pem": public_key_pem(pub),
        },
        "payload_digest": sha256_bytes(signed_bytes),
    }


def sign_run(
    run_dir: Path,
    private_key: Ed25519PrivateKey,
    *,
    engine: dict[str, Any] | None = None,
    extra: dict[str, Any] | None = None,
    inject_footer: bool = True,
) -> Path:
    manifest = build_manifest(run_dir, private_key, engine=engine, extra=extra)
    manifest_path = run_dir / MANIFEST_NAME
    manifest_path.write_bytes(_pretty(manifest))

    if inject_footer:
        report = run_dir / "penetration_test_report.md"
        if report.exists():
            _inject_footer(report, manifest)
            # The report changed, so its hash in the manifest is now stale.
            # Re-sign with the footer in place so the on-disk report verifies.
            manifest = build_manifest(
                run_dir, private_key, engine=engine, extra=extra
            )
            manifest_path.write_bytes(_pretty(manifest))
    return manifest_path


def _pretty(manifest: dict[str, Any]) -> bytes:
    import json

    return json.dumps(manifest, indent=2, ensure_ascii=False).encode("utf-8")


def _inject_footer(report_path: Path, manifest: dict[str, Any]) -> None:
    text = report_path.read_text(encoding="utf-8")
    text = _strip_footer(text)
    fp = manifest["payload"]["key_fingerprint"]
    sig = manifest["signature"]["value"]
    signed_at = manifest["payload"]["signed_at"]
    footer = (
        f"\n\n{_FOOTER_BEGIN}\n"
        "\n---\n\n"
        "### 🛡️ Signed & verifiable by Arès\n\n"
        f"- **Producer:** Arès\n"
        f"- **Signed at:** {signed_at}\n"
        f"- **Signing key:** `{fp}`\n"
        f"- **Signature (Ed25519):** `{sig[:32]}…{sig[-16:]}`\n\n"
        "This report is cryptographically signed. Any modification to its "
        "content — or removal of this notice — breaks the signature and is "
        "detectable. Verify with:\n\n"
        "```bash\n"
        "ares-provenance verify <report-directory>\n"
        "```\n"
        f"\n{_FOOTER_END}\n"
    )
    report_path.write_text(text.rstrip() + footer, encoding="utf-8")


def _strip_footer(text: str) -> str:
    if _FOOTER_BEGIN in text and _FOOTER_END in text:
        head, _, rest = text.partition(_FOOTER_BEGIN)
        _, _, tail = rest.partition(_FOOTER_END)
        return head.rstrip() + tail
    return text
