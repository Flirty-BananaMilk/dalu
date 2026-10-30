# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Flirty_BananaMilk — 상업적 이용 금지, 자세한 내용은 LICENSE
"""볼륨 믹서: 마스터 볼륨과 앱별 볼륨(Core Audio 세션)을 읽고 바꾼다. ctypes COM 만 쓴다(pythonnet/외부 패키지 없음).

- 마스터: IAudioEndpointVolume (기본 재생 장치)
- 앱별: IAudioSessionManager2 -> 세션 열거 -> ISimpleAudioVolume. 같은 프로세스의 세션(브라우저는 여럿)은 하나로 묶는다.
호출한 스레드에서 COM 을 초기화하고 끝나면 정리하므로 어느 스레드에서 불러도 된다. 모든 함수는 실패하면 None/False 를 돌려준다.
"""
import ctypes
import os
import re
from ctypes import wintypes

import sysmon
from sysmon import _GUID, _guid, _release, _vcall

ole32 = ctypes.windll.ole32
kernel32 = ctypes.windll.kernel32
kernel32.OpenProcess.restype = ctypes.c_void_p
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
kernel32.QueryFullProcessImageNameW.argtypes = [ctypes.c_void_p, wintypes.DWORD, ctypes.c_wchar_p, ctypes.POINTER(wintypes.DWORD)]

_IID_IAudioSessionManager2 = _guid("{77AA99A0-1BD6-484F-8BC7-2C654C9A9B6F}")
_IID_IAudioSessionControl2 = _guid("{BFB7FF88-7239-4FC9-8FA2-07C950BE9C6D}")
_IID_ISimpleAudioVolume = _guid("{87CE5498-68D6-44E5-9215-6DA47EF883D8}")
_CLSCTX_ALL = 0x17
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
MAX_APPS = 16

_KNOWN = {"chrome": "Chrome", "msedge": "Edge", "firefox": "Firefox", "brave": "Brave", "spotify": "Spotify", "cider": "Cider",
          "discord": "Discord", "vlc": "VLC", "teams": "Teams", "zoom": "Zoom", "slack": "Slack", "obs64": "OBS", "steam": "Steam",
          "wmplayer": "Media Player", "melon": "Melon", "kakaotalk": "KakaoTalk", "potplayermini64": "PotPlayer", "potplayer64": "PotPlayer"}


def pretty_name(exe_path_or_stem):
    """'C:\\...\\chrome.exe' -> 'Chrome'. 모르는 이름은 첫 글자를 대문자로."""
    stem = os.path.splitext(os.path.basename(exe_path_or_stem or ""))[0]
    key = re.sub(r"[^a-z0-9]", "", stem.lower())
    if key in _KNOWN:
        return _KNOWN[key]
    return (stem[:1].upper() + stem[1:]) if stem else ""


def _process_exe(pid):
    h = kernel32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(520)
        n = wintypes.DWORD(520)
        return buf.value if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n)) else ""
    finally:
        kernel32.CloseHandle(h)


class _Com:
    """with 블록 동안 이 스레드의 COM 을 초기화한다."""
    def __enter__(self):
        self.hr = ole32.CoInitializeEx(None, 0)       # COINIT_MULTITHREADED; 0=처음, 1=이미 초기화됨, 음수=다른 모델로 이미 초기화(그래도 사용 가능)
        return self

    def __exit__(self, *a):
        if self.hr in (0, 1):
            ole32.CoUninitialize()


def _default_device(flow=0):
    enum = ctypes.c_void_p()
    dev = ctypes.c_void_p()
    hr = ole32.CoCreateInstance(ctypes.byref(sysmon._CLSID_MMDeviceEnumerator), None, _CLSCTX_ALL,
                                ctypes.byref(sysmon._IID_IMMDeviceEnumerator), ctypes.byref(enum))
    if hr != 0 or not enum.value:
        return None, None
    if _vcall(enum, 4, ctypes.c_long, ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_void_p))(enum, flow, 1, ctypes.byref(dev)) != 0 or not dev.value:
        _release(enum)
        return None, None
    return enum, dev


def _activate(dev, iid):
    out = ctypes.c_void_p()
    ok = _vcall(dev, 3, ctypes.c_long, ctypes.POINTER(_GUID), ctypes.c_ulong, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p))(
        dev, ctypes.byref(iid), _CLSCTX_ALL, None, ctypes.byref(out)) == 0
    return out if ok and out.value else None


