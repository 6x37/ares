# Provenance: signing & verification

Arès signs every scan run so a report's **integrity** and **authenticity** can be
checked by anyone, without trusting Arès at verify time. This document describes
exactly what that does — and, just as importantly, what it does **not** — prove.

Source: `ares_provenance/` (`sign.py`, `verify.py`, `keys.py`, `canonical.py`,
`__main__.py`).

## What signing proves — and what it does not

Signing is over the **report artifacts**, using an Ed25519 key. It guarantees:

- **Authenticity** — a valid signature can only be produced with the signer's
  private key. Nobody can forge "signed by Arès" on their own output.
- **Integrity** — every artifact's SHA-256 is in the signed manifest. Change one
  byte of any report and verification fails.
- **Completeness** — a signed file that is now missing, or an extra file that was
  slipped in, is detected.
- **Engine provenance** — the manifest records *what generated the report* (e.g.
  the local model, and whether the run was local) when that is supplied at signing.

It does **not** prove the findings are correct. A signature says "this is exactly
the report Arès produced, unaltered", not "the vulnerabilities are real and
complete". Judging whether a run should be trusted at all is a separate concern,
handled by the [confidence gate](reliability.md#the-confidence-gate-high--ok--low).

Signing also does not claim the marker is impossible to delete — no local file can
guarantee that. The real lock is: you cannot remove the marker or edit the content
**and still pass verification** without the private key.

## The signed manifest

`ares sign` (and the auto-sign in `ares watch` / `ares demo`) writes
`ares.provenance.json` into the run directory. The artifacts it covers, from a
Strix run layout, are:

```
penetration_test_report.md
vulnerabilities.csv
vulnerabilities.json
run.json
findings.sarif
vulnerabilities/*.md
```

The manifest itself is excluded (it cannot hash itself). Its structure:

- `payload` — the signed object: manifest version, producer, `signed_at`, the
  signing key's fingerprint, an `engine` block, and a `files` list of
  `{path, sha256, bytes}` for every artifact.
- `signature` — `{alg: "Ed25519", value: <hex>, public_key_pem: <PEM>}` over the
  **canonical** bytes of `payload`.
- `payload_digest` — a SHA-256 of the signed bytes, for convenience.

Canonicalization (`canonical.py`) is deterministic: JSON with sorted keys, compact
separators, UTF-8, no NaN. The verifier re-serializes `payload` the same way and
checks the signature against those exact bytes. Artifacts are hashed as raw bytes,
prefixed `sha256:`.

When signing, Arès also injects a short **"Signed & verifiable by Arès"** footer
into `penetration_test_report.md` (signing key, timestamp, a truncated signature).
Because that edits the report, Arès re-hashes and re-signs with the footer in
place, so the on-disk report still verifies.

## The three verdicts

`ares verify <run>` prints exactly one verdict. The logic is in
`verify.py::VerifyResult.summary()`:

### `VERIFIED` — authentic

```
VERIFIED — authentic Arès report · trusted key ARES-XXXX-XXXX-XXXX-XXXX
```

The signature is valid over the manifest, **nothing was modified or dropped or
added**, **and** the signing key is one you trust (pinned, or in your default
trust set). This is the only verdict that asserts authorship.

### `INTACT` — integrity only, authorship not established

```
INTACT — signature valid, content unmodified · signed by ARES-… (key NOT pinned).
Pass the trusted Arès public key to assert authenticity.
```

The signature is internally valid and nothing was modified — but **no trust anchor
was available** to judge whose key signed it. Anyone can generate a keypair and
produce an internally-valid signature over their own report, so `INTACT` proves
integrity, not authorship. It typically appears when you verify somewhere with no
trusted keys present (for example a bare install without the release key on disk
and no key of your own), or when calling the library without a trust set.

### `FAILED` — not verifiable as genuine

```
FAILED — report is NOT verifiable as genuine Arès output:
  • signature invalid or unparseable
  • signed by an UNTRUSTED key (ARES-…)
  • TAMPERED (content changed): <file>
  • MISSING (was signed, now absent): <file>
  • UNSIGNED (present but not in manifest): <file>
```

Any of: the signature does not match, the content of a signed artifact changed, a
signed artifact is missing, an unsigned artifact appeared, **or** a trust set was
available and the signer's key is **not** in it (an untrusted re-sign). Note the
distinction from `INTACT`: `INTACT` means "no way to judge the key"; `FAILED` with
"UNTRUSTED key" means "we could judge it, and it is not trusted".

The verifier catches all four tamper classes: content edits, marker/file removal,
file injection, and re-signing with an unknown key.

## Keys and fingerprints

Keys are Ed25519, stored as PEM. Create your own:

```bash
ares keygen                          # writes to ~/.ares/keys/ by default
```

This writes the private key (`ares_signing_ed25519.pem`, mode `0600`) and the
public key (`ares_signing_ed25519.pub.pem`), and prints the **fingerprint**.

A fingerprint is a short, human-quotable label derived from the raw 32-byte public
key: the first 8 bytes of its SHA-256, uppercased, in the form:

```
ARES-XXXX-XXXX-XXXX-XXXX
```

You eyeball the fingerprint to confirm you hold the genuine key. The shipped Arès
**release** key is:

```
ARES-2BC4-652E-E25F-6414
```

published at [`../keys/ares-release.pub.pem`](../keys/ares-release.pub.pem) (and
recorded in [`../keys/FINGERPRINT`](../keys/FINGERPRINT)).

## The default trust set

When you run `ares verify`, Arès assembles the set of trusted public keys from
three places (see `__main__.py::_trusted_keys`):

1. **Your deployment's own signing key** — `<key-dir>/ares_signing_ed25519.pub.pem`
   (default `~/.ares/keys/`). So reports you signed verify as `VERIFIED` on your
   own machine.
2. **Keys shipped in the repo** — every `keys/*.pub.pem`, which includes the Arès
   **release** key. So official Arès artifacts verify out of the box **when the
   release key is present on disk** (as it is in a repo checkout / editable
   install).
3. **Anything you explicitly trust** — every `*.pem` in `~/.ares/trusted/`. Drop a
   colleague's public key there to trust their signed reports.

You can also pin one expected key for a single check:

```bash
ares verify strix_runs/my-run --pubkey /path/to/expected.pub.pem
```

A pinned key is added to the trust set for that run. If the report is signed by a
different key, the result is `FAILED` (untrusted), not `VERIFIED`.

## Running verification

```bash
ares verify strix_runs/my-run
```

Exit code: `0` when the verdict is trustworthy (`VERIFIED` or `INTACT`), `1`
otherwise. The report's injected footer also prints the equivalent module command,
`ares-provenance verify <report-directory>`; both invoke the same verifier.

## How runs get signed in practice

- `ares watch` signs automatically when a scan completes — **after** running the
  confidence gate and annotating the report, so the trust verdict is part of the
  signed content and a bailed "0 findings" cannot hide.
- `ares demo` signs its scripted run the same way.
- `ares sign <run>` signs by hand, optionally recording `--model` and `--local`.

## See also

- [reliability.md](reliability.md) — the confidence gate that decides whether a
  run is worth trusting in the first place.
- [`../SECURITY.md`](../SECURITY.md) — the project's trust-model summary and how to
  report a vulnerability in Arès.
