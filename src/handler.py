#!/usr/bin/env python3
"""
Custom handler wrapper for RunPod ComfyUI worker.
Adds execution metadata (location + hardware specs) to job responses.

This handler integrates with the base image's handler system by:
1. Starting the base ComfyUI worker
2. Intercepting job responses to add execution metadata
"""

import json
import logging
import os
import sys
import time
import subprocess
import threading
from typing import Dict, Any, Optional

import requests
import psutil
import pynvml

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Module-level cache for geolocation data
_cached_location: Optional[Dict[str, Any]] = None


def get_geolocation() -> Optional[Dict[str, Any]]:
    """Fetch geolocation data from ifconfig.co API with caching."""
    global _cached_location
    
    if _cached_location is not None:
        return _cached_location
    
    try:
        logger.info("Fetching geolocation data...")
        response = requests.get("https://ifconfig.co/json", timeout=5)
        response.raise_for_status()
        
        geo_data = response.json()
        _cached_location = {
            "ip": geo_data.get("ip"),
            "city": geo_data.get("city"),
            "region": geo_data.get("region"),
            "country": geo_data.get("country"),
            "latitude": geo_data.get("latitude"),
            "longitude": geo_data.get("longitude")
        }
        
        logger.info(f"Geolocation cached: {geo_data.get('city')}, {geo_data.get('region')}")
        return _cached_location
        
    except Exception as e:
        logger.warning(f"Failed to fetch geolocation: {e}")
        return None


def get_gpu_info() -> Optional[Dict[str, Any]]:
    """Get GPU information using pynvml."""
    try:
        pynvml.nvmlInit()
        device_count = pynvml.nvmlDeviceGetCount()
        
        if device_count == 0:
            logger.warning("No NVIDIA GPUs found")
            return None
        
        # Get info for first GPU (most common case)
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        
        # Get GPU name
        name = pynvml.nvmlDeviceGetName(handle).decode('utf-8')
        
        # Get power draw
        power_draw = pynvml.nvmlDeviceGetPowerUsage(handle) / 1000.0  # Convert mW to W
        
        # Get utilization
        util = pynvml.nvmlDeviceGetUtilizationRates(handle)
        utilization_percent = util.gpu
        
        # Get memory info
        mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
        memory_used_mb = mem_info.used // (1024 * 1024)
        memory_total_mb = mem_info.total // (1024 * 1024)
        
        # Get temperature
        temperature = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
        
        return {
            "name": name,
            "power_draw_watts": power_draw,
            "utilization_percent": utilization_percent,
            "memory_used_mb": memory_used_mb,
            "memory_total_mb": memory_total_mb,
            "temperature_celsius": temperature
        }
        
    except Exception as e:
        logger.warning(f"Failed to get GPU info: {e}")
        return None


def get_system_info() -> Dict[str, Any]:
    """Get basic system information."""
    try:
        # CPU info
        cpu_info = {
            "model": "Unknown",
            "cores": psutil.cpu_count(logical=False)  # Physical cores
        }
        
        # Try to get CPU model from /proc/cpuinfo
        try:
            with open('/proc/cpuinfo', 'r') as f:
                for line in f:
                    if line.startswith('model name'):
                        cpu_info["model"] = line.split(':')[1].strip()
                        break
        except:
            pass
        
        # Memory info
        memory = psutil.virtual_memory()
        memory_total_gb = memory.total // (1024 * 1024 * 1024)
        
        return {
            "cpu": cpu_info,
            "memory_total_gb": memory_total_gb
        }
        
    except Exception as e:
        logger.warning(f"Failed to get system info: {e}")
        return {
            "cpu": {"model": "Unknown", "cores": 0},
            "memory_total_gb": 0
        }


def collect_execution_metadata() -> Dict[str, Any]:
    """Collect all execution metadata."""
    metadata = {
        "location": get_geolocation(),
        "hardware": {
            "gpu": get_gpu_info(),
            **get_system_info()
        }
    }
    
    return metadata


def handler(job):
    """
    Custom handler that integrates with RunPod serverless architecture.
    
    This handler:
    1. Collects execution metadata
    2. Processes the job using ComfyUI
    3. Adds metadata to the response
    """
    try:
        logger.info("Custom handler: Starting job processing...")
        
        # Collect execution metadata first
        logger.info("Collecting execution metadata...")
        execution_metadata = collect_execution_metadata()
        logger.info(f"Execution metadata collected: {execution_metadata}")
        
        # For now, return a simple response with metadata
        # TODO: Integrate with ComfyUI processing
        result = {
            "output": {
                "message": "Custom handler processing job",
                "job_input": job.get("input", {}),
                "execution_metadata": execution_metadata
            }
        }
        
        logger.info("Custom handler: Job processing completed successfully")
        return result
        
    except Exception as e:
        logger.error(f"Custom handler execution failed: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        # Return error with metadata if possible
        try:
            execution_metadata = collect_execution_metadata()
            return {
                "error": "Handler execution failed", 
                "details": str(e),
                "execution_metadata": execution_metadata
            }
        except:
            return {
                "error": "Handler execution failed", 
                "details": str(e)
            }


if __name__ == "__main__":
    # This allows the handler to be called directly for testing
    import sys
    if len(sys.argv) > 1:
        test_job = {"input": json.loads(sys.argv[1])}
        result = handler(test_job)
        print(json.dumps(result, indent=2))
