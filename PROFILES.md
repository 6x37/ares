# Arès engine profiles

| Profile | File | Engine | Use |
|---|---|---|---|
| **default** | `ares.env` | Qwen3.6-27B-OBLITERATED (local) | general local runs |
| **cascade** ★ | `ares-cascade.env` | root+validate → 27B, breadth → 14B | **recommended** — best local balance |
| **fast** | `ares-fast.env` | qwen3.5 14B | quick, lower accuracy |
| **offensive** | `ares-offensive.env` | Qwen3.6-27B-OBLITERATED | slow, strong |
| **offline** | any + `--offline` | local only, zero telemetry | air-gapped engagements |

Enable the hosted **escalate** tier on top of cascade:
`ARES_CASCADE_ESCALATE=1` + `ANTHROPIC_API_KEY=...` (validation agents go frontier).
