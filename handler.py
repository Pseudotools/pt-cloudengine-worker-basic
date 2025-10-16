import os
import sys
from typing import Any, Dict, Optional

# Add diagnostic logging at module level
print(f"[worker_metadata][MODULE] handler.py module loaded at startup")
print(f"[worker_metadata][MODULE] Python path: {sys.path}")
print(f"[worker_metadata][MODULE] Current working directory: {os.getcwd()}")
print(f"[worker_metadata][MODULE] Handler file location: {__file__}")

# Third-party libs used inside the container
try:
    import requests  # type: ignore
except Exception:  # pragma: no cover
    requests = None  # type: ignore

try:
    import psutil  # type: ignore
except Exception:  # pragma: no cover
    psutil = None  # type: ignore

try:
    import pynvml  # type: ignore
except Exception:  # pragma: no cover
    pynvml = None  # type: ignore


_geo_cache: Dict[str, Any] = {}
_LOG_LEVEL = os.environ.get("LOG_LEVEL", "info").upper()


def _log_debug(msg: str) -> None:
    if _LOG_LEVEL == "DEBUG":
        print(f"[worker_metadata][DEBUG] {msg}")


def _get_geo_cached() -> Optional[Dict[str, Any]]:
    if "geo" in _geo_cache:
        return _geo_cache["geo"]
    if requests is None:
        _log_debug("requests not available; skipping geolocation")
        _geo_cache["geo"] = None
        return None
    try:
        _log_debug("fetching geolocation from ifconfig.co")
        resp = requests.get("https://ifconfig.co/json", timeout=5)
        resp.raise_for_status()
        data = resp.json()
        _geo_cache["geo"] = {
            "ip": data.get("ip"),
            "city": data.get("city"),
            "region": data.get("region"),
            "country": data.get("country"),
            "latitude": data.get("latitude"),
            "longitude": data.get("longitude"),
        }
    except Exception as e:
        _log_debug(f"geolocation fetch failed: {e}")
        _geo_cache["geo"] = None
    return _geo_cache["geo"]


def _gpu_info() -> Optional[Dict[str, Any]]:
    if pynvml is None:
        _log_debug("pynvml not available; skipping GPU info")
        return None
    try:
        _log_debug("initializing NVML")
        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        utilization = pynvml.nvmlDeviceGetUtilizationRates(handle)
        memory = pynvml.nvmlDeviceGetMemoryInfo(handle)
        name = pynvml.nvmlDeviceGetName(handle)
        gpu_name = name.decode("utf-8") if isinstance(name, bytes) else str(name)
        power_watts = float(pynvml.nvmlDeviceGetPowerUsage(handle)) / 1000.0
        temperature_celsius = pynvml.nvmlDeviceGetTemperature(
            handle, pynvml.NVML_TEMPERATURE_GPU
        )
        _log_debug(f"gpu={gpu_name} util={getattr(utilization,'gpu',None)}% temp={temperature_celsius}C")
        return {
            "name": gpu_name,
            "power_draw_watts": power_watts,
            "utilization_percent": getattr(utilization, "gpu", None),
            "memory_used_mb": memory.used // (1024 * 1024),
            "memory_total_mb": memory.total // (1024 * 1024),
            "temperature_celsius": temperature_celsius,
        }
    except Exception as e:
        _log_debug(f"NVML probe failed: {e}")
        return None


def _system_info() -> Dict[str, Any]:
    cpu_model = "Unknown"
    cores = 0
    total_mem_gb = 0

    try:
        with open("/proc/cpuinfo", "r") as f:
            for line in f:
                if line.startswith("model name"):
                    cpu_model = line.split(":", 1)[1].strip()
                    break
    except Exception as e:
        _log_debug(f"cpuinfo read failed: {e}")
        pass

    try:
        if psutil is not None:
            physical = psutil.cpu_count(logical=False)
            cores = int(physical) if physical is not None else 0
            total_mem_gb = psutil.virtual_memory().total // (1024 * 1024 * 1024)
    except Exception as e:
        _log_debug(f"psutil probe failed: {e}")
        pass

    return {
        "cpu": {"model": cpu_model, "cores": cores},
        "memory_total_gb": total_mem_gb,
    }


def _collect_metadata() -> Dict[str, Any]:
    return {
        "location": _get_geo_cached(),
        "hardware": {"gpu": _gpu_info(), **_system_info()},
    }


def handler(job: Dict[str, Any]) -> Dict[str, Any]:
    print(f"[worker_metadata][INFO] Custom handler.py called with job ID: {job.get('id', 'unknown')}")
    
    # Import base handler from the image and call it. The base image places rp_handler in /app
    if "/app" not in sys.path:
        sys.path.append("/app")
    
    try:
        from rp_handler import handler as base_handler  # type: ignore
        print(f"[worker_metadata][INFO] Successfully imported base rp_handler")
    except ImportError as e:
        print(f"[worker_metadata][ERROR] Failed to import rp_handler: {e}")
        # Fallback: return job without metadata if base handler unavailable
        return {"output": {"error": "Base handler unavailable"}, "worker_metadata": {"error": str(e)}}

    print(f"[worker_metadata][INFO] Invoking base rp_handler.handler")
    result = base_handler(job)

    print(f"[worker_metadata][INFO] Base handler returned: {type(result)}")
    print(f"[worker_metadata][INFO] Collecting worker metadata")
    metadata = _collect_metadata()

    # Attach metadata without changing images structure
    if isinstance(result, dict):
        output = result.get("output")
        if isinstance(output, dict):
            output["worker_metadata"] = metadata
            print(f"[worker_metadata][INFO] Added metadata to output dict")
        else:
            result["worker_metadata"] = metadata
            print(f"[worker_metadata][INFO] Added metadata to result dict")
        return result
    else:
        print(f"[worker_metadata][INFO] Wrapping non-dict result with metadata")
        return {"output": result, "worker_metadata": metadata}


