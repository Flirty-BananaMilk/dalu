# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Flirty_BananaMilk — 상업적 이용 금지, 자세한 내용은 LICENSE
"""방해 금지(Do Not Disturb) 켜고 끄기.

윈도우 11 의 알림 센터 '방해 금지' 스위치는 HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Notifications\\Settings 의
NOC_GLOBAL_SETTING_TOASTS_ENABLED(0 = 알림 배너/소리 끔)로 저장된다. 공개된 API 는 없어서 이 값을 직접 바꾼다.

안전장치: 우리가 바꾸기 전의 값을 파일(state_path)에 적어 두고, 끌 때 그 값으로 되돌린다. 앱이 도중에 죽어도 다음 실행 때 restore_if_pending() 이
되돌린다(사용자가 방해 금지를 켠 채로 갇히지 않게). 사용자가 중간에 직접 바꾼 값은 존중한다(그때는 덮어쓰지 않고 상태 파일만 지운다).
"""
import json
import os
import winreg

SUBKEY = r"Software\Microsoft\Windows\CurrentVersion\Notifications\Settings"
VALUE = "NOC_GLOBAL_SETTING_TOASTS_ENABLED"
_ABSENT = None


def _read(subkey=SUBKEY):
    """현재 값(0/1) 또는 None(값 없음 = 기본값, 알림 켜짐)."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, subkey) as k:
            return int(winreg.QueryValueEx(k, VALUE)[0])
    except OSError:
        return _ABSENT


def _write(value, subkey=SUBKEY):
    """value=None 이면 값을 지운다(기본 상태로)."""
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, subkey) as k:
        if value is None:
            try:
                winreg.DeleteValue(k, VALUE)
            except FileNotFoundError:
                pass
        else:
            winreg.SetValueEx(k, VALUE, 0, winreg.REG_DWORD, int(value))


def _load_state(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _save_state(path, prev):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"prev": prev}, f)
    os.replace(tmp, path)


def is_on(subkey=SUBKEY):
    return _read(subkey) == 0


def enable(state_path, subkey=SUBKEY):
    """방해 금지를 켠다. 이미 켜져 있으면(사용자가 켠 것 포함) 아무것도 바꾸지 않는다. 우리가 바꿨으면 True."""
    cur = _read(subkey)
    if cur == 0:
        return False
    if _load_state(state_path) is None:
        _save_state(state_path, cur)           # 바꾸기 전 값을 먼저 적어 둔다 (적은 뒤에 바꿔야 도중에 죽어도 복구된다)
    _write(0, subkey)
    return True


def disable(state_path, subkey=SUBKEY):
    """우리가 켰던 방해 금지를 원래 값으로 되돌린다. 우리가 켠 게 아니면 건드리지 않는다. 되돌렸으면 True."""
    st = _load_state(state_path)
    if st is None:
        return False
    try:
        if _read(subkey) == 0:                 # 아직 우리가 켠 상태일 때만 되돌린다 (사용자가 그 사이 바꿨다면 존중)
            _write(st.get("prev"), subkey)
            restored = True
        else:
            restored = False
    finally:
        try:
            os.remove(state_path)
        except OSError:
            pass
    return restored


def restore_if_pending(state_path, subkey=SUBKEY):
    """앱 시작 때: 지난번에 방해 금지를 켜 둔 채 종료됐다면 되돌린다."""
    return disable(state_path, subkey)
