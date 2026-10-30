# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Flirty_BananaMilk — 상업적 이용 금지, 자세한 내용은 LICENSE
"""설정(prefs): 기본값, 병합/검증, 저장, 윈도우 시작 프로그램 등록.

설정은 data.json 의 `settings`(그리고 `pomo`, `water`) 아래에 저장된다. 화면(JS)과 파이썬이 같은 값을 쓰므로
파이썬이 소비하는 키(외부 가사, 미디어 소스 우선순위, 전체화면 양보, 버즈 배터리 경고 기준 ...)의 기본값을 여기에 둔다.
화면 쪽 기본값/검증은 app.js(DEFAULT_STORE)와 settings.js(스키마)에 있고, 같은 키 이름을 쓴다.
"""
import copy
import json
import os
import sys
import threading

# 파이썬이 직접 읽는 설정 키와 기본값 (화면 전용 키는 여기에 없어도 된다: 저장은 통째로 병합해서 한다)
LANGS = ("ko", "en", "zh", "ja")      # 지원하는 화면 언어(한국어, English, 简体中文, 日本語)

PY_DEFAULTS = {
    "extLyrics": True,          # Cider 가 아닌 앱의 곡 가사를 외부 서비스에서 찾는다
    "extApple": True,           # Cider 를 거쳐 Apple Music 에서 같은 곡의 가사를 찾는다 (Cider 가 켜져 있고 로그인돼 있을 때)
    "extNetease": True,
    "extLrclib": True,
    "smtcOn": True,             # Cider 외 앱(윈도우 미디어 세션)의 곡을 표시/제어
    "mediaPriority": "auto",    # 둘 다 재생 중일 때: auto(보던 쪽 유지) | cider | other
    "fullscreenMode": "yield",  # 전체화면 앱이 켜졌을 때: yield(항상 위를 풀어 비켜남) | hide(완전히 숨김) | hidepeek(숨기되 미디어 키를 누르면 잠깐 표시) | show(그대로)
    "hotkeysOn": True,          # 전역 단축키
    "hkToggle": "Ctrl+Alt+N",   # 노치 펼침/접힘(고정)
    "hkSettings": "Ctrl+Alt+S", # 설정 창
    "hkMixer": "Ctrl+Alt+V",    # 볼륨 믹서
    "hkLyrics": "Ctrl+Alt+L",   # 가사 켜기/끄기
    "winNotify": False,         # 윈도우 알림이 오면 보조 노치(작은 동그라미)로 알린다 (알림 내용은 읽지 않는다). 기본은 꺼짐
    "winNotifyIgnore": "",      # 윈도우 알림을 동그라미로 알리지 않을 앱 이름(쉼표로 구분, 부분 일치, 예: chrome, discord)
    "hkCapture": "Ctrl+Alt+P",  # 캡처 모드: 리퀴드 글래스 '전체'에서 노치를 스크린샷에 보이게 한다 (켜고 끄는 단축키)
    "captureNotch": "auto",     # 스크린샷·영상 녹화에서 노치(리퀴드 글래스 '전체'일 때만 의미): hide(가리기: 캡처에 안 찍힘) | auto(평소엔 가리고, 캡처 도구가 켜지면 그동안만 찍힘) | show(표시: 항상 찍힘, 뒤 화면은 정지 화면)
    "captureSeconds": 15,       # 캡처 모드를 켜 두는 시간(초): 15 | 60 | 300 | 0(끌 때까지. 최대 4시간). 영상 녹화는 길게 켜 두어야 한다
    "clipboardOn": False,       # 클립보드 기록 (민감한 내용이 있을 수 있어 기본은 꺼짐)
    "calendarUrl": "",          # 캘린더(.ics) 주소 또는 파일 경로
    "calendarRemindMin": 10,    # 일정 시작 몇 분 전에 알릴지
    "budsWatch": True,          # 이어버드 제어 연결을 유지해 충전 상태·경고(땀/얼룩으로 충전 중지)를 받는다
    "budsLowPct": 20,           # 이어버드 배터리 부족 알림 기준(%)
    "upNext": True,             # Cider 대기열의 다음 곡을 읽는다
    "appFilterMode": "off",      # 다른 앱 미디어 필터: off | allow | block
    "appFilterList": "",        # 쉼표로 구분한 앱 이름(부분 일치, 예: spotify, chrome)
    "pluginsEnabled": "",   # 사용자가 추가한 플러그인 id(쉼표). 기본은 비어 있어 플러그인 탭이 보이지 않는다
    "glassNotch": "controls",   # 노치 리퀴드 글래스: off | controls(안의 버튼·타일만) | full(+본체가 뒤 화면을 비춤)
    "monitor": 0,               # 노치를 띄울 모니터의 식별 번호 (0 = 주 모니터, 기본). 그 번호가 없으면 주 모니터
    "uiScale": 100,             # 노치 크기 배율(%): 노치와 안의 모든 것이 함께 커지고 작아진다
    "lang": "ko",
}
PRIORITIES = ("auto", "cider", "other")

