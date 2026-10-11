"""Fail-closed GPU workload supervisor. Never installs, resets or changes GPU settings."""
import argparse, json, os, subprocess, sys, time
from pathlib import Path
from gpu_telemetry import POLICY, ROOT, atomic_json, log_event, read_live, violations, recovery_ok, utc
from windows_job import OwnedJob

def fake_sample(initial, scenario, count):
    data=json.loads(json.dumps(initial))
    data["source"]="SIMULATED_TEST_ONLY"
    data.update(utc=utc(),captured_monotonic=time.monotonic())
    if count >= 6:
        if scenario=="hot": data["core_c"]=75
        elif scenario=="missing": data["core_c"]=None
        elif scenario=="thermal_flag": data["flags"]["clocks_event_reason_hw_thermal_slowdown"]="Active"
        elif scenario=="power": data["power_w"]=350
        elif scenario=="timeout": raise TimeoutError("SIMULATED telemetry timeout")
        elif scenario=="hang": time.sleep(30)
        elif scenario=="malformed": raise ValueError("SIMULATED malformed telemetry")
    return data

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--spec",required=True)
    args=ap.parse_args()
    spec=json.loads(Path(args.spec).read_text(encoding="utf-8"))
    run=Path(spec["run_dir"]).resolve()
    if not run.is_relative_to(ROOT/"logs"):
        raise ValueError("Run logs must stay under this runtime root")
    run.mkdir(parents=True,exist_ok=False)
    simulation=spec.get("simulation",False)
    command=spec["command"]
    script=Path(command[1]).resolve()
    allowed=[ROOT/"test_worker.py"] if simulation or spec.get("cpu_only_diagnostic",False) else [ROOT/"smoke_inference.py",ROOT/"runtime_capability.py",ROOT/"query_inference.py"]
    if script not in allowed or not Path(command[0]).is_absolute():
        raise ValueError("Workload outside the explicit reviewed allowlist")
    if not 0 < spec.get("max_seconds",600) <= POLICY["max_workload_seconds"]:
        raise ValueError("Workload duration outside policy")
    # No GPU child exists until telemetry, lease and job setup all pass.
    atomic_json(run/"guard-lease.json",{"pid":os.getpid(),"monotonic":time.monotonic(),"disarmed":False})
    atomic_json(run/"spec.json",spec)
    count=0
    baseline=json.loads((ROOT/"evidence/idle-baseline-02/summary.json").read_text(encoding="utf-8"))
    if baseline.get("status") != "BASELINE_READY":
        raise ValueError("A successful observed idle baseline is required")
    if not simulation and baseline.get("synthetic"):
        raise ValueError("Synthetic test evidence cannot authorize live execution")
    seed=baseline["last"]
    initial=fake_sample(seed,"normal",0) if simulation else read_live()
    atomic_json(run/"initial.json",initial)
    issue=violations(initial,starting=True)
    log_event(run/"vitals.jsonl","preflight",telemetry=initial,violations=issue)
    if issue:
        atomic_json(run/"result.json",{"status":"PREFLIGHT_REFUSED","reasons":issue,"workload_started":False})
        return 3
    sentry_command=[sys.executable,str(ROOT/"guard_sentry.py"),"--guard-pid",str(os.getpid()),"--run-dir",str(run)]
    if simulation: sentry_command.append("--simulation")
    with (run/"sentry-console.txt").open("x",encoding="utf-8") as sentry_console:
        sentry=subprocess.Popen(sentry_command,creationflags=subprocess.CREATE_NO_WINDOW,
                            stdin=subprocess.DEVNULL,stdout=sentry_console,stderr=sentry_console,close_fds=True)
    job=None
    started=time.monotonic()
    outcome="ABORTED"
    reason=[]
    exit_code=None
    work_started=False
    try:
        deadline=time.monotonic()+2
        while not (run/"sentry-lease.json").exists():
            if sentry.poll() is not None or time.monotonic()>deadline:
                raise RuntimeError("Independent sentry failed readiness")
            time.sleep(0.02)
        job=OwnedJob()
        pid=job.launch(command,ROOT)
        work_started=True
        atomic_json(run/"owned-workload.json",{"pid":pid,"guard_pid":os.getpid(),"sentry_pid":sentry.pid,
                    "job_kill_on_close":True,"created_suspended_then_assigned":True,"simulation":simulation})
        log_event(run/"vitals.jsonl","workload_started",pid=pid)
        while True:
            sample_start=time.monotonic()
            if sentry.poll() is not None: raise RuntimeError("Independent sentry stopped with exit code "+str(sentry.returncode))
            s=json.loads((run/"sentry-lease.json").read_text(encoding="utf-8"))
            if time.monotonic()-s["monotonic"] > POLICY["lease_timeout_seconds"]:
                raise RuntimeError("Independent sentry lease stale")
            if (run/"STOP").exists():
                reason=["operator_stop"]; break
            if time.monotonic()-started >= spec.get("max_seconds",600):
                reason=["workload_wall_time_limit"]; break
            data=fake_sample(seed,spec.get("scenario","normal"),count) if simulation else read_live()
            count+=1
            reason=violations(data,initial)
            if reason:
                # Terminate before logging or any other potentially slow I/O.
                job.terminate()
                log_event(run/"vitals.jsonl","abort_trigger",telemetry=data,reasons=reason)
                break
            log_event(run/"vitals.jsonl","sample",telemetry=data,warning=data["core_c"]>=POLICY["core_warn_c"])
            atomic_json(run/"guard-lease.json",{"pid":os.getpid(),"monotonic":time.monotonic(),"disarmed":False})
            exit_code=job.poll()
            if exit_code is not None:
                outcome="COMPLETED" if exit_code==0 else "WORKLOAD_FAILED"
                reason=[] if exit_code==0 else ["nonzero_workload_exit"]
                break
            time.sleep(max(0,POLICY["poll_seconds"]-(time.monotonic()-sample_start)))
    except BaseException as exc:
        reason=["guard_exception:"+repr(exc)]
        if job:
            job.terminate()
        log_event(run/"vitals.jsonl","guard_exception",reasons=reason)
    finally:
        if job:
            try:
                job.terminate()
                until=time.monotonic()+2
                while job.active_count() and time.monotonic()<until: time.sleep(0.01)
                remaining=job.active_count()
            finally:
                job.close()
        else: remaining=0
    atomic_json(run/"workload-stop.json",{"utc":utc(),"status":outcome,"reasons":reason,
                "exit_code":exit_code,"workload_started":work_started,"remaining_job_processes":remaining})
    # Keep the independent sentry alive during recovery; it will take over if this guard dies.
    if not simulation:
        stable=None
        while True:
            atomic_json(run/"guard-lease.json",{"pid":os.getpid(),"monotonic":time.monotonic(),"disarmed":False})
            try:
                data=read_live()
                healthy=recovery_ok(data,initial)
                log_event(run/"vitals.jsonl","recovery",telemetry=data,healthy=healthy)
                stable=(stable or time.monotonic()) if healthy else None
                if stable and time.monotonic()-stable>=POLICY["recovery_stable_seconds"]: break
            except Exception as exc:
                stable=None
                log_event(run/"vitals.jsonl","recovery_telemetry_unavailable",error=repr(exc))
            time.sleep(POLICY["poll_seconds"])
    atomic_json(run/"result.json",{"utc":utc(),"status":outcome,"reasons":reason,"exit_code":exit_code,
          "workload_started":work_started,"remaining_job_processes":remaining,
          "recovery":"SIMULATED_NOT_A_HARDWARE_TEST" if simulation else "60_SECONDS_HEALTHY_OBSERVED",
          "simulation":simulation,"automatic_restart":False})
    atomic_json(run/"guard-lease.json",{"pid":os.getpid(),"monotonic":time.monotonic(),"disarmed":True})
    try: sentry.wait(timeout=2)
    except subprocess.TimeoutExpired: sentry.terminate()
    return 0 if outcome=="COMPLETED" else 2

if __name__=="__main__":
    raise SystemExit(main())
