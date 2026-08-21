"""Detect the machine's usable memory for LLM inference (macOS + Linux).

The number that matters for "can I run model X" is *usable inference memory*:
- Apple Silicon: unified memory. Metal can address most of it, but macOS needs
  headroom, so we budget ~75% of total RAM as usable for the model.
- NVIDIA GPU: dedicated VRAM from nvidia-smi is the hard ceiling.
- CPU-only: system RAM minus an OS reserve; inference will be slow but works.
"""

from __future__ import annotations

import platform
import re
import shutil
import subprocess
from dataclasses import dataclass


@dataclass
class Hardware:
    os: str                      # "macos" | "linux" | "other"
    arch: str                    # "arm64" | "x86_64" | ...
    chip: str                    # human label, e.g. "Apple M4 Pro"
    total_ram_gb: float
    apple_silicon: bool
    gpu: str                     # "apple-metal" | "nvidia" | "none"
    gpu_vram_gb: float | None    # dedicated VRAM if a discrete GPU
    usable_inference_gb: float   # what we budget for a model

    def summary(self) -> str:
        gpu = {
            "apple-metal": f"Apple GPU (Metal, unified {self.total_ram_gb:.0f} GB)",
            "nvidia": f"NVIDIA GPU ({self.gpu_vram_gb:.0f} GB VRAM)"
            if self.gpu_vram_gb else "NVIDIA GPU",
            "none": "CPU only (no supported GPU)",
        }[self.gpu]
        return (
            f"{self.chip} — {self.os}/{self.arch}\n"
            f"  RAM: {self.total_ram_gb:.0f} GB · {gpu}\n"
            f"  Usable for a local model: ~{self.usable_inference_gb:.0f} GB"
        )


def _run(cmd: list[str]) -> str:
    try:
        return subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL).strip()
    except (subprocess.SubprocessError, OSError, FileNotFoundError):
        return ""


def _mac_total_ram_gb() -> float:
    out = _run(["sysctl", "-n", "hw.memsize"])
    return round(int(out) / 1024**3, 1) if out.isdigit() else 0.0


def _linux_total_ram_gb() -> float:
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    kb = int(re.search(r"(\d+)", line).group(1))
                    return round(kb / 1024**2, 1)
    except (OSError, AttributeError):
        pass
    return 0.0


def _nvidia_vram_gb() -> float | None:
    if not shutil.which("nvidia-smi"):
        return None
    out = _run(["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"])
    vals = [int(x) for x in re.findall(r"\d+", out)]
    if not vals:
        return None
    return round(max(vals) / 1024, 1)  # MiB -> GiB, largest GPU


def detect() -> Hardware:
    system = platform.system()
    arch = platform.machine()
    os_name = {"Darwin": "macos", "Linux": "linux"}.get(system, "other")
    apple_silicon = os_name == "macos" and arch == "arm64"

    if os_name == "macos":
        chip = _run(["sysctl", "-n", "machdep.cpu.brand_string"]) or "Mac"
        total = _mac_total_ram_gb()
    elif os_name == "linux":
        chip = platform.processor() or "Linux host"
        total = _linux_total_ram_gb()
    else:
        chip = platform.processor() or system
        total = 0.0

    vram = _nvidia_vram_gb()
    if apple_silicon:
        gpu, gpu_vram = "apple-metal", None
        # Metal budget: ~75% of unified memory, leave the OS room.
        usable = round(total * 0.75, 1)
    elif vram:
        gpu, gpu_vram = "nvidia", vram
        usable = vram  # VRAM is the hard ceiling for GPU inference
    else:
        gpu, gpu_vram = "none", None
        usable = round(max(total - 4, 0) * 0.8, 1)  # CPU: reserve 4GB, 80% of rest

    return Hardware(
        os=os_name, arch=arch, chip=chip, total_ram_gb=total,
        apple_silicon=apple_silicon, gpu=gpu, gpu_vram_gb=gpu_vram,
        usable_inference_gb=usable,
    )
