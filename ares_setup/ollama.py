"""Thin wrapper around the local Ollama runtime.

Arès talks to models through Ollama's OpenAI-compatible endpoint. This module
only inspects and drives the local `ollama` CLI/daemon; it never reaches the
network except to pull a model the user explicitly chose.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass

DEFAULT_ENDPOINT = "http://localhost:11434"


@dataclass
class OllamaStatus:
    installed: bool
    running: bool
    endpoint: str
    models: list[str]        # installed model tags


def is_installed() -> bool:
    return shutil.which("ollama") is not None


def status(endpoint: str = DEFAULT_ENDPOINT) -> OllamaStatus:
    if not is_installed():
        return OllamaStatus(False, False, endpoint, [])
    try:
        out = subprocess.run(
            ["ollama", "list"], capture_output=True, text=True, timeout=10
        )
    except (subprocess.SubprocessError, OSError):
        return OllamaStatus(True, False, endpoint, [])
    if out.returncode != 0:
        # CLI present but daemon not reachable.
        return OllamaStatus(True, False, endpoint, [])
    models = []
    for line in out.stdout.splitlines()[1:]:  # skip header
        parts = line.split()
        if parts:
            models.append(parts[0])
    return OllamaStatus(True, True, endpoint, models)


def has_model(tag: str, st: OllamaStatus | None = None) -> bool:
    st = st or status()
    # match exact tag or the base name before ':latest'
    base = tag.split(":")[0]
    return any(m == tag or m.split(":")[0] == base for m in st.models)


def pull(tag: str) -> int:
    """Pull a model, streaming progress to the terminal. Returns exit code."""
    if not is_installed():
        raise RuntimeError("ollama is not installed")
    proc = subprocess.run(["ollama", "pull", tag])
    return proc.returncode


def install_hint() -> str:
    return (
        "Ollama is not installed. Install it, then re-run `ares init`:\n"
        "  • macOS:  brew install ollama   (or https://ollama.com/download)\n"
        "  • Linux:  curl -fsSL https://ollama.com/install.sh | sh"
    )
