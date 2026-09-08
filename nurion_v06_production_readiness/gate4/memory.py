"""Process memory sampling helpers (Windows-friendly, no psutil required)."""

from __future__ import annotations

import ctypes
import sys
from typing import Dict


def sample_memory_mb() -> Dict:
    """Return working set / peak working set in MiB."""
    if sys.platform.startswith("win"):
        class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("cb", ctypes.c_ulong),
                ("PageFaultCount", ctypes.c_ulong),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        try:
            from ctypes import wintypes

            psapi = ctypes.WinDLL("psapi")
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            psapi.GetProcessMemoryInfo.argtypes = [
                wintypes.HANDLE,
                ctypes.POINTER(PROCESS_MEMORY_COUNTERS),
                wintypes.DWORD,
            ]
            psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
            counters = PROCESS_MEMORY_COUNTERS()
            counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
            handle = kernel32.GetCurrentProcess()
            ok = bool(psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb))
            if not ok:
                return {"ok": False, "rssMb": 0.0, "peakRssMb": 0.0, "error": ctypes.get_last_error()}
            return {
                "ok": True,
                "rssMb": round(counters.WorkingSetSize / (1024 * 1024), 2),
                "peakRssMb": round(counters.PeakWorkingSetSize / (1024 * 1024), 2),
            }
        except Exception as exc:
            return {"ok": False, "rssMb": 0.0, "peakRssMb": 0.0, "error": str(exc)}
    try:
        import resource  # type: ignore

        ru = resource.getrusage(resource.RUSAGE_SELF)
        rss = float(ru.ru_maxrss) / 1024.0
        return {"ok": True, "rssMb": round(rss, 2), "peakRssMb": round(rss, 2)}
    except Exception as exc:
        return {"ok": False, "rssMb": 0.0, "peakRssMb": 0.0, "error": str(exc)}
