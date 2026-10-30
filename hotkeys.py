# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Flirty_BananaMilk — 상업적 이용 금지, 자세한 내용은 LICENSE
"""전역 단축키 (RegisterHotKey). 어떤 앱이 앞에 있어도 눌리고, 키 입력을 가로채는 훅은 쓰지 않는다.

RegisterHotKey 는 '메시지 루프를 도는 그 스레드'에서 등록해야 하므로 전용 스레드가 등록/해제/메시지 수신을 모두 맡는다.
다른 프로그램이 이미 쓰는 조합이면 등록이 실패하고, 그 결과(status)를 설정 창이 보여 준다.
"""
import ctypes
import queue
import threading
import time
from ctypes import wintypes

user32 = ctypes.windll.user32
user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]

MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN, MOD_NOREPEAT = 0x1, 0x2, 0x4, 0x8, 0x4000
WM_HOTKEY = 0x0312
PM_REMOVE = 0x0001

_MODS = {"ctrl": MOD_CONTROL, "control": MOD_CONTROL, "alt": MOD_ALT, "shift": MOD_SHIFT, "win": MOD_WIN, "windows": MOD_WIN, "meta": MOD_WIN}
_NAMED = {"space": 0x20, "enter": 0x0D, "return": 0x0D, "tab": 0x09, "esc": 0x1B, "escape": 0x1B, "backspace": 0x08, "delete": 0x2E, "del": 0x2E,
          "insert": 0x2D, "ins": 0x2D, "home": 0x24, "end": 0x23, "pageup": 0x21, "pgup": 0x21, "pagedown": 0x22, "pgdn": 0x22,
          "left": 0x25, "up": 0x26, "right": 0x27, "down": 0x28, "`": 0xC0, "-": 0xBD, "=": 0xBB, "[": 0xDB, "]": 0xDD, ";": 0xBA,
          "'": 0xDE, ",": 0xBC, ".": 0xBE, "/": 0xBF, "\\": 0xDC}


def parse_combo(text):
    """'Ctrl+Alt+N' -> (modifiers, vk). 형식이 틀렸거나 수식키가 없으면(전역 단축키는 최소 하나 필요) None."""
    parts = [p.strip().lower() for p in str(text or "").replace(" ", "").split("+") if p.strip()]
    if len(parts) < 2:
        return None
    mods = 0
    for p in parts[:-1]:
        if p not in _MODS:
            return None
        mods |= _MODS[p]
    key = parts[-1]
    vk = None
    if len(key) == 1 and key.isalnum():
        vk = ord(key.upper())
    elif key.startswith("f") and key[1:].isdigit() and 1 <= int(key[1:]) <= 24:
        vk = 0x6F + int(key[1:])
    elif key in _NAMED:
        vk = _NAMED[key]
    if vk is None or mods == 0:
        return None
    return mods, vk


def format_combo(text):
    """저장된 문자열을 보기 좋게 정규화한다('ctrl + alt+n' -> 'Ctrl+Alt+N'). 해석할 수 없으면 원문."""
    parsed = parse_combo(text)
    if not parsed:
        return str(text or "")
    mods, vk = parsed
    out = [n for flag, n in ((MOD_CONTROL, "Ctrl"), (MOD_ALT, "Alt"), (MOD_SHIFT, "Shift"), (MOD_WIN, "Win")) if mods & flag]
    key = next((k for k, v in _NAMED.items() if v == vk and len(k) > 1), None)
    if 0x70 <= vk <= 0x87:
        key = f"F{vk - 0x6F}"
    out.append(key.capitalize() if key else chr(vk))
    return "+".join(out)


class HotkeyService:
    """actions: {이름: 콜백}. set_bindings({이름: 'Ctrl+Alt+N'}) 로 다시 등록한다. status(): {이름: 'ok'|'invalid'|'conflict'|'off'}"""

    def __init__(self, actions, log=None):
        self._actions = dict(actions)
        self._log = log or (lambda m: None)
        self._cmds = queue.Queue()
        self._status = {}
        self._lock = threading.Lock()
        self._thread = None
        self._running = False

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True, name="hotkeys")
        self._thread.start()

    def stop(self):
        self._running = False

    def set_bindings(self, bindings, enabled=True):
        """bindings: {이름: 'Ctrl+Alt+N'}. enabled=False 면 전부 해제한다."""
        self._cmds.put((dict(bindings), bool(enabled)))

    def status(self):
        with self._lock:
            return dict(self._status)

    # -- 스레드 ---------------------------------------------------------
    def _register_all(self, bindings, enabled, registered):
        for hk_id in list(registered):
            user32.UnregisterHotKey(None, hk_id)
        registered.clear()
        status = {}
        for i, (name, combo) in enumerate(bindings.items(), start=1):
            if not enabled:
                status[name] = "off"
                continue
            parsed = parse_combo(combo)
            if not parsed:
                status[name] = "invalid"
                continue
            mods, vk = parsed
            if user32.RegisterHotKey(None, i, mods | MOD_NOREPEAT, vk):
                registered[i] = name
                status[name] = "ok"
            else:
                status[name] = "conflict"          # 이미 다른 프로그램이 쓰는 조합
                self._log(f"hotkey {name} ({combo}) could not be registered (in use?)")
        with self._lock:
            self._status = status

    def _run(self):
        registered = {}
        msg = wintypes.MSG()
        while self._running:
            try:
                while True:
                    bindings, enabled = self._cmds.get_nowait()
                    self._register_all(bindings, enabled, registered)
            except queue.Empty:
                pass
            while user32.PeekMessageW(ctypes.byref(msg), None, WM_HOTKEY, WM_HOTKEY, PM_REMOVE):
                name = registered.get(int(msg.wParam))
                cb = self._actions.get(name)
                if cb:
                    try:
                        threading.Thread(target=cb, daemon=True, name="hotkey-" + name).start()
                    except Exception as e:
                        self._log(f"hotkey action {name} failed: {e!r}")
            time.sleep(0.03)
        for hk_id in list(registered):
            user32.UnregisterHotKey(None, hk_id)
