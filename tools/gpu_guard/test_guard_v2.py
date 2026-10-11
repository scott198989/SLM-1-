"""Regression evidence for Windows heartbeat file contention; CPU only."""
import json, os, subprocess, sys, time, unittest
from unittest.mock import patch
from pathlib import Path
os.environ["FORGE_GPU_UUID"] = "GPU-SYNTHETIC-TEST"
from gpu_telemetry import ROOT, atomic_json
from test_guard import PolicyTests, IntegrationTests, pid_alive
from windows_job import process_handle, TerminateProcess, Close, checked

class HeartbeatTests(unittest.TestCase):
    def test_synthetic_baseline_cannot_launch_live(self):
        tag='synthetic-live-refusal-'+str(time.time_ns())
        run=ROOT/'logs'/tag; spec=ROOT/'tests'/(tag+'.json')
        atomic_json(spec,{'run_dir':str(run),'simulation':False,'max_seconds':10,
            'command':[sys.executable,str(ROOT/'runtime_capability.py')]})
        result=subprocess.run([sys.executable,str(ROOT/'gpu_guard.py'),'--spec',str(spec)],
            capture_output=True,text=True,timeout=5,creationflags=subprocess.CREATE_NO_WINDOW)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('Synthetic test evidence cannot authorize live execution',result.stderr)
        self.assertFalse((run/'owned-workload.json').exists())

    def test_query_workload_still_refuses_synthetic_live_baseline(self):
        tag='query-synthetic-live-refusal-'+str(time.time_ns())
        run=ROOT/'logs'/tag; spec=ROOT/'tests'/(tag+'.json')
        atomic_json(spec,{'run_dir':str(run),'simulation':False,'max_seconds':10,
            'command':[sys.executable,str(ROOT/'query_inference.py'),str(run)]})
        result=subprocess.run([sys.executable,str(ROOT/'gpu_guard.py'),'--spec',str(spec)],
            capture_output=True,text=True,timeout=5,creationflags=subprocess.CREATE_NO_WINDOW)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('Synthetic test evidence cannot authorize live execution',result.stderr)
        self.assertFalse((run/'owned-workload.json').exists())

    def test_transient_replace_contention(self):
        p=ROOT/'tests'/('transient-'+str(time.time_ns())+'.json')
        real=os.replace
        count=0
        def temporarily_busy(a,b):
            nonlocal count
            count+=1
            if count<=3: raise PermissionError('SIMULATED Windows sharing violation')
            real(a,b)
        with patch('gpu_telemetry.os.replace',temporarily_busy): atomic_json(p,{'complete':True})
        self.assertEqual(count,4)
        self.assertTrue(json.loads(p.read_text())['complete'])

    def test_persistent_contention_fails_within_lease(self):
        p=ROOT/'tests'/('persistent-'+str(time.time_ns())+'.json')
        start=time.monotonic()
        with patch('gpu_telemetry.os.replace',side_effect=PermissionError('SIMULATED persistent sharing violation')):
            with self.assertRaises(PermissionError): atomic_json(p,{'never_published':True})
        self.assertLess(time.monotonic()-start,.6)
        self.assertFalse(p.exists())

    def test_sentry_crash_kills_owned_tree(self):
        tag='sentry-crash-'+str(time.time_ns())
        run=ROOT/'logs'/tag; work=ROOT/'tests'/tag; spec=ROOT/'tests'/(tag+'.json')
        atomic_json(spec,{'run_dir':str(run),'simulation':True,'scenario':'normal','max_seconds':15,
            'command':[sys.executable,str(ROOT/'test_worker.py'),'--output',str(work),'--lifetime','30']})
        guard=subprocess.Popen([sys.executable,str(ROOT/'gpu_guard.py'),'--spec',str(spec)],creationflags=subprocess.CREATE_NO_WINDOW)
        until=time.monotonic()+5
        while not (work/'grandchild.json').exists() and time.monotonic()<until: time.sleep(.02)
        self.assertTrue((work/'grandchild.json').exists())
        ids=[json.loads((work/(role+'.json')).read_text())['pid'] for role in ('root','child','grandchild')]
        sentry=json.loads((run/'owned-workload.json').read_text())['sentry_pid']
        handle=process_handle(sentry)
        try: checked(TerminateProcess(handle,97))
        finally: Close(handle)
        guard.wait(timeout=5)
        result=json.loads((run/'result.json').read_text())
        self.assertEqual(result['status'],'ABORTED')
        self.assertEqual(result['remaining_job_processes'],0)
        self.assertFalse(any(pid_alive(x) for x in ids))

if __name__=='__main__':
    suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(c) for c in (PolicyTests,IntegrationTests,HeartbeatTests))
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    atomic_json(ROOT/'evidence/guard-tests-v2.json',{'tests':result.testsRun,'failures':len(result.failures),
        'errors':len(result.errors),'passed':result.wasSuccessful(),'GPU_workload_performed':False,'integration':IntegrationTests.results})
    raise SystemExit(0 if result.wasSuccessful() else 1)
