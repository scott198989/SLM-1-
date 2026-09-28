"""GPU monitoring contract tested without accessing or changing GPU hardware."""

from types import SimpleNamespace
from contextlib import nullcontext
import subprocess
import time
from unittest.mock import patch

import pytest
import torch

from forge1.hardware import ThermalGuard, gpu_telemetry, telemetry_device_id


GPU_UUID = "GPU-12345678-abcd-1234-abcd-1234567890ab"


def test_telemetry_parses_read_only_query_and_has_subprocess_timeout():
    output = "Fixture GPU, 62, 145.5, 4096, 32768, 80\n"
    with patch("forge1.hardware.subprocess.run", return_value=SimpleNamespace(stdout=output)) as run:
        result = gpu_telemetry(0)
    assert result == {"name": "Fixture GPU", "temperature_c": 62, "power_w": 145.5,
                      "memory_used_mib": 4096, "memory_total_mib": 32768, "utilization_percent": 80}
    command = run.call_args.args[0]
    assert command[0] == "nvidia-smi"
    assert all(flag not in command for flag in ("-pl", "-lgc", "--power-limit", "--gpu-reset"))
    assert run.call_args.kwargs["timeout"] <= 5
    assert run.call_args.kwargs["check"] is True
    assert run.call_args.kwargs.get("shell", False) is False


@pytest.mark.parametrize("error", [FileNotFoundError("missing"),
    subprocess.TimeoutExpired("nvidia-smi", 5), subprocess.CalledProcessError(1, "nvidia-smi")])
def test_query_failure_is_unavailable_not_zero_temperature(error):
    with patch("forge1.hardware.subprocess.run", side_effect=error):
        assert gpu_telemetry() is None


@pytest.mark.parametrize("output", ["", "Fixture, 62", "Fixture, N/A, 1, 2, 3, 4",
    "Fixture, nan, 1, 2, 3, 4", "Fixture, inf, 1, 2, 3, 4",
    "Fixture, 62, nan, 2, 3, 4", "Fixture, 62, 1, 2, inf, 4"])
def test_malformed_and_nonfinite_telemetry_fails_closed(output):
    with patch("forge1.hardware.subprocess.run", return_value=SimpleNamespace(stdout=output)):
        assert gpu_telemetry() is None


def test_initial_missing_telemetry_requests_stop_and_thread_closes():
    with patch("forge1.hardware.gpu_telemetry", return_value=None):
        guard = ThermalGuard(maximum_c=83, interval_seconds=0.001).start()
        try:
            assert guard.reason is not None
            assert "unavailable" in guard.reason.lower()
            assert guard.latest is None
        finally:
            guard.close()
        assert not guard._thread.is_alive()


def test_thermal_threshold_stop_retains_peak_and_latest():
    readings = [{"temperature_c": 60.0}, {"temperature_c": 83.0}]
    with patch("forge1.hardware.gpu_telemetry", side_effect=readings):
        guard = ThermalGuard(maximum_c=83, interval_seconds=0.001).start()
        try:
            deadline = time.monotonic() + 0.5
            while guard.reason is None and time.monotonic() < deadline:
                time.sleep(0.001)
            assert guard.reason is not None
            assert "83" in guard.reason
            assert guard.peak_c == 83
            assert guard.latest == readings[-1]
        finally:
            guard.close()


def test_telemetry_loss_after_valid_read_stops_instead_of_reusing_stale_temperature():
    with patch("forge1.hardware.gpu_telemetry", side_effect=[{"temperature_c": 58.0}, None]):
        guard = ThermalGuard(maximum_c=83, interval_seconds=0.001).start()
        try:
            deadline = time.monotonic() + 0.5
            while guard.reason is None and time.monotonic() < deadline:
                time.sleep(0.001)
            assert guard.reason is not None
            assert "unavailable" in guard.reason.lower()
            assert guard.peak_c == 58
            assert guard.latest is None
        finally:
            guard.close()


@pytest.mark.parametrize("threshold", [39.9, 85.1, float("nan"), float("inf")])
def test_temperature_threshold_validation(threshold):
    with pytest.raises(ValueError):
        ThermalGuard(maximum_c=threshold)


def test_cuda_benchmark_telemetry_failure_stops_before_model_allocation():
    from forge1.benchmark import benchmark
    from forge1.config import ModelConfig

    class FailedGuard:
        reason = "GPU telemetry unavailable; stopping conservatively"
        closed = False
        def start(self):
            return self
        def close(self):
            self.closed = True

    guard = FailedGuard()
    with patch("forge1.benchmark.torch.cuda.is_available", return_value=True), \
         patch("forge1.benchmark.torch.cuda.current_device", return_value=0), \
         patch("forge1.benchmark.telemetry_device_id", return_value=GPU_UUID), \
         patch("forge1.benchmark.gpu_telemetry", return_value=None), \
         patch("forge1.benchmark.ThermalGuard", return_value=guard), \
         patch("forge1.benchmark.ForgeModel", side_effect=AssertionError("Must not allocate a model")):
        with pytest.raises(RuntimeError, match="telemetry unavailable"):
            benchmark(ModelConfig(), device="cuda", steps=1)
    assert guard.closed is True


def test_cpu_telemetry_identity_never_calls_cuda():
    with patch("torch.cuda.is_available", side_effect=AssertionError("CPU must not query CUDA")), \
         patch("torch.cuda.current_device", side_effect=AssertionError("CPU must not query CUDA")), \
         patch("torch.cuda.get_device_properties", side_effect=AssertionError("CPU must not query CUDA")):
        assert telemetry_device_id("cpu") is None
        assert telemetry_device_id(torch.device("cpu")) is None


