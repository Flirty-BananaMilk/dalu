# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Flirty_BananaMilk — 상업적 이용 금지, 자세한 내용은 LICENSE
"""키 조합 보내기(Win+D, Win+Shift+S 같은 시스템 단축키를 노치에서 누르기). keybd_event 로 키를 눌렀다 뗀다."""
import ctypes
import time

import hotkeys

user32 = ctypes.windll.user32
KEYEVENTF_KEYUP = 0x0002
_MOD_VKS = ((hotkeys.MOD_WIN, 0x5B), (hotkeys.MOD_CONTROL, 0x11), (hotkeys.MOD_ALT, 0x12), (hotkeys.MOD_SHIFT, 0x10))


def send_combo(text, delay=0.02, press=None, release=None):
    """'Win+Shift+S' 를 보낸다. 해석할 수 없으면 False. press/release 는 테스트용 주입."""
    parsed = hotkeys.parse_combo(text)
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