# 병합할 수 있는 최상위 섹션 (그 밖의 키는 무시: 설정 창이 선반/할 일 같은 데이터를 건드리지 못하게)
PATCH_SECTIONS = ("settings", "pomo", "water")


def clean_launcher(items):
    """바로가기 목록 검증: 최대 24개, 이름/대상이 있는 것만, 길이 제한, id 는 영숫자."""
    out, seen = [], set()
    for i, raw in enumerate(items if isinstance(items, list) else []):
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("name") or "").strip()[:30]
        target = str(raw.get("target") or "").strip()[:500]
        if not name or not target or "\n" in target or "\r" in target:
            continue
        iid = "".join(ch for ch in str(raw.get("id") or "") if ch.isalnum())[:16] or f"s{i}"
        while iid in seen:
            iid += "x"
        seen.add(iid)
        out.append({"id": iid, "name": name, "icon": str(raw.get("icon") or "").strip()[:16], "target": target,
                    "args": str(raw.get("args") or "").strip()[:300]})
        if len(out) >= 24:
            break
    return out
MAX_STRING = 200


def deep_merge(base, patch):
    """patch 의 값을 base 에 재귀적으로 덮어쓴다 (base 를 바꾸지 않고 복사본을 돌려준다)."""
    out = copy.deepcopy(base)
    for k, v in (patch or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def clean_patch(patch):
    """설정 창에서 온 패치를 걸러낸다: 허용된 섹션만, 값은 JSON 기본형(너무 긴 문자열 제외)만."""
    out = {}
    if not isinstance(patch, dict):
        return out

    def ok(v, depth=0):
        if depth > 3:
            return False
        if isinstance(v, (bool, int, float)) or v is None:
            return True
        if isinstance(v, str):
            return len(v) <= MAX_STRING
        if isinstance(v, dict):
            return all(isinstance(k, str) and len(k) <= 64 and ok(x, depth + 1) for k, x in v.items())
        return False

    for sec in PATCH_SECTIONS:
        v = patch.get(sec)
        if isinstance(v, dict) and ok(v):
            out[sec] = v
    return out


class Prefs:
    """파이썬 쪽이 읽는 설정의 메모리 사본. 스레드 안전."""

    def __init__(self, data=None):
        self._lock = threading.Lock()
        self._settings = dict(PY_DEFAULTS)
        self.update_from_data(data or {})

    def update_from_data(self, data):
        s = (data or {}).get("settings") if isinstance(data, dict) else None
        with self._lock:
            merged = dict(PY_DEFAULTS)
            if isinstance(s, dict):
                merged.update(s)
            if "fullscreenMode" not in (s or {}) and isinstance(s, dict) and s.get("fullscreenYield") is False:
                merged["fullscreenMode"] = "show"        # 예전 설정(전체화면 양보 끔)을 새 방식으로 옮긴다
            if merged.get("fullscreenMode") not in ("yield", "hide", "hidepeek", "show"):
                merged["fullscreenMode"] = "yield"
            for hk in ("hkToggle", "hkSettings", "hkMixer", "hkLyrics", "hkCapture", "calendarUrl", "pluginsEnabled"):
                merged[hk] = str(merged.get(hk) or "")[:MAX_STRING]
            try:
                merged["calendarRemindMin"] = max(1, min(120, int(merged.get("calendarRemindMin", 10))))
            except Exception:
                merged["calendarRemindMin"] = 10
            if merged.get("captureNotch") not in ("hide", "auto", "show"):
                merged["captureNotch"] = "auto"
            if merged.get("captureSeconds") not in (15, 60, 300, 0):
                merged["captureSeconds"] = 15
            if merged.get("appFilterMode") not in ("off", "allow", "block"):
                merged["appFilterMode"] = "off"
            merged["appFilterList"] = str(merged.get("appFilterList") or "")[:MAX_STRING]
            merged["winNotifyIgnore"] = str(merged.get("winNotifyIgnore") or "")[:MAX_STRING]
            if merged.get("lang") not in LANGS:
                merged["lang"] = "ko"
            if merged.get("glassNotch") not in ("off", "controls", "full"):
                merged["glassNotch"] = "controls"
            if merged.get("mediaPriority") not in PRIORITIES:
                merged["mediaPriority"] = "auto"
            try:
                merged["budsLowPct"] = max(5, min(50, int(merged.get("budsLowPct", 20))))
            except Exception:
                merged["budsLowPct"] = 20
            try:
                merged["monitor"] = max(0, min(32, int(merged.get("monitor", PY_DEFAULTS["monitor"]))))
            except Exception:
                merged["monitor"] = PY_DEFAULTS["monitor"]
            try:
                merged["uiScale"] = max(80, min(200, int(round(float(merged.get("uiScale", 100))))))
            except Exception:
                merged["uiScale"] = 100
            self._settings = merged

    def get(self, key, default=None):
        with self._lock:
            return self._settings.get(key, PY_DEFAULTS.get(key, default))

    def snapshot(self):
        with self._lock:
            return dict(self._settings)


# ---------------------------------------------------------------------- 윈도우 시작 프로그램
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_NAME = "Dalu"
LNK_NAME = "Dalu.lnk"


def startup_folder():
    return os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Start Menu", "Programs", "Startup")


def launch_command(script_path):
    """콘솔 창이 안 뜨도록 pythonw 로 실행하는 명령."""
    exe = sys.executable
    base = os.path.basename(exe).lower()
    if base == "python.exe":
        cand = os.path.join(os.path.dirname(exe), "pythonw.exe")
        if os.path.exists(cand):
            exe = cand
    return f'"{exe}" "{script_path}"'


def autostart_enabled(run_key=RUN_KEY, startup_dir=None):
    """시작 프로그램에 등록돼 있는가 (레지스트리 Run 항목 또는 시작프로그램 폴더의 바로가기). 인자는 테스트용."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, run_key) as k:
            try:
                winreg.QueryValueEx(k, RUN_NAME)
                return True
            except FileNotFoundError:
                pass
    except Exception:
        pass
    try:
        return os.path.exists(os.path.join(startup_dir or startup_folder(), LNK_NAME))
    except Exception:
        return False


def set_autostart(enabled, script_path, run_key=RUN_KEY, startup_dir=None):
    """켜기: Run 키에 등록하고 시작프로그램 폴더의 바로가기는 지워 중복 실행을 막는다. 끄기: 둘 다 지운다. 성공 여부를 돌려준다."""
    try:
        import winreg
        lnks = [os.path.join(startup_dir or startup_folder(), LNK_NAME)]
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, run_key) as k:
            if enabled:
                winreg.SetValueEx(k, RUN_NAME, 0, winreg.REG_SZ, launch_command(script_path))
            else:
                try:
                    winreg.DeleteValue(k, RUN_NAME)
                except FileNotFoundError:
                    pass
        for lnk in lnks:
            if os.path.exists(lnk):
                os.remove(lnk)
        return True
    except Exception:
        return False
