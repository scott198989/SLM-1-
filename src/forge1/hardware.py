"""Read-only GPU monitoring. Never changes clocks, firmware, power, or fan settings."""
from __future__ import annotations

import subprocess
import math
import threading
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING
import uuid

if TYPE_CHECKING:
    import torch


def telemetry_device_id(device: str | int | torch.device) -> str | None:
    """Map a CUDA *logical* device to its stable NVIDIA GPU UUID.

    ``CUDA_VISIBLE_DEVICES`` can reorder/hide GPUs, whereas ``nvidia-smi --id``
    addresses physical devices. A UUID binds monitoring to the device PyTorch
    actually selected. CPU devices return None without calling any CUDA API.
    Missing/unsupported UUID metadata fails closed; there is no ordinal fallback.
    ``int`` means a logical CUDA ordinal; ``cuda`` uses the current CUDA device.
    """
    import torch

    if isinstance(device, bool):
        raise ValueError("Telemetry device must be a device name or a logical CUDA index")
    target = torch.device("cuda", device) if isinstance(device, int) else torch.device(device)
    if target.type == "cpu":
        return None
    if target.type != "cuda":
        raise ValueError("GPU telemetry supports CUDA devices only")
    if not torch.cuda.is_available():
        raise ValueError("CUDA telemetry requested without an available CUDA runtime")
    index = target.index if target.index is not None else torch.cuda.current_device()
    identity = getattr(torch.cuda.get_device_properties(index), "uuid", None)
    try:
        if isinstance(identity, bytes):
            identifier = uuid.UUID(bytes=identity)
        else:
            text = str(identity).strip()
            identifier = uuid.UUID(text.removeprefix("GPU-"))
    except (ValueError, AttributeError, TypeError) as error:
        raise ValueError("CUDA device lacks a usable GPU UUID; refusing to monitor a possibly different GPU") from error
    return f"GPU-{identifier}"


def gpu_telemetry(index: str | int = 0) -> dict[str, float | str] | None:
    try:
        result = subprocess.run(
            ["nvidia-smi", f"--id={index}",
             "--query-gpu=name,temperature.gpu,power.draw,memory.used,memory.total,utilization.gpu",
             "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=5,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), check=True,
        )
        values = [part.strip() for part in result.stdout.strip().split(",")]
        if len(values) != 6:
            return None
        reading = {"name": values[0], **{key: float(value) for key, value in zip(
            ("temperature_c", "power_w", "memory_used_mib", "memory_total_mib", "utilization_percent"),
            values[1:], strict=True)}}
        if any(not math.isfinite(value) or value < 0 for key, value in reading.items() if key != "name"):
            return None
        if not reading["name"] or reading["memory_total_mib"] <= 0 or reading["utilization_percent"] > 100:
            return None
        return reading
    except (OSError, subprocess.SubprocessError, ValueError):
        return None


@dataclass
class ThermalGuard:
    """Request a checkpoint/stop at the next optimizer boundary if too hot.

    The background reader is not a replacement for the GPU's own protections and
    cannot interrupt an in-flight kernel. Missing telemetry fails closed on CUDA.
    """
    maximum_c: float = 83.0
    index: str | int = 0
    interval_seconds: float = 2.0

    def __post_init__(self):
        if not 40 <= self.maximum_c <= 85:
            raise ValueError("Thermal threshold must be between 40 and 85 C")
        self.reason: str | None = None
        self.latest: dict | None = None
        self.peak_c: float = 0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def _poll(self):
        while not self._stop.is_set():
            reading = gpu_telemetry(self.index)
            self.latest = reading
            if reading is None:
                self.reason = "GPU telemetry unavailable; stopping conservatively"
                return
            self.peak_c = max(self.peak_c, float(reading["temperature_c"]))
            if self.peak_c >= self.maximum_c:
                self.reason = f"GPU temperature reached {self.peak_c:.0f} C (limit {self.maximum_c:.0f} C)"
                return
            self._stop.wait(self.interval_seconds)

    def start(self):
        self._thread = threading.Thread(target=self._poll, daemon=True, name="forge-thermal-guard")
        self._thread.start()
        # Verify the first read before launching expensive work.
        deadline = time.monotonic() + 6
        while self.latest is None and self.reason is None and time.monotonic() < deadline:
            time.sleep(0.02)
        if self.latest is None:
            self.reason = self.reason or "GPU telemetry initial read timed out"
        return self

    def close(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=6)
