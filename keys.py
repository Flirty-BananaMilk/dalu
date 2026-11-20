# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Flirty_BananaMilk — 상업적 이용 금지, 자세한 내용은 LICENSE
"""키 조합 보내기(Win+D, Win+Shift+S 같은 시스템 단축키를 노치에서 누르기). keybd_event 로 키를 눌렀다 뗀다."""
import ctypes
import time

# 키 조합 해석('Ctrl+Alt+N' -> 수식키 + 가상 키 코드). 전역 단축키 기능을 없애면서 여기로 옮겼다
MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN, MOD_NOREPEAT = 0x1, 0x2, 0x4, 0x8, 0x4000

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
    if len(key) == 1 and key.isascii() and key.isalnum():          # 한글 같은 글자는 가상 키 코드가 아니다
        vk = ord(key.upper())
    elif key.startswith("f") and key[1:].isascii() and key[1:].isdigit() and 1 <= int(key[1:]) <= 24:
        vk = 0x6F + int(key[1:])
    elif key in _NAMED:
        vk = _NAMED[key]
    if vk is None or mods == 0:
        return None
    return mods, vk

user32 = ctypes.windll.user32
KEYEVENTF_KEYUP = 0x0002
_MOD_VKS = ((MOD_WIN, 0x5B), (MOD_CONTROL, 0x11), (MOD_ALT, 0x12), (MOD_SHIFT, 0x10))


def send_combo(text, delay=0.02, press=None, release=None):
    """'Win+Shift+S' 를 보낸다. 해석할 수 없으면 False. press/release 는 테스트용 주입."""
    parsed = parse_combo(text)
    if not parsed:
        return False
    mods, vk = parsed
    press = press or (lambda k: user32.keybd_event(k, 0, 0, 0))
    release = release or (lambda k: user32.keybd_event(k, 0, KEYEVENTF_KEYUP, 0))
    held = [v for flag, v in _MOD_VKS if mods & flag]
    for k in held:
        press(k)
    time.sleep(delay)
    press(vk)
    release(vk)
    time.sleep(delay)
    for k in reversed(held):
        release(k)
    return True
