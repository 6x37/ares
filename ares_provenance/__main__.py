"""CLI: ares-provenance {keygen,sign,verify}."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import (
    DEFAULT_KEY_DIR, generate_keypair, key_fingerprint, load_private_key,
    load_public_key, save_keypair, sign_run, verify_run,
)
from .keys import PRIV_NAME, PUB_NAME


def _cmd_keygen(args: argparse.Namespace) -> int:
    key_dir = Path(args.key_dir)
    priv, pub = save_keypair(generate_keypair(), key_dir=key_dir)
    fp = key_fingerprint(load_public_key(pub))
    print(f"Generated Arès signing keypair:\n  private: {priv}\n  public:  {pub}")
    print(f"  fingerprint: {fp}")
    print("\nKeep the private key secret. Distribute the public key + fingerprint "
          "so anyone can verify.")
    return 0


def _cmd_sign(args: argparse.Namespace) -> int:
    priv = load_private_key(Path(args.key_dir) / PRIV_NAME)
    engine = {}
    if args.model:
        engine["model"] = args.model
    if args.local:
        engine["execution"] = "local"
    path = sign_run(Path(args.run_dir), priv, engine=engine)
    print(f"Signed. Manifest: {path}")
    return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    expected = None
    if args.pubkey:
        expected = load_public_key(Path(args.pubkey))
    elif (Path(args.key_dir) / PUB_NAME).exists():
        expected = load_public_key(Path(args.key_dir) / PUB_NAME)
    result = verify_run(Path(args.run_dir), expected_public_key=expected)
    print(result.summary())
    return 0 if result.ok else 1


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="ares-provenance")
    p.add_argument("--key-dir", default=str(DEFAULT_KEY_DIR))
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("keygen").set_defaults(func=_cmd_keygen)

    sp = sub.add_parser("sign")
    sp.add_argument("run_dir")
    sp.add_argument("--model", default=None, help="engine model, e.g. qwen3.6-27b-obliterated")
    sp.add_argument("--local", action="store_true", help="mark scan as locally-run")
    sp.set_defaults(func=_cmd_sign)

    vp = sub.add_parser("verify")
    vp.add_argument("run_dir")
    vp.add_argument("--pubkey", default=None, help="pin an expected public key PEM")
    vp.set_defaults(func=_cmd_verify)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