def test_remapped_cuda_uses_selected_logical_devices_uuid_in_nvidia_query(monkeypatch):
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "4,2")
    with patch("torch.cuda.is_available", return_value=True), \
         patch("torch.cuda.current_device", side_effect=AssertionError("Explicit index must be preserved")), \
         patch("torch.cuda.get_device_properties", return_value=SimpleNamespace(uuid=GPU_UUID)) as properties:
        identifier = telemetry_device_id("cuda:1")
    properties.assert_called_once_with(1)
    assert identifier == GPU_UUID
    with patch("forge1.hardware.subprocess.run", return_value=SimpleNamespace(stdout="Fixture, 60, 1, 2, 3, 4")) as run:
        assert gpu_telemetry(identifier)["temperature_c"] == 60
    assert f"--id={GPU_UUID}" in run.call_args.args[0]
    assert "--id=1" not in run.call_args.args[0]


def test_implicit_cuda_uses_current_device_and_accepts_raw_uuid_bytes():
    import uuid
    with patch("torch.cuda.is_available", return_value=True), \
         patch("torch.cuda.current_device", return_value=3), \
         patch("torch.cuda.get_device_properties", return_value=SimpleNamespace(uuid=uuid.UUID(GPU_UUID[4:]).bytes)) as properties:
        assert telemetry_device_id("cuda") == GPU_UUID
    properties.assert_called_once_with(3)


@pytest.mark.parametrize("identity", [None, "", "not-a-uuid", "GPU-0"])
def test_missing_or_unusable_uuid_never_falls_back_to_ordinal(identity):
    with patch("torch.cuda.is_available", return_value=True), \
         patch("torch.cuda.get_device_properties", return_value=SimpleNamespace(uuid=identity)):
        with pytest.raises(ValueError, match="usable GPU UUID"):
            telemetry_device_id(0)


def test_thermal_guard_passes_uuid_through_to_telemetry():
    with patch("forge1.hardware.gpu_telemetry", return_value=None) as query:
        guard = ThermalGuard(index=GPU_UUID).start()
        guard.close()
    query.assert_called_once_with(GPU_UUID)


def test_nondefault_benchmark_targets_selected_device_for_monitoring_and_memory():
    from forge1.benchmark import benchmark
    from forge1.config import ModelConfig

    target = torch.device("cuda:1")

    class CPUStandIn(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.weight = torch.nn.Parameter(torch.tensor(0.1))
            self.selected = None
        def to(self, device):
            self.selected = device
            return self
        def gradient_checkpointing_enable(self):
            pass
        def forward(self, ids, **kwargs):
            return SimpleNamespace(loss=(self.weight * ids.float()).square().mean(), aux={})

    class HealthyGuard:
        reason = None
        latest = {"temperature_c": 60}
        peak_c = 60
        closed = False
        def start(self):
            return self
        def close(self):
            self.closed = True

    model, guard = CPUStandIn(), HealthyGuard()
    real_randint = torch.randint

    def cpu_tokens(low, high, size, *, device):
        assert device == target
        return real_randint(low, high, size, device="cpu")

    with patch("forge1.benchmark.torch.cuda.is_available", return_value=True), \
         patch("forge1.benchmark.torch.cuda.current_device", side_effect=AssertionError("Must use cuda:1 explicitly")), \
         patch("forge1.benchmark.torch.manual_seed"), \
         patch("forge1.benchmark.telemetry_device_id", return_value=GPU_UUID) as identity, \
         patch("forge1.benchmark.gpu_telemetry", return_value=guard.latest) as telemetry, \
         patch("forge1.benchmark.ThermalGuard", return_value=guard) as guard_factory, \
         patch("forge1.benchmark.ForgeModel", return_value=model), \
         patch("forge1.benchmark.torch.randint", side_effect=cpu_tokens), \
         patch("forge1.benchmark.autocast_context", return_value=nullcontext()), \
         patch("forge1.benchmark.parameter_report", return_value={"unique_parameters": 1}), \
         patch("forge1.benchmark.torch.cuda.reset_peak_memory_stats") as reset, \
         patch("forge1.benchmark.torch.cuda.synchronize") as synchronize, \
         patch("forge1.benchmark.torch.cuda.max_memory_allocated", return_value=2 ** 30) as allocated, \
         patch("forge1.benchmark.torch.cuda.max_memory_reserved", return_value=2 * 2 ** 30) as reserved:
        result = benchmark(ModelConfig(), device="cuda:1", steps=1, warmup_steps=1,
                           sequence_length=4, precision="fp32")
    identity.assert_called_once_with(target)
    guard_factory.assert_called_once_with(83, index=GPU_UUID)
    assert all(call.args == (GPU_UUID,) for call in telemetry.call_args_list)
    assert len(telemetry.call_args_list) == 2
    reset.assert_called_once_with(target)
    allocated.assert_called_once_with(target)
    reserved.assert_called_once_with(target)
    assert all(call.args == (target,) for call in synchronize.call_args_list)
    assert model.selected == target and guard.closed
    assert result["device"] == "cuda:1" and result["telemetry_device_id"] == GPU_UUID
    assert result["peak_allocated_gib"] == 1 and result["peak_reserved_gib"] == 2
