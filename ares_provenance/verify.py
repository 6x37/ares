"""Verify an Arès-signed run. This is where the guarantee is enforced.

Verification answers three questions, in order:
  1. Is the signature valid for the signed payload, under the expected key?
     -> proves the payload was produced by the holder of the Arès private key.
  2. Does every artifact on disk still hash to what the manifest recorded?
     -> proves no report was edited after signing.
  3. Are there signed artifacts now missing, or unsigned extras present?
     -> proves nothing was dropped or slipped in.

Any failure => the report is NOT authentic Arès output. That is the whole point:
you cannot alter the content or forge the marker and still pass verification
without the private key.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature

from .canonical import canonical_json_bytes, sha256_file
from .keys import (
    Ed25519PublicKey,
    key_fingerprint,
    load_public_key_from_pem,
)
from .sign import MANIFEST_NAME, collect_artifacts


@dataclass
class VerifyResult:
    ok: bool
    signature_valid: bool
    key_fingerprint: str | None = None
    trusted_key: bool | None = None  # None = no expected key was pinned
    tampered: list[str] = field(default_factory=list)   # hash mismatch
    missing: list[str] = field(default_factory=list)    # in manifest, not on disk
    unsigned: list[str] = field(default_factory=list)   # on disk, not in manifest
    errors: list[str] = field(default_factory=list)

    def summary(self) -> str:
        if self.ok and self.trusted_key:
            return f"VERIFIED — authentic Arès report · trusted key {self.key_fingerprint}"
        if self.ok:
            # Signature is internally valid and nothing was modified, but the key
            # was not pinned to a known Arès key — this proves integrity, not
            # authorship. Anyone can re-sign with their own key.
            return (f"INTACT — signature valid, content unmodified · signed by "
                    f"{self.key_fingerprint} (key NOT pinned). Pass the trusted "
                    f"Arès public key to assert authenticity.")
        parts = ["FAILED — report is NOT verifiable as genuine Arès output:"]
        if not self.signature_valid:
            parts.append("  • signature invalid or unparseable")
        if self.trusted_key is False:
            parts.append(f"  • signed by an UNTRUSTED key ({self.key_fingerprint})")
        for f in self.tampered:
            parts.append(f"  • TAMPERED (content changed): {f}")
        for f in self.missing:
            parts.append(f"  • MISSING (was signed, now absent): {f}")
        for f in self.unsigned:
            parts.append(f"  • UNSIGNED (present but not in manifest): {f}")
        for e in self.errors:
            parts.append(f"  • {e}")
        return "\n".join(parts)


def verify_run(
    run_dir: Path,
    *,
    expected_public_key: Ed25519PublicKey | None = None,
    trusted_keys: "list[Ed25519PublicKey] | None" = None,
) -> VerifyResult:
    manifest_path = run_dir / MANIFEST_NAME
    if not manifest_path.exists():
        return VerifyResult(
            ok=False, signature_valid=False,
            errors=[f"no provenance manifest ({MANIFEST_NAME}) — report is unsigned"],
        )
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        payload = manifest["payload"]
        sig_hex = manifest["signature"]["value"]
        pub_pem = manifest["signature"]["public_key_pem"]
    except (json.JSONDecodeError, KeyError, OSError) as exc:
        return VerifyResult(
            ok=False, signature_valid=False,
            errors=[f"manifest unreadable/malformed: {exc}"],
        )

    # --- 1. signature over the canonical payload ---
    try:
        embedded_key = load_public_key_from_pem(pub_pem)
        embedded_key.verify(bytes.fromhex(sig_hex), canonical_json_bytes(payload))
        signature_valid = True
    except (InvalidSignature, ValueError, TypeError) as exc:
        return VerifyResult(
            ok=False, signature_valid=False,
            key_fingerprint=_safe_fp(pub_pem),
            errors=[f"signature does not match payload: {exc}"],
        )

    fp = key_fingerprint(embedded_key)

    # --- key trust (optional pinning) ---
    trusted_key: bool | None = None
    trust_set = list(trusted_keys or [])
    if expected_public_key is not None:
        trust_set.append(expected_public_key)
    if trust_set:
        trusted_key = any(_same_key(embedded_key, k) for k in trust_set)

    result = VerifyResult(
        ok=False,
        signature_valid=signature_valid,
        key_fingerprint=fp,
        trusted_key=trusted_key,
    )

    # --- 2 & 3. content integrity + completeness ---
    signed_files: dict[str, dict[str, Any]] = {
        f["path"]: f for f in payload.get("files", [])
    }
    on_disk = {p.relative_to(run_dir).as_posix() for p in collect_artifacts(run_dir)}

    for rel, meta in signed_files.items():
        fpath = run_dir / rel
        if not fpath.exists():
            result.missing.append(rel)
            continue
        if sha256_file(fpath) != meta["sha256"]:
            result.tampered.append(rel)

    for rel in on_disk:
        if rel not in signed_files:
            result.unsigned.append(rel)

    result.ok = (
        signature_valid
        and (trusted_key is not False)
        and not result.tampered
        and not result.missing
        and not result.unsigned
    )
    return result


def _same_key(a: Ed25519PublicKey, b: Ed25519PublicKey) -> bool:
    from cryptography.hazmat.primitives import serialization

    raw = lambda k: k.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return raw(a) == raw(b)


def _safe_fp(pub_pem: str) -> str | None:
    try:
        return key_fingerprint(load_public_key_from_pem(pub_pem))
    except Exception:
        return None
