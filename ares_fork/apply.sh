#!/bin/bash
# Apply the Arès fork patches onto a fresh `strix-agent` install.
# Usage: bash ares_fork/apply.sh
set -e
SP="$(python3 -c 'import strix,os;print(os.path.dirname(strix.__file__))' 2>/dev/null)"
[ -z "$SP" ] && { echo "strix not installed. Run: uv tool install --python 3.12 strix-agent"; exit 1; }
here="$(cd "$(dirname "$0")" && pwd)"
cp -R "$here/strix/." "$SP/"
echo "✓ Arès fork applied to $SP"
echo "  (ethical disclaimer, openai//v1, ares-sandbox naming, caido/entrypoint fix,"
echo "   cascade routing, local reinforcement, tolerant image pull)"
