"""Meaningful CPU-only safety regression tests; never import ML or run GPU kernels."""
import copy, ctypes, json, os, subprocess, sys, time, unittest
os.environ["FORGE_GPU_UUID"] = "GPU-SYNTHETIC-TEST"
from pathlib import Path
from gpu_telemetry import ROOT, parse_xml, violations, POLICY, atomic_json
from windows_job import process_handle, alive, Close

SEED=parse_xml((ROOT/"fixtures/healthy-synthetic.xml").read_text(encoding="utf-8-sig"))
(ROOT/"tests").mkdir(exist_ok=True)
(ROOT/"evidence/idle-baseline-02").mkdir(parents=True,exist_ok=True)
atomic_json(ROOT/"evidence/idle-baseline-02/summary.json",{"status":"BASELINE_READY","last":SEED,"synthetic":True})

def sample():
    d=copy.deepcopy(SEED); d["gpu_util_percent"]=1; return d
def pid_alive(pid):
    try: h=process_handle(pid)
    except OSError: return False
    try: return alive(h)
    finally: Close(h)

class PolicyTests(unittest.TestCase):
    def test_current_supported_snapshot(self):
        self.assertEqual(violations(sample(),starting=True),[])
    def test_core_stop_at_75(self):
        d=sample(); d["core_c"]=75; self.assertIn("core_temperature_abort",violations(d))
    def test_thermal_margin(self):
        d=sample(); d["tlimit_c"]=15; self.assertIn("thermal_margin_abort",violations(d))
    def test_power_cap(self):
        d=sample(); d["power_w"]=350; self.assertIn("power_abort",violations(d))
    def test_required_sensor_loss(self):
        for key in ("core_c","tlimit_c","power_w","fan_command_percent","graphics_mhz","pcie_replay_counter"):
            d=sample(); d[key]=None; self.assertIn("required_sensor_missing:"+key,violations(d))
    def test_nonfinite_sensor(self):
        d=sample(); d["core_c"]=float("nan"); self.assertTrue(violations(d))
    def test_wrong_gpu_or_driver(self):
        for key in ("uuid","driver"):
            d=sample(); d[key]="changed"; self.assertTrue(violations(d))
    def test_no_invented_optional_sensors(self):
        d=sample(); self.assertIsNone(d["memory_c"]); self.assertIsNone(d["hotspot_c"])
        self.assertEqual(violations(d,d),[])
    def test_optional_sensor_loss_after_support(self):
        initial=sample(); initial["memory_c"]=50
        self.assertIn("previously_supported_sensor_lost:memory_c",violations(sample(),initial))
    def test_optional_memory_and_hotspot_thresholds(self):
        for key in ("memory_c","hotspot_c"):
            d=sample(); d[key]=85; self.assertIn(key+"_abort",violations(d))
    def test_fan_zero_when_hot(self):
        d=sample(); d["core_c"]=65; d["fan_command_percent"]=0
        self.assertIn("fan_command_zero_while_hot",violations(d))
    def test_zero_fan_at_idle_is_allowed(self):
        d=sample(); d["core_c"]=38; d["fan_command_percent"]=0
        self.assertEqual(violations(d),[])
    def test_thermal_or_power_brake_flag(self):
        for key in sample()["flags"]:
            d=sample(); d["flags"][key]="Active"; self.assertTrue(violations(d))
    def test_flag_loss(self):
        d=sample(); d["flags"]={}; self.assertTrue(violations(d))
    def test_new_hardware_errors(self):
        initial=sample(); initial["error_counters"]={"ECC":0}
        d=copy.deepcopy(initial); d["error_counters"]["ECC"]=1
        self.assertIn("hardware_error_counter_increased:ECC",violations(d,initial))
    def test_replay_growth(self):
        initial=sample(); d=copy.deepcopy(initial); d["pcie_replay_counter"]+=1
        self.assertIn("pcie_replay_increased",violations(d,initial))
    def test_settings_drift(self):
        d=sample(); d["power_limit_w"]=650; self.assertIn("power_setting_changed",violations(d))
    def test_malformed_xml(self):
        with self.assertRaises(Exception): parse_xml("<broken>")
    def test_no_gpu(self):
        with self.assertRaises(ValueError): parse_xml("<nvidia_smi_log></nvidia_smi_log>")

