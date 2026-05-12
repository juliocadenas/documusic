"""
GPU Watchdog for DocuMusic
Monitors VRAM usage, GPU temperature, and CUDA health.
Alerts the frontend when the GPU is approaching dangerous levels.
Prevents generation jobs from starting when GPU is in critical state.
"""
import os
import time
import threading
import logging
import subprocess
import json

logger = logging.getLogger(__name__)

# Watchdog state (shared across threads)
_watchdog_state = {
    "vram_total_mb": 0,
    "vram_used_mb": 0,
    "vram_free_mb": 0,
    "vram_usage_pct": 0,
    "gpu_temp_c": 0,
    "gpu_utilization_pct": 0,
    "status": "unknown",       # "healthy", "warning", "critical", "offline"
    "alerts": [],              # List of active alerts
    "last_check": 0,
    "cuda_errors": 0,
    "generation_blocked": False,
    "block_reason": "",
}

# Thresholds
VRAM_WARNING_PCT = 85         # Warn when VRAM > 85%
VRAM_CRITICAL_PCT = 95        # Block generation when VRAM > 95%
TEMP_WARNING_C = 80           # Warn when temp > 80°C
TEMP_CRITICAL_C = 88          # Block when temp > 88°C
CHECK_INTERVAL_S = 5          # Check every 5 seconds
MAX_ALERTS = 10               # Keep last 10 alerts


def _add_alert(level: str, message: str):
    """Add an alert to the watchdog state."""
    alert = {
        "level": level,  # "warning", "critical", "info"
        "message": message,
        "timestamp": time.time(),
    }
    _watchdog_state["alerts"].insert(0, alert)
    # Keep only last MAX_ALERTS
    _watchdog_state["alerts"] = _watchdog_state["alerts"][:MAX_ALERTS]


def _read_gpu_stats_nvidia_smi() -> dict:
    """Read GPU stats using nvidia-smi (works inside container)."""
    try:
        cmd = [
            "nvidia-smi",
            "--query-gpu=memory.total,memory.used,memory.free,temperature.gpu,utilization.gpu",
            "--format=csv,noheader,nounits"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            parts = result.stdout.strip().split(", ")
            if len(parts) >= 5:
                return {
                    "vram_total_mb": int(parts[0]),
                    "vram_used_mb": int(parts[1]),
                    "vram_free_mb": int(parts[2]),
                    "gpu_temp_c": int(parts[3]),
                    "gpu_utilization_pct": int(parts[4]),
                }
    except Exception as e:
        logger.debug(f"[Watchdog] nvidia-smi failed: {e}")
    return {}


def _read_gpu_stats_torch() -> dict:
    """Read GPU stats using PyTorch (fallback)."""
    try:
        import torch
        if not torch.cuda.is_available():
            return {}
        
        total, used = torch.cuda.mem_get_info(0)
        free = total - used
        
        return {
            "vram_total_mb": total // (1024 * 1024),
            "vram_used_mb": used // (1024 * 1024),
            "vram_free_mb": free // (1024 * 1024),
        }
    except Exception as e:
        logger.debug(f"[Watchdog] torch stats failed: {e}")
        return {}
    return {}


def _check_gpu_health():
    """Perform a single GPU health check."""
    global _watchdog_state
    
    # Try nvidia-smi first (more info), then torch fallback
    stats = _read_gpu_stats_nvidia_smi()
    if not stats:
        stats = _read_gpu_stats_torch()
    
    if not stats:
        _watchdog_state["status"] = "offline"
        _watchdog_state["generation_blocked"] = True
        _watchdog_state["block_reason"] = "GPU no detectada"
        return
    
    # Update state
    _watchdog_state.update(stats)
    _watchdog_state["last_check"] = time.time()
    
    vram_total = stats.get("vram_total_mb", 1)
    vram_used = stats.get("vram_used_mb", 0)
    _watchdog_state["vram_usage_pct"] = round((vram_used / vram_total) * 100, 1) if vram_total > 0 else 0
    
    temp = stats.get("gpu_temp_c", 0)
    vram_pct = _watchdog_state["vram_usage_pct"]
    
    # Determine status
    alerts = []
    blocked = False
    block_reason = ""
    
    # Check VRAM
    if vram_pct >= VRAM_CRITICAL_PCT:
        alerts.append(("critical", f"VRAM crítica: {vram_pct}% ({vram_used}MB/{vram_total}MB)"))
        blocked = True
        block_reason = f"VRAM al {vram_pct}%, espera a que se libere"
    elif vram_pct >= VRAM_WARNING_PCT:
        alerts.append(("warning", f"VRAM alta: {vram_pct}% ({vram_used}MB/{vram_total}MB)"))
    
    # Check temperature
    if temp >= TEMP_CRITICAL_C:
        alerts.append(("critical", f"GPU sobrecalentada: {temp}°C (máx {TEMP_CRITICAL_C}°C)"))
        blocked = True
        block_reason = f"GPU a {temp}°C, muy caliente para generar"
    elif temp >= TEMP_WARNING_C:
        alerts.append(("warning", f"GPU caliente: {temp}°C"))
    
    # Add alerts
    for level, msg in alerts:
        _add_alert(level, msg)
    
    # Update status
    if blocked:
        _watchdog_state["status"] = "critical"
    elif alerts:
        _watchdog_state["status"] = "warning"
    else:
        _watchdog_state["status"] = "healthy"
    
    _watchdog_state["generation_blocked"] = blocked
    _watchdog_state["block_reason"] = block_reason


def _watchdog_loop():
    """Background thread that monitors GPU health."""
    logger.info("[Watchdog] 🐕 GPU Watchdog iniciado")
    while True:
        try:
            _check_gpu_health()
        except Exception as e:
            logger.error(f"[Watchdog] Error en check: {e}")
        time.sleep(CHECK_INTERVAL_S)


def start_watchdog():
    """Start the GPU watchdog background thread."""
    thread = threading.Thread(target=_watchdog_loop, daemon=True)
    thread.start()
    logger.info("[Watchdog] Thread lanzado")


def get_watchdog_status() -> dict:
    """Get the current watchdog status (for API endpoint)."""
    return dict(_watchdog_state)


def can_generate() -> tuple[bool, str]:
    """
    Check if the GPU is healthy enough to start a new generation.
    Returns (can_generate, reason_if_blocked).
    """
    status = _watchdog_state.get("status", "unknown")
    
    if status == "critical":
        return False, _watchdog_state.get("block_reason", "GPU en estado crítico")
    
    if status == "offline":
        return False, "GPU no disponible"
    
    # Check if there's already a generation running (VRAM > 80% usually means model loaded)
    vram_pct = _watchdog_state.get("vram_usage_pct", 0)
    if vram_pct > 90:
        return False, f"VRAM ocupada al {vram_pct}%, generación en curso"
    
    return True, "OK"
