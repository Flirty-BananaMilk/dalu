# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Flirty_BananaMilk — 상업적 이용 금지, 자세한 내용은 LICENSE
"""화면 캡처/녹화를 하는 도구가 켜지면 노치를 캡처에 보이게 한다 (자동 캡처 모드).

리퀴드 글래스 '전체'는 노치가 자기 자신을 비추지 않도록 노치 창을 화면 캡처에서 빼 둔다(deskcap.py). 그래서 스크린샷/녹화에는
노치가 찍히지 않는다. 이 모듈은 캡처가 시작될 낌새를 보고 deskcap 의 '캡처 모드'(뒤 화면을 얼리고 노치를 캡처에 보이게 함)를 대신 눌러 준다.

- 키: PrintScreen(Alt/Win 조합 포함), Win+Shift+S(캡처 도구), Win+Alt+R(Xbox Game Bar 녹화), Win+Shift+R(캡처 도구 녹화).
  키가 눌린 직후에 풀어 주는 방식이라, 아주 빠른 PrintScreen 은 노치가 안 찍힐 수 있다 (그럴 땐 단축키 캡처 모드를 쓴다).
- 프로그램: OBS, Bandicam 등 화면을 녹화하는 프로그램이 실행 중인 동안 계속 캡처 모드를 유지한다.
외부로 보내는 것은 없다. 키 상태와 실행 중인 프로세스 이름만 로컬에서 본다.
"""
import ctypes
import threading
import time
from ctypes import wintypes

# 이 이름(소문자, 확장자 포함)의 프로세스가 떠 있으면 화면을 찍고 있다고 본다. 항상 떠 있기만 하는 도구(ShareX, Lightshot 등)와
# 창을 닫은 뒤에도 오래 남아 있는 윈도우 캡처 도구(SnippingTool.exe)는 넣지 않는다(오탐으로 글래스가 계속 얼어 버린다) — 그쪽은 키로 잡는다.
CAPTURE_PROCESSES = frozenset({
    "obs64.exe", "obs32.exe", "obs.exe", "streamlabs desktop.exe", "bdcam.exe", "bandicam.exe",
    "screenclippinghost.exe", "camrecorder.exe", "xsplit.core.exe", "screenrec.exe",
})

VK_SNAPSHOT, VK_SHIFT, VK_MENU, VK_LWIN, VK_RWIN = 0x2C, 0x10, 0x12, 0x5B, 0x5C
VK_S, VK_R, VK_F9 = 0x53, 0x52, 0x78
KEY_SECONDS = 20.0          # 키로 시작한 캡처: 캡처 도구에서 영역을 고르는 시간까지 넉넉히
PROC_SECONDS = 6.0          # 프로그램이 떠 있는 동안: 몇 초마다 다시 연장한다


def keys_trigger(down):
    """down(vk) -> 그 키가 지금 눌려 있나. 캡처를 시작하는 키 조합이면 그 이름, 아니면 None."""
    win = down(VK_LWIN) or down(VK_RWIN)
    if down(VK_SNAPSHOT):
        return "printscreen"
    if down(VK_MENU) and down(VK_F9):
        return "alt+f9"      # NVIDIA(그래픽 카드 앱) 녹화 시작/중지 기본 단축키
    if win and down(VK_SHIFT) and down(VK_S):
        return "win+shift+s"
    if win and down(VK_MENU) and down(VK_R):
        return "win+alt+r"
    if win and down(VK_SHIFT) and down(VK_R):
        return "win+shift+r"
    return None


def running_names():
    """실행 중인 프로세스 이름(소문자) 집합. 못 읽으면 빈 집합."""
    TH32CS_SNAPPROCESS = 0x2

    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD), ("th32ProcessID", wintypes.DWORD),
                    ("th32DefaultHeapID", ctypes.c_size_t), ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
                    ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", ctypes.c_long), ("dwFlags", wintypes.DWORD),
                    ("szExeFile", ctypes.c_wchar * 260)]

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    k32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    k32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    k32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    k32.CloseHandle.argtypes = [wintypes.HANDLE]
    out = set()
    snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if not snap or snap == wintypes.HANDLE(-1).value:
        return out
    try:
        pe = PROCESSENTRY32W()
        pe.dwSize = ctypes.sizeof(PROCESSENTRY32W)
        ok = k32.Process32FirstW(snap, ctypes.byref(pe))
        while ok:
            out.add(pe.szExeFile.lower())
            ok = k32.Process32NextW(snap, ctypes.byref(pe))
    finally:
        k32.CloseHandle(snap)
    return out


def capture_tool_running(names=None, processes=None):
    """화면을 찍는 프로그램이 떠 있으면 그 이름, 없으면 None. (테스트에서는 processes 를 넘겨 준다)"""
    procs = running_names() if processes is None else processes
    hit = sorted((names or CAPTURE_PROCESSES) & set(procs))
    return hit[0] if hit else None


class CaptureWatch:
    """백그라운드에서 키와 프로세스를 보다가, 캡처 낌새가 있으면 on_capture(seconds, why) 를 부른다."""

    def __init__(self, on_capture, enabled=lambda: True, log=None, key_poll=0.03, proc_poll=2.0):
        self._on_capture = on_capture
        self._enabled = enabled
        self._log = log or (lambda m: None)
        self._key_poll = key_poll
        self._proc_poll = proc_poll
        self._stop = threading.Event()
        self._thread = None
        self._last_key = None

    def start(self):
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, daemon=True, name="capture-watch")
            self._thread.start()

    def stop(self):
        self._stop.set()

    def _down(self, vk):
        return bool(ctypes.windll.user32.GetAsyncKeyState(vk) & 0x8000)

    def tick_keys(self):
        """키 한 번 확인. 새로 눌린 조합이면 캡처 모드를 켠다 (키를 누르고 있는 동안 반복해서 켜지 않는다)."""
        why = keys_trigger(self._down)
        if why and why != self._last_key and self._enabled():
            self._log(f"capturewatch: {why} -> capture mode")
            self._on_capture(KEY_SECONDS, why)
        self._last_key = why

    def tick_procs(self):
        if not self._enabled():
            return
        name = capture_tool_running()
        if name:
            self._on_capture(PROC_SECONDS, name)

    def _run(self):
        next_proc = 0.0
        while not self._stop.is_set():
            try:
                self.tick_keys()
                now = time.monotonic()
                if now >= next_proc:
                    next_proc = now + self._proc_poll
                    self.tick_procs()
            except Exception as e:
                self._log(f"capturewatch error: {e!r}")
            self._stop.wait(self._key_poll)
