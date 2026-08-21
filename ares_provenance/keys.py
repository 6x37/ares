"""Ed25519 key management for Arès report signing.

Design decisions
----------------
* Ed25519: small keys, fast, deterministic signatures, no parameter choices to
  get wrong. The de-facto modern signing primitive.
* The PRIVATE key never leaves the signer (CI secret / local keyring). It is the
  only thing that makes an Arès signature unforgeable. Losing control of it is
  the only way someone can forge the "signed by Arès" marker — so we treat it
  like a code-signing key.
* The PUBLIC key is distributed freely (shipped in the repo, printed in reports)
  so *anyone* can verify without trusting us at verify time.
* Keys are stored as PEM. Private keys can be encrypted at rest with a password.
"""

from __future__ import annotations

import os
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

DEFAULT_KEY_DIR = Path.home() / ".ares" / "keys"
PRIV_NAME = "ares_signing_ed25519.pem"
PUB_NAME = "ares_signing_ed25519.pub.pem"


def generate_keypair() -> Ed25519PrivateKey:
    return Ed25519PrivateKey.generate()


def key_fingerprint(public_key: Ed25519PublicKey) -> str:
    """Short, human-quotable fingerprint of a public key.

    Uses the raw 32-byte public key; the fingerprint is what a verifier eyeballs
    to confirm they hold the genuine Arès key ("trust on first sight").
    """
    from .canonical import sha256_bytes

    raw = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    digest = sha256_bytes(raw).removeprefix("sha256:")
    groups = [digest[i : i + 4] for i in range(0, 16, 4)]
    return "ARES-" + "-".join(groups).upper()


def save_keypair(
    private_key: Ed25519PrivateKey,
    key_dir: Path = DEFAULT_KEY_DIR,
    password: bytes | None = None,
) -> tuple[Path, Path]:
    key_dir.mkdir(parents=True, exist_ok=True)
    enc = (
        serialization.BestAvailableEncryption(password)
        if password
        else serialization.NoEncryption()
    )
    priv_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=enc,
    )
    pub_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    priv_path = key_dir / PRIV_NAME
    pub_path = key_dir / PUB_NAME
    # Private key readable only by owner.
    priv_path.write_bytes(priv_pem)
    os.chmod(priv_path, 0o600)
    pub_path.write_bytes(pub_pem)
    return priv_path, pub_path


def load_private_key(
    path: Path, password: bytes | None = None
) -> Ed25519PrivateKey:
    key = serialization.load_pem_private_key(path.read_bytes(), password=password)
    if not isinstance(key, Ed25519PrivateKey):
        raise TypeError("Not an Ed25519 private key: " + str(path))
    return key


def load_public_key(path: Path) -> Ed25519PublicKey:
    key = serialization.load_pem_public_key(path.read_bytes())
    if not isinstance(key, Ed25519PublicKey):
        raise TypeError("Not an Ed25519 public key: " + str(path))
    return key


def public_key_pem(public_key: Ed25519PublicKey) -> str:
    return public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")


def load_public_key_from_pem(pem: str) -> Ed25519PublicKey:
    key = serialization.load_pem_public_key(pem.encode("ascii"))
    if not isinstance(key, Ed25519PublicKey):
        raise TypeError("PEM is not an Ed25519 public key")
    return key