def _query(ptr, iid):
    out = ctypes.c_void_p()
    ok = _vcall(ptr, 0, ctypes.c_long, ctypes.POINTER(_GUID), ctypes.POINTER(ctypes.c_void_p))(ptr, ctypes.byref(iid), ctypes.byref(out)) == 0
    return out if ok and out.value else None


# ---------------------------------------------------------------------- 마스터
def master_get(flow=0):
    """{'volume': 0~1, 'muted': bool} 또는 None. flow=1 이면 기본 마이크(녹음 장치)."""
    with _Com():
        enum = dev = vol = None
        try:
            enum, dev = _default_device(flow)
            if not dev:
                return None
            vol = _activate(dev, sysmon._IID_IAudioEndpointVolume)
            if not vol:
                return None
            sc = ctypes.c_float()
            mute = ctypes.c_int()
            if _vcall(vol, 9, ctypes.c_long, ctypes.POINTER(ctypes.c_float))(vol, ctypes.byref(sc)) != 0:
                return None
            _vcall(vol, 15, ctypes.c_long, ctypes.POINTER(ctypes.c_int))(vol, ctypes.byref(mute))
            return {"volume": round(sc.value, 4), "muted": bool(mute.value)}
        except Exception:
            return None
        finally:
            _release(vol), _release(dev), _release(enum)


def master_set(volume=None, muted=None, flow=0):
    """마스터 볼륨(0~1)/음소거를 설정한다(flow=1 이면 마이크). 성공하면 True."""
    with _Com():
        enum = dev = vol = None
        try:
            enum, dev = _default_device(flow)
            vol = _activate(dev, sysmon._IID_IAudioEndpointVolume) if dev else None
            if not vol:
                return False
            ok = True
            if volume is not None:
                v = max(0.0, min(1.0, float(volume)))
                ok &= _vcall(vol, 7, ctypes.c_long, ctypes.c_float, ctypes.c_void_p)(vol, ctypes.c_float(v), None) == 0
            if muted is not None:
                ok &= _vcall(vol, 14, ctypes.c_long, ctypes.c_int, ctypes.c_void_p)(vol, 1 if muted else 0, None) == 0
            return bool(ok)
        except Exception:
            return False
        finally:
            _release(vol), _release(dev), _release(enum)


def master_step(delta):
    """마스터 볼륨을 delta(예: +0.02)만큼 바꾼다. 새 값을 돌려준다."""
    cur = master_get()
    if cur is None:
        return None
    new = max(0.0, min(1.0, cur["volume"] + float(delta)))
    if cur["muted"] and delta > 0:
        master_set(muted=False)
    return new if master_set(volume=new) else None


# ---------------------------------------------------------------------- 앱별
def _sessions(dev):
    """기본 장치의 모든 세션 -> [{pid, state, system, ctl2(COM, 호출자가 해제), vol(COM)}]. COM 포인터는 호출자가 해제한다."""
    mgr = _activate(dev, _IID_IAudioSessionManager2)
    if not mgr:
        return [], None
    en = ctypes.c_void_p()
    out = []
    if _vcall(mgr, 5, ctypes.c_long, ctypes.POINTER(ctypes.c_void_p))(mgr, ctypes.byref(en)) != 0 or not en.value:
        _release(mgr)
        return [], None
    n = ctypes.c_int()
    _vcall(en, 3, ctypes.c_long, ctypes.POINTER(ctypes.c_int))(en, ctypes.byref(n))
    for i in range(n.value):
        ctl = ctypes.c_void_p()
        if _vcall(en, 4, ctypes.c_long, ctypes.c_int, ctypes.POINTER(ctypes.c_void_p))(en, i, ctypes.byref(ctl)) != 0 or not ctl.value:
            continue
        ctl2 = _query(ctl, _IID_IAudioSessionControl2)
        vol = _query(ctl, _IID_ISimpleAudioVolume)
        state = ctypes.c_int(-1)
        _vcall(ctl, 3, ctypes.c_long, ctypes.POINTER(ctypes.c_int))(ctl, ctypes.byref(state))
        pid = wintypes.DWORD(0)
        system = False
        if ctl2:
            _vcall(ctl2, 14, ctypes.c_long, ctypes.POINTER(wintypes.DWORD))(ctl2, ctypes.byref(pid))
            system = _vcall(ctl2, 15, ctypes.c_long)(ctl2) == 0       # IsSystemSoundsSession: S_OK(0) = 시스템 소리
        out.append({"pid": pid.value, "state": state.value, "system": system, "ctl": ctl, "ctl2": ctl2, "vol": vol})
    return out, (mgr, en)