class IntegrationTests(unittest.TestCase):
    results=[]
    def scenario(self,name):
        token=str(time.time_ns())
        run=ROOT/"logs"/("test-"+name+"-"+token)
        work=ROOT/"tests"/("worker-"+name+"-"+token)
        specpath=ROOT/"tests"/("spec-"+name+"-"+token+".json")
        scenario="normal" if name in ("normal","guard_crash") else name
        spec={"run_dir":str(run),"simulation":True,"scenario":scenario,"max_seconds":15,
              "command":[sys.executable,str(ROOT/"test_worker.py"),"--output",str(work),
              "--lifetime","0.8" if name=="normal" else "30"]}
        atomic_json(specpath,spec)
        started=time.monotonic()
        guard=subprocess.Popen([sys.executable,str(ROOT/"gpu_guard.py"),"--spec",str(specpath)],
                stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
        until=time.monotonic()+5
        while not (work/"grandchild.json").exists() and time.monotonic()<until and guard.poll() is None:
            time.sleep(.02)
        self.assertTrue((work/"grandchild.json").exists(),"No full test tree: "+str(run))
        ids=[json.loads((work/(role+".json")).read_text())["pid"] for role in ("root","child","grandchild")]
        fault=time.monotonic()
        if name=="guard_crash":
            guard.terminate()
        stdout,stderr=guard.communicate(timeout=12)
        until=time.monotonic()+2
        while any(pid_alive(pid) for pid in ids) and time.monotonic()<until: time.sleep(.02)
        self.assertFalse(any(pid_alive(pid) for pid in ids),"Owned child/grandchild escaped: "+str(ids))
        if name in ("guard_crash","hang"):
            deadline=time.monotonic()+2
            while not (run/"SENTRY_ABORT.json").exists() and time.monotonic()<deadline: time.sleep(.02)
            self.assertTrue((run/"SENTRY_ABORT.json").exists(),"Independent sentry did not record fault")
            result=json.loads((run/"SENTRY_ABORT.json").read_text())
            self.assertEqual(result["reason"],"guard_process_died" if name=="guard_crash" else "guard_lease_expired")
        else:
            self.assertTrue((run/"result.json").exists(),stderr)
            result=json.loads((run/"result.json").read_text())
            self.assertEqual(result["status"],"COMPLETED" if name=="normal" else "ABORTED")
            self.assertEqual(result["remaining_job_processes"],0)
        elapsed=time.monotonic()-started
        self.assertLess(elapsed,10)
        self.results.append({"scenario":name,"run":str(run),"owned_pids":ids,"all_stopped":True,
            "elapsed_seconds":elapsed,"seconds_from_explicit_crash":time.monotonic()-fault if name=="guard_crash" else None,
            "result":result})
    def test_normal_completion_tree(self): self.scenario("normal")
    def test_temperature_abort_tree(self): self.scenario("hot")
    def test_missing_sensor_abort_tree(self): self.scenario("missing")
    def test_timeout_abort_tree(self): self.scenario("timeout")
    def test_power_abort_tree(self): self.scenario("power")
    def test_thermal_flag_abort_tree(self): self.scenario("thermal_flag")
    def test_malformed_telemetry_abort_tree(self): self.scenario("malformed")
    def test_guard_crash_kills_tree(self): self.scenario("guard_crash")
    def test_guard_hang_sentry_kills_tree(self): self.scenario("hang")

if __name__=="__main__":
    suite=unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(PolicyTests),
                              unittest.defaultTestLoader.loadTestsFromTestCase(IntegrationTests)])
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    atomic_json(ROOT/"evidence/guard-tests.json",{"tests":result.testsRun,
        "failures":len(result.failures),"errors":len(result.errors),"passed":result.wasSuccessful(),
        "GPU_workload_performed":False,"integration":IntegrationTests.results})
    raise SystemExit(0 if result.wasSuccessful() else 1)
