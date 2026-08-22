# Vendored engine — Strix (modified)

This directory vendors the Strix engine source (github.com/usestrix/strix,
© OmniSecure Inc., Apache-2.0), pinned at 1.5.3, **with Arès modifications**.

Arès owns this copy — it is not a live patch of an external install. Modified
files carry Arès notices per Apache-2.0 §4. Changes vs upstream:
- interface/main.py ...... ethical disclaimer replaces model-quality warning
- interface/environment.py  tolerant image pull (local-only tags)
- config/settings.py ..... default image ares-sandbox:1.3.0
- config/models.py ....... cloud models bypass local api_base (escalate tier)
- runtime/docker_client.py  ares-* Docker naming + preserve image entrypoint
- runtime/caido_bootstrap.py  caido readiness attempts 10 → 30
- agents/factory.py ...... cascade per-role model routing + local reinforcement
- interface/tui/backend/controller.py  drop model-quality warning
