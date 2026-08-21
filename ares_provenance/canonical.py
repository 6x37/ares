"""Deterministic, canonical serialization + hashing primitives.

Signing must be reproducible: the exact same logical content must always
produce the exact same bytes, on any machine, in any language. We therefore
serialize the manifest with sorted keys, no insignificant whitespace, and
UTF-8 — a JSON Canonicalization-friendly form — and hash artifacts with
SHA-256 over their raw bytes.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

SHA256_PREFIX = "sha256:"


def sha256_bytes(data: bytes) -> str:
    return SHA256_PREFIX + hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return SHA256_PREFIX + h.hexdigest()


def canonical_json_bytes(obj: Any) -> bytes:
    """Canonical JSON: sorted keys, compact separators, UTF-8, no NaN.

    This is the exact byte sequence that gets signed and verified. Keep it
    stable forever — changing it invalidates every previously issued signature.
    """
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
