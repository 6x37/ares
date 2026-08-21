"""Arès local setup: guided install + resource dial for local LLMs."""
from .hardware import detect, Hardware
from .dial import compute, EngineConfig, PRESETS
from .wizard import run, InitOptions, InitResult

__all__ = ["detect", "Hardware", "compute", "EngineConfig", "PRESETS",
           "run", "InitOptions", "InitResult"]
