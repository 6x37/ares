#!/usr/bin/env bash
# Arès engine sync — pull an upstream Strix release and re-apply the Arès patches.
#
#   bash ares_engine/update.sh [vX.Y.Z]      (default: latest upstream tag)
#
# For each Arès-modified file it does a 3-way check against the recorded baseline:
#   • upstream file unchanged  -> re-apply the Arès version cleanly
#   • upstream file changed     -> CONFLICT: keep upstream, flag for manual re-port
# Then it runs the test suite. Nothing is pushed; you review and commit.
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"
UPSTREAM="https://github.com/usestrix/strix"
TARGET="${1:-}"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

if [ -z "$TARGET" ]; then
  TARGET="$(git ls-remote --tags "$UPSTREAM" | grep -oE 'v[0-9]+\.[0-9]+\.[0-9]+' | sort -V | tail -1)"
fi
BASE="$(cat ares_engine/BASELINE 2>/dev/null || echo '?')"
echo "▸ baseline actuelle : $BASE"
echo "▸ cible upstream    : $TARGET"
[ "$BASE" = "$TARGET" ] && { echo "✓ déjà à jour."; exit 0; }

echo "▸ clone pristine $TARGET…"
git clone --depth 1 --branch "$TARGET" "$UPSTREAM" "$TMP/new" -q
find "$TMP/new" -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true

clean=(); conflict=()
while IFS= read -r f; do
  [ -z "$f" ] && continue
  up="$TMP/new/strix/$f"; base="patches/baseline/$f"; ares="patches/ares/$f"
  if [ ! -f "$up" ]; then conflict+=("$f (disparu upstream)"); continue; fi
  if cmp -s "$up" "$base"; then
    mkdir -p "$TMP/new/strix/$(dirname "$f")"; cp "$ares" "$TMP/new/strix/$f"; clean+=("$f")
  else
    conflict+=("$f"); fi
done < patches/MODIFIED_FILES

echo ""
echo "▸ patches ré-appliqués proprement : ${#clean[@]}"
for f in "${clean[@]:-}"; do [ -n "$f" ] && echo "    ✓ $f"; done
echo "▸ CONFLITS (upstream a changé ces fichiers, à ré-porter à la main) : ${#conflict[@]}"
for f in "${conflict[@]:-}"; do [ -n "$f" ] && echo "    ⚠ $f"; done

if [ "${#conflict[@]}" -gt 0 ] && [ -n "${conflict[0]:-}" ]; then
  echo ""
  echo "✗ Ne pas merger tel quel. Compare pour chaque conflit :"
  echo "    diff patches/baseline/<f>  $TMP/new/strix/<f>   (ce qu'upstream a changé)"
  echo "    diff patches/baseline/<f>  patches/ares/<f>     (ta modif à reporter)"
  echo "  Le nouvel arbre pristine est dans : $TMP/new  (copie-le avant qu'il soit nettoyé)"
  cp -R "$TMP/new/strix" "ares_engine/strix.$TARGET.pending"
  echo "  → sauvegardé dans ares_engine/strix.$TARGET.pending pour inspection."
  exit 2
fi

echo ""
echo "▸ aucun conflit — bascule du moteur vers $TARGET"
rm -rf ares_engine/strix; cp -R "$TMP/new/strix" ares_engine/strix
cp "$TMP/new/LICENSE" ares_engine/strix/LICENSE 2>/dev/null || true
# refresh the recorded baseline files to the new upstream (unchanged ones)
while IFS= read -r f; do [ -z "$f" ] && continue; mkdir -p "patches/baseline/$(dirname "$f")"; cp "$TMP/new/strix/$f" "patches/baseline/$f" 2>/dev/null || true; cp "ares_engine/strix/$f" "patches/ares/$f" 2>/dev/null || true; done < patches/MODIFIED_FILES
# but keep patches/ares as OUR versions (already overlaid into ares_engine)
for f in $(cat patches/MODIFIED_FILES); do cp "ares_engine/strix/$f" "patches/ares/$f" 2>/dev/null || true; done
echo "$TARGET" > ares_engine/BASELINE
echo "▸ tests…"
python3 -m pytest tests/ -q || { echo "✗ tests KO — revérifie avant de committer."; exit 1; }
echo ""
echo "✅ moteur à jour ($BASE → $TARGET), patches ré-appliqués, tests verts. Review & commit."
