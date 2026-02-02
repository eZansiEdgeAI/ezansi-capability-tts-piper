"""
Hardware detection module for eZansi TTS capability.

This module detects system hardware capabilities including:
- Architecture (x86_64, aarch64, armv7l, etc.)
- Available RAM
- CPU cores
- GPU availability
"""

import os
import platform
import subprocess
from typing import Dict, Optional


class HardwareDetector:
    """Detect and report system hardware capabilities."""

    def __init__(self):
        self._cache: Optional[Dict] = None

    def detect(self) -> Dict:
        """
        Detect all hardware capabilities.
        
        Returns:
            Dict containing architecture, ram_mb, cpu_cores, gpu_type
        """
        if self._cache is not None:
            return self._cache

        self._cache = {
            "architecture": self._detect_architecture(),
            "ram_mb": self._detect_ram_mb(),
            "cpu_cores": self._detect_cpu_cores(),
            "gpu_type": self._detect_gpu(),
        }
        return self._cache

    def _detect_architecture(self) -> str:
        """
        Detect system architecture.
        
        Returns:
            Architecture string (e.g., 'x86_64', 'aarch64', 'armv7l')
        """
        return platform.machine()

    def _detect_ram_mb(self) -> int:
        """
        Detect available system RAM in MB.
        
        Returns:
            Available RAM in megabytes
        """
        try:
            # Try reading from /proc/meminfo (Linux)
            with open("/proc/meminfo", "r") as f:
                for line in f:
                    if line.startswith("MemAvailable:"):
                        # MemAvailable is in kB
                        kb = int(line.split()[1])
                        return kb // 1024
            
            # Fallback to MemTotal if MemAvailable not found
            with open("/proc/meminfo", "r") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        kb = int(line.split()[1])
                        return kb // 1024
        except (FileNotFoundError, ValueError, IndexError):
            pass
        
        # Fallback: assume minimal RAM
        return 512

    def _detect_cpu_cores(self) -> int:
        """
        Detect number of CPU cores.
        
        Returns:
            Number of CPU cores
        """
        try:
            return os.cpu_count() or 1
        except Exception:
            return 1

    def _detect_gpu(self) -> str:
        """
        Detect GPU availability and type.
        
        Returns:
            GPU type: 'cuda', 'rocm', 'openvino', or 'none'
        """
        # Check for NVIDIA CUDA
        if self._check_cuda():
            return "cuda"
        
        # Check for AMD ROCm
        if self._check_rocm():
            return "rocm"
        
        # Check for Intel OpenVINO
        if self._check_openvino():
            return "openvino"
        
        return "none"

    def _check_cuda(self) -> bool:
        """Check if NVIDIA CUDA is available."""
        try:
            result = subprocess.run(
                ["nvidia-smi"],
                capture_output=True,
                timeout=5,
                check=False
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def _check_rocm(self) -> bool:
        """Check if AMD ROCm is available."""
        try:
            result = subprocess.run(
                ["rocm-smi"],
                capture_output=True,
                timeout=5,
                check=False
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def _check_openvino(self) -> bool:
        """Check if Intel OpenVINO is available."""
        # Check for common OpenVINO environment variables or libraries
        return (
            os.path.exists("/opt/intel/openvino") or
            "INTEL_OPENVINO_DIR" in os.environ
        )

    def get_recommended_resources(self) -> Dict:
        """
        Get recommended resource allocation based on detected hardware.
        
        Returns:
            Dict with recommended ram_mb, cpu_cores, and accelerator settings
        """
        hw = self.detect()
        
        # Base requirements for Piper TTS
        base_ram = 300  # MB
        base_cpu = 1
        
        # Calculate recommended resources (use a portion of available)
        available_ram = hw["ram_mb"]
        available_cpu = hw["cpu_cores"]
        
        # Use up to 50% of available RAM, minimum base requirement
        recommended_ram = max(base_ram, min(600, available_ram // 2))
        
        # Use 1 core for small systems, up to 2 for larger systems
        recommended_cpu = min(2, max(1, available_cpu // 2))
        
        return {
            "ram_mb": recommended_ram,
            "cpu_cores": recommended_cpu,
            "accelerator": hw["gpu_type"],
            "architecture": hw["architecture"],
        }


# Global instance
_detector = HardwareDetector()


def get_hardware_info() -> Dict:
    """Get detected hardware information."""
    return _detector.detect()


def get_recommended_resources() -> Dict:
    """Get recommended resource allocation."""
    return _detector.get_recommended_resources()
