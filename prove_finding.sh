#!/bin/bash
# Arès — prove a real autonomous finding, end to end, with the hosted escalate tier.
# Requires: ANTHROPIC_API_KEY in your env. Restarts Ollama + Docker + Juice Shop.
set -e
export PATH="$HOME/.local/bin:/opt/homebrew/bin:$PATH"
cd "$(cd "$(dirname "$0")" && pwd)"

[ -z "$ANTHROPIC_API_KEY" ] && { echo "✗ export ANTHROPIC_API_KEY=... d'abord"; exit 1; }

echo "▸ démarrage Ollama + Docker…"
open -a Ollama 2>/dev/null || ollama serve >/dev/null 2>&1 &
open -a Docker 2>/dev/null || true
until docker info >/dev/null 2>&1; do sleep 2; done
until curl -s http://localhost:11434/api/tags >/dev/null 2>&1; do sleep 1; done

echo "▸ Juice Shop…"
docker rm -f juice-shop 2>/dev/null || true
docker run -d --name juice-shop -p 3000:3000 bkimminich/juice-shop >/dev/null
until curl -s -o /dev/null -w "%{http_code}" http://localhost:3000 | grep -q 200; do sleep 2; done

echo "▸ préchauffe des modèles cascade…"
for m in ares-cascade-triage-qwen3-5 ares-cascade-validate-qwen3-6-27b-obliterated; do
  curl -s http://localhost:11434/v1/chat/completions -H "Content-Type: application/json" \
    -d "{\"model\":\"$m\",\"messages\":[{\"role\":\"user\",\"content\":\"hi\"}],\"max_tokens\":1}" >/dev/null 2>&1 || true
done

echo "▸ scan cascade + ESCALATE hosted (validation → frontier)…"
set -a; source ares-cascade.env; set +a
export ARES_CASCADE_ESCALATE=1              # validation agents → hosted frontier
export ARES_CASCADE_ESCALATE_MODEL="anthropic/claude-sonnet-5"
strix -t http://host.docker.internal:3000 -m quick -n --max-turns 25 \
  --instruction "OWASP Juice Shop (authorized). Find and validate SQL injection, XSS and broken access control. Report each with a PoC."

RD=$(ls -dt strix_runs/*/ | head -1)
echo "▸ confidence + signature…"
python3 -m ares_setup.confidence "$RD" --annotate
python3 -m ares_provenance sign "$RD"
python3 -m ares_provenance verify "$RD"
echo "▸ rapport: $RD/penetration_test_report.md"
