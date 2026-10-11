"""Read-only NVIDIA telemetry and conservative workload policy. No ML imports."""
from __future__ import annotations
import json, math, os, subprocess, time
from datetime import datetime, timezone
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
GPU_UUID = os.environ.get("FORGE_GPU_UUID", "UNCONFIGURED")
SMI = r"C:\Windows\System32\nvidia-smi.exe"
POLICY = {
    "gpu_uuid": GPU_UUID, "driver_version": "591.86",
    "poll_seconds": 0.5, "query_timeout_seconds": 1.5,
    "lease_timeout_seconds": 3.0,
    "core_abort_c": 75, "core_warn_c": 65, "tlimit_abort_c": 15,
    "memory_abort_c_if_exposed": 85, "hotspot_abort_c_if_exposed": 85,
    "power_abort_w": 350, "fan_zero_abort_core_c": 65,
    "start_max_core_c": 50, "start_max_power_w": 100, "start_max_gpu_util_percent": 10,
    "max_workload_seconds": 600, "max_total_vram_used_mib": 8192,
    "recovery_max_core_c": 50, "recovery_max_power_w": 100,
    "recovery_stable_seconds": 60,
    "observed_power_limit_w": 600,
}
CRITICAL_FLAGS = ("clocks_event_reason_hw_slowdown", "clocks_event_reason_hw_thermal_slowdown",
    "clocks_event_reason_sw_thermal_slowdown", "clocks_event_reason_hw_power_brake_slowdown",
    "clocks_event_reason_sw_power_cap")
NUMERIC_FIELDS = {
    "core_c": "temperature/gpu_temp", "tlimit_c": "temperature/gpu_temp_tlimit",
    "memory_c": "temperature/memory_temp",
    "power_w": "gpu_power_readings/instant_power_draw",
    "average_power_w": "gpu_power_readings/average_power_draw",
    "power_limit_w": "gpu_power_readings/current_power_limit",
    "fan_command_percent": "fan_speed",
    "graphics_mhz": "clocks/graphics_clock", "memory_mhz": "clocks/mem_clock",
    "gpu_util_percent": "utilization/gpu_util", "memory_util_percent": "utilization/memory_util",
    "vram_used_mib": "fb_memory_usage/used", "vram_total_mib": "fb_memory_usage/total",
    "pcie_replay_counter": "pci/replay_counter",
}
REQUIRED = tuple(k for k in NUMERIC_FIELDS if k != "memory_c")

def utc():
    return datetime.now(timezone.utc).isoformat()

def atomic_json(path, obj):
    path = Path(path)
    temp = path.with_name(path.name + ".tmp")
    with temp.open("w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, allow_nan=False)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    # Windows readers may transiently hold the destination without FILE_SHARE_DELETE.
    # Bound sharing retries well below the 3 s watchdog lease; persistent I/O fails closed.
    deadline = time.monotonic() + 0.25
    while True:
        try:
            os.replace(temp, path)
            break
        except PermissionError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.01)

def log_event(path, event, **values):
    row = {"utc": utc(), "monotonic": time.monotonic(), "event": event, **values}
    with Path(path).open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, allow_nan=False) + "\n")
        f.flush()
        os.fsync(f.fileno())
    return row

def number(text):
    if text is None or text.strip() in ("N/A", "[N/A]", "Not Supported", ""):
        return None
    value = float(text.split()[0])
    if not math.isfinite(value):
        raise ValueError("Nonfinite sensor")
    return value

def parse_xml(text):
    root = ET.fromstring(text)
    gpus = root.findall("gpu")
    if len(gpus) != 1:
        raise ValueError("Expected exactly one queried GPU")
    g = gpus[0]
    data = {key: number(g.findtext(path)) for key, path in NUMERIC_FIELDS.items()}
    data.update(uuid=g.findtext("uuid"), name=g.findtext("product_name"),
                driver=root.findtext("driver_version"), pstate=g.findtext("performance_state"),
                recovery_action=g.findtext("gpu_recovery_action"),
                flags={key: g.findtext("clocks_event_reasons/" + key) for key in CRITICAL_FLAGS},
                hotspot_c=None, sensor_schema="nvidia-smi-591.86-xml-v1")
    data["error_counters"] = {}
    for section in ("ecc_errors/volatile", "ecc_errors/aggregate",
                    "retired_pages/multiple_single_bit_retirement",
                    "retired_pages/double_bit_retirement"):
        node = g.find(section)
        if node is not None:
            for item in node:
                value = item.text
                if value is not None:
                    try:
                        numeric = number(value)
                    except ValueError:
                        continue
                    if numeric is not None:
                        data["error_counters"][section + "/" + item.tag] = numeric
    return data

def read_live():
    if GPU_UUID == "UNCONFIGURED" or GPU_UUID == "GPU-SYNTHETIC-TEST":
        raise ValueError("A separately verified real GPU identity is required for live reads")
    started = time.monotonic()
    result = subprocess.run([SMI, "-q", "-x", "-i", GPU_UUID], capture_output=True,
            text=True, encoding="utf-8", timeout=POLICY["query_timeout_seconds"],
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), check=True)
    data = parse_xml(result.stdout)
    data.update(utc=utc(), captured_monotonic=time.monotonic(),
                query_seconds=time.monotonic()-started, source="LIVE_NVIDIA_SMI")
    return data

