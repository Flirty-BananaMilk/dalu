# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Flirty_BananaMilk — 상업적 이용 금지, 자세한 내용은 LICENSE
"""모니터 목록과 선택. 윈도우의 '디스플레이 식별 번호'(설정 > 디스플레이 > 식별)는 GDI 장치 이름 \\\\.\\DISPLAYn 의 n 과 같다.

좌표는 이 프로세스가 창을 옮길 때 쓰는 좌표계(물리 픽셀, 가상 화면 기준)다. 주 모니터가 아닌 곳은 left/top 이 음수일 수 있다.
"""
import ctypes
import re
from ctypes import wintypes


class _MONITORINFOEX(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT), ("rcWork", wintypes.RECT),
                ("dwFlags", wintypes.DWORD), ("szDevice", wintypes.WCHAR * 32)]


_NUM_RE = re.compile(r"DISPLAY(\d+)\s*$", re.I)


def number_of(device, fallback):
    """'\\\\.\\DISPLAY2' -> 2. 못 읽으면 fallback."""
    m = _NUM_RE.search(device or "")
    return int(m.group(1)) if m else fallback


def list_monitors():
    """연결된 모니터: [{number, device, left, top, width, height, primary}] (번호 순)."""
    user32 = ctypes.windll.user32
    found = []
    proc_t = ctypes.WINFUNCTYPE(ctypes.c_int, wintypes.HMONITOR, wintypes.HDC, ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)

    def cb(hmon, hdc, rect, lparam):
        mi = _MONITORINFOEX()
        mi.cbSize = ctypes.sizeof(mi)
        if user32.GetMonitorInfoW(hmon, ctypes.byref(mi)):
            r = mi.rcMonitor
            found.append({"device": mi.szDevice, "left": r.left, "top": r.top, "width": r.right - r.left,
                          "height": r.bottom - r.top, "primary": bool(mi.dwFlags & 1)})
        return 1

    user32.EnumDisplayMonitors(None, None, proc_t(cb), 0)
    for i, m in enumerate(found):
        m["number"] = number_of(m["device"], i + 1)
    return sorted(found, key=lambda m: m["number"])


def pick_monitor(monitors, wanted):
    """wanted: 식별 번호(1~) 또는 0/None(= 주 모니터). 그 번호가 없으면(연결 안 됨) 주 모니터로 대신한다."""
    if not monitors:
        return None
    try:
        wanted = int(wanted or 0)
    except (TypeError, ValueError):
        wanted = 0
    if wanted > 0:
        for m in monitors:
            if m["number"] == wanted:
                return m
    return next((m for m in monitors if m["primary"]), monitors[0])


def monitor_key(m):
    """모니터가 바뀌었는지(연결/해제/해상도/배치 변경) 비교하는 값."""
    return None if m is None else (m["device"], m["left"], m["top"], m["width"], m["height"])


def centered_x(mon, window_width_px):
    """모니터 가로 가운데에 폭 window_width_px(물리 픽셀) 창을 놓을 때의 left."""
    return mon["left"] + (mon["width"] - window_width_px) // 2