def _free(sessions, holders):
    for s in sessions:
        _release(s["vol"]), _release(s["ctl2"]), _release(s["ctl"])
    if holders:
        _release(holders[1]), _release(holders[0])


def list_apps():
    """[{id, pid, name, volume, muted, active}] — 프로세스별로 묶은 오디오 세션 (활성 > 이름 순). 만료된 세션(state 2)은 뺀다."""
    with _Com():
        enum = dev = None
        sessions, holders = [], None
        try:
            enum, dev = _default_device()
            if not dev:
                return None
            sessions, holders = _sessions(dev)
            groups = {}
            for s in sessions:
                if s["state"] == 2 or not s["vol"]:
                    continue
                key = "system" if s["system"] else f"pid:{s['pid']}"
                g = groups.setdefault(key, {"id": key, "pid": s["pid"], "system": s["system"], "vols": [], "muted": False, "active": False})
                v = ctypes.c_float()
                m = ctypes.c_int()
                if _vcall(s["vol"], 4, ctypes.c_long, ctypes.POINTER(ctypes.c_float))(s["vol"], ctypes.byref(v)) == 0:
                    g["vols"].append(v.value)
                if _vcall(s["vol"], 6, ctypes.c_long, ctypes.POINTER(ctypes.c_int))(s["vol"], ctypes.byref(m)) == 0:
                    g["muted"] = g["muted"] or bool(m.value)
                g["active"] = g["active"] or s["state"] == 1
            apps = []
            own = os.getpid()
            for g in groups.values():
                if g["pid"] == own and not g["system"]:
                    continue                      # 이 앱 자신(알림음)은 믹서에 보이지 않는다
                name = "" if g["system"] else pretty_name(_process_exe(g["pid"]))
                if name.lower() == "msedgewebview2":
                    continue                      # 노치/설정 창의 웹뷰 프로세스
                apps.append({"id": g["id"], "pid": g["pid"], "name": name or ("system" if g["system"] else f"PID {g['pid']}"),
                             "system": g["system"], "volume": round(max(g["vols"]) if g["vols"] else 1.0, 4), "muted": g["muted"], "active": g["active"]})
            apps.sort(key=lambda a: (not a["active"], a["system"], a["name"].lower()))
            return apps[:MAX_APPS]
        except Exception:
            return None
        finally:
            _free(sessions, holders)
            _release(dev), _release(enum)


def set_app(app_id, volume=None, muted=None):
    """list_apps 의 id 로 지정한 앱(같은 프로세스의 모든 세션)의 볼륨(0~1)/음소거를 바꾼다."""
    with _Com():
        enum = dev = None
        sessions, holders = [], None
        try:
            enum, dev = _default_device()
            if not dev:
                return False
            sessions, holders = _sessions(dev)
            hit = False
            for s in sessions:
                key = "system" if s["system"] else f"pid:{s['pid']}"
                if key != app_id or not s["vol"] or s["state"] == 2:
                    continue
                hit = True
                if volume is not None:
                    _vcall(s["vol"], 3, ctypes.c_long, ctypes.c_float, ctypes.c_void_p)(s["vol"], ctypes.c_float(max(0.0, min(1.0, float(volume)))), None)
                if muted is not None:
                    _vcall(s["vol"], 5, ctypes.c_long, ctypes.c_int, ctypes.c_void_p)(s["vol"], 1 if muted else 0, None)
            return hit
        except Exception:
            return False
        finally:
            _free(sessions, holders)
            _release(dev), _release(enum)


# ---------------------------------------------------------------------- 마이크
def mic_get():
    """기본 마이크의 {'volume','muted'} 또는 None(마이크 없음)."""
    return master_get(flow=1)


def mic_toggle_mute():
    """기본 마이크 음소거를 뒤집는다. 새 상태(True=음소거됨)를 돌려주고, 마이크가 없으면 None."""
    cur = mic_get()
    if cur is None:
        return None
    new = not cur["muted"]
    return new if master_set(muted=new, flow=1) else None


def apps_matching(name_part):
    """이름에 name_part(대소문자 무시)가 들어 있는 오디오 앱들의 id 목록."""
    low = name_part.lower()
    return [a["id"] for a in (list_apps() or []) if low in a["name"].lower()]
