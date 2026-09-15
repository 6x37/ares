# Security Policy

## Ethical use
Arès is an offensive-security tool for **authorized** testing only — on systems
you own or have explicit written permission to test. Misuse is your
responsibility; the authors accept no liability.

## Reporting a vulnerability in Arès
Please do **not** open a public issue for security bugs. Email the maintainer
(see the GitHub profile) with:
- a description and impact,
- steps to reproduce,
- affected version / commit.

You'll get an acknowledgement within a few days. Coordinated disclosure is
appreciated.

## Provenance & trust model
Reports are signed with Ed25519. `ares verify` reports `VERIFIED` **only** when
the signature is valid *and* the key is pinned to a trusted Arès key; otherwise
it reports `INTACT` (integrity only). Do not treat an unpinned `INTACT` result as
proof of authorship. See the README for the full model.
