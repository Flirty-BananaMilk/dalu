# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Flirty_BananaMilk — 상업적 이용 금지, 자세한 내용은 LICENSE
"""모니터 목록과 선택. 번호는 윈도우 설정 > 디스플레이 > 식별의 번호와 같다: 연결된 모니터를 GDI 장치 이름(\\\\.\\DISPLAYn)의 n 순서대로 1부터 센 값이다.
(장치 이름의 n 은 모니터를 뺐다 꽂으면 1, 2, 5 처럼 건너뛰지만, 식별 번호는 늘 1, 2, 3 이다. 장치 이름의 n 은 'gdi' 로 따로 들고 있다.)

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


def monitor_dpi(hmon):
    """모니터의 실제(유효) DPI. 못 읽으면 96. (GetDpiForMonitor, Windows 8.1 이상)"""
    try:
        dx, dy = ctypes.c_uint(0), ctypes.c_uint(0)
        if ctypes.windll.shcore.GetDpiForMonitor(hmon, 0, ctypes.byref(dx), ctypes.byref(dy)) == 0 and dx.value >= 48:
            return int(dx.value)
    except Exception:
        pass
    return 96


def list_monitors():
    """연결된 모니터: [{number, gdi, device, left, top, width, height, primary, dpi}] (식별 번호 순). number = 윈도우 식별 번호, gdi = 장치 이름 DISPLAYn 의 n."""
    user32 = ctypes.windll.user32
    found = []
    proc_t = ctypes.WINFUNCTYPE(ctypes.c_int, wintypes.HMONITOR, wintypes.HDC, ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)

    def cb(hmon, hdc, rect, lparam):
        mi = _MONITORINFOEX()
        mi.cbSize = ctypes.sizeof(mi)
        if user32.GetMonitorInfoW(hmon, ctypes.byref(mi)):
            r = mi.rcMonitor
            found.append({"device": mi.szDevice, "left": r.left, "top": r.top, "width": r.right - r.left,
                          "height": r.bottom - r.top, "primary": bool(mi.dwFlags & 1), "dpi": monitor_dpi(hmon)})
        return 1

    user32.EnumDisplayMonitors(None, None, proc_t(cb), 0)
    for i, m in enumerate(found):
        m["gdi"] = number_of(m["device"], 10 ** 6 + i)
    found.sort(key=lambda m: (m["gdi"], m["device"]))
    for i, m in enumerate(found):
        m["number"] = i + 1      # 윈도우의 식별 번호(1, 2, 3 ...)
    return found


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
    return None if m is None else (m["device"], m["left"], m["top"], m["width"], m["height"], m.get("dpi", 96))


def dpi_scale(m):
    """모니터의 DPI 배율 (150% -> 1.5). dpi 를 모르면 None."""
    try:
        return max(1.0, float(m["dpi"]) / 96.0) if m and m.get("dpi") else None
    except Exception:
        return None


def centered_x(mon, window_width_px):
    """모니터 가로 가운데에 폭 window_width_px(물리 픽셀) 창을 놓을 때의 left."""
    return mon["left"] + (mon["width"] - window_width_px) // 2


# 노치 가로 위치(notchPos): 16:9 기준 화면을 세로로 5등분한 칸 단위로 -2(맨 왼쪽) ~ 2(맨 오른쪽), 0 = 가운데.
NOTCH_POS_MIN, NOTCH_POS_MAX = -2, 2
EXPANDED_HALF_CSS = 290      # 가장 넓게 펼쳐진 노치(파일 선반 560)의 절반 + 여유. 위치는 '펼친 크기' 기준으로 화면 안에 들어오게 맞춘다.


def clamp_pos(pos):
    try:
        return max(NOTCH_POS_MIN, min(NOTCH_POS_MAX, int(round(float(pos)))))
    except (TypeError, ValueError):
        return 0


def notch_center_x(mon, pos, scale=1.0, half_css=EXPANDED_HALF_CSS):
    """모니터 mon 에서 노치 가운데의 가로 좌표(물리 픽셀). 기준 폭은 모니터 높이 기준 16:9 폭(더 좁은 화면이면 실제 폭)을
    모니터 가운데에 두고 5등분한 칸 하나의 폭이다. 펼친 노치(half_css*scale)가 화면 밖으로 나가면 안쪽으로 당긴다."""
    pos = clamp_pos(pos)
    ref_w = min(mon["width"], mon["height"] * 16.0 / 9.0)
    cx = mon["left"] + mon["width"] / 2.0 + pos * (ref_w / 5.0)
    margin = half_css * scale
    lo, hi = mon["left"] + margin, mon["left"] + mon["width"] - margin
    if lo > hi:                       # 화면이 펼친 노치보다 좁으면 가운데
        return int(mon["left"] + mon["width"] / 2.0)
    return int(max(lo, min(hi, cx)))


def placed_x(mon, window_width_px, pos, scale=1.0):
    """폭 window_width_px 창을 notch_center_x 에 가운데로 맞출 때의 left."""
    return notch_center_x(mon, pos, scale) - window_width_px // 2
