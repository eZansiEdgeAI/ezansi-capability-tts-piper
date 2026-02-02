from __future__ import annotations

import os
import platform
from typing import Any, Dict


def _read_meminfo_mb() -> int:
    # Linux-first; fall back gracefully.
    try:
        with open("/proc/meminfo", "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    parts = line.split()
                    # MemTotal: <kB>
                    kb = int(parts[1])
                    return max(1, kb // 1024)
    except Exception:
        pass

    # Best-effort fallback: unknown
    return 0


def _cpu_cores() -> int:
    try:
        return max(1, int(os.cpu_count() or 1))
    except Exception:
        return 1


def _detect_gpu() -> str:
    # Very lightweight heuristics.
    if os.path.exists("/dev/nvidia0"):
        return "cuda"
    if os.path.exists("/dev/dri"):
        # Could be Intel/AMD; we don’t attempt detailed vendor detection here.
        return "dri"
    return "none"


def get_hardware_info() -> Dict[str, Any]:
    return {
        "architecture": platform.machine() or "unknown",
        "ram_mb": _read_meminfo_mb(),
        "cpu_cores": _cpu_cores(),
        "gpu_type": _detect_gpu(),
    }


def get_recommended_resources() -> Dict[str, Any]:
    """Return recommended resource hints.

    Matches the documented policy:
    - RAM: 50% of total, min 300MB, max 600MB
    - CPU: 1 core for small devices, otherwise 2
    - Accelerator: best-effort (currently none/cuda/dri)

    These are hints used for:
    - logging and health diagnostics
    - optional preflight (.env generation) for compose resource constraints
    """

    hw = get_hardware_info()
    total_ram_mb = int(hw.get("ram_mb") or 0)

    if total_ram_mb > 0:
        ram_mb = int(total_ram_mb * 0.5)
    else:
        ram_mb = 600

    ram_mb = max(300, min(600, ram_mb))

    cores = int(hw.get("cpu_cores") or 1)
    cpu_cores = 1 if cores <= 2 else 2

    gpu = str(hw.get("gpu_type") or "none")
    accelerator = "cuda" if gpu == "cuda" else "none"

    return {
        "ram_mb": ram_mb,
        "cpu_cores": cpu_cores,
        "accelerator": accelerator,
    }
