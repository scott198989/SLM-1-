"""Independent lease enforcer. Holds no job handle, so guard death closes its job."""
import argparse, json, os, time
from pathlib import Path
from windows_job import process_handle, alive, TerminateProcess, Close, checked
from gpu_telemetry import atomic_json, log_event, read_live, recovery_ok, utc, POLICY

ap=argparse.ArgumentParser()
ap.add_argument("--guard-pid",type=int,required=True)
ap.add_argument("--run-dir",required=True)
ap.add_argument("--simulation",action="store_true")
args=ap.parse_args()
run=Path(args.run_dir)
handle=process_handle(args.guard_pid)
lease=run/"guard-lease.json"
reason=None
try:
    log_event(run/"sentry.jsonl","sentry_started",guard_pid=args.guard_pid,pid=os.getpid())
    while True:
        atomic_json(run/"sentry-lease.json",{"pid":os.getpid(),"monotonic":time.monotonic(),"utc":utc()})
        if not alive(handle):
            reason="guard_process_died"; break
        try:
            state=json.loads(lease.read_text(encoding="utf-8"))
            if state.get("disarmed") is True:
                log_event(run/"sentry.jsonl","sentry_disarmed"); break
            if time.monotonic()-state["monotonic"] > POLICY["lease_timeout_seconds"]:
                reason="guard_lease_expired"; break
        except Exception as exc:
            reason="guard_lease_unreadable:"+type(exc).__name__; break
        time.sleep(0.1)
    if reason:
        # Terminate the exact process handle opened before the workload starts: no PID reuse hazard.
        if alive(handle): checked(TerminateProcess(handle,92))
        log_event(run/"sentry.jsonl","emergency_guard_termination",reason=reason)
        atomic_json(run/"SENTRY_ABORT.json",{"utc":utc(),"reason":reason,"simulation":args.simulation})
        # Job kill-on-close takes care of all workload descendants. No restart.
        if not args.simulation:
            initial=json.loads((run/"initial.json").read_text(encoding="utf-8"))
            stable=None
            while True:
                try:
                    sample=read_live()
                    healthy=recovery_ok(sample,initial)
                    log_event(run/"recovery-sentry.jsonl","recovery_observation",telemetry=sample,healthy=healthy)
                    stable=(stable or time.monotonic()) if healthy else None
                    if stable and time.monotonic()-stable >= POLICY["recovery_stable_seconds"]:
                        atomic_json(run/"RECOVERED.json",{"utc":utc(),"observed_by":"independent_sentry"})
                        break
                except Exception as exc:
                    stable=None
                    log_event(run/"recovery-sentry.jsonl","telemetry_unavailable",error=repr(exc))
                time.sleep(POLICY["poll_seconds"])
finally:
    Close(handle)
