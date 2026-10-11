"""Own only child workloads: suspended creation, no breakaway, kill on job close."""
import ctypes as C
from ctypes import wintypes as W
import subprocess

K = C.WinDLL("kernel32", use_last_error=True)
class BASIC_LIMIT(C.Structure):
    _fields_ = [("ProcessTime", C.c_longlong), ("JobTime", C.c_longlong), ("LimitFlags", W.DWORD),
                ("MinimumWorkingSet", C.c_size_t), ("MaximumWorkingSet", C.c_size_t),
                ("ActiveProcessLimit", W.DWORD), ("Affinity", C.c_size_t),
                ("PriorityClass", W.DWORD), ("SchedulingClass", W.DWORD)]
class IO_COUNTERS(C.Structure):
    _fields_ = [(n, C.c_ulonglong) for n in ("ReadOperations","WriteOperations","OtherOperations",
                 "ReadBytes","WriteBytes","OtherBytes")]
class EXTENDED_LIMIT(C.Structure):
    _fields_ = [("Basic", BASIC_LIMIT), ("Io", IO_COUNTERS), ("ProcessMemory", C.c_size_t),
                ("JobMemory", C.c_size_t), ("PeakProcessMemory", C.c_size_t), ("PeakJobMemory", C.c_size_t)]
class STARTUPINFO(C.Structure):
    _fields_ = [("cb", W.DWORD), ("reserved", W.LPWSTR), ("desktop", W.LPWSTR), ("title", W.LPWSTR),
                ("x", W.DWORD), ("y", W.DWORD), ("xsize", W.DWORD), ("ysize", W.DWORD),
                ("xchars", W.DWORD), ("ychars", W.DWORD), ("fill", W.DWORD), ("flags", W.DWORD),
                ("show", W.WORD), ("reserved2size", W.WORD), ("reserved2", C.POINTER(C.c_byte)),
                ("stdin", W.HANDLE), ("stdout", W.HANDLE), ("stderr", W.HANDLE)]
class PROCESSINFO(C.Structure):
    _fields_ = [("process", W.HANDLE), ("thread", W.HANDLE), ("pid", W.DWORD), ("tid", W.DWORD)]
class ACCOUNTING(C.Structure):
    _fields_ = [(n,C.c_longlong) for n in ("User","Kernel","UserPeriod","KernelPeriod")] + [
        ("PageFault",W.DWORD),("TotalProcesses",W.DWORD),("ActiveProcesses",W.DWORD),("TerminatedProcesses",W.DWORD)]

def bind(name, args, result):
    f = getattr(K, name); f.argtypes=args; f.restype=result; return f
CreateJob = bind("CreateJobObjectW",[C.c_void_p,W.LPCWSTR],W.HANDLE)
SetJob = bind("SetInformationJobObject",[W.HANDLE,C.c_int,C.c_void_p,W.DWORD],W.BOOL)
Assign = bind("AssignProcessToJobObject",[W.HANDLE,W.HANDLE],W.BOOL)
TerminateJob = bind("TerminateJobObject",[W.HANDLE,W.UINT],W.BOOL)
Close = bind("CloseHandle",[W.HANDLE],W.BOOL)
Resume = bind("ResumeThread",[W.HANDLE],W.DWORD)
Create = bind("CreateProcessW",[W.LPCWSTR,W.LPWSTR,C.c_void_p,C.c_void_p,W.BOOL,W.DWORD,
                               C.c_void_p,W.LPCWSTR,C.POINTER(STARTUPINFO),C.POINTER(PROCESSINFO)],W.BOOL)
GetExit = bind("GetExitCodeProcess",[W.HANDLE,C.POINTER(W.DWORD)],W.BOOL)
Wait = bind("WaitForSingleObject",[W.HANDLE,W.DWORD],W.DWORD)
Query = bind("QueryInformationJobObject",[W.HANDLE,C.c_int,C.c_void_p,W.DWORD,C.c_void_p],W.BOOL)
OpenProcess = bind("OpenProcess",[W.DWORD,W.BOOL,W.DWORD],W.HANDLE)
TerminateProcess = bind("TerminateProcess",[W.HANDLE,W.UINT],W.BOOL)

def checked(ok):
    if not ok:
        raise C.WinError(C.get_last_error())
    return ok

class OwnedJob:
    def __init__(self):
        self.handle = checked(CreateJob(None, None))
        self.process = None
        limits = EXTENDED_LIMIT()
        limits.Basic.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE; no breakaway bits.
        try:
            checked(SetJob(self.handle, 9, C.byref(limits), C.sizeof(limits)))
        except BaseException:
            Close(self.handle); self.handle=None; raise
    def launch(self, command, cwd):
        startup = STARTUPINFO(); startup.cb=C.sizeof(startup)
        info=PROCESSINFO()
        checked(Create(command[0], C.create_unicode_buffer(subprocess.list2cmdline(command)),
            None,None,False,0x4|0x08000000,None,str(cwd),C.byref(startup),C.byref(info)))
        self.process=info.process; self.pid=info.pid
        try:
            checked(Assign(self.handle, self.process))
            if Resume(info.thread) == 0xffffffff:
                raise C.WinError(C.get_last_error())
        except BaseException:
            TerminateProcess(self.process, 91)
            raise
        finally:
            Close(info.thread)
        return self.pid
    def poll(self):
        if not self.process: return None
        if Wait(self.process,0) == 0x102: return None
        exit_code=W.DWORD(); checked(GetExit(self.process,C.byref(exit_code)))
        return exit_code.value
    def active_count(self):
        stats=ACCOUNTING()
        checked(Query(self.handle,1,C.byref(stats),C.sizeof(stats),None))
        return stats.ActiveProcesses
    def terminate(self):
        if self.handle: checked(TerminateJob(self.handle,90))
    def close(self):
        if self.handle: Close(self.handle); self.handle=None
        if self.process: Close(self.process); self.process=None

def process_handle(pid):
    return checked(OpenProcess(0x100000|0x1000|0x1, False, int(pid)))
def alive(handle):
    return Wait(handle,0) == 0x102
