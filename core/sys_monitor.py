"""
sys_monitor.py  (Windows-enhanced replacement)
-----------------------------------------------
Provides real-time system stats used by the model selector to decide
which Ollama models are safe to run without crashing.

Windows CPU-only machine: no VRAM tracking needed, but we track:
  - CPU %
  - RAM used / available / percent
  - Disk I/O rates (MB/s read & write) over a rolling 1-second window
  - Estimated safe RAM headroom for model loading

All public functions are synchronous (psutil is sync) so they can be
called from both sync and async contexts.
"""

import time
from dataclasses import dataclass

import psutil

# ── Rolling I/O baseline ─────────────────────────────────────────────────────
_last_io_time: float = 0.0
_last_io_counters: psutil._common.sdiskio | None = None


@dataclass
class SystemStats:
    cpu_percent: float
    ram_used_gb: float
    ram_available_gb: float
    ram_total_gb: float
    ram_percent: float
    disk_read_mbps: float
    disk_write_mbps: float
    safe_model_ram_gb: float          # headroom estimate for model loading
    load_level: str                   # "low" | "medium" | "high" | "critical"


def _get_disk_io() -> tuple[float, float]:
    """Return (read_MB/s, write_MB/s) since last call, or (0,0) on first call."""
    global _last_io_time, _last_io_counters
    try:
        now = time.monotonic()
        counters = psutil.disk_io_counters()
        if _last_io_counters is None or (now - _last_io_time) < 0.01:
            _last_io_time = now
            _last_io_counters = counters
            return 0.0, 0.0
        elapsed = now - _last_io_time
        read_mb  = (counters.read_bytes  - _last_io_counters.read_bytes)  / 1_048_576 / elapsed
        write_mb = (counters.write_bytes - _last_io_counters.write_bytes) / 1_048_576 / elapsed
        _last_io_time = now
        _last_io_counters = counters
        return round(max(read_mb, 0), 2), round(max(write_mb, 0), 2)
    except Exception:
        return 0.0, 0.0


def system_stats() -> SystemStats:
    """Full snapshot of system health."""
    vm = psutil.virtual_memory()
    cpu = psutil.cpu_percent(interval=0.2)
    read_mbps, write_mbps = _get_disk_io()

    ram_avail_gb = vm.available / 1_073_741_824
    ram_used_gb  = vm.used      / 1_073_741_824
    ram_total_gb = vm.total     / 1_073_741_824

    # Conservative headroom: leave 1.5 GB for OS + other processes
    safe_ram_gb = max(ram_avail_gb - 1.5, 0.0)

    # Load level used by model_selector
    if cpu > 90 or vm.percent > 92:
        level = "critical"
    elif cpu > 70 or vm.percent > 80:
        level = "high"
    elif cpu > 40 or vm.percent > 60:
        level = "medium"
    else:
        level = "low"

    return SystemStats(
        cpu_percent=round(cpu, 1),
        ram_used_gb=round(ram_used_gb, 2),
        ram_available_gb=round(ram_avail_gb, 2),
        ram_total_gb=round(ram_total_gb, 2),
        ram_percent=round(vm.percent, 1),
        disk_read_mbps=read_mbps,
        disk_write_mbps=write_mbps,
        safe_model_ram_gb=round(safe_ram_gb, 2),
        load_level=level,
    )


# ── Convenience helpers (keep backward-compat with old callers) ───────────────

def get_cpu_percent() -> float:
    return psutil.cpu_percent(interval=0.1)


def get_memory_percent() -> float:
    return psutil.virtual_memory().percent


def get_available_ram_gb() -> float:
    return psutil.virtual_memory().available / 1_073_741_824


def is_system_under_load(cpu_threshold: float = 75, mem_threshold: float = 80) -> bool:
    """True if CPU OR RAM is above the given thresholds."""
    return get_cpu_percent() > cpu_threshold or get_memory_percent() > mem_threshold


def model_fits_in_ram(model_name: str) -> bool:
    """
    Estimate whether a model can safely be loaded given current free RAM.
    Uses rough size heuristics (no VRAM on CPU-only Windows build).

    Heuristic: model param-count (B) × 2 bytes (INT4 quant) + 20% overhead.
    """
    import re
    name = model_name.lower()

    # Try to parse size from name (e.g. "llama3:8b" → 8)
    m = re.search(r'(\d+\.?\d*)\s*b', name)
    if m:
        size_b = float(m.group(1))
    elif any(k in name for k in ["nano", "tiny", "mini"]):
        size_b = 1.0
    elif "large" in name:
        size_b = 30.0
    else:
        size_b = 7.0   # safe default assumption

    # INT4 quant ≈ 0.5 bytes/param; 1B params ≈ 0.5 GB + 20% overhead
    estimated_ram_gb = size_b * 0.5 * 1.2

    available = get_available_ram_gb()
    return estimated_ram_gb <= (available - 1.0)   # keep 1 GB headroom for OS