def violations(data, initial=None, starting=False):
    problems = []
    if data.get("uuid") != GPU_UUID:
        problems.append("gpu_identity_changed")
    if data.get("driver") != POLICY["driver_version"]:
        problems.append("driver_schema_changed")
    for key in REQUIRED:
        value = data.get(key)
        if not isinstance(value, (int, float)) or not math.isfinite(value):
            problems.append("required_sensor_missing:" + key)
    if problems:
        return problems
    if not 0 <= data["core_c"] <= 120 or not -30 <= data["tlimit_c"] <= 100:
        problems.append("temperature_invalid")
    if data["core_c"] >= POLICY["core_abort_c"]:
        problems.append("core_temperature_abort")
    if data["tlimit_c"] <= POLICY["tlimit_abort_c"]:
        problems.append("thermal_margin_abort")
    for key, threshold in (("memory_c", "memory_abort_c_if_exposed"), ("hotspot_c", "hotspot_abort_c_if_exposed")):
        value = data.get(key)
        if value is not None and (not math.isfinite(value) or value < 0 or value >= POLICY[threshold]):
            problems.append(key + "_abort")
        if initial and initial.get(key) is not None and value is None:
            problems.append("previously_supported_sensor_lost:" + key)
    if not 0 <= data["power_w"] < POLICY["power_abort_w"] or not 0 <= data["average_power_w"] < POLICY["power_abort_w"]:
        problems.append("power_abort")
    if data["power_limit_w"] != POLICY["observed_power_limit_w"]:
        problems.append("power_setting_changed")
    if not 0 <= data["fan_command_percent"] <= 200:
        problems.append("fan_invalid")
    if data["core_c"] >= POLICY["fan_zero_abort_core_c"] and data["fan_command_percent"] == 0:
        problems.append("fan_command_zero_while_hot")
    for key in ("gpu_util_percent", "memory_util_percent"):
        if not 0 <= data[key] <= 100:
            problems.append(key + "_invalid")
    if not 0 <= data["vram_used_mib"] <= POLICY["max_total_vram_used_mib"]:
        problems.append("vram_budget_exceeded")
    if not data.get("pstate", "").startswith("P"):
        problems.append("pstate_missing")
    if data.get("recovery_action") != "None":
        problems.append("gpu_recovery_action")
    for key in CRITICAL_FLAGS:
        if data.get("flags", {}).get(key) != "Not Active":
            problems.append("clock_or_thermal_flag:" + key)
    if initial:
        if data["pcie_replay_counter"] > initial["pcie_replay_counter"]:
            problems.append("pcie_replay_increased")
        for key, value in initial.get("error_counters", {}).items():
            if key not in data.get("error_counters", {}):
                problems.append("previously_supported_error_counter_lost:" + key)
            elif data["error_counters"][key] > value:
                problems.append("hardware_error_counter_increased:" + key)
    if starting:
        if data["core_c"] > POLICY["start_max_core_c"] or data["power_w"] > POLICY["start_max_power_w"]:
            problems.append("not_cool_for_start")
        if data["gpu_util_percent"] > POLICY["start_max_gpu_util_percent"]:
            problems.append("gpu_busy_at_start")
    return problems

def recovery_ok(data, initial):
    return not violations(data, initial) and data["core_c"] <= min(
        POLICY["recovery_max_core_c"], initial["core_c"] + 5) and data["power_w"] <= min(
        POLICY["recovery_max_power_w"], initial["power_w"] + 25)

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline-seconds", type=float, default=60)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=False)
    readings = []
    started = time.monotonic()
    while time.monotonic() - started < args.baseline_seconds:
        r = read_live()
        # Desktop rendering can cause brief utilization bursts without heat/power trouble.
        # Record these; require low utilization again at workload launch, not every idle sample.
        issues = [x for x in violations(r, readings[0] if readings else None, starting=True)
                  if x != "gpu_busy_at_start"]
        log_event(out / "vitals.jsonl", "baseline", telemetry=r, violations=issues)
        if issues:
            atomic_json(out / "summary.json", {"status":"BASELINE_FAILED", "violations":issues})
            raise SystemExit(2)
        readings.append(r)
        time.sleep(POLICY["poll_seconds"])
    summary = {"at_utc":utc(), "status":"BASELINE_READY", "samples":len(readings),
        "duration_seconds":time.monotonic()-started, "policy":POLICY,
        "core_min_max_c":[min(x["core_c"] for x in readings),max(x["core_c"] for x in readings)],
        "power_min_max_w":[min(x["power_w"] for x in readings),max(x["power_w"] for x in readings)],
        "gpu_util_min_max_percent":[min(x["gpu_util_percent"] for x in readings),max(x["gpu_util_percent"] for x in readings)],
        "supported":list(REQUIRED)+["pstate", "critical_clock_flags", "recovery_action"],
        "unsupported":["memory_junction_temperature", "hotspot_temperature", "physical_fan_rpm",
                       "connector_temperature_current", "ECC_counters_on_this_card"],
        "first":readings[0], "last":readings[-1]}
    atomic_json(out / "summary.json", summary)
    print(json.dumps(summary))
