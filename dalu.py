# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Flirty_BananaMilk — 상업적 이용 금지, 자세한 내용은 LICENSE
import os
import re
os.environ["WEBVIEW2_DEFAULT_BACKGROUND_COLOR"] = "0"
import sys
import json
import time
import threading
import subprocess
import hashlib
import shutil
import base64
import ctypes
from ctypes import wintypes
from pathlib import Path
import webview
from cider_client import CiderClient
import sysmon
import prefs
import chimes
import monitors
import audiomix
import sysctl
import perf
import weather
import geoloc
import servicekeys
import lyricscache
import clipwatch
import calendar_ics
import plugins
import dnd
import deskcap
try:
    import audiolevels
except Exception:   # 비주얼라이저 없이도 앱은 떠야 한다
    audiolevels = None
try:
    import buds
except Exception:   # 이어버드 기능 없이도 앱은 떠야 한다
    buds = None
try:
    import btdevices
except Exception:   # 다른 무선 기기 배터리 없이도 앱은 떠야 한다
    btdevices = None
try:
    import updatecheck
except Exception:   # 새 버전 알림 없이도 앱은 떠야 한다
    updatecheck = None
try:
    import smtc
except Exception:   # Cider 외 앱의 미디어 표시 없이도 앱은 떠야 한다
    smtc = None
try:
    import tray
except Exception:   # 트레이 아이콘 없이도 앱은 떠야 한다
    tray = None
try:
    import capturewatch
except Exception:      # 없어도 앱은 돌아간다 (자동 캡처 모드만 빠진다)
    capturewatch = None
try:
    import gamewatch
except Exception:
    gamewatch = None
try:
    import winnotif
except Exception:      # 없어도 앱은 돌아간다 (윈도우 알림 표시만 빠진다)
    winnotif = None
try:
    import linkserver
except Exception:      # 없어도 앱은 돌아간다 (폰 앱 연결만 빠진다)
    linkserver = None
try:
    import phonemirror
except Exception:      # 없어도 앱은 돌아간다 (폰 화면 보기만 빠진다)
    phonemirror = None
try:
    import filexfer
except Exception:      # 없어도 앱은 돌아간다 (폰과 파일 주고받기만 빠진다)
    filexfer = None
try:
    import clipimg
except Exception:      # 없어도 앱은 돌아간다 (클립보드 이미지 동기화만 빠진다)
    clipimg = None
try:
    import clipfiles
except Exception:      # 없어도 앱은 돌아간다 (폰 사진 '복사'만 빠진다)
    clipfiles = None
try:
    import lyric_providers
except Exception:   # 외부 가사 검색 없이도 앱은 떠야 한다
    lyric_providers = None

# Setup directories
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
APPDATA_DIR = os.environ.get("APPDATA", "")
DATA_DIR = os.path.join(APPDATA_DIR, "Dalu")
ISLAND_DIR = os.path.join(DATA_DIR, "island")


os.makedirs(ISLAND_DIR, exist_ok=True)
ICON_FILE = os.path.join(ISLAND_DIR, "dalu.ico")

LOG_FILE = os.path.join(ISLAND_DIR, "app.log")
LOG_MAX_BYTES = 1024 * 1024  # 1MB 넘으면 다음 실행 때 새로 시작 (무한 증가 방지)
CALL_MEDIA_FILE = os.path.join(ISLAND_DIR, "call_media.json")      # 통화 중 줄여 둔 볼륨(앱이 도중에 꺼져도 다음에 되돌리기 위해)
CALL_DUCK_FACTOR = 0.2
CALL_DUCK_SKIP = ("discord", "kakao", "zoom", "teams", "slack", "telegram", "skype", "line", "pythonw", "dalu", "yourphone", "phone link", "msedgewebview2")        # 통화·메신저 앱과 Dalu 자신은 줄이지 않는다                                              # 전화 중 PC 볼륨: 원래의 20%
DND_STATE_FILE = os.path.join(ISLAND_DIR, "dnd_state.json")   # 방해 금지를 켜기 전 값(앱이 도중에 꺼져도 되돌리기 위해)
DATA_FILE = os.path.join(ISLAND_DIR, "data.json")   # 설정/할 일/물 기록/선반 등 (이 PC 에만 저장)
DATA_MAX_BYTES = 2 * 1024 * 1024
THUMB_DIR = os.path.join(ISLAND_DIR, "thumbs")   # 선반 썸네일 캐시
THUMB_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
THUMB_MAX_SOURCE = 300 * 1024 * 1024

log_fp = None
_log_lock = threading.Lock()
try:
    log_mode = "w" if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) > LOG_MAX_BYTES else "a"
    log_fp = open(LOG_FILE, log_mode, encoding="utf-8")
    log_fp.write("\n=== DALU STARTED ===\n")
    log_fp.flush()
    sys.stdout = log_fp
    sys.stderr = log_fp
except Exception:
    pass

def log(msg):
    if log_fp:
        try:
            with _log_lock:
                log_fp.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")
                log_fp.flush()
        except Exception:
            pass

# 창 크기 (index.html 의 STATES / .island 크기와 맞춰야 함)
# 높이 200: 가장 큰 상태(선반 172px) + 스프링 오버슈트 + 그림자 여유
# 폭 1040: 보조 노치 두 개를 같은 쪽에 놓을 때(노치를 맨 왼쪽/오른쪽에 둔 경우)도 창 안에 들어가도록 (노치 반폭 150 + 간격 + 보조 노치 둘 <= 520).
# 창은 투명하고 클릭 영역(SetWindowRgn)이 노치 모양으로 제한돼 있어서, 넓어도 아래 창을 가리지 않는다.
EXPANDED_WIDTH = 1040
EXPANDED_HEIGHT = 360   # 가장 큰 상태(알림 카드 최대 300px, 사진·문자 화면 226px, 선반 172px) + 탭 아이콘 독(23px) + 알림 띠(38px) 에 스프링 오버슈트·그림자 여유(창이 노치보다 작으면 노치 아래 모서리가 잘려 평평해 보인다)
NOTCH_WIDTH = 300   # 접힌(mini) 노치
NOTCH_HEIGHT = 32

POLL_INTERVAL = 0.25   # Cider 폴링 주기(초). 사이 시간은 오디오 시계 투영으로 채움
POLL_BOOST_INTERVAL = 0.05   # 재생 컨트롤을 누른 직후 잠시 이 주기로 폴링해 결과가 바로 반영되게 한다
BOOST_SECONDS = 2.0
MISS_LIMIT = 3         # 연속 N번 응답이 없어야 '정지'로 판단 (일시적 타임아웃 깜빡임 방지)
LYRICS_RETRY_DELAYS = (0, 0.5, 1, 2, 3, 5, 8, 10)  # 가사 조회 재시도 간격(초), 총 약 30초
LYRICS_SHOW_NONE_AFTER = 5   # 이 번째 시도까지 못 받으면 먼저 '가사 없음'을 보여 준다(나머지 재시도는 뒤에서 계속, 받으면 바로 바뀐다)
LYRICS_SLOW_DELAY = 20      # '가사 없음'으로 표시한 뒤에도 곡이 계속되는 동안 이 간격(초)으로 다시 시도
LYRICS_SLOW_RETRIES = 6
LYRICS_SLOW_RETRIES_NF = 2   # Cider 가 '가사 없음'을 확답한 곡
EXTERNAL_LYRICS_DELAYS = (0, 3, 10)   # Cider 외 앱 곡의 외부 가사 조회: 네트워크 오류 시 재시도 간격(초)

SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
HWND_TOPMOST = -1
HWND_NOTOPMOST = -2
SW_HIDE = 0
SW_SHOWNOACTIVATE = 4
GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x00000020
WS_EX_LAYERED = 0x00080000
LWA_ALPHA = 0x00000002
WS_EX_TOPMOST = 0x00000008
GW_HWNDPREV = 3

_z_user32 = None


def _zu():
    """창 순서를 다루는 user32. 핸들 인자를 64비트로 지정한다(지정하지 않으면 HWND_TOPMOST(-1) 가 32비트 -1 로 넘어가
    SetWindowPos 가 0 을 돌려주고(오류 1400: 잘못된 창 핸들) 아무것도 하지 않는다 - 노치가 다른 창 밑에 깔려도 다시 올라오지 못하던 원인)."""
    global _z_user32
    if _z_user32 is None:
        u = ctypes.WinDLL("user32", use_last_error=True)
        u.GetWindow.restype = wintypes.HWND
        u.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]
        u.GetWindowLongW.restype = ctypes.c_long
        u.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
        u.IsWindowVisible.restype = wintypes.BOOL
        u.IsWindowVisible.argtypes = [wintypes.HWND]
        u.SetWindowPos.restype = wintypes.BOOL
        u.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
        _z_user32 = u
    return _z_user32


def set_topmost(hwnd, on=True, user32=None):
    """창을 '항상 위'로 올리거나(on) 풀고(off) 제자리에 둔 채 순서만 바꾼다(이동·크기·활성화 없음). 성공하면 True."""
    try:
        u = user32 if user32 is not None else _zu()
        insert_after = ctypes.c_void_p(-1 if on else -2).value          # HWND_TOPMOST / HWND_NOTOPMOST (64비트 값)
        return bool(u.SetWindowPos(hwnd, insert_after, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE))
    except Exception:
        return False


def topmost_buried(hwnd, user32=None):
    """'항상 위' 창인데 일반 창(항상 위가 아닌 보이는 창) 밑으로 내려가 있으면 True.
    윈도우는 '항상 위' 속성이 켜져 있어도 다른 프로그램(전체화면 앱, 게임 오버레이 등)이 Z 순서를 건드리면
    창이 일반 창 밑으로 가라앉을 수 있다. 이때 속성만 믿으면 노치가 다른 창에 가려진 채로 남는다."""
    global _z_user32
    try:
        u = user32
        if u is None:
            u = _zu()
        if not u.IsWindowVisible(hwnd):
            return False
        if not (u.GetWindowLongW(hwnd, GWL_EXSTYLE) & WS_EX_TOPMOST):
            return False                                         # 항상 위가 아닌 상태(비켜 주기 모드 등)는 일부러 그런 것
        w = u.GetWindow(hwnd, GW_HWNDPREV)
        for _ in range(600):
            if not w:
                return False
            if u.IsWindowVisible(w) and not (u.GetWindowLongW(w, GWL_EXSTYLE) & WS_EX_TOPMOST):
                return True
            w = u.GetWindow(w, GW_HWNDPREV)
    except Exception:
        pass
    return False


APP_VERSION = "1.1.0"   # 배포 버전(MAJOR.MINOR.PATCH). 올릴 때는 CHANGELOG.md 에 같은 버전의 항목을 먼저 쓴다 (installer/build_release.py 가 확인)
SETTINGS_W = 980
SETTINGS_H = 680

EVENT_QUEUE_MAX = 100   # 프론트가 한동안 폴링하지 못해도 큐가 무한히 커지지 않게

class _PluginCtx:
    """플러그인 동작이 쓰는 창구: Cider 클라이언트, SMTC, 지금 재생 상태."""

    def __init__(self, api):
        self._api = api

    @property
    def client(self):
        return self._api._client

    @property
    def smtc(self):
        return self._api._smtc

    def state(self):
        with self._api._lock:
            return dict(self._api._last_state)

    def cider_up(self):
        return bool(self._api._cider_pb)


class IslandAPI:
    def __init__(self, client: CiderClient):
        self._client = client
        self._lock = threading.Lock()
        self._region_lock = threading.Lock()      # 클릭 영역(SetWindowRgn) 호출은 pywebview 가 스레드를 따로 만들어 부르므로, 순서가 뒤바뀌지 않게 하나씩 처리한다
        self._region_seq = 0                      # 가장 최근에 적용한 호출 번호: 더 낮은 번호(= 늦게 도착한 옛 호출)는 버린다
        self._running = True
        self._misses = 0

        # 시스템 이벤트(볼륨/Caps Lock/충전기 등) 큐. 프론트가 get_state 때 한꺼번에 가져간다.
        self._events = []
        self._events_lock = threading.Lock()
        self._fullscreen = False
        self._perf = None               # 성능 탭용 샘플러(처음 쓸 때 만든다)
        self._weather = weather.WeatherCache()
        self._locator = geoloc.Locator()
        self._lyrics_cache = lyricscache.LyricsCache()          # 받은 가사를 기억해 둔다(메모리만): 다시 틀면 바로, 다음 곡은 미리
        self._keys = servicekeys.load()          # 만든 사람의 OpenAQ / 에어코리아 키(설치 파일 안, 저장소에는 없음)
        self._game = ""                # 지금 앞에 있는 게임의 실행 파일 이름 ('' = 없음). 있으면 노치를 숨긴다 (설정 hideInGames)
        self._prefs = prefs.Prefs(self.load_data())     # 파이썬이 읽는 설정 사본 (설정 창/화면이 바꾸면 갱신)
        self._settings_win = None
        self._settings_lock = threading.Lock()
        self._mirror = None              # 폰 화면 보기: 폰의 화면 조각을 창에 넘기는 PC 안 서버(phonemirror.MirrorHub), 처음 쓸 때 만든다
        self._mirror_win = None
        self._mirror_lock = threading.Lock()
        self._mirror_ctl = False          # 이번 화면 보기에서 폰 조작을 요청했는가
        self._mirror_fit_key = None
        self._mirror_stop_sent = 0.0
        self._pm = None                  # 폰에서 재생 중인 미디어(설정 phoneMedia): 마지막으로 받은 곡 정보
        self._pm_clock = None            # 폰 시계와 이 PC 시계의 차이({off 초, rtt 초, at}): 폰이 보낸 재생 위치가 오는 데 걸린 시간을 보정한다
        self._pm_clock_busy = False
        self._apk_seen = 0               # 폰 앱이 옛 버전이라고 PC 화면에 알린 앱 파일 버전(같은 버전은 실행당 한 번만 알린다)
        self._app_sent_at = 0.0          # 폰 앱 파일을 마지막으로 보내기 시작한 시각(연타 방지)
        self._data_lock = threading.Lock()
        self._monitor = sysmon.SysMonitor(push=self._push_event, on_fullscreen=self._on_fullscreen,
                                         own_hwnd=self._get_hwnd, on_game=self._on_game, game_check=self._game_check)
        self._monitor.start()
        # 비주얼라이저용 오디오 레벨 (루프백). 화면이 get_levels() 를 호출할 때만 계산한다.
        self._buds = None
        if buds is not None:
            try:
                self._buds = buds.BudsService(log=log, push=self._push_event)
                if not self._buds.start():
                    self._buds = None
            except Exception as e:
                log(f"buds start failed: {e!r}")
                self._buds = None
        # 다른 무선 음향 기기(헤드셋·스피커·에어팟)의 연결과 배터리: 윈도우가 이미 가진 값을 읽는다(갤럭시 버즈는 위 buds 가 따로 다룬다)
        self._bt = None
        if btdevices is not None:
            try:
                self._bt = btdevices.BtDevices(log=log, push=self._push_event, skip=self._bt_skip)
                self._bt.start()
            except Exception as e:
                log(f"btdevices start failed: {e!r}")
                self._bt = None
        # 새 버전 알림: 하루에 한 번 공개 웹사이트의 version.json 하나만 읽는다(설정에서 끌 수 있다). 설치 파일은 받지도 실행하지도 않는다
        self._update = None
        self._updater = None
        if updatecheck is not None:
            try:
                self._update = updatecheck.UpdateChecker(APP_VERSION, log=log, push=self._push_event,
                                                         enabled=lambda: bool(self._prefs.get("updateCheck")),
                                                         state_path=os.path.join(ISLAND_DIR, "update_state.json"))
                self._update.start()
                self._updater = updatecheck.Updater(self._update, os.path.join(DATA_DIR, "update"), log=log)
            except Exception as e:
                log(f"updatecheck start failed: {e!r}")
                self._update = None
        # Cider 가 아닌 앱(Spotify, 브라우저 등)의 미디어: 윈도우 미디어 세션(SMTC)에서 읽는다
        self._smtc = None
        if smtc is not None:
            try:
                self._smtc = smtc.MediaSessionService(log=log)
                self._smtc.start()
            except Exception as e:
                log(f"smtc start failed: {e!r}")
                self._smtc = None
        self._source = "cider"        # 지금 화면에 보여 주는 쪽: 'cider' | 'smtc'
        self._cider_pb = None         # Cider 의 마지막 재생 상태 (응답이 끊기면 None)
        self._levels = None
        if audiolevels is not None:
            try:
                self._levels = audiolevels.LevelMonitor(log=log)
                self._levels.start()
            except Exception as e:
                log(f"audiolevels start failed: {e!r}")

        # 아래 값들은 모두 self._lock 으로 보호
        self._current_track_id = ""
        self._cached_lyrics = None
        self._lyrics_version = 0  # 가사가 바뀔 때마다 증가. 프론트는 이 값이 바뀔 때만 가사를 받는다.

        # Precision Audio Clock Projection
        self._last_raw_time = -1.0
        self._anchor_time = 0.0
        self._anchor_perf = time.perf_counter()
        self._is_playing = False

        self._click_through = False

        self._last_state = {
            "isPlaying": False,
            "state": "stopped",
            "currentTime": 0.0,
            "duration": 0.0,
            "title": "",
            "artist": "",
            "album": "",
            "artworkUrl": "",
            "trackId": "",
            "repeat": "none",
            "shuffle": False,
            "source": "cider",
            "appName": "Cider",
            "canMode": True,
            "next": None,
            "sources": [],
        }

        try:
            if dnd.restore_if_pending(DND_STATE_FILE):
                log("Restored Do Not Disturb left on by a previous run.")
        except Exception as e:
            log(f"dnd restore failed: {e!r}")
        self._plugin_ctx = _PluginCtx(self)
        self._plugins = plugins.Registry(os.path.join(DATA_DIR, "plugins"), log=log)
        self._mon_key = None
        self._boost_until = 0.0
        self._forced_source = None      # 사용자가 노치에서 직접 고른 소스('cider'|'smtc'). 그 소스에 곡이 없어지면 해제
        self._peek_hide_timer = None
        # 클립보드 기록 (설정에서 켠 경우에만 읽는다)
        self._clip = clipwatch.ClipHistory()
        self._call_media = None         # 통화 중 PC 소리를 줄이거나 멈춘 기록(끝나면 되돌린다)
        self._clip_from_phone = ""      # 마지막으로 폰에서 받아 클립보드에 넣은 글(되돌려 보내지 않기 위해)
        self._img_asm = clipimg.Assembler() if clipimg is not None else None      # 폰이 조각으로 보낸 이미지를 모은다
        self._img_hash_from_phone = ""  # 마지막으로 폰에서 받아 넣은 이미지의 해시(되돌려 보내지 않기 위해)
        self._img_hash_sent = ""
        self._clipwatch = clipwatch.ClipWatcher(self._clip, log=log, on_text=self._clip_changed, sync_when=self._clip_sync_wanted, on_image=self._clip_image_changed)
        self._clipwatch.start()
        self._call_media_recover()      # 앞서 통화 도중에 꺼졌다면 줄여 둔 볼륨을 되돌린다
        # 캘린더(.ics)
        self._cal = calendar_ics.CalendarSource()
        self._cal_notified = set()
        threading.Thread(target=self._calendar_worker, daemon=True, name="calendar").start()
        self._next_for, self._next_at = None, 0.0
        self._desk = deskcap.DeskCapture(self._get_hwnd, self._desk_rect, self._desk_push, log=log)
        self._winnotif = None
        if winnotif is not None:
            self._winnotif = winnotif.NotificationWatch(lambda apps: self._push_event({"type": "win_notify", "apps": list(apps)[:8]}),
                                                        enabled=lambda: bool(self._prefs.get("winNotify")), log=log,
                                                        ignore=lambda: self._winnotif_ignore(),
                                                        store_path=os.path.join(ISLAND_DIR, "winnotif_apps.json"),
                                                        on_clear=lambda why: self._push_event({"type": "win_notify_clear", "why": why}))
            self._winnotif.start()
        self._files = None              # 폰과 파일 주고받기(filexfer.Manager): 처음 쓸 때 만든다
        self._phone_apps = {}           # 폰에서 알림을 보낸 앱: {패키지: {name, count}} (앱 이름과 횟수만 이 PC 에 기억한다)
        self._phone_apps_loaded = False
        self._snooze = {}                # 임시 차단 중인 폰 앱 {패키지: 풀리는 시각(초)}: 노치 알림 카드의 1시간·6시간·24시간 단추
        self._snooze_loaded = False
        self._snooze_timer = None
        self._pull_until = 0.0          # PC 가 폰에서 가져오기를 요청한 뒤 이 시각까지는 폰이 보내는 파일을 묻지 않고 받는다
        self._file_paths = {}           # 폰에서 받은 파일의 경로(순서 있는 사전)(열기·폴더 보기는 이 경로만 허용한다)
        self._copy_job = None           # 폰 사진 '복사' 진행 중인 작업(받은 파일을 모아 클립보드에 올린다)
        self._copy_lock = threading.Lock()
        self._link = None               # Dalu Link(폰 앱) 서버: 설정에서 켰을 때만 만든다
        self._apk = None                # 폰 앱 설치 파일을 LAN 으로 내려 주는 작은 서버(설정 화면에서 요청했을 때만)
        self._link_info = {"battery": None, "charging": None, "name": "", "ringer": None, "dnd": None, "policy": None, "missed": 0, "missed_ack": 0, "call": None}
        self._phone_asked = 0.0         # JS 가 마지막으로 휴대폰 상태를 물어본 시각
        self._capwatch = None
        if capturewatch is not None:
            self._capwatch = capturewatch.CaptureWatch(lambda sec, why: self._capture_auto(sec, why),
                                                      enabled=lambda: self._prefs.get("captureNotch") == "auto" and self._desk._on, log=log)
            self._capwatch.start()
        self._apply_prefs()            # 위에서 만든 서비스(클립보드/캘린더/단축키/버즈/SMTC)에 설정을 반영
        threading.Thread(target=self._monitor_watch, daemon=True, name="monitor-watch").start()

        # Start low-latency background polling thread
        self._poll_thread = threading.Thread(target=self._background_poll_worker, daemon=True, name="cider-poll")
        self._poll_thread.start()
        log("Background polling thread started.")

    # ------------------------------------------------------------------
    # Win32 helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _primary_screen():
        screens = webview.screens
        return next((s for s in screens if s.x == 0 and s.y == 0), screens[0])

    def _get_scale(self):
        """시스템 DPI 배율(150% -> 1.5). 이 프로세스는 시스템 DPI 인식이라 값이 프로세스 내내 변하지 않는 GetDpiForSystem 을 쓴다.
        (예전에는 '물리 폭 / pywebview 의 주 화면 폭'으로 구했는데, 부팅 직후 모니터 번호/목록이 흔들리는 동안 1.5 와 1.0 사이를
        오가서 창이 작게 만들어지고 노치 아래쪽이 잘렸다)"""
        try:
            dpi = int(ctypes.windll.user32.GetDpiForSystem())
            if 48 <= dpi <= 960:
                return max(1.0, dpi / 96.0)
        except Exception:
            pass
        try:
            phys_w = ctypes.windll.user32.GetSystemMetrics(0)
            return max(1.0, phys_w / self._primary_screen().width)
        except Exception:
            return 1.0

    def _ui_scale(self):
        try:
            return max(0.8, min(2.0, float(self._prefs.get("uiScale")) / 100.0))
        except Exception:
            return 1.0

    def _notch_scale(self):
        """노치 창의 물리 픽셀 배율: 시스템 DPI 배율 x 'UI 크기' 설정. (설정 창은 UI 크기의 영향을 받지 않는다)"""
        return self._get_scale() * self._ui_scale()

    def _apply_zoom(self):
        """WebView2 확대 배율을 'UI 크기'에 맞춘다. 화면(CSS) 크기는 그대로고 모든 것이 물리 픽셀로 커지며,
        devicePixelRatio 도 같이 커져서 화면 쪽 영역 계산(SetWindowRgn)이 그대로 맞는다."""
        try:
            if not webview.windows:
                return False
            form = webview.windows[0].native
            z = self._ui_scale()
            from System import Action
            done = {}

            def setz():
                wv = form.webview
                if abs(float(wv.ZoomFactor) - z) > 1e-6:
                    wv.ZoomFactor = z
                done["z"] = float(wv.ZoomFactor)

            form.Invoke(Action(setz))
            return abs(done.get("z", 0) - z) < 1e-3
        except Exception as e:
            log(f"_apply_zoom error: {e!r}")
            return False

    def apply_ui_scale(self):
        """UI 크기가 바뀌었을 때(또는 시작할 때): 확대 배율과 창 크기를 맞추고 같은 자리(모니터 위 가운데)에 다시 놓는다."""
        self._apply_zoom()
        self.recenter_window()
        self._ui_scale_applied = self._ui_scale()
        return {"status": "ok", "scale": self._ui_scale_applied}

    @staticmethod
    def _get_hwnd():
        if webview.windows:
            native = getattr(webview.windows[0], 'native', None)
            if native:
                return int(native.Handle.ToInt64())
        return None

    def _set_window_region(self, hwnd, left, right, bottom, dpr, diameter):
        """상단은 평평하고 하단만 둥근 영역으로 창을 잘라, 그 밖의 투명 영역은 클릭이 통과되게 한다."""
        user32 = ctypes.windll.user32
        gdi32 = ctypes.windll.gdi32
        RGN_OR = 2
        hrgn_top = gdi32.CreateRectRgn(left, 0, right, max(1, min(int(18 * dpr), bottom)))          # 띠는 18px 이되 영역 자체(슬림은 12px)보다 높지 않게
        hrgn_round = gdi32.CreateRoundRectRgn(left, 0, right, bottom, diameter, diameter)
        hrgn_final = gdi32.CreateRectRgn(0, 0, 0, 0)
        gdi32.CombineRgn(hrgn_final, hrgn_top, hrgn_round, RGN_OR)
        gdi32.DeleteObject(hrgn_top)
        gdi32.DeleteObject(hrgn_round)
        # 성공하면 리전 소유권이 시스템으로 넘어간다. 실패했을 때만 직접 해제 (GDI 핸들 누수 방지)
        if not user32.SetWindowRgn(hwnd, hrgn_final, True):
            gdi32.DeleteObject(hrgn_final)

    # ------------------------------------------------------------------
    # Playback polling
    # ------------------------------------------------------------------
    def _projected_time_locked(self):
        duration = self._last_state.get("duration", 0.0)
        if self._is_playing:
            t = self._anchor_time + (time.perf_counter() - self._anchor_perf)          # 길이를 모를 때(0)도 시계로 이어 간다
            return min(duration, t) if duration > 0 else t
        return self._anchor_time

    def _background_poll_worker(self):
        """Cider REST API 와 윈도우 미디어 세션을 폴링해, 재생 중인 쪽을 오디오 투영 시계에 맞춰 반영한다."""
        last_err = None
        while self._running:
            try:
                self._poll_once()
                last_err = None
            except Exception as e:
                msg = repr(e)
                if msg != last_err:  # 같은 오류가 반복돼도 로그가 도배되지 않게
                    log(f"poll error: {msg}")
                    last_err = msg

            time.sleep(POLL_BOOST_INTERVAL if time.monotonic() < self._boost_until else POLL_INTERVAL)

    def _refresh_up_next(self, track_id):
        """Cider 대기열의 다음 곡. 곡이 바뀐 직후와 이후 15초마다 갱신한다(대기열이 바뀔 수 있으므로)."""
        now = time.monotonic()
        if track_id == self._next_for and now - self._next_at < 15:
            return
        self._next_for, self._next_at = track_id, now
        try:
            nxt = self._client.get_up_next()
        except Exception:
            nxt = None
        with self._lock:
            self._last_state["next"] = nxt if self._prefs.get("upNext") else None
        if nxt and nxt.get("title"):
            self._prefetch_lyrics(nxt)

    def _prefetch_lyrics(self, nxt):
        """다음 곡 가사를 지금 곡이 나오는 동안 Cider 에서 미리 받아 기억해 둔다(한 곡당 한 번, 백그라운드). 곡이 바뀌면 바로 보인다."""
        key = lyricscache.key_for(nxt.get("trackId", ""), nxt.get("catalogId", ""))
        if not self._lyrics_cache.claim(key):
            return

        def run():
            try:
                lyrics, _info = self._client.get_lyrics_ex(nxt.get("trackId", ""), nxt.get("title", ""), nxt.get("artist", ""),
                                                           catalog_id=nxt.get("catalogId", ""), has_lyrics=None)
                if lyrics and self._lyrics_cache.put(key, lyrics):
                    log(f"Lyrics prefetched for the next song: {nxt.get('title')} ({len(lyrics.get('lines', []))} lines)")
            except Exception as e:
                log(f"lyrics prefetch failed for {nxt.get('title')}: {type(e).__name__}")
            finally:
                self._lyrics_cache.release(key)
        threading.Thread(target=run, daemon=True, name="lyrics-prefetch").start()

    def _poll_once(self):
        pb = self._client.get_playback_state()
        if pb:
            self._misses = 0
            self._cider_pb = pb
        else:
            self._misses += 1
            if self._misses == MISS_LIMIT:
                self._cider_pb = None
        other = self._smtc.snapshot() if (self._smtc is not None and self._prefs.get("smtcOn")) else None
        phone = self._phone_media_pb()
        cider = self._cider_pb
        cider_has = bool(cider and cider.get("title"))
        if self._forced_source == "cider" and not cider_has or self._forced_source == "smtc" and not other or self._forced_source == "phone" and not phone:
            self._forced_source = None                      # 직접 고른 소스에 곡이 없어졌다: 자동 선택으로 돌아간다
        if self._forced_source:
            src = self._forced_source
        elif smtc is not None:
            src = smtc.choose_source(cider_has, bool(cider and cider.get("isPlaying")),
                                     bool(other), bool(other and other["isPlaying"]), self._source,
                                     self._prefs.get("mediaPriority"))
        else:
            src = "cider"
        if phone and not self._forced_source:
            cur_playing = bool((src == "cider" and cider and cider.get("isPlaying")) or (src == "smtc" and other and other["isPlaying"]))
            if phone["isPlaying"] and not cur_playing:
                src = "phone"                                 # PC 쪽이 멈춰 있을 때 폰에서 재생 중인 곡을 보여 준다
            elif not phone["isPlaying"] and not cur_playing and self._source == "phone":
                src = "phone"                                 # 보던 폰 곡이 일시정지돼도 그대로 둔다
        sources = []
        if cider_has:
            sources.append({"id": "cider", "name": "Cider", "playing": bool(cider.get("isPlaying"))})
        if other:
            sources.append({"id": "smtc", "name": other.get("appName") or "Media", "playing": bool(other.get("isPlaying"))})
        if phone:
            sources.append({"id": "phone", "name": self._phone_label(phone), "playing": bool(phone["isPlaying"])})
        with self._lock:
            self._last_state["sources"] = sources
        ssig = tuple((x["id"], x["name"], x["playing"]) for x in sources)
        if ssig != getattr(self, "_src_sig", None):      # 재생 소스 목록이 바뀔 때만 기록(어떤 앱이 둘째 소스로 잡히는지 나중에 알 수 있게)
            self._src_sig = ssig
            log(f"Media sources: {[list(x) for x in ssig]}" + (f" other app={other.get('app')!r}" if other else ""))
        if src != self._source:
            log(f"Media source: {self._source} -> {src}" + (f" ({other['appName']})" if src == "smtc" and other else ""))
            self._source = src
        if src == "smtc" and other:
            self._apply_playback(self._smtc_to_pb(other))
            with self._lock:
                self._last_state["next"] = None            # 다른 앱은 다음 곡을 알 수 없다
        elif src == "phone" and phone:
            self._apply_playback(phone)
            with self._lock:
                self._last_state["next"] = None            # 폰의 다음 곡은 알 수 없다
        elif src == "cider" and cider:
            self._apply_playback(cider)
            if hasattr(self._client, "get_up_next"):          # '다음 곡' 표시를 꺼 두어도 다음 곡 가사는 미리 받아 둔다(표시만 끈다)
                self._refresh_up_next(cider.get("trackId"))
        elif self._last_state.get("source") in ("smtc", "phone"):
            self._clear_track()          # 보던 앱이 꺼졌다: 곡 정보를 비워 시계로 돌아가게 한다
        elif self._misses == MISS_LIMIT:
            self._mark_stopped()

    @staticmethod
    def _smtc_to_pb(sm):
        """윈도우 미디어 세션 정보를 Cider 재생 상태와 같은 모양으로 맞춘다."""
        return {"source": "smtc", "appName": sm["appName"], "state": sm["state"], "isPlaying": sm["isPlaying"],
                "currentTime": sm["position"], "duration": sm["duration"], "trackId": sm["key"], "catalogId": "",
                "hasLyrics": False, "title": sm["title"], "artist": sm["artist"], "album": sm["album"],
                "artworkUrl": sm["artworkUrl"], "repeat": sm["repeat"] or "none", "shuffle": bool(sm["shuffle"]),
                "canMode": sm["repeat"] is not None or sm["shuffle"] is not None}

    def _clear_track(self):
        with self._lock:
            self._current_track_id = ""
            self._cached_lyrics = None
            self._lyrics_version += 1
            self._is_playing = False
            self._last_state.update({"isPlaying": False, "state": "stopped", "title": "", "artist": "", "album": "",
                                     "artworkUrl": "", "trackId": "", "duration": 0.0, "currentTime": 0.0,
                                     "source": "cider", "appName": "Cider", "canMode": True})
            self._anchor_time = 0.0
            self._anchor_perf = time.perf_counter()

    def _mark_stopped(self):
        """Cider 응답이 끊겼을 때: 시계를 현재 위치에서 멈춘다."""
        with self._lock:
            self._anchor_time = self._projected_time_locked()
            self._anchor_perf = time.perf_counter()
            self._is_playing = False
            self._last_state.update({
                "isPlaying": False,
                "state": "stopped",
                "currentTime": self._anchor_time,
            })

    def _apply_playback(self, pb):
        t_id = pb.get("trackId", "")
        title = pb.get("title", "")
        artist = pb.get("artist", "")
        is_playing = pb.get("isPlaying", False)
        raw_cur_time = float(pb.get("currentTime", 0.0))
        duration = float(pb.get("duration", 0.0))

        # 1. 곡이 바뀌면 이전 곡 가사를 즉시 비우고, 새 곡 가사는 별도 스레드에서 조회한다.
        #    (조회를 폴링 루프 안에서 하면 HTTP 타임아웃 동안 재생 상태 갱신이 통째로 멈춘다)
        with self._lock:
            track_changed = bool(t_id) and t_id != self._current_track_id
            if track_changed:
                self._current_track_id = t_id
                self._cached_lyrics = None
                self._lyrics_version += 1
        if track_changed and pb.get("source") in ("smtc", "phone"):
            # Cider 가 아닌 앱의 곡: Cider 가사 API 는 쓸 수 없으니 외부 가사 서비스(NetEase, LRCLIB)에서 직접 찾는다
            log(f"Track changed: {title} - {artist} [{pb.get('appName')}] -> searching external lyrics")
            threading.Thread(target=self._external_lyrics_worker,
                             args=(t_id, title, artist, pb.get("album", ""), duration),
                             daemon=True, name="ext-lyrics").start()
        elif track_changed:
            hit = self._lyrics_cache.get(lyricscache.key_for(t_id, pb.get("catalogId", "")))
            if hit is not None and self._commit_lyrics(t_id, hit):
                log(f"Track changed: {title} - {artist} (id: {t_id}) -> lyrics from memory ({len(hit.get('lines', []))} lines, no request)")
            else:
                log(f"Track changed: {title} - {artist} (id: {t_id}) -> resetting lyrics cache")
                threading.Thread(
                    target=self._lyrics_worker,
                    args=(t_id, title, artist, pb.get("catalogId", ""), pb.get("hasLyrics")),
                    daemon=True, name="cider-lyrics"
                ).start()

        # 2. 오디오 시계 동기화
        now_perf = time.perf_counter()
        with self._lock:
            # Cider 가 currentTime 을 갱신했거나 재생 상태/곡이 바뀌면 앵커를 새로 잡는다
            advancing = bool(is_playing) and not pb.get("posFrozen")      # 폰 미디어의 버퍼링: 재생 중으로 보이지만 위치는 흐르지 않는다
            if track_changed or (raw_cur_time != self._last_raw_time) or (advancing != self._is_playing):
                self._last_raw_time = raw_cur_time
                self._anchor_time = raw_cur_time
                self._anchor_perf = now_perf
                self._is_playing = advancing

            self._last_state.update({
                "isPlaying": is_playing,
                "state": pb.get("state", "stopped"),
                "duration": duration,
                "title": title,
                "artist": artist,
                "album": pb.get("album", ""),
                "artworkUrl": pb.get("artworkUrl", ""),
                "trackId": t_id,
                "repeat": pb.get("repeat", "none"),
                "shuffle": bool(pb.get("shuffle", False)),
                "source": pb.get("source", "cider"),
                "appName": pb.get("appName", "Cider"),
                "canMode": pb.get("canMode", True),     # 앱이 반복/셔플을 지원하는가 (Cider 는 항상)
                "posRev": pb.get("posRev", 0),          # 폰 미디어: 폰이 위치를 새로 알릴 때마다 바뀌는 번호(화면이 그때 재생 위치를 다시 맞춘다)
                "posFrozen": bool(pb.get("posFrozen")),  # 폰 미디어: 버퍼링 중이라 위치가 멈춰 있다(화면도 시간을 흘려 보내지 않는다)
            })
            self._last_state["currentTime"] = self._projected_time_locked()

    # ------------------------------------------------------------------
    # Lyrics (별도 스레드)
    # ------------------------------------------------------------------
    def _is_current_track(self, track_id):
        with self._lock:
            return self._running and self._current_track_id == track_id

    def _commit_lyrics(self, track_id, lyrics):
        """조회하는 사이 곡이 바뀌었다면 버린다 (이전 곡 가사가 새 곡에 붙는 것 방지)."""
        with self._lock:
            if self._current_track_id != track_id:
                return False
            self._cached_lyrics = lyrics
            self._lyrics_version += 1
            return True

    def _wait_on_track(self, track_id, seconds):
        """seconds 동안 대기하되, 곡이 바뀌었으면 즉시 False."""
        waited = 0.0
        while waited < seconds:
            if not self._is_current_track(track_id):
                return False
            step = min(0.25, seconds - waited)
            time.sleep(step)
            waited += step
        return self._is_current_track(track_id)

    def _try_lyrics(self, track_id, title, artist, catalog_id, has_lyrics, last=False):
        """한 번 조회한다. 'ok'(성공) | 'none'(Cider 가 가사 없음을 확답) | 'fail'(타임아웃 등 불확실).
        실패 이유(trace)는 마지막 시도 또는 확답을 받았을 때 로그로 남긴다."""
        try:
            lyrics, info = self._client.get_lyrics_ex(track_id, title, artist, catalog_id=catalog_id, has_lyrics=has_lyrics)
        except Exception as e:
            log(f"get_lyrics error for {title}: {e!r}")
            return "fail"
        if lyrics:
            self._lyrics_cache.put(lyricscache.key_for(track_id, catalog_id), lyrics)
            if self._commit_lyrics(track_id, lyrics):
                log(f"Lyrics bound for {title} (source: {lyrics.get('source')}, timing: {lyrics.get('timingType')}, "
                    f"lines: {len(lyrics.get('lines', []))}{', unsynced' if lyrics.get('unsynced') else ''})")
            return "ok"
        if last or info.get("not_found"):
            log(f"Lyrics lookup failed for {title} (id={track_id}, catalog={catalog_id}, hasLyrics={has_lyrics}, "
                f"notFound={info.get('not_found')}): " + "; ".join(info.get("trace") or ["no trace"]))
        return "none" if info.get("not_found") else "fail"

    def _lyrics_worker(self, track_id, title, artist, catalog_id="", has_lyrics=None):
        # Cider 가 곡이 없다고 알려 주면(hasLyrics=False) 오래 기다리지 않는다 (로컬 TTML 은 첫 시도에서 잡힌다)
        delays = LYRICS_RETRY_DELAYS if has_lyrics is not False else LYRICS_RETRY_DELAYS[:3]
        not_found_streak = 0
        shown_none = False
        for i, delay in enumerate(delays):
            if not self._wait_on_track(track_id, delay):
                return
            result = self._try_lyrics(track_id, title, artist, catalog_id, has_lyrics, last=(i == len(delays) - 1))
            if result == "ok":
                return
            if i + 1 == LYRICS_SHOW_NONE_AFTER and len(delays) > i + 1 and not shown_none:
                # 앞의 몇 번에 못 받았다: '불러오는 중'만 계속 보이지 않게 먼저 '없음'을 표시하고, 남은 재시도는 계속한다(받으면 바로 가사로 바뀐다)
                shown_none = True
                self._commit_lyrics(track_id, {"lines": []})
            not_found_streak = not_found_streak + 1 if result == "none" else 0
            if not_found_streak >= 2:   # 연속 두 번 '가사 없음' 확답: 30초 동안 '불러오는 중'을 보이지 않는다
                break

        # '가사 없음'을 화면에 보여 주되, 곡이 계속 재생되는 동안은 느리게 몇 번 더 시도한다
        # (Cider 가 늦게 가사를 받아 오는 경우 구제). 확답을 받은 곡은 횟수를 줄인다.
        if self._commit_lyrics(track_id, {"lines": []}):
            log(f"No lyrics for {title} (confirmed by Cider: {not_found_streak >= 2}); showing 'none'.")
        retries = LYRICS_SLOW_RETRIES_NF if not_found_streak >= 2 else LYRICS_SLOW_RETRIES
        for j in range(retries):
            if not self._wait_on_track(track_id, LYRICS_SLOW_DELAY):
                return
            if self._try_lyrics(track_id, title, artist, catalog_id, has_lyrics, last=(j == retries - 1)) == "ok":
                return

    def _external_lyrics_worker(self, track_id, title, artist, album, duration):
        """윈도우 미디어 세션으로 읽은 곡의 가사를 외부 서비스에서 찾는다. 네트워크 오류면 몇 번 다시 시도한다."""
        providers = tuple(p for p in (lyric_providers.PROVIDERS if lyric_providers else ())
                          if self._prefs.get({"Apple Music": "extApple", "NetEase": "extNetease", "LRCLIB": "extLrclib"}.get(p[0], ""), True))
        if lyric_providers is None or not self._prefs.get("extLyrics") or not providers:
            self._commit_lyrics(track_id, {"lines": []})        # 외부 가사 검색을 꺼 둔 경우: 조회하지 않는다
            return
        for attempt, delay in enumerate(EXTERNAL_LYRICS_DELAYS):
            if not self._wait_on_track(track_id, delay):
                return
            try:
                lyrics, info = lyric_providers.fetch_lyrics(title, artist, album, duration, providers=providers, log=log)
            except Exception as e:
                log(f"external lyrics error for {title}: {e!r}")
                lyrics, info = None, {"errors": [repr(e)], "not_found": False}
            if lyrics:
                lyrics["trackId"] = track_id
                if self._commit_lyrics(track_id, lyrics):
                    log(f"Lyrics bound for {title} (external: {lyrics.get('source')}, timing: {lyrics.get('timingType')}, "
                        f"lines: {len(lyrics.get('lines', []))}{', unsynced' if lyrics.get('unsynced') else ''}"
                        f"{', cached' if info.get('cached') else ''})")
                return
            if info.get("not_found"):
                break
            log(f"external lyrics attempt {attempt + 1} failed for {title}: " + "; ".join(info.get("errors") or ["?"]))
        if self._commit_lyrics(track_id, {"lines": []}):
            log(f"No external lyrics for {title} - {artist}; showing 'none'.")

    # ------------------------------------------------------------------
    # JS bridge
    # ------------------------------------------------------------------
    def get_state(self, known_lyrics_version=None):
        """Instantaneous in-memory projected lookup.

        가사는 크기가 커서(수백 줄 x 단어) 매 폴링마다 직렬화하면 낭비이므로,
        프론트가 가진 버전과 다를 때만 포함시킨다.
        """
        with self._lock:
            state = dict(self._last_state)  # 복사본: 락 밖에서 직렬화돼도 안전
            state["currentTime"] = self._projected_time_locked()
            state["lyricsVersion"] = self._lyrics_version
            if known_lyrics_version != self._lyrics_version:
                state["lyrics"] = self._cached_lyrics
        state["events"] = self._drain_events()
        state["buds"] = self._buds.snapshot() if self._buds else {"available": False, "connected": False}
        state["btdevices"] = self._bt.snapshot() if self._bt else {"enabled": False, "devices": []}
        state["update"] = self._update_state()
        state["idleSec"] = sysmon.read_idle_sec()   # 입력이 없었던 시간(초): 캐릭터(눈) 상태에 사용
        return state

    # ------------------------------------------------------------------
    # 시스템 이벤트 / 전체화면
    # ------------------------------------------------------------------
    def _push_event(self, event):
        if event.get("type") == "media_key":
            self._peek_over_fullscreen()
        with self._events_lock:
            self._events.append(event)
            del self._events[:-EVENT_QUEUE_MAX]

    def _update_state(self):
        """노치 안 '업데이트' 칩이 읽는 값: 새 버전이 확인돼 있으면 {version, download, state, percent, error}, 아니면 None(설정에서 끄면 항상 None)."""
        try:
            if not self._update or not self._prefs.get("updateCheck"):
                return None
            snap = self._update.snapshot()
            if not snap:
                return None
            st = self._updater.status() if self._updater else {"state": "idle", "percent": 0, "error": ""}
            return {"version": snap["version"], "download": bool(snap.get("download")), **st}
        except Exception:
            return None

    def _bt_skip(self):
        """갤럭시 버즈가 연결돼 있으면 그 이름은 따로 다루므로 일반 목록에서 뺀다."""
        try:
            snap = self._buds.snapshot() if self._buds else None
            return [snap.get("name")] if snap and snap.get("connected") and snap.get("name") else []
        except Exception:
            return []

    def bt_refresh(self):
        """다른 무선 기기 목록을 바로 다시 읽는다(노치의 이어버드 탭을 열 때)."""
        if self._bt is not None:
            self._bt.refresh()
        return {"status": "ok"}

    def buds_set_mode(self, mode):
        """이어버드 소음 제어 모드 설정 (0 끄기, 1 노이즈 캔슬링, 2 주변 소리, 3 어댑티브). 확인 응답까지 최대 약 20초 블로킹."""
        if self._buds is None:
            return {"status": "error", "message": "earbuds support unavailable"}
        try:
            return self._buds.set_noise_mode(int(mode))
        except Exception as e:
            return {"status": "error", "message": repr(e)}

    def buds_set_eq(self, preset):
        """이퀄라이저 프리셋(0 일반, 1 베이스 부스트, 2 소프트, 3 다이내믹, 4 클리어, 5 트레블 부스트)을 이어버드에 보낸다."""
        if self._buds is None:
            return {"status": "error", "message": "buds unavailable"}
        try:
            preset = int(preset)
        except Exception:
            return {"status": "error", "message": "invalid preset"}
        return self._buds.set_equalizer(preset)

    def buds_set_custom_eq(self, bands):
        """9밴드 사용자 이퀄라이저(각 -10~+10)를 이어버드에 보내고 '사용자' 프리셋을 고른다."""
        if self._buds is None:
            return {"status": "error", "message": "buds unavailable"}
        try:
            return self._buds.set_custom_eq(list(bands))
        except Exception as e:
            return {"status": "error", "message": repr(e)}

    def buds_eq_table(self):
        """이어버드의 프리셋 표와 사용자 곡선(읽기만)."""
        if self._buds is None:
            return {"status": "error", "message": "buds unavailable"}
        try:
            return self._buds.eq_table()
        except Exception as e:
            return {"status": "error", "message": repr(e)}

    def buds_set_nc_one(self, on):
        """한쪽만 착용해도 소음 제어 허용 켜기/끄기."""
        if self._buds is None:
            return {"status": "error", "message": "buds unavailable"}
        try:
            return self._buds.set_nc_one_earbud(bool(on))
        except Exception as e:
            return {"status": "error", "message": repr(e)}

    def buds_prepare(self):
        """버즈 페이지를 열 때 호출: 제어 연결을 미리 맺어 첫 모드 변경이 즉시 되게 한다 (기다리지 않고 반환)."""
        try:
            if self._buds is not None:
                self._buds.prepare_control()
        except Exception as e:
            log(f"buds_prepare error: {e!r}")
        return {"status": "ok"}

    def get_levels(self):
        """저음~고음 5개 대역의 현재 레벨(0~1). available=False 면 화면이 자체 애니메이션으로 대체한다."""
        if self._levels is None:
            return {"levels": [0.0] * 5, "available": False}
        return self._levels.poll()

    def _drain_events(self):
        with self._events_lock:
            events, self._events = self._events, []
        return events

    def _show_window(self, visible):
        try:
            hwnd = self._get_hwnd()
            if visible and self._game:        # 게임 중에는 다른 기능이 노치를 다시 보이게 하지 못한다
                return
            if hwnd:
                ctypes.windll.user32.ShowWindow(hwnd, SW_SHOWNOACTIVATE if visible else SW_HIDE)
        except Exception as e:
            log(f"_show_window error: {e!r}")

    def _game_check(self, own_hwnd):
        """게임 숨기기가 켜져 있으면 앞의 전체화면 앱이 게임(DirectX/OpenGL/Vulkan)인지 확인해 이름을 돌려준다."""
        if not self._prefs.get("hideInGames") or gamewatch is None:
            return ""
        return gamewatch.foreground_game(own_hwnd, gamewatch.parse_names(self._prefs.get("gameAlways")),
                                         gamewatch.parse_names(self._prefs.get("gameNever")))

    def _on_game(self, name):
        """게임이 앞에 생기면 노치를 숨기고(뒤 화면 캡처도 같이 멈춘다), 게임이 끝나면 되돌린다."""
        try:
            self._game = name or ""
            hwnd = self._get_hwnd()
            if not hwnd:
                return
            if self._game:
                self._cancel_peek_hide()
                ctypes.windll.user32.ShowWindow(hwnd, SW_HIDE)
            else:
                # 전체화면 숨김 모드로 이미 숨겨 둔 경우는 그 규칙을 따른다
                if not (self._fullscreen and self._prefs.get("fullscreenMode") in ("hide", "hidepeek")):
                    ctypes.windll.user32.ShowWindow(hwnd, SW_SHOWNOACTIVATE)
                self._apply_desk()
            log(f"Game {'detected: ' + self._game if self._game else 'gone'}; notch {'hidden' if self._game else 'shown'}.")
        except Exception as e:
            log(f"_on_game error: {e!r}")

    def _on_fullscreen(self, is_fullscreen):
        """전체화면 앱이 켜졌을 때의 동작(설정 fullscreenMode):
        yield 항상 위를 풀어 비켜남 / hide 완전히 숨김 / hidepeek 숨기되 미디어 키를 누르면 잠깐 표시 / show 그대로."""
        self._fullscreen = is_fullscreen
        mode = self._prefs.get("fullscreenMode")
        try:
            hwnd = self._get_hwnd()
            if not hwnd:
                return
            hidden = is_fullscreen and mode in ("hide", "hidepeek")
            yielded = is_fullscreen and mode == "yield"
            if not hidden:
                self._cancel_peek_hide()
                self._show_window(True)
            set_topmost(hwnd, not yielded)
            if hidden:
                self._show_window(False)
            log(f"Full-screen app {'detected' if is_fullscreen else 'gone'} (mode={mode}): "
                + ("hidden." if hidden else "stepping aside." if yielded else "on top."))
        except Exception as e:
            log(f"_on_fullscreen error: {e!r}")

    def _cancel_peek_hide(self):
        t, self._peek_hide_timer = self._peek_hide_timer, None
        if t is not None:
            t.cancel()

    def _peek_over_fullscreen(self):
        """hidepeek: 전체화면 중에 미디어 키를 눌렀을 때 노치를 4초 보여 준다."""
        if not (self._fullscreen and self._prefs.get("fullscreenMode") == "hidepeek"):
            return
        self._cancel_peek_hide()
        self._show_window(True)
        self._peek_hide_timer = threading.Timer(4.0, lambda: self._fullscreen and self._show_window(False))
        self._peek_hide_timer.daemon = True
        self._peek_hide_timer.start()

    # ------------------------------------------------------------------
    # 저장소 (설정, 할 일, 물 기록, 선반) — 이 PC 의 data.json 에만 저장한다
    # ------------------------------------------------------------------
    @staticmethod
    def _system_lang():
        """윈도우 표시 언어에 맞춘 처음 실행 때의 기본 언어: 한국어 'ko', 중국어 'zh'(간체 문구), 일본어 'ja', 그 밖은 'en'."""
        try:
            primary = ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF
        except Exception:
            return "en"
        return {0x12: "ko", 0x04: "zh", 0x11: "ja"}.get(primary, "en")

    def load_data(self):
        try:
            if os.path.exists(DATA_FILE) and os.path.getsize(DATA_FILE) <= DATA_MAX_BYTES:
                with open(DATA_FILE, encoding="utf-8-sig") as f:     # 메모장 등으로 저장해 BOM 이 붙어도 읽는다
                    data = json.load(f)
                if isinstance(data, dict):
                    self._migrate_monitor_numbering(data)
                    return data
            if not os.path.exists(DATA_FILE):
                return {"settings": {"lang": self._system_lang()}}        # 처음 실행: 저장된 설정이 없다
        except Exception as e:
            log(f"load_data error: {e!r}")
        return {}

    def _migrate_monitor_numbering(self, data):
        """모니터 번호의 기준이 바뀌었다: 예전에는 장치 이름 DISPLAYn 의 n(1, 2, 5 …), 지금은 윈도우 식별 번호(1, 2, 3 …).
        저장된 설정 'monitor' 가 예전 번호면 새 번호로 한 번만 옮긴다(monitorScheme = 2 로 표시). 그 모니터가 지금 없으면 주 모니터(0)."""
        try:
            st = data.get("settings")
            if not isinstance(st, dict) or st.get("monitorScheme") == 2:
                return
            try:
                old = int(st.get("monitor") or 0)
            except (TypeError, ValueError):
                old = 0
                if "monitor" in st:
                    st["monitor"] = 0        # 읽을 수 없는 값은 주 모니터
            if old > 0:
                hit = next((m for m in monitors.list_monitors() if m.get("gdi") == old), None)
                st["monitor"] = hit["number"] if hit else 0
            st["monitorScheme"] = 2
            self._write_data(data)
        except Exception as e:
            log(f"_migrate_monitor_numbering error: {e!r}")

    def _write_data(self, data):
        raw = json.dumps(data, ensure_ascii=False)
        if len(raw.encode("utf-8")) > DATA_MAX_BYTES:
            return {"status": "error", "message": "too large"}
        tmp = DATA_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(raw)
        os.replace(tmp, DATA_FILE)   # 쓰는 도중 꺼져도 기존 파일이 깨지지 않게 교체 방식으로 저장
        return {"status": "ok"}

    def save_data(self, data):
        try:
            if not isinstance(data, dict):
                return {"status": "error", "message": "data must be an object"}
            with self._data_lock:
                st = data.get("settings")
                if isinstance(st, dict):
                    st["monitorScheme"] = 2      # 노치가 보내는 저장본에는 이 표시가 없다: 지워지면 다음 실행 때 모니터 번호를 또 새 체계로 옮겨 버려 고른 모니터가 바뀔 수 있다(_migrate_monitor_numbering)
                if "launcher" not in data:
                    keep = self.load_data().get("launcher")
                    if keep is not None:
                        data["launcher"] = keep
                if "dday" not in data:
                    keep = self.load_data().get("dday")
                    if keep is not None:
                        data["dday"] = keep
                res = self._write_data(data)
            if res.get("status") == "ok":
                self._prefs.update_from_data(data)
                self._apply_prefs()
                self._sync_settings_window(data)
            return res
        except Exception as e:
            log(f"save_data error: {e!r}")
            return {"status": "error", "message": str(e)}

    # ------------------------------------------------------------------
    # 설정 (설정 창 <-> 노치 화면 <-> 파이썬)
    # ------------------------------------------------------------------
    def _apply_prefs(self):
        """파이썬 쪽에서 즉시 반영해야 하는 설정."""
        try:
            if self._buds is not None:
                self._buds.low_battery = int(self._prefs.get("budsLowPct"))
                self._buds.set_watch(bool(self._prefs.get("budsWatch")))
            if self._bt is not None:
                self._bt.set_enabled(bool(self._prefs.get("btDevices")))
                self._bt.set_airpods_scan(bool(self._prefs.get("airpodsScan")))
            self._link_sync()
            self._link_push_filter()
            self._link_push_media()
            if not (self._prefs.get("linkOn") and self._prefs.get("linkMirror")) and self._mirror_win is not None:
                self.phone_screen_stop()                              # 설정에서 화면 보기를 끄면 열려 있던 화면도 닫는다
            elif not self._prefs.get("linkMirrorControl") and self._mirror_ctl:
                self._mirror_ctl = False                              # 보는 도중에 조작을 끄면 폰도 '보기 전용'으로 바꾼다(다시 허용을 묻지 않는다: 이미 공유 중일 때만)
                if (getattr(self._mirror, "_state", None) or {}).get("state") == "running":
                    self._mirror_send({"t": "scr_start", "control": False})
            self._clipwatch.enabled = bool(self._prefs.get("clipboardOn")) and not self._tab_hidden("clip")      # 클립보드 탭이 꺼져 있으면 기록도 하지 않는다(보이지 않는 곳에서 모으지 않게)
            self._cal.set_source(self._prefs.get("calendarUrl"))
            if self._smtc is not None and smtc is not None:
                self._smtc.filter_mode = self._prefs.get("appFilterMode")
                self._smtc.filter_names = smtc.parse_filter_list(self._prefs.get("appFilterList"))
            self._apply_desk()
            if getattr(self, "_mon_key", None) is not None and abs(self._ui_scale() - getattr(self, "_ui_scale_applied", 1.0)) > 1e-6:
                threading.Thread(target=self.apply_ui_scale, daemon=True, name="ui-scale").start()
            if getattr(self, "_mon_key", None) is not None:      # 창이 이미 자리 잡은 뒤에만 (시작 중에는 on_shown 이 놓는다)
                key = monitors.monitor_key(self._target_monitor())
                if key != self._mon_key or monitors.clamp_pos(self._prefs.get("notchPos")) != getattr(self, "_pos_applied", 0):
                    threading.Thread(target=self.recenter_window, daemon=True, name="move-notch").start()
        except Exception as e:
            log(f"_apply_prefs error: {e!r}")

    # ------------------------------------------------------------------
    # 노치 본체 유리(glassNotch = full): 노치 뒤의 화면을 찍어 화면(HTML)에 넘긴다 (deskcap.py)
    # ------------------------------------------------------------------
    def _desk_rect(self):
        """노치 뒤 화면에서 찍을 영역(물리 픽셀): 창 가운데 위쪽의 1040x210(CSS px = 창 너비. 탭 아이콘 독이 열린 가장 큰 노치와, 옆으로 나온 폭이 넓은 보조 노치까지 덮는다). 창이 숨겨져 있으면 None."""
        hwnd = self._get_hwnd()
        if not hwnd or not ctypes.windll.user32.IsWindowVisible(hwnd):
            return None
        rc = wintypes.RECT()
        ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rc))
        dpr = self._notch_scale()
        w, h = int(1040 * dpr), int(210 * dpr)
        return int((rc.left + rc.right) / 2 - w / 2), rc.top, w, h

    def _desk_push(self, url):
        if webview.windows:
            webview.windows[0].evaluate_js(f"setDesk({json.dumps(url)})")

    def _apply_desk(self):
        """설정(glassNotch)에 따라 뒤 화면 캡처를 켜고 끈다. 창이 아직 없으면(시작 중) on_shown 이 다시 부른다."""
        try:
            want = self._prefs.get("glassNotch") == "full"
            self._desk.enable(want)
            self._desk.set_visible(self._prefs.get("captureNotch") == "show")
            if not want and webview.windows:
                try:
                    webview.windows[0].evaluate_js("setDesk(null)")
                except Exception:
                    pass
        except Exception as e:
            log(f"_apply_desk error: {e!r}")

    def settings_get(self):
        """설정 창이 처음 열릴 때: 저장된 값 + 시작 프로그램 등록 상태 + 정보."""
        return {"data": self.load_data(), "autostart": prefs.autostart_enabled(), "about": self.get_about(),
                "monitors": self.get_monitors(), "plugins": self.plugins_catalog(),
                "launcher": self.launcher_get()["items"], "presets": self.launcher_presets()}

    def settings_patch(self, patch):
        """설정 창에서 바꾼 값을 저장하고 노치 화면에 알린다. patch: {"settings": {...}, "pomo": {...}, "water": {...}}"""
        try:
            patch = prefs.clean_patch(patch)
            if not patch:
                return {"status": "error", "message": "nothing to apply"}
            with self._data_lock:
                data = prefs.deep_merge(self.load_data(), patch)
                res = self._write_data(data)
            if res.get("status") == "ok":
                self._prefs.update_from_data(data)
                self._apply_prefs()
                self._push_event({"type": "prefs", "patch": patch})
                try:   # 다음 폴링(최대 200ms)을 기다리지 않고 노치가 바로 가져가게 한다 (설정을 바꾸고 노치에 반영되기까지 한 박자 느리던 것)
                    if webview.windows:
                        webview.windows[0].evaluate_js("pollNow()")
                except Exception:
                    pass
                if "lang" in (patch.get("settings") or {}) and self._settings_win is not None:      # 열려 있는 설정 창의 제목(작업 표시줄)도 새 언어로
                    try:
                        self._settings_win.set_title(self._settings_title())
                    except Exception as e:
                        log(f"settings title update failed: {e!r}")
            return res
        except Exception as e:
            log(f"settings_patch error: {e!r}")
            return {"status": "error", "message": str(e)}

    def settings_reset(self):
        """모든 설정을 기본값으로 (할 일/선반/물 기록은 그대로). 설정 키만 지우면 화면이 기본값으로 채운다."""
        try:
            with self._data_lock:
                data = self.load_data()
                data["settings"] = {"monitorScheme": 2}          # 설정 값은 비우되 '새 모니터 번호 체계' 표시는 남긴다
                for sec, keys in (("pomo", ("focusMin", "breakMin")),
                                  ("water", ("enabled", "bottleMl", "goalMl", "startHour", "endHour", "intervalMin"))):
                    if isinstance(data.get(sec), dict):
                        for k in keys:
                            data[sec].pop(k, None)
                res = self._write_data(data)
            if res.get("status") == "ok":
                self._prefs.update_from_data(data)
                self._apply_prefs()
                self._push_event({"type": "prefs_reset"})
            return res
        except Exception as e:
            log(f"settings_reset error: {e!r}")
            return {"status": "error", "message": str(e)}

    def test_notify(self):
        """설정 창의 '테스트 알림': 노치에 샘플 알림을 띄운다."""
        self._push_event({"type": "test_notify"})
        return {"status": "ok"}

    # ---- 마스터 볼륨 (노치의 볼륨 팝오버·Ctrl+휠). 앱별 볼륨 믹서 화면은 시스템 탭이 대신해서 없앴다
    def mixer_get(self):
        return {"master": audiomix.master_get()}

    def mixer_step(self, delta):
        """마스터 볼륨을 delta(예: 0.02)만큼 바꾸고 새 값(0~1)을 돌려준다. Ctrl+휠용."""
        try:
            return audiomix.master_step(float(delta))
        except Exception:
            return None

    def mixer_set(self, target, volume=None, muted=None):
        """target 은 'master'(마스터 볼륨)만 받는다."""
        try:
            ok = audiomix.master_set(volume, muted) if target == "master" else False
            return {"status": "ok" if ok else "error"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    # ------------------------------------------------------------------
    # 시스템 탭 / 전원 탭 (sysctl.py): 배터리·밝기·볼륨·마이크·Wi-Fi·블루투스 읽기와 바꾸기, 전원 동작
    # ------------------------------------------------------------------
    def sys_get(self):
        """시스템 탭에 보여 줄 값(없는 항목은 None). 읽기만 한다."""
        try:
            return sysctl.snapshot()
        except Exception as e:
            log(f"sys_get failed: {e!r}")
            return {}

    def sys_do(self, action, value=None):
        """action: volume(0~100) / mute / brightness(0~100) / mic / wifi(true|false) / bluetooth(true|false). 바꾼 뒤의 값을 돌려준다."""
        try:
            ok = False
            if action == "volume":
                ok = sysctl.volume_set(value)
            elif action == "mute":
                ok = sysctl.volume_toggle_mute() is not None
            elif action == "brightness":
                ok = sysctl.brightness_set(value)
            elif action == "mic":
                ok = sysctl.mic_toggle_mute() is not None
            elif action in ("wifi", "bluetooth"):
                ok = sysctl.radio_set(action, bool(value))
            else:
                return {"status": "error", "message": "unknown action"}
            radios = action in ("wifi", "bluetooth")
            state = sysctl.snapshot(radios=radios)
            if not radios:
                state.pop("wifi", None)          # 무선 장치는 다시 읽지 않았다: null 로 보내면 화면이 있던 값을 지운 줄 안다
                state.pop("bluetooth", None)
            return {"status": "ok" if ok else "error", "state": state}
        except Exception as e:
            log(f"sys_do {action} failed: {e!r}")
            return {"status": "error", "message": str(e)}

    def perf_get(self):
        """성능 탭/작은 노치: {cpu: 0~100|None, mem: {percent, used_gb, total_gb}|None, net: {down, up}(바이트/초)|None, gpu: 0~100|None}. 읽기만 한다."""
        try:
            if self._perf is None:
                self._perf = perf.PerfSampler()
            return self._perf.sample()
        except Exception as e:
            log(f"perf_get failed: {e!r}")
            return {"cpu": None, "mem": None, "net": None, "gpu": None}

    # ---- D-day: 직접 만든 항목과 일정에서 별로 표시한 항목(data.json 의 dday). 일정 탭에 보인다
    def dday_get(self):
        """{items: [{id,name,date,done,cal}]}"""
        try:
            return {"items": prefs.clean_dday((self.load_data().get("dday") or {}).get("items"))}
        except Exception as e:
            log(f"dday_get failed: {e!r}")
            return {"items": []}

    def dday_set(self, items):
        """설정 창에서 편집한 D-day 목록 전체를 저장한다. 저장된(검증된) 목록을 돌려준다."""
        clean = prefs.clean_dday(items)
        try:
            with self._data_lock:
                data = self.load_data()
                data["dday"] = {"items": clean}
                res = self._write_data(data)
            if res.get("status") != "ok":
                return res
            self._push_event({"type": "dday"})
            return {"status": "ok", "items": clean}
        except Exception as e:
            log(f"dday_set failed: {e!r}")
            return {"status": "error", "message": str(e)}

    def weather_search(self, query):
        """설정 창의 도시 검색(사용자가 '검색'을 눌렀을 때만): 입력한 이름을 Open-Meteo 지오코딩으로 보내 후보를 돌려준다."""
        try:
            return {"status": "ok", "items": weather.search_city(query, str(self._prefs.get("lang") or "en"))}
        except Exception as e:
            log(f"weather_search failed: {type(e).__name__}")
            return {"status": "error", "items": []}

    def weather_get(self, force=False):
        """날씨 탭/작은 노치. '내 위치의 날씨 보기'(기본 켜짐)면 윈도우 위치 서비스로 현재 위치를 읽어 그 날씨를, 위치를 읽지 못하면 설정에서 고른 도시를 쓴다.
        위치도 도시도 없으면 아무것도 보내지 않는다. 15분 캐시. 미세먼지는 에어코리아 인증키가 있으면 한국 측정소의 실제 값, 아니면 모델 값."""
        try:
            here = bool(self._prefs.get("weatherLocate"))
            loc_status, where = None, "city"
            lat = lon = None
            if here:
                loc = self._locator.get(bool(force))
                loc_status = loc.get("status")
                if loc_status == "ok" and weather.clean_coords(loc.get("lat"), loc.get("lon")):
                    lat, lon, where = loc["lat"], loc["lon"], "here"
            if where != "here":
                lat, lon = self._prefs.get("weatherLat"), self._prefs.get("weatherLon")
                if not weather.clean_coords(lat, lon):
                    return {"status": "noloc" if here else "nocity", "loc": loc_status}
            key = str(self._keys.get("airkorea") or "").strip()
            oaq = str(self._keys.get("openaq") or "").strip()
            w = self._weather.get(lat, lon, self._prefs.get("weatherUnit"), bool(force), key, oaq)
            if w is None:
                return {"status": "error", "loc": loc_status}
            if where == "here":
                place = weather.reverse_place(lat, lon, self._prefs.get("lang"))
                city = str((place or {}).get("label") or "")[:80]
            else:
                city = str(self._prefs.get("weatherCity") or "")[:60]
            return {"status": "ok", "weather": w, "stale": bool(self._weather.error), "city": city, "where": where, "loc": loc_status}
        except Exception as e:
            log(f"weather_get failed: {type(e).__name__}")
            return {"status": "error"}

    def location_check(self, force=False):
        """설정 창: 윈도우 위치 서비스를 쓸 수 있는지만 확인한다 -> {status: ok|denied|unavailable|timeout|error}. 서버로는 아무것도 보내지 않고 좌표도 돌려주지 않는다."""
        try:
            return {"status": str(self._locator.get(bool(force)).get("status") or "error")}
        except Exception:
            return {"status": "error"}

    def wifi_scan(self):
        """주변 Wi-Fi 목록(노치 선택창). 읽기만 한다(약 1초)."""
        try:
            return {"status": "ok", "items": sysctl.wifi_list(rescan=True), "current": sysctl.wifi_name()}
        except Exception as e:
            log(f"wifi_scan failed: {e!r}")
            return {"status": "error", "items": []}

    def wifi_connect(self, ssid, password=None):
        """고른 Wi-Fi 에 연결한다. 비밀번호는 윈도우에만 넘기고 기록하지 않는다."""
        try:
            r = sysctl.wifi_connect(str(ssid or ""), password if isinstance(password, str) and password else None)
            log(f"Wi-Fi connect requested: {'ok' if r.get('ok') else 'failed (' + str(r.get('error')) + ')'}")      # 이름·비밀번호는 기록하지 않는다
            return {"status": "ok" if r.get("ok") else "error", "error": r.get("error", "")}
        except Exception as e:
            log(f"wifi_connect failed: {type(e).__name__}")
            return {"status": "error", "error": "connect"}

    def bt_devices(self):
        """짝지은 블루투스 기기 목록(노치 선택창). 읽기만 한다."""
        try:
            return {"status": "ok", "items": sysctl.bt_list()}
        except Exception as e:
            log(f"bt_devices failed: {e!r}")
            return {"status": "error", "items": []}

    def bt_connect(self, address, on):
        """짝지은 기기를 연결(on) 또는 해제한다."""
        try:
            ok = sysctl.bt_set(str(address or ""), bool(on))
            log(f"Bluetooth {'connect' if on else 'disconnect'} requested: {'ok' if ok else 'failed'}")
            return {"status": "ok" if ok else "error"}
        except Exception as e:
            log(f"bt_connect failed: {e!r}")
            return {"status": "error"}

    def power_do(self, kind, confirmed=False):
        """전원 동작. 로그아웃·다시 시작·종료는 화면에서 한 번 더 눌러 확인한 요청(confirmed=True)만 실행한다."""
        try:
            if kind not in sysctl.POWER_KINDS:
                return {"status": "error", "message": "unknown power action"}
            if kind in sysctl.CONFIRM_KINDS and confirmed is not True:
                return {"status": "error", "message": "needs confirmation"}
            log(f"Power action: {kind}")
            return {"status": "ok" if sysctl.power(kind) else "error"}
        except Exception as e:
            log(f"power_do {kind} failed: {e!r}")
            return {"status": "error", "message": str(e)}

    def set_source(self, source_id):
        """노치에서 재생 소스를 직접 고른다. 'auto' 면 자동 선택으로 되돌린다."""
        sid = source_id if source_id in ("cider", "smtc", "phone") else None
        with self._lock:
            have = {x["id"] for x in self._last_state.get("sources", [])}
        if sid and sid not in have:
            return {"status": "error", "message": "that source has nothing to show"}
        self._forced_source = sid
        log(f"Media source chosen by user: {sid or 'auto'}")
        return {"status": "ok", "source": sid or "auto"}

    def _js(self, code):
        try:
            if webview.windows:
                webview.windows[0].evaluate_js(code)
        except Exception as e:
            log(f"evaluate_js failed: {e!r}")

    def open_notification_center(self):
        """보조 노치의 알림 동그라미를 눌렀을 때: 윈도우 알림 센터를 연다(윈도우 11: Win+N, 10: Win+A). 이미 열려 있으면 그대로 둔다."""
        try:
            if self._winnotif is not None:
                self._winnotif.acknowledge()
            opened = winnotif.open_center() if winnotif is not None else False
            # 알림 센터는 윈도우가 마우스·앞 창·주 모니터 중 어느 쪽에 열지 정하므로 노치가 있는 모니터와 다를 수 있다: 방금 열었든 이미 열려 있었든 노치가 있는 모니터로 옮긴다
            mon = self._target_monitor() if winnotif is not None else None
            if mon:
                threading.Thread(target=winnotif.move_center_to, args=(mon["number"], 2.5, log), daemon=True, name="center-move").start()
            return {"status": "ok", "opened": bool(opened)}
        except Exception as e:
            log(f"open_notification_center error: {e!r}")
            return {"status": "error", "message": str(e)}

    AUTO_RECORD_SECONDS = 1800             # 엔비디아 녹화 단축키(Alt+F9)로 켠 캡처 모드의 안전 한도

    def capture_mode(self, seconds=15):
        """리퀴드 글래스 '전체'는 노치 창을 화면 캡처에서 빼 둔다(자기 자신을 비추지 않으려고). 스크린샷/녹화가 시작되면(capturewatch)
        seconds 초 동안 뒤 화면을 얼려 두고 노치가 캡처에 보이게 한 뒤, 자동으로 원래대로 돌아간다. 조용히(알림 없이) 동작한다.
        (예전의 수동 캡처 모드 단축키와 안내는 자동 캡처가 같은 일을 해서 없앴다.)"""
        try:
            on = self._desk.freeze(float(seconds))
            return {"status": "ok", "active": bool(on)}
        except Exception as e:
            log(f"capture_mode error: {e!r}")
            return {"status": "error", "message": str(e)}

    _rec_hold = False

    def _capture_auto(self, seconds, why):
        """capturewatch 가 부르는 자동 캡처 모드. 엔비디아 녹화 단축키(Alt+F9)는 눌러 시작/다시 눌러 중지라서, 켜 두었다가 다시 누르면 끈다."""
        if why == "alt+f9":
            if self._rec_hold and self._desk.frozen:
                self._rec_hold = False
                self._desk.thaw()
            else:
                self._rec_hold = bool(self._desk.freeze(self.AUTO_RECORD_SECONDS))
            return
        self.capture_mode(seconds)

    # ---- 클립보드 기록
    def _tab_hidden(self, tab):
        """설정 › 모양·동작 › 탭 구성에서 이 탭을 껐는가(tabHidden 은 쉼표로 구분한 탭 id)."""
        return tab in [x.strip() for x in str(self._prefs.get("tabHidden") or "").split(",")]

    def clip_list(self):
        return {"enabled": bool(self._prefs.get("clipboardOn")) and not self._tab_hidden("clip"), "items": self._clip.list()}

    def clip_use(self, item_id):
        """기록의 항목을 다시 클립보드에 넣는다(맨 앞으로 올라온다)."""
        it = self._clip.get(int(item_id))
        if not it:
            return {"status": "error", "message": "gone"}
        self._clipwatch.ignore_next_change()
        ok = clipwatch.write_text(it["text"])
        if ok:
            self._clip.add(it["text"])
        return {"status": "ok" if ok else "error"}

    def clip_delete(self, item_id):
        return {"status": "ok" if self._clip.delete(int(item_id)) else "error"}

    def clip_clear(self):
        self._clip.clear()
        return {"status": "ok"}

    # ---- 캘린더 (.ics)
    def _calendar_worker(self):
        """주소를 주기적으로 다시 읽고, 일정 시작 N분 전에 알림 이벤트를 낸다."""
        while self._running:
            try:
                if self._prefs.get("calendarUrl"):
                    self._cal.refresh()
                    self._calendar_remind()
            except Exception as e:
                log(f"calendar worker error: {e!r}")
            time.sleep(20)

    def _calendar_remind(self):
        lead = int(self._prefs.get("calendarRemindMin")) * 60
        now = time.time()
        for ev in self._cal.events(days=1):
            if ev["allDay"]:
                continue
            key = (ev["title"], ev["start"])
            if key in self._cal_notified:
                continue
            if 0 <= ev["start"] - now <= lead:
                self._cal_notified.add(key)
                self._push_event({"type": "agenda", "title": ev["title"], "start": ev["start"], "location": ev["location"]})
        if len(self._cal_notified) > 500:
            self._cal_notified = {k for k in self._cal_notified if k[1] > now - 86400}

    def calendar_test(self):
        """설정 창의 '지금 불러오기': 동기적으로 읽어 보고 결과(일정 개수/오류)를 돌려준다."""
        if not self._prefs.get("calendarUrl"):
            return {"status": "error", "message": "no address"}
        self._cal.set_source(self._prefs.get("calendarUrl"))
        self._cal.refresh(force=True)
        if self._cal.error:
            return {"status": "error", "message": self._cal.error}
        return {"status": "ok", "count": len(self._cal.events(days=7))}

    def calendar_get(self, force=False):
        """화면용: {configured, error, events:[{title,start,end,allDay,location}]} (앞으로 7일)."""
        url = self._prefs.get("calendarUrl")
        if not url:
            return {"configured": False, "error": "", "events": []}
        if force:
            threading.Thread(target=lambda: self._cal.refresh(force=True), daemon=True, name="calendar-refresh").start()
        return {"configured": True, "error": self._cal.error, "events": self._cal.events(days=7)[:40]}

    def calendar_range(self, since_ts, days):
        """월/주 보기용: since_ts(epoch 초)부터 days 일 사이의 일정 (최대 600개). 값이 이상하면 이번 달 정도로 보정한다."""
        url = self._prefs.get("calendarUrl")
        if not url:
            return {"configured": False, "error": "", "events": []}
        try:
            since = calendar_ics.datetime.fromtimestamp(float(since_ts), calendar_ics.timezone.utc)
            n = max(1, min(62, int(days)))
        except Exception:
            since, n = calendar_ics.datetime.now(calendar_ics.timezone.utc), 7
        return {"configured": True, "error": self._cal.error, "events": self._cal.events(days=n, since=since)[:600]}

    # ---- 설정 내보내기 / 가져오기 (할 일·선반·물 기록 같은 개인 데이터는 포함하지 않는다)
    EXPORT_MARK = "dalu-settings"

    def export_settings(self):
        w = self._settings_win
        if w is None:
            return {"status": "error", "message": "no window"}
        data = self.load_data()
        exported = {k: v for k, v in (data.get("settings") or {}).items() if k != "calendarUrl"}     # 비공개 캘린더 주소는 내보내지 않는다
        payload = {"format": self.EXPORT_MARK, "version": 1, "settings": exported,
                   "pomo": {k: v for k, v in (data.get("pomo") or {}).items() if k in ("focusMin", "breakMin")},
                   "water": {k: v for k, v in (data.get("water") or {}).items() if k in ("enabled", "bottleMl", "goalMl", "startHour", "endHour", "intervalMin")}}
        try:
            res = w.create_file_dialog(webview.SAVE_DIALOG, save_filename="dalu-settings.json", file_types=("JSON (*.json)",))
            if not res:
                return {"status": "cancelled"}
            path = res if isinstance(res, str) else res[0]
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            return {"status": "ok", "path": path}
        except Exception as e:
            log(f"export_settings failed: {e!r}")
            return {"status": "error", "message": str(e)}

    def import_settings(self):
        w = self._settings_win
        if w is None:
            return {"status": "error", "message": "no window"}
        try:
            res = w.create_file_dialog(webview.OPEN_DIALOG, allow_multiple=False, file_types=("JSON (*.json)",))
            if not res:
                return {"status": "cancelled"}
            path = res if isinstance(res, str) else res[0]
            if os.path.getsize(path) > 256 * 1024:
                return {"status": "error", "message": "file too large"}
            with open(path, encoding="utf-8") as f:
                payload = json.load(f)
            return self.apply_imported(payload)
        except Exception as e:
            log(f"import_settings failed: {e!r}")
            return {"status": "error", "message": str(e)}

    def apply_imported(self, payload):
        """파일에서 읽은 설정을 검증해 적용한다 (clean_patch 가 허용한 섹션/값 형태만). 가져온 키 개수를 돌려준다."""
        if not isinstance(payload, dict) or payload.get("format") != self.EXPORT_MARK:
            return {"status": "error", "message": "not a settings file"}
        patch = prefs.clean_patch({k: payload.get(k) for k in ("settings", "pomo", "water")})
        if not patch:
            return {"status": "error", "message": "nothing to import"}
        res = self.settings_patch(patch)
        if res.get("status") == "ok":
            self._push_event({"type": "prefs_reset"})            # 화면이 저장된 값을 통째로 다시 읽는다
            res["count"] = sum(len(v) for v in patch.values())
        return res

    # ---- 사용자 바로가기 (노치의 "바로가기" 페이지)
    def launcher_get(self):
        return {"items": prefs.clean_launcher((self.load_data().get("launcher") or {}).get("items"))}

    def launcher_set(self, items):
        """설정 창에서 편집한 바로가기 전체를 저장한다. 저장된(검증된) 목록을 돌려준다."""
        clean = prefs.clean_launcher(items)
        try:
            with self._data_lock:
                data = self.load_data()
                data["launcher"] = {"items": clean}
                res = self._write_data(data)
            if res.get("status") != "ok":
                return res
            self._push_event({"type": "launcher", "items": clean})
            return {"status": "ok", "items": clean}
        except Exception as e:
            log(f"launcher_set failed: {e!r}")
            return {"status": "error", "message": str(e)}

    def launcher_run(self, item_id):
        item = next((i for i in self.launcher_get()["items"] if i["id"] == item_id), None)
        if item is None:
            return {"status": "error", "message": "unknown shortcut"}
        r = plugins.run_program(item["target"], item["args"]) if item["args"] else plugins.open_target(item["target"])
        if r.get("status") != "ok":
            log(f"launcher_run {item['name']!r} failed: {r.get('message')}")
        return r

    def launcher_presets(self):
        """설정 창의 '자주 쓰는 것 추가' 목록. 이름은 지금 화면 언어로 돌려준다(고르면 그 이름으로 바로가기에 저장된다)."""
        lang = self._prefs.get("lang")
        names = {   # 앱 id -> (ko, en, zh, ja)
            "notepad.exe": ("메모장", "Notepad", "记事本", "メモ帳"), "calc.exe": ("계산기", "Calculator", "计算器", "電卓"),
            "explorer.exe": ("탐색기", "File Explorer", "文件资源管理器", "エクスプローラー"), "mspaint.exe": ("그림판", "Paint", "画图", "ペイント"),
            "taskmgr.exe": ("작업 관리자", "Task Manager", "任务管理器", "タスクマネージャー"), "wt.exe": ("터미널", "Terminal", "终端", "ターミナル"),
            "ms-settings:": ("윈도우 설정", "Windows Settings", "Windows 设置", "Windows の設定"), "ms-screenclip:": ("캡처 도구", "Snipping Tool", "截图工具", "切り取り"),
        }
        idx = {"ko": 0, "en": 1, "zh": 2, "ja": 3}.get(lang, 1)
        return [{"name": names[t][idx], "icon": i, "target": t} for i, t in (
            ("note", "notepad.exe"), ("calc", "calc.exe"), ("folder", "explorer.exe"), ("brush", "mspaint.exe"),
            ("gauge", "taskmgr.exe"), ("terminal", "wt.exe"), ("gear", "ms-settings:"), ("crop", "ms-screenclip:"))]

    def pick_launcher_target(self):
        """설정 창의 '찾아보기': 프로그램/파일을 고른다. 고른 경로를 돌려준다."""
        w = self._settings_win
        if w is None:
            return {"status": "error", "message": "no window"}
        try:
            res = w.create_file_dialog(webview.OPEN_DIALOG, allow_multiple=False)
            if not res:
                return {"status": "cancelled"}
            return {"status": "ok", "path": res if isinstance(res, str) else res[0]}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    # ---- 플러그인
    def plugins_list(self):
        """켜 둔 플러그인과 그 동작 목록 (노치의 플러그인 페이지용)."""
        return [p.summary() for p in self._plugins.enabled(self._prefs.get("pluginsEnabled"))]

    def plugins_catalog(self):
        """설정 창용: 모든 플러그인과 켜짐 여부."""
        on = {x.strip() for x in str(self._prefs.get("pluginsEnabled")).split(",") if x.strip()}
        return [dict(p.summary(), enabled=p.id in on) for p in self._plugins.plugins]

    def plugin_status(self, plugin_id):
        return self._plugins.status(plugin_id, self._plugin_ctx)

    def plugin_states(self, plugin_id):
        """플러그인 버튼들의 지금 상태 (반복이 전체/한 곡인지, 음소거 중인지 ...). 켜 둔 플러그인만."""
        if plugin_id not in {x.strip() for x in str(self._prefs.get("pluginsEnabled")).split(",") if x.strip()}:
            return {}
        return self._plugins.states(plugin_id, self._plugin_ctx)

    def plugin_run(self, plugin_id, action_id):
        if plugin_id not in {x.strip() for x in str(self._prefs.get("pluginsEnabled")).split(",") if x.strip()}:
            return {"status": "error", "message": "plugin is off"}
        r = self._plugins.run(plugin_id, action_id, self._plugin_ctx)
        if r.get("status") != "ok":
            log(f"plugin {plugin_id}/{action_id} failed: {r.get('message')}")
        return r

    def plugin_install_example(self):
        """설정 창의 '예제 설치': 플러그인 폴더에 예제 JSON 을 만들고 다시 읽는다(이미 있으면 그대로)."""
        try:
            path = plugins.install_example(os.path.join(DATA_DIR, "plugins"))
            self._plugins.reload()
            return {"status": "ok", "installed": bool(path)}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def plugins_reload(self):
        self._plugins.reload()
        return {"status": "ok", "count": len(self._plugins.plugins)}

    def open_plugin_folder(self):
        try:
            os.makedirs(os.path.join(DATA_DIR, "plugins"), exist_ok=True)
            os.startfile(os.path.join(DATA_DIR, "plugins"))
            return {"status": "ok"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def dnd_set(self, enabled):
        """집중 시간 동안 윈도우 방해 금지를 켜고 끈다. 우리가 켠 것만 되돌리고, 이미 켜져 있던 방해 금지는 건드리지 않는다."""
        try:
            changed = dnd.enable(DND_STATE_FILE) if enabled else dnd.disable(DND_STATE_FILE)
            log(f"Do Not Disturb {'on' if enabled else 'off'} (changed={changed}).")
            return {"status": "ok", "on": dnd.is_on(), "changed": changed}
        except Exception as e:
            log(f"dnd_set failed: {e!r}")
            return {"status": "error", "message": str(e)}

    def get_autostart(self):
        return prefs.autostart_enabled()

    def set_autostart(self, enabled):
        ok = prefs.set_autostart(bool(enabled), os.path.join(BASE_DIR, "dalu.py"))
        log(f"autostart {'enabled' if enabled else 'disabled'}: {'ok' if ok else 'FAILED'}")
        return {"status": "ok" if ok else "error", "enabled": prefs.autostart_enabled()}

    def get_about(self):
        try:
            wv = getattr(webview, "__version__", "") or ""
        except Exception:
            wv = ""
        return {"version": APP_VERSION, "python": sys.version.split()[0], "webview": wv, "dataDir": ISLAND_DIR,
                "logFile": LOG_FILE, "smtc": smtc is not None, "buds": buds is not None,
                "viz": audiolevels is not None, "update": self._update.snapshot() if self._update else None}

    def check_update(self):
        """설정 › 정보 › '지금 확인'. 새 버전이면 {'status':'new','version'}, 이미 최신이면 'latest', 못 읽으면 'error'."""
        if self._update is None:
            return {"status": "error"}
        try:
            return self._update.check(announce=False)
        except Exception as e:
            log(f"check_update failed: {e!r}")
            return {"status": "error"}

    def start_update(self):
        """설정 › 정보 › '지금 업데이트'(사용자가 눌렀을 때만): 새 설치 파일을 받아 해시·크기를 확인한 뒤 조용히 설치한다.
        반환: started | busy | none(받을 파일 정보가 없음: 화면이 다운로드 페이지를 연다) | error"""
        try:
            return self._updater.start() if self._updater else {"status": "none"}
        except Exception as e:
            log(f"start_update failed: {e!r}")
            return {"status": "error"}

    def update_status(self):
        try:
            return self._updater.status() if self._updater else {"state": "idle", "percent": 0, "error": ""}
        except Exception:
            return {"state": "idle", "percent": 0, "error": ""}

    def open_update_page(self):
        """새 버전 다운로드 페이지를 기본 브라우저로 연다. 주소는 화면이 아니라 여기서 정한다(허용된 주소만)."""
        try:
            import webbrowser
            url = self._update.url() if self._update else "https://flirty-bananamilk.itch.io/dalu"
            webbrowser.open(url)
            return {"status": "ok"}
        except Exception as e:
            log(f"open_update_page failed: {e!r}")
            return {"status": "error"}

    def clear_lyrics_cache(self):
        """외부 가사 캐시(찾은 가사와 '없음' 결과)를 지운다. 지운 개수를 돌려준다."""
        n = 0
        try:
            d = lyric_providers.CACHE_DIR if lyric_providers else ""
            if d and os.path.isdir(d):
                for fn in os.listdir(d):
                    if fn.endswith(".json"):
                        try:
                            os.remove(os.path.join(d, fn))
                            n += 1
                        except OSError:
                            pass
        except Exception as e:
            log(f"clear_lyrics_cache error: {e!r}")
        return {"status": "ok", "removed": n}

    def open_folder(self, kind="data"):
        try:
            if kind == "log" and os.path.exists(LOG_FILE):
                subprocess.Popen(["explorer", "/select,", LOG_FILE])
            else:
                os.startfile(ISLAND_DIR)
            return {"status": "ok"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    # ---- 설정 창
    def open_settings(self, page=None):
        """설정 창을 연다 (이미 열려 있으면 앞으로 가져온다)."""
        with self._settings_lock:
            w = self._settings_win
            if w is not None and w in webview.windows:
                try:
                    w.restore()
                    w.show()
                    if page:
                        w.evaluate_js(f"openPage({json.dumps(str(page))})")
                except Exception as e:
                    log(f"settings window focus failed: {e!r}")
                return {"status": "ok"}
            try:
                x, y = self._settings_origin()
                url = Path(BASE_DIR, "settings.html").as_uri() + (f"#{page}" if page else "")
                w = webview.create_window(self._settings_title(), url=url, js_api=self, width=SETTINGS_W, height=SETTINGS_H, x=x, y=y,
                                          frameless=True, transparent=True, on_top=False, min_size=(760, 520),
                                          easy_drag=False)   # 창 아무 데나 눌러 끄는 기본 동작을 끈다: 슬라이더/버튼/입력창을 누르고 끌 때 창이 딸려 움직였다
                w.events.shown += lambda: self._place_settings(w, x, y)
                w.events.shown += lambda: self._set_window_icon(w)      # 작업 표시줄에 파이썬 로고 대신 Dalu 아이콘
                w.events.closed += self._on_settings_closed
                self._settings_win = w
                log("Settings window opened.")
                return {"status": "ok"}
            except Exception as e:
                log(f"open_settings failed: {e!r}")
                return {"status": "error", "message": str(e)}

    def _settings_title(self):
        """설정 창 제목(작업 표시줄 미리보기에 보인다): 언어별 'Dalu 설정'."""
        return {"ko": "Dalu 설정", "zh": "Dalu 设置", "ja": "Dalu 設定"}.get(self._prefs.get("lang"), "Dalu Settings")

    def _set_window_icon(self, w):
        """창의 작업 표시줄·제목 아이콘을 Dalu 앱 아이콘으로 한다(기본은 pythonw 의 파이썬 로고). .ico 는 처음 한 번만 만든다."""
        try:
            path = ensure_icon()
            if not path:
                return
            from System import Action
            from System.Drawing import Icon
            form = w.native
            ico = Icon(path)
            form.Invoke(Action(lambda: setattr(form, "Icon", ico)))
        except Exception as e:
            log(f"_set_window_icon error: {e!r}")

    def _settings_origin(self):
        """설정 창의 초기 위치(논리 좌표): 노치가 있는 모니터의 가운데."""
        scale = self._get_scale()
        mon = self._target_monitor()
        if mon:
            px = mon["left"] + (mon["width"] - SETTINGS_W * scale) / 2
            py = mon["top"] + (mon["height"] - SETTINGS_H * scale) / 2
            return int(px / scale), int(py / scale)
        scr = self._primary_screen()
        return max(0, (scr.width - SETTINGS_W) // 2), max(0, (scr.height - SETTINGS_H) // 2)

    def _place_settings(self, w, x, y):
        """프레임 없는 창이 요청보다 작게 만들어지는 문제(DPI)를 바로잡는다 (노치 창과 같은 처리)."""
        try:
            time.sleep(0.15)
            hwnd = int(w.native.Handle.ToInt64())
            scale = self._get_scale()
            mon = self._target_monitor()
            w_phys, h_phys = int(SETTINGS_W * scale), int(SETTINGS_H * scale)
            if mon:
                px = mon["left"] + (mon["width"] - w_phys) // 2
                py = mon["top"] + (mon["height"] - h_phys) // 2
            else:
                px, py = int(x * scale), int(y * scale)
            ctypes.windll.user32.SetWindowPos(hwnd, 0, px, py, w_phys, h_phys, SWP_NOZORDER)
        except Exception as e:
            log(f"_place_settings error: {e!r}")

    def _on_settings_closed(self):
        with self._settings_lock:
            self._settings_win = None
        log("Settings window closed.")

    def settings_close(self):
        w = self._settings_win
        if w is not None:
            try:
                w.destroy()
            except Exception as e:
                log(f"settings_close error: {e!r}")
        return {"status": "ok"}

    def settings_minimize(self):
        w = self._settings_win
        if w is not None:
            try:
                w.minimize()
            except Exception as e:
                log(f"settings_minimize error: {e!r}")
        return {"status": "ok"}

    def _sync_settings_window(self, data):
        """노치 화면에서 바꾼 값(우클릭 메뉴, 포모도로 시간 등)을 열려 있는 설정 창에도 반영한다."""
        w = self._settings_win
        if w is None:
            return
        try:
            slim = {k: data.get(k) for k in ("settings", "pomo", "water") if k in data}
            w.evaluate_js(f"onExternalData({json.dumps(slim, ensure_ascii=False)})")
        except Exception:
            pass

    def restart_app(self):
        """새 프로세스를 띄우고 지금 것을 끝낸다 (새 프로세스는 단일 인스턴스 잠금이 풀릴 때까지 기다린다)."""
        try:
            cmd = prefs.launch_command(os.path.join(BASE_DIR, "dalu.py"))
            subprocess.Popen(cmd, cwd=BASE_DIR, creationflags=0x00000008 | 0x00000200, close_fds=True)   # DETACHED | NEW_GROUP
            log("restart_app: new process spawned")
        except Exception as e:
            log(f"restart_app failed: {e!r}")
            return {"status": "error", "message": str(e)}
        self.close_app()
        return {"status": "ok"}

    # ------------------------------------------------------------------
    # 파일 선반
    # ------------------------------------------------------------------
    def file_info(self, paths):
        out = []
        for p in paths or []:
            try:
                st = os.stat(p)
                out.append({"path": p, "name": os.path.basename(p.rstrip("\\/")) or p,
                            "size": 0 if os.path.isdir(p) else st.st_size,
                            "isDir": os.path.isdir(p), "exists": True})
            except OSError:
                out.append({"path": p, "name": os.path.basename(str(p)), "size": 0, "isDir": False, "exists": False})
        return out

    def get_thumbs(self, paths, size=96):
        """이미지 파일의 작은 썸네일(JPEG data URI). 원본(수 MB~수십 MB)을 <img> 로 직접 쓰면 화면 스레드에서
        통째로 디코딩해 끊기므로, 여기서 축소해(JPEG 는 축소 디코딩이라 빠르다) 캐시한다."""
        out = {}
        for p in paths or []:
            try:
                uri = self._thumb_for(p, max(32, min(256, int(size))))
                if uri:
                    out[p] = uri
            except Exception as e:
                log(f"thumb error for {p!r}: {e!r}")
        return out

    def _thumb_for(self, path, size):
        if os.path.splitext(path)[1].lower() not in THUMB_EXTS:
            return None
        st = os.stat(path)
        if st.st_size > THUMB_MAX_SOURCE:
            return None
        key = hashlib.sha1(f"{path}|{st.st_mtime_ns}|{st.st_size}|{size}".encode("utf-8")).hexdigest()
        cache = os.path.join(THUMB_DIR, key + ".jpg")
        if not os.path.exists(cache):
            from PIL import Image, ImageOps
            with Image.open(path) as im:
                im.draft("RGB", (size * 2, size * 2))      # JPEG: 1/2~1/8 크기로 바로 디코딩
                im = ImageOps.exif_transpose(im)
                im = im.convert("RGB")
                im.thumbnail((size, size))
                os.makedirs(THUMB_DIR, exist_ok=True)
                tmp = cache + ".tmp"
                im.save(tmp, "JPEG", quality=82)
                os.replace(tmp, cache)
        with open(cache, "rb") as f:
            return "data:image/jpeg;base64," + base64.b64encode(f.read()).decode("ascii")

    def open_path(self, path):
        try:
            if os.path.exists(path):
                os.startfile(path)
                return {"status": "ok"}
            return {"status": "error", "message": "not found"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def reveal_path(self, path):
        try:
            if os.path.exists(path):
                subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
                return {"status": "ok"}
            return {"status": "error", "message": "not found"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def pick_files(self):
        """드래그가 어려울 때를 위한 '파일 추가' 대화상자."""
        try:
            dialog = getattr(webview, "FileDialog", None)
            kind = dialog.OPEN if dialog else webview.OPEN_DIALOG
            paths = webview.windows[0].create_file_dialog(kind, allow_multiple=True)
            return [str(p) for p in (paths or [])]
        except Exception as e:
            log(f"pick_files error: {e!r}")
            return []

    def start_file_drag(self, paths):
        """선반의 파일을 다른 앱(채팅/메일/탐색기)으로 끌어낸다 (OLE 드래그 앤 드롭, CF_HDROP).
        마우스 왼쪽 버튼이 눌린 상태에서 호출되어야 하며, 놓을 때까지 이 호출은 반환되지 않는다."""
        try:
            existing = [p for p in (paths or []) if os.path.exists(p)]
            if not existing:
                return {"status": "error", "message": "no files"}
            import clr
            clr.AddReference("System.Windows.Forms")
            from System.Windows.Forms import DataObject, DragDropEffects
            from System.Collections.Specialized import StringCollection
            from System import Action
            form = webview.windows[0].native
            result = {}

            def do_drag():
                data = DataObject()
                files = StringCollection()
                for p in existing:
                    files.Add(p)
                data.SetFileDropList(files)
                result["effect"] = str(form.DoDragDrop(data, DragDropEffects.Copy))

            form.Invoke(Action(do_drag))   # DoDragDrop 은 UI 스레드에서 실행해야 한다
            return {"status": "ok", "effect": result.get("effect")}
        except Exception as e:
            log(f"start_file_drag error: {e!r}")
            return {"status": "error", "message": str(e)}

    def _on_files_dropped(self, event):
        """pywebview DOM drop 이벤트: 탐색기에서 노치로 떨어뜨린 파일의 전체 경로를 프론트로 전달."""
        try:
            files = event.get("dataTransfer", {}).get("files", [])
            paths = [f["pywebviewFullPath"] for f in files if f.get("pywebviewFullPath")]
            if paths:
                self._push_event({"type": "shelf_drop", "paths": paths})
                try:   # 다음 폴링(최대 200ms)을 기다리지 않고 화면이 바로 가져가게 한다
                    if webview.windows:
                        webview.windows[0].evaluate_js("pollNow()")
                except Exception:
                    pass
        except Exception as e:
            log(f"on_files_dropped error: {e!r}")

    # ------------------------------------------------------------------
    # 알림음
    # ------------------------------------------------------------------
    _OLD_BEEPS = {      # 합성음을 못 쓸 때만 쓰는 옛 삑 소리
        "pomo": [(784, 140), (1047, 140), (1319, 260)],
        "water": [(660, 150), (880, 220)],
        "todo": [(880, 120), (880, 120), (1175, 220)],
    }

    def _sound_opts(self, opts=None):
        """알림음 설정: opts(설정 창의 미리듣기가 지금 화면의 값을 넘긴다)가 있으면 그것, 없으면 저장된 설정."""
        o = opts if isinstance(opts, dict) else {}
        pick = lambda key, pref: o[key] if key in o else self._prefs.get(pref)
        return {"type": pick("type", "soundType"), "volume": pick("volume", "soundVolume"),
                "file": pick("file", "soundFile"), "system": pick("system", "soundSystem")}

    def chime(self, kind="pomo", opts=None):
        """알림음을 낸다(설정: 종류·길이·크기·내 파일). 소리가 끝날 때까지 스레드에서 재생한다."""
        so = self._sound_opts(opts)

        def play():
            try:
                vol = so["volume"] if so["volume"] is not None else 80
                try:
                    if so["type"] == "custom":
                        chimes.play_custom(str(so["file"] or ""), vol)
                    else:
                        chimes.play_system(str(so["system"] or chimes.DEFAULT_SYSTEM), vol)
                    return
                except Exception as e:
                    log(f"alert sound failed ({e!r}), using the built-in chime")
                chimes.play(kind, "chime", "normal", vol)      # 고른 소리를 쓸 수 없을 때만(파일이 없어졌을 때 등) 앱 안의 기본 차임
            except Exception as e:
                log(f"chime error: {e!r}")
                try:
                    import winsound
                    for freq, ms in self._OLD_BEEPS.get(kind, self._OLD_BEEPS["pomo"]):
                        winsound.Beep(freq, ms)
                except Exception as e2:
                    log(f"beep fallback error: {e2!r}")
        threading.Thread(target=play, daemon=True, name="chime").start()
        return {"status": "ok"}

    def list_system_sounds(self):
        """설정 창의 '윈도우 소리' 목록(C:\\Windows\\Media 의 쓸 수 있는 .wav 이름)."""
        try:
            return chimes.system_sounds()
        except Exception as e:
            log(f"list_system_sounds failed: {e!r}")
            return []

    def pick_sound_file(self):
        """설정 창의 '찾아보기': .wav 파일을 고르고 검사한다. {'status': 'ok', 'path': ...} / cancelled / invalid."""
        w = self._settings_win
        if w is None:
            return {"status": "error", "message": "no window"}
        try:
            res = w.create_file_dialog(webview.OPEN_DIALOG, allow_multiple=False, file_types=("WAV audio (*.wav)",))
            if not res:
                return {"status": "cancelled"}
            path = res if isinstance(res, str) else res[0]
            info = chimes.custom_info(path)
            if not info["ok"]:
                return {"status": "invalid", "why": info.get("why", "")}
            return {"status": "ok", "path": path, "seconds": info["seconds"]}
        except Exception as e:
            log(f"pick_sound_file failed: {e!r}")
            return {"status": "error", "message": str(e)}

    def _region_is_stale(self, rect):
        """화면(JS)이 호출마다 붙이는 순번이 이미 적용한 것보다 낮으면 옛 호출이다 (늦게 도착해 작은 영역으로 되돌리는 일을 막는다)."""
        try:
            seq = int(rect.get('seq')) if isinstance(rect, dict) and rect.get('seq') is not None else None
        except (TypeError, ValueError):
            seq = None
        if seq is None:
            return False
        if seq < self._region_seq:
            return True
        self._region_seq = seq
        return False

    def expand_window(self, rect=None):
        """rect 가 있으면 확장된 필 영역만 클릭 가능하게, 없으면 창 전체를 상호작용 가능하게(컨텍스트 메뉴용)."""
        try:
            with self._region_lock:
                if self._region_is_stale(rect):
                    return {"status": "ok", "stale": True}
                hwnd = self._get_hwnd()
                if hwnd:
                    if rect and isinstance(rect, dict):
                        dpr = float(rect.get('dpr') or self._notch_scale())
                        phys_l = int((float(rect['left']) - 4) * dpr)
                        phys_r = int((float(rect['right']) + 4) * dpr)
                        phys_b = int((float(rect['bottom']) + 6) * dpr)
                        self._set_window_region(hwnd, phys_l, phys_r, phys_b, dpr, int(32 * dpr))
                        log("Expanded window region applied (pill area interactive).")
                    else:
                        ctypes.windll.user32.SetWindowRgn(hwnd, 0, True)
                        log("Expanded window region cleared (full window interactive).")
                return {"status": "ok"}
        except Exception as e:
            log(f"expand_window error: {e}")
            return {"status": "error", "message": str(e)}

    def collapse_window(self, rect=None):
        try:
            with self._region_lock:
                if self._region_is_stale(rect):
                    return {"status": "ok", "stale": True}
                hwnd = self._get_hwnd()
                if hwnd:
                    if rect and isinstance(rect, dict):
                        dpr = float(rect.get('dpr') or self._notch_scale())
                        pad_x, pad_y = 4, 6
                        left, right, bottom = float(rect['left']), float(rect['right']), float(rect['bottom'])
                    else:
                        # 렉트가 없을 때(초기 on_shown): 창 중앙 기준 노치 크기로 계산. 여유를 조금 더 둔다.
                        dpr = self._notch_scale()
                        pad_x, pad_y = 12, 6
                        left = (EXPANDED_WIDTH - NOTCH_WIDTH) / 2
                        right = left + NOTCH_WIDTH
                        bottom = NOTCH_HEIGHT

                    phys_l = int((left - pad_x) * dpr)
                    phys_r = int((right + pad_x) * dpr)
                    phys_b = int((bottom + pad_y) * dpr)
                    self._set_window_region(hwnd, phys_l, phys_r, phys_b, dpr, int(22 * dpr))
                    log(f"Collapsed notch region applied: l={phys_l}, r={phys_r}, b={phys_b}")
                return {"status": "ok"}
        except Exception as e:
            log(f"collapse_window error: {e}")
            return {"status": "error", "message": str(e)}

    def resize_window(self, height=None, dpr=None):
        """창 높이만 바꾼다(위치/너비 유지). 컨텍스트 메뉴가 기본 창 높이보다 커서 잘리는 문제 해결용."""
        try:
            hwnd = self._get_hwnd()
            if hwnd:
                scale = float(dpr) if dpr else self._notch_scale()
                h_phys = int(float(height or EXPANDED_HEIGHT) * scale)
                self._custom_height = bool(height)       # 메뉴 때문에 일부러 키운 동안에는 창 크기 점검(_window_size_ok)이 높이를 보지 않는다
                rc = wintypes.RECT()
                ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rc))
                ctypes.windll.user32.SetWindowPos(
                    hwnd, 0, 0, 0, rc.right - rc.left, h_phys,
                    SWP_NOMOVE | SWP_NOZORDER | SWP_NOACTIVATE
                )
            return {"status": "ok"}
        except Exception as e:
            log(f"resize_window error: {e}")
            return {"status": "error", "message": str(e)}

    def hide_from_taskbar(self):
        """Permanently removes the notch window from the Windows Taskbar."""
        try:
            hwnd = self._get_hwnd()
            if hwnd:
                user32 = ctypes.windll.user32
                ole32 = ctypes.windll.ole32

                # 1. Update extended styles: Add WS_EX_TOOLWINDOW and remove WS_EX_APPWINDOW
                WS_EX_TOOLWINDOW = 0x00000080
                WS_EX_APPWINDOW = 0x00040000
                ex = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
                user32.SetWindowLongW(hwnd, GWL_EXSTYLE, (ex | WS_EX_TOOLWINDOW) & ~WS_EX_APPWINDOW)

                # 2. Call ITaskbarList::DeleteTab via COM vtable
                class GUID(ctypes.Structure):
                    _fields_ = [
                        ("Data1", ctypes.c_ulong),
                        ("Data2", ctypes.c_ushort),
                        ("Data3", ctypes.c_ushort),
                        ("Data4", ctypes.c_ubyte * 8)
                    ]

                def s2g(s):
                    g = GUID()
                    ole32.CLSIDFromString(ctypes.c_wchar_p(s), ctypes.byref(g))
                    return g

                CLSID_TaskbarList = s2g("{56FDF344-FD6D-11D0-958A-006097C9A090}")
                IID_ITaskbarList = s2g("{56FDF342-FD6D-11D0-958A-006097C9A090}")

                # S_OK(0) / S_FALSE(1) 일 때만 CoUninitialize 와 짝이 맞는다.
                # (RPC_E_CHANGED_MODE 등 실패 시 Uninitialize 하면 다른 코드의 COM 초기화를 깨뜨림)
                hr_init = ole32.CoInitialize(0)
                try:
                    pTaskbar = ctypes.c_void_p()
                    hr = ole32.CoCreateInstance(
                        ctypes.byref(CLSID_TaskbarList),
                        None,
                        0x17,  # CLSCTX_ALL
                        ctypes.byref(IID_ITaskbarList),
                        ctypes.byref(pTaskbar)
                    )
                    if hr == 0 and pTaskbar.value:
                        vtable_ptr = ctypes.cast(pTaskbar.value, ctypes.POINTER(ctypes.c_void_p))[0]
                        vtable = ctypes.cast(vtable_ptr, ctypes.POINTER(ctypes.c_void_p))
                        HrInit = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p)(vtable[3])
                        DeleteTab = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.c_void_p)(vtable[5])
                        Release = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(vtable[2])
                        try:
                            HrInit(pTaskbar.value)
                            res = DeleteTab(pTaskbar.value, hwnd)
                            log(f"Window hidden from Windows Taskbar (DeleteTab result={res}).")
                        finally:
                            Release(pTaskbar.value)
                finally:
                    if hr_init in (0, 1):
                        ole32.CoUninitialize()
            return {"status": "ok"}
        except Exception as e:
            log(f"hide_from_taskbar error: {e}")
            return {"status": "error", "message": str(e)}

    def start_drag(self):
        """Starts native Windows modal window drag."""
        try:
            hwnd = self._get_hwnd()
            if hwnd:
                ctypes.windll.user32.ReleaseCapture()
                ctypes.windll.user32.SendMessageW(hwnd, 0x00A1, 2, 0)  # WM_NCLBUTTONDOWN = 0x00A1, HTCAPTION = 2
            return {"status": "ok"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _boost_polling(self):
        self._boost_until = time.monotonic() + BOOST_SECONDS
        if self._smtc is not None:
            try:
                self._smtc.boost(BOOST_SECONDS)
            except Exception:
                pass

    def media_action(self, action: str, arg=None):
        self._boost_polling()
        try:
            if self._source == "phone":
                return self._media_action_phone(action, arg)
            if self._source == "smtc" and self._smtc is not None:
                return self._media_action_smtc(action, arg)
            if action == "toggle":
                self._client.toggle_playback()
            elif action == "play":
                self._client.play()
            elif action == "pause":
                self._client.pause()
            elif action == "next":
                self._client.next_track()
            elif action == "prev":
                self._client.previous_track()
            elif action == "repeat" and arg in ("none", "one", "all"):
                self._client.set_repeat(arg)
                with self._lock:
                    self._last_state["repeat"] = arg
            elif action == "shuffle" and arg is not None:
                self._client.set_shuffle(bool(arg))
                with self._lock:
                    self._last_state["shuffle"] = bool(arg)
            elif action == "seek" and arg is not None:
                self._client.seek(float(arg))
                with self._lock:
                    self._anchor_time = float(arg)
                    self._anchor_perf = time.perf_counter()
            return {"status": "ok"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    # ---- 폰에서 재생 중인 미디어(Dalu Link): 곡 정보는 폰이 보내고, 조작은 폰의 미디어 세션으로 간다
    PM_LABEL = {"ko": "폰", "zh": "手机", "ja": "スマホ"}

    def _phone_label(self, pm):
        return f"{pm.get('appName') or 'Media'} · {self.PM_LABEL.get(self._prefs.get('lang'), 'Phone')}"

    def _pm_now(self, pm):
        """폰 곡의 지금 재생 위치(초): 마지막으로 받은 위치에서 재생 속도만큼 흘려 보낸다."""
        pos = pm["pos"] - pm.get("lat", 0.0)          # 폰의 출력 지연(블루투스 이어폰 등)만큼 뺀다: 귀에 들리는 소리 기준의 위치
        if pm["playing"] and pm["speed"] > 0:
            pos += (time.perf_counter() - pm["at"]) * pm["speed"]
        if pm["dur"] > 0:
            pos = min(pos, pm["dur"])
        return max(0.0, pos)

    def _phone_media_pb(self):
        """폰 곡을 Cider 재생 상태와 같은 모양으로(설정이 꺼져 있거나 폰과 끊겼으면 None)."""
        pm = self._pm
        if not pm or not self._prefs.get("phoneMedia") or not pm.get("title"):
            return None
        s = self._link
        if s is None or not s.connected_ids():
            return None
        return {"source": "phone", "appName": pm["app"] or "Media", "state": "playing" if pm["playing"] else "paused", "isPlaying": bool(pm["playing"]),
                "currentTime": self._pm_now(pm), "duration": pm["dur"], "trackId": "phone:" + pm["tk"], "catalogId": "", "hasLyrics": False,
                "title": pm["title"], "artist": pm["artist"], "album": pm["album"], "artworkUrl": pm["art"], "repeat": "none", "shuffle": False, "canMode": False,
                "posRev": pm.get("rev", 0), "posFrozen": bool(pm["playing"] and pm["speed"] <= 0)}

    def _on_phone_media(self, e):
        """폰이 보낸 재생 정보(phone_media). 설정에서 꺼 두었으면 버린다."""
        if not self._prefs.get("phoneMedia"):
            return
        if e.get("none"):
            self._pm = None
            return

        def num(k, default=0.0, lo=0.0, hi=1e9):
            try:
                v = float(e.get(k))
            except (TypeError, ValueError):
                return default
            return default if v != v else min(max(v, lo), hi)

        tk = str(e.get("tk") or "")[:40]
        if not re.fullmatch(r"[0-9a-f-]{1,40}", tk):
            tk = "x"
        old = self._pm if self._pm and self._pm.get("tk") == tk else None
        art = str(e.get("art") or "")
        if art and len(art) <= 90000 and re.fullmatch(r"[A-Za-z0-9+/=]+", art):
            art = "data:image/jpeg;base64," + art
        else:
            art = old["art"] if old else ""                    # 같은 곡이면 앞서 받은 그림을 그대로 쓴다(그림은 곡마다 한 번만 보낸다)
        can = e.get("can") if isinstance(e.get("can"), dict) else {}
        at = time.perf_counter()
        ck = getattr(self, "_pm_clock", None)
        if ck:                                                 # 폰이 위치를 잰 시각을 PC 시계로 옮긴다: 무선 전송에 걸린 시간만큼 가사가 늦는 것을 없앤다
            est = num("at", 0.0, 0.0, 1e13) / 1000.0 - ck["off"]
            if e.get("at") is not None and at - 3.0 <= est <= at + 0.05:
                at = min(est, at)
            if at - ck["at"] > 180:
                self._link_clock_sync()                        # 시계는 조금씩 어긋난다: 가끔 다시 맞춘다
        lat = num("lat", 0.0, 0.0, 1000.0) / 1000.0
        if old is None or abs(old.get("lat", 0.0) - lat) >= 0.04:          # 가사 싱크를 살필 수 있게 숫자만 남긴다(곡이 바뀌거나 출력 지연이 달라졌을 때)
            log(f"phone media: output delay {lat * 1000:.0f} ms, link delay {(time.perf_counter() - at) * 1000:.0f} ms"
                + (f" (clock round trip {ck['rtt'] * 1000:.0f} ms)" if ck else " (clock not synced)"))
        playing = bool(e.get("playing"))
        speed = 0.0 if (not playing or e.get("buf")) else (num("speed", 0.0, 0.0, 4.0) or 1.0)          # 버퍼링 중(buf): 재생 중으로 보이되 위치는 흐르지 않는다
        self._pm_rev = getattr(self, "_pm_rev", 0) + 1                                                  # 폰이 위치를 새로 알릴 때마다 바뀐다: 화면이 작은 차이도 바로 따라가게 한다
        new = {"pkg": str(e.get("pkg") or "")[:120], "app": str(e.get("app") or "")[:60], "title": str(e.get("title") or "")[:200], "artist": str(e.get("artist") or "")[:200],
               "album": str(e.get("album") or "")[:200], "dur": num("dur", 0.0, 0.0, 1e8) / 1000.0, "pos": num("pos", 0.0, 0.0, 1e8) / 1000.0,
               "speed": speed, "playing": playing, "tk": tk, "art": art, "at": at, "lat": lat, "rev": self._pm_rev,
               "can": {k: bool(can.get(k)) for k in ("next", "prev", "seek")}}
        if old is not None and old["playing"] and playing and old["speed"] > 0:
            d = self._pm_now(new) - self._pm_now(old)
            if abs(d) >= 0.15:                                                                         # 버퍼링·탐색 등으로 재생이 이어지지 않았다(숫자만 남긴다)
                log(f"phone media: position corrected by {d * 1000:+.0f} ms")
        self._pm = new

    def _link_clock_sync(self):
        """폰 시계(부팅 뒤 흐른 시간)와 이 PC 시계의 차이를 잰다: 몇 번 주고받아 가장 빨리 돌아온 것을 쓴다(옛 폰 앱은 답하지 않는다 -> 보정 없이 쓴다)."""
        if getattr(self, "_pm_clock_busy", False):
            return
        self._pm_clock_busy = True

        def run():
            try:
                best = None
                for _ in range(8):                             # 쉬지 않고 이어서 묻는다: 폰의 Wi-Fi 가 절전에서 깨어 있는 동안 재야 가는 길·오는 길이 비슷해져 오차가 준다
                    s = self._link
                    ids = s.connected_ids() if s else []
                    if not ids:
                        break
                    t0 = time.perf_counter()
                    r = s.request(ids[0], {"t": "clock"}, "clock_result", timeout=2.0)
                    t1 = time.perf_counter()
                    try:
                        now = float(r.get("now")) / 1000.0
                    except (AttributeError, TypeError, ValueError):
                        break
                    if best is None or t1 - t0 < best["rtt"]:
                        best = {"off": now - (t0 + t1) / 2.0, "rtt": t1 - t0, "at": t1}
                    time.sleep(0.03)
                if best:
                    old = getattr(self, "_pm_clock", None)
                    self._pm_clock = best
                    if old is None or abs(old["rtt"] - best["rtt"]) > 0.05:
                        log(f"link: phone clock synced (round trip {best['rtt'] * 1000:.0f} ms)")
            except Exception as ex:
                log(f"link clock sync failed: {type(ex).__name__}")
            finally:
                self._pm_clock_busy = False
        threading.Thread(target=run, daemon=True, name="link-clock").start()

    def _on_phone_media_art(self, e):
        """앨범 그림을 주소로만 주는 앱: 폰이 받아서 따로 보낸 그림(곡이 그대로일 때만 붙인다)."""
        pm = self._pm
        art = str(e.get("art") or "")
        if not pm or not self._prefs.get("phoneMedia") or str(e.get("tk") or "") != pm.get("tk"):
            return
        if art and len(art) <= 90000 and re.fullmatch(r"[A-Za-z0-9+/=]+", art):
            pm["art"] = "data:image/jpeg;base64," + art

    def _link_push_media(self, force=False):
        """폰 미디어 표시 설정(phoneMedia)을 연결된 폰에 알린다: 꺼져 있으면 폰은 아무것도 보내지 않는다."""
        try:
            s = self._link
            if s is None:
                return
            on = bool(self._prefs.get("phoneMedia"))
            ids = s.connected_ids()
            if not on:
                self._pm = None
            if not ids:
                return
            if not force and on == getattr(self, "_pm_sig", None):
                return
            self._pm_sig = on
            for i in ids:
                s.send(i, {"t": "media_watch", "on": on})
            if on:
                self._link_clock_sync()
        except Exception as ex:
            log(f"link media push failed: {type(ex).__name__}")

    def _media_action_phone(self, action, arg):
        pm = self._pm
        s = self._link
        ids = s.connected_ids() if s else []
        if not pm or not ids:
            return {"status": "error", "message": "no phone media"}
        if action not in ("toggle", "play", "pause", "next", "prev", "seek"):
            return {"status": "ok"}                                     # 반복·셔플은 폰 곡에는 없다
        msg = {"t": "media_ctl", "action": action}
        now = self._pm_now(pm)
        if action == "seek" and arg is not None:
            msg["arg"] = max(0, int(float(arg) * 1000))
            pm.update({"pos": float(arg) + pm.get("lat", 0.0), "at": time.perf_counter()})
        elif action in ("toggle", "play", "pause"):
            playing = (not pm["playing"]) if action == "toggle" else (action == "play")
            pm.update({"pos": now + pm.get("lat", 0.0), "at": time.perf_counter(), "playing": playing, "speed": pm["speed"] or 1.0})      # 폰의 답이 오기 전에 화면부터 바꾼다
        s.send(ids[0], msg)
        return {"status": "ok"}

    def _media_action_smtc(self, action, arg):
        """Cider 가 아닌 앱을 윈도우 미디어 세션으로 제어한다. 앱이 지원하지 않는 동작은 조용히 무시된다."""
        ok = self._smtc.control(action, arg)
        if ok and action in ("repeat", "shuffle", "seek"):
            with self._lock:
                if action == "repeat":
                    self._last_state["repeat"] = arg
                elif action == "shuffle":
                    self._last_state["shuffle"] = bool(arg)
                else:
                    self._anchor_time = float(arg)
                    self._anchor_perf = time.perf_counter()
        return {"status": "ok" if ok else "error", "message": "" if ok else "the app did not accept the command"}

    # ------------------------------------------------------------------
    # 모니터 선택 (설정 'monitor': 식별 번호, 0 = 주 모니터. 없는 번호면 주 모니터)
    # ------------------------------------------------------------------
    def _target_monitor(self):
        try:
            return monitors.pick_monitor(monitors.list_monitors(), self._prefs.get("monitor"))
        except Exception as e:
            log(f"_target_monitor error: {e!r}")
            return None

    def _top_center(self, mon, width_px):
        """모니터 mon 의 가로 가운데·맨 위에 폭 width_px(물리 픽셀) 창을 놓을 좌표. 모니터를 모르면 주 화면 기준."""
        if mon:
            return monitors.placed_x(mon, width_px, self._prefs.get("notchPos"), width_px / float(EXPANDED_WIDTH)), mon["top"]
        return int((self._primary_screen().width * self._get_scale() - width_px) // 2), 0

    def get_monitors(self):
        """설정 창용: 연결된 모니터 목록과 지금 노치가 있는 번호."""
        try:
            mons = monitors.list_monitors()
            cur = monitors.pick_monitor(mons, self._prefs.get("monitor"))
            return {"monitors": mons, "current": cur["number"] if cur else None, "wanted": self._prefs.get("monitor")}
        except Exception as e:
            return {"monitors": [], "current": None, "wanted": self._prefs.get("monitor"), "error": str(e)}

    def recenter_window(self):
        try:
            hwnd = self._get_hwnd()
            if hwnd:
                mon = self._target_monitor()
                scale = self._notch_scale()
                w_phys = int(EXPANDED_WIDTH * scale)
                h_phys = int(EXPANDED_HEIGHT * scale)
                x_phys, y_phys = self._top_center(mon, w_phys)
                ctypes.windll.user32.SetWindowPos(hwnd, 0, x_phys, y_phys, w_phys, h_phys, SWP_NOZORDER | SWP_NOACTIVATE)
                self._mon_key = monitors.monitor_key(mon)
                self._pos_applied = monitors.clamp_pos(self._prefs.get("notchPos"))
                log(f"Window placed on monitor {mon['number'] if mon else '?'} at ({x_phys}, {y_phys}), scale {scale:.2f}, position {self._pos_applied}.")
            return {"status": "ok"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _monitor_watch(self):
        """모니터가 연결/해제/재배치되거나 설정한 번호가 바뀌면 노치를 다시 그 모니터 위쪽 가운데로 옮긴다.
        (사용자가 직접 끌어 옮긴 위치는 그대로 둔다: 모니터 구성이 바뀔 때만 움직인다)"""
        while self._running:
            time.sleep(3.0)
            try:
                hwnd = self._get_hwnd()
                key = monitors.monitor_key(self._target_monitor())
                if key != getattr(self, "_mon_key", None) and hwnd:
                    log("Monitor layout/choice changed; moving the notch.")
                    self.recenter_window()
                elif hwnd and getattr(self, "_mon_key", None) is not None and not self._window_size_ok(hwnd):
                    log("Window size does not match the expected size; fixing it.")
                    self.apply_ui_scale()
                if hwnd and not self._game and not (self._fullscreen and self._prefs.get("fullscreenMode") == "yield") \
                        and topmost_buried(hwnd):
                    # 항상 위 속성은 켜져 있는데 일반 창 밑으로 내려가 있다 → 다시 맨 위로 올린다(활성화·이동 없이)
                    ok = set_topmost(hwnd, True)
                    log("Notch was buried under a normal window; raised to the top again." if ok else "Notch was buried under a normal window; raising it failed.")
            except Exception as e:
                log(f"_monitor_watch error: {e!r}")

    def _window_size_ok(self, hwnd):
        """창의 실제 크기가 (CSS 크기 x 배율)과 맞는지. 시작 직후 배율이 잘못 잡혔을 때 스스로 바로잡기 위한 확인."""
        try:
            rc = wintypes.RECT()
            ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rc))
            scale = self._notch_scale()
            if abs((rc.right - rc.left) - int(EXPANDED_WIDTH * scale)) > 2:
                return False
            if getattr(self, "_custom_height", False):       # 우클릭 메뉴가 열려 있어 창이 더 높다
                return (rc.bottom - rc.top) >= int(EXPANDED_HEIGHT * scale) - 2
            return abs((rc.bottom - rc.top) - int(EXPANDED_HEIGHT * scale)) <= 2
        except Exception:
            return True

    def toggle_click_through(self, enable: bool):
        try:
            hwnd = self._get_hwnd()
            if hwnd:
                user32 = ctypes.windll.user32
                ex_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
                # WS_EX_TRANSPARENT 만으로는 최상위 창이 마우스를 그대로 받는다(같은 스레드의 아래 형제 창에만 영향).
                # 레이어드(WS_EX_LAYERED)와 함께 써야 창 전체(WebView2 자식 창 포함)가 클릭을 아래 창으로 흘려보낸다.
                if enable:
                    ex_style |= WS_EX_TRANSPARENT | WS_EX_LAYERED
                else:
                    ex_style &= ~(WS_EX_TRANSPARENT | WS_EX_LAYERED)
                user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex_style)
                if enable:
                    user32.SetLayeredWindowAttributes(hwnd, 0, 255, LWA_ALPHA)   # 불투명 그대로(레이어드 창은 이걸 불러야 그려진다)

                was_on = self._click_through
                self._click_through = bool(enable)
                if enable and not was_on:
                    threading.Thread(target=self._click_through_watcher, daemon=True, name="click-through").start()
            return {"status": "ok", "clickThrough": enable}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    # ---- 휴대폰: 알림·배터리·벨소리 모드·방해 금지·폰 찾기는 모두 폰 앱(Dalu Link)으로 한다
    def _winnotif_ignore(self):
        """윈도우 알림 동그라미가 무시할 앱(설정값)."""
        return str(self._prefs.get("winNotifyIgnore") or "")

    # ---- Dalu Link: 폰 앱(Dalu Link)과 직접 연결. 알림·배터리·벨소리 모드·방해 금지를 받고, 답장·폰 찾기·모드 변경을 보낸다
    def _link_sync(self):
        """설정 linkOn 에 맞춰 서버를 켜거나 끈다."""
        if linkserver is None:
            return
        try:
            want = bool(self._prefs.get("linkOn"))
            if want and self._link is None:
                srv = linkserver.LinkServer(os.path.join(ISLAND_DIR, "link"), on_event=self._on_link_event, log=log, pc_name=os.environ.get("COMPUTERNAME") or "PC")
                srv.set_relay(self._relay_wanted())
                srv.start()
                if srv.port:
                    self._link = srv
                else:
                    log(f"link: the server did not start ({srv.error})")
            elif want and self._link is not None:
                self._link.set_relay(self._relay_wanted())
            elif not want and self._link is not None:
                self._link.stop()
                self._link = None
                self._link_info = {"battery": None, "charging": None, "name": "", "ringer": None, "dnd": None, "policy": None, "missed": 0, "missed_ack": 0, "call": None}
        except Exception as e:
            log(f"link sync error: {type(e).__name__}")

    def _relay_wanted(self):
        """중계 서버 주소: 설정에서 켰을 때만. 우리 서버만 쓴다(예전에 설정에 적어 둔 다른 주소는 쓰지 않는다). 꺼져 있으면 ''."""
        if not self._prefs.get("linkRelayOn"):
            return ""
        return linkserver.RELAY_DEFAULT

    def _on_link_event(self, e):
        """폰 앱이 보낸 것: 알림은 노치의 알림 팝업(답장 카드)으로, 배터리·연결 변화는 상태로. 알림 내용은 저장하지 않고 로그에는 길이만 남긴다."""
        try:
            t = e.get("t")
            if t == "notif":
                self._note_phone_app(str(e.get("pkg", "")), str(e.get("app", "")), bool(e.get("initial")))
                if not self._phone_notify_allowed(str(e.get("pkg", "")), e.get("imp")):
                    return                                    # 설정에서 이 앱(또는 소리·진동 없는 알림)은 노치에 띄우지 않기로 했다(새 폰 앱은 폰에서 먼저 거르고, 옛 폰 앱을 위해 여기서도 거른다)
                pkg = str(e.get("pkg", "")).lower()
                if str(e.get("category", "")) in ("call", "missed_call") or (self._link_info.get("call") and any(w in pkg for w in ("incallui", "dialer", "telecom"))):
                    return                                    # 전화 알림(걸려 옴·통화 중·부재중)은 통화 화면이 따로 보여 준다: 같은 알림이 1초마다 갱신돼 팝업이 계속 뜨고 보조 노치를 가리던 문제
                if e.get("initial") or not self._prefs.get("phoneNotify"):
                    return                                    # 연결할 때 지금 떠 있는 알림을 한꺼번에 보내 준다: 팝업은 새 알림만(설정에서 끄면 띄우지 않는다)
                title, text, app = str(e.get("title", "")), str(e.get("text", "")), str(e.get("app", ""))
                msgs = []
                for m in (e.get("messages") if isinstance(e.get("messages"), list) else [])[-12:]:
                    if isinstance(m, dict) and str(m.get("text", "")).strip():
                        msgs.append({"sender": str(m.get("sender", ""))[:80], "text": str(m.get("text", ""))[:500]})
                icon = ""
                raw_icon = str(e.get("icon", ""))
                if raw_icon and len(raw_icon) <= 32000 and re.fullmatch(r"[A-Za-z0-9+/=]+", raw_icon):          # 앱 아이콘(PNG): base64 글자만 통과시킨다
                    icon = "data:image/png;base64," + raw_icon
                log(f"link notification: app_len={len(app)} title_len={len(title)} text_len={len(text)} messages={len(msgs)} conv_len={len(str(e.get('conv', '')))} group={bool(e.get('group'))} reply={bool(e.get('canReply'))}")
                self._push_event({"type": "phone_notify", "id": abs(hash(str(e.get("key", "")) + str(e.get("time", 0)))) % 1000000007, "app": app, "sender": title, "body": text,
                                  "kind": "app", "lines": [app, title, text], "key": str(e.get("key", "")), "pkg": str(e.get("pkg", ""))[:120], "canReply": bool(e.get("canReply")), "source": "link",
                                  "messages": msgs, "group": bool(e.get("group")), "conv": str(e.get("conv", ""))[:120], "icon": icon})
            elif t == "notif_gone":
                self._push_event({"type": "phone_notify_gone", "key": str(e.get("key", ""))})
            elif t == "phone_media":
                self._on_phone_media(e)
            elif t == "phone_media_art":
                self._on_phone_media_art(e)
            elif t == "scr_f":
                self._on_scr_frame(e)
            elif t == "scr_state":
                self._on_scr_state(e)
            elif t == "notif_seen":
                self._note_phone_app(str(e.get("pkg", "")), str(e.get("app", "")), False)          # 폰이 거른 알림: 내용은 받지 않고 어느 앱인지만 알려 준다(설정의 앱 목록에 나타나게)
            elif t == "battery":
                self._link_info["battery"] = int(e.get("level", 0))
                self._link_info["charging"] = bool(e.get("charging"))
            elif t == "pc_cmd":
                threading.Thread(target=self._on_pc_cmd, args=(e,), daemon=True, name="link-pc-cmd").start()      # 연결을 처리하는 스레드를 붙잡지 않는다
            elif t == "new_media":
                if not self._prefs.get("linkNewPhoto"):
                    return
                items = []
                for it in (e.get("items") if isinstance(e.get("items"), list) else [])[:10]:
                    if isinstance(it, dict) and it.get("k") in ("i", "v"):
                        try:
                            items.append({"id": int(it["id"]), "k": it["k"], "name": str(it.get("name", ""))[:120], "size": int(it.get("size") or 0), "t": int(it.get("t") or 0),
                                          "dur": int(it.get("dur") or 0), "th": ("data:image/jpeg;base64," + str(it["th"])[:60000]) if it.get("th") else ""})
                        except (TypeError, ValueError, KeyError):
                            pass
                if items:
                    log(f"link new media: {len(items)} item(s)")
                    self._push_event({"type": "phone_new_media", "items": items})
            elif t == "call_audio_state":
                # 폰에서 직접(또는 자동 녹음으로) 스피커·음소거·녹음이 바뀌었다: 통화 중일 때만 반영한다
                if self._link_info.get("call"):
                    audio = {"speaker": bool(e.get("speaker")), "mute": bool(e.get("mute")), "bt": bool(e.get("bt"))}
                    rec = bool(e.get("rec"))
                    try:
                        rec_ms = max(0, int(e.get("recMs") or 0))
                    except (TypeError, ValueError):
                        rec_ms = 0
                    self._link_info["call_audio"] = audio
                    self._link_info["call_rec"] = {"on": rec, "t0": int(time.time() * 1000) - rec_ms if rec else 0}
                    self._push_event({"type": "phone_call_audio", "speaker": audio["speaker"], "mute": audio["mute"], "bt": audio["bt"], "rec": rec, "recMs": rec_ms})
            elif t == "call_state":
                st = str(e.get("state", ""))
                if st in ("ringing", "active", "idle"):
                    number, name = str(e.get("number", ""))[:40], str(e.get("name", ""))[:80]
                    incoming = bool(e.get("incoming"))
                    self._link_info["call"] = None if st == "idle" else {"state": st, "incoming": incoming, "number": number, "name": name}
                    if st == "idle":
                        self._link_info["call_audio"] = None
                        self._link_info["call_rec"] = None
                    if st == "idle":
                        self._call_media_end()
                    else:
                        self._call_media_begin()
                    log(f"link call: {st} incoming={incoming} (number {len(number)} chars)")          # 번호·이름은 기록하지 않고 길이만
                    self._push_event({"type": "phone_call", "state": st, "incoming": incoming, "number": number, "name": name, "missed": bool(e.get("missed"))})
            elif t == "missed":
                try:
                    cnt = max(0, min(999, int(e.get("count", 0))))
                except (TypeError, ValueError):
                    cnt = 0
                self._link_info["missed"] = cnt
                if cnt < int(self._link_info.get("missed_ack") or 0):
                    self._link_info["missed_ack"] = cnt             # 폰에서 기록을 읽어 수가 줄었다: 본 것으로 친 수도 맞춘다
                self._push_event({"type": "phone_state"})
            elif t == "clip":
                self._clip_from_phone_set(e.get("text"))
            elif t == "clip_img":
                self._clip_image_from_phone(e)
            elif t == "phone_state":
                r = str(e.get("ringer", ""))
                self._link_info["ringer"] = r if r in ("sound", "vibrate", "mute") else None
                self._link_info["dnd"] = bool(e.get("dnd"))
                self._link_info["policy"] = bool(e.get("policy"))
                self._push_event({"type": "phone_state"})
            elif t == "link_connected":
                self._link_info["name"] = str(e.get("name", ""))
                self._link_push_filter(force=True)                        # 이 폰에 알림 거르기 설정을 알려 준다(폰에서 먼저 거른다)
                self._link_push_media(force=True)                         # 폰 미디어를 보여 주는 설정도 알려 준다
                self._link_app_hello(e)                                   # 폰 앱의 버전을 기억하고, 앱 파일의 버전을 폰에 알린다(알림 거르기 규칙이 가장 먼저 가야 한다)
                log(f"link: phone connected ({len(self._link_info['name'])} char name)")
                self._push_event({"type": "link_state", "connected": True})
                if self._link is not None:
                    self._link.send(e.get("id"), {"t": "sync"})          # 지금 배터리·알림을 받아 둔다
            elif t == "app_check":
                self._link_send_app_ver(e.get("device") or e.get("id"))   # 폰의 '업데이트 확인'(서버는 폰이 보낸 메시지에 device 를 붙인다)
            elif t == "app_get":
                self._link_app_get(e)                                     # 폰의 '업데이트' 요청
            elif isinstance(t, str) and t.startswith("file_"):
                m = self._file_mgr()
                if m is not None:
                    m.handle(e)
            elif t == "link_disconnected":
                if self._files is not None:
                    self._files.link_lost()
                self._link_info.update({"battery": None, "charging": None, "ringer": None, "dnd": None, "policy": None, "call": None, "call_audio": None, "call_rec": None, "missed": 0, "missed_ack": 0, "app_code": 0, "app_name": ""})
                self._call_media_end()                                    # 폰 연결이 끊기면 통화 중이었더라도 소리를 되돌린다
                self._pm = None
                self._pm_sig = None
                self._pm_clock = None                                     # 다시 연결되면 시계를 새로 맞춘다(폰이 재시작했을 수 있다)
                self._mirror_set_state({"state": "stopped", "why": "link"})
                log("link: phone disconnected")
                self._push_event({"type": "link_state", "connected": False})
        except Exception as ex:
            log(f"link event error: {type(ex).__name__}")

    # ------------------------------------------------------------------
    # 폰 앱(Dalu Link) 업데이트: Dalu 에 들어 있는 앱 파일이 폰의 것보다 새 버전이면 알리고, 폰이 요청하면 그 파일을 보낸다
    # ------------------------------------------------------------------
    def _apk_path(self):
        return os.path.join(BASE_DIR, linkserver.APK_NAME) if linkserver is not None else ""

    def _apk_info(self):
        """Dalu 에 들어 있는 폰 앱 파일의 {code, name, size, sha256} (없거나 앱 파일이 아니면 None)."""
        if linkserver is None:
            return None
        return linkserver.apk_meta(self._apk_path())

    def _link_send_app_ver(self, dev_id, notify=False):
        """폰에 앱 파일의 버전을 알린다(app_ver). notify=True 면 폰이 알림도 띄운다(설정의 '폰에 알리기')."""
        meta = self._apk_info()
        msg = {"t": "app_ver", "code": meta["code"] if meta else 0, "name": meta["name"] if meta else "", "size": meta["size"] if meta else 0, "sha256": meta["sha256"] if meta else ""}
        if notify:
            msg["notify"] = True
        return bool(self._link is not None and dev_id and self._link.send(dev_id, msg))

    def _link_app_hello(self, e):
        """폰이 연결됐다: 앱 파일의 버전을 알려 주고, 폰 앱이 옛 버전이면 PC 화면(노치)에도 한 번 알린다."""
        self._link_info["app_code"] = int(e.get("app_code") or 0)
        self._link_info["app_name"] = str(e.get("app_name") or "")
        self._link_send_app_ver(e.get("id"))
        meta = self._apk_info()
        code = self._link_info["app_code"]
        if meta and code < meta["code"] and self._prefs.get("updateCheck") and self._apk_seen < meta["code"]:
            self._apk_seen = meta["code"]
            log(f"link: the phone app ({code}) is older than the bundled one ({meta['code']})")
            self._push_event({"type": "link_app_update", "from": self._link_info["app_name"], "to": meta["name"], "unknown": code == 0})

    def _link_app_get(self, e):
        """폰에서 '업데이트'를 눌렀다. 폰이 요청한 버전이 지금 Dalu 에 든 앱 파일의 버전이고 폰이 그보다 낮을 때만, 그 파일을 파일 전송 길로 보낸다."""
        meta = self._apk_info()
        if not meta or not (e.get("device") or e.get("id")):
            return
        phone = int(self._link_info.get("app_code") or 0)
        try:
            want = int(e.get("code") or 0)
        except (TypeError, ValueError):
            want = 0
        if want != meta["code"] or (phone and phone >= meta["code"]):
            log("link: phone app update request ignored")
            return
        now = time.time()
        if now - self._app_sent_at < 8.0:
            return
        m = self._file_mgr()
        if m is None:
            return
        self._app_sent_at = now
        ok, err, _fid = m.send_file(self._apk_path(), purpose="app_update")
        log(f"link: sending the phone app ({meta['size']} bytes): {'started' if ok else err}")

    def link_app_notify(self):
        """설정 › Dalu Link '폰에 알리기': 폰에 새 앱 버전이 있다고 알린다. 설치는 폰에서 사용자가 시작한다."""
        try:
            s = self._link
            ids = s.connected_ids() if s is not None else []
            if not ids:
                return {"ok": False, "error": "nolink"}
            if not self._apk_info():
                return {"ok": False, "error": "noapk"}
            return {"ok": any([self._link_send_app_ver(i, notify=True) for i in ids])}
        except Exception as ex:
            log(f"link_app_notify error: {type(ex).__name__}")
            return {"ok": False, "error": "exception"}

    def link_status(self):
        """설정 '휴대폰 연결' 화면용: 서버 상태, 연결된 폰, 배터리."""
        s = self._link
        meta = self._apk_info()
        return {"apk": ({"code": meta["code"], "name": meta["name"]} if meta else None), "enabled": bool(self._prefs.get("linkOn")), "available": linkserver is not None, "listening": s is not None, "port": getattr(s, "port", 0) if s else 0,
                "error": getattr(s, "error", "") if s else "", "devices": s.devices() if s else [], "connected": bool(s and s.connected_ids()),
                "battery": self._link_info.get("battery"), "charging": self._link_info.get("charging"),
                "relay": ({"url": s.relay_info()["url"], "state": s.relay_info()["state"]} if s else {"url": "", "state": "off"}), "relayWanted": bool(self._prefs.get("linkRelayOn"))}

    def link_pair_start(self):
        """새 폰을 연결하려고 QR 을 만든다(5분 동안 한 번만 쓸 수 있다)."""
        try:
            self._link_sync()
            if self._link is None:
                return {"ok": False, "error": "server"}
            p = self._link.pair_start()
            return {"ok": True, "uri": p["uri"], "svg": linkserver.qr_svg(p["uri"]), "expires": p["expires"], "hosts": p["hosts"], "port": p["port"], "relay": bool(p.get("relay"))}
        except Exception as e:
            log(f"link_pair_start error: {type(e).__name__}")
            return {"ok": False, "error": "exception"}

    def link_apk_start(self):
        """폰에 앱을 설치하는 방법: 같은 와이파이의 폰이 받을 수 있는 주소(QR)를 만든다. 설치 파일은 Dalu 에 들어 있고 15분 동안만 열어 둔다."""
        try:
            if linkserver is None:
                return {"ok": False, "error": "unavailable"}
            if self._apk is None:
                self._apk = linkserver.ApkServer(os.path.join(BASE_DIR, linkserver.APK_NAME), log=log)
            if not self._apk.available():
                return {"ok": False, "error": "noapk"}
            port = self._apk.start()
            if not port:
                return {"ok": False, "error": "port"}
            hosts = linkserver.local_ips()
            if not hosts:
                return {"ok": False, "error": "nonet"}
            url = "http://%s:%d/" % (hosts[0], port)
            return {"ok": True, "url": url, "svg": linkserver.qr_svg(url), "sha256": self._apk.sha256, "mb": round(self._apk.size / 1048576.0, 1), "hosts": hosts}
        except Exception as e:
            log(f"link_apk_start error: {type(e).__name__}")
            return {"ok": False, "error": "exception"}

    def link_pair_cancel(self):
        if self._link is not None:
            self._link.pair_cancel()
        return {"ok": True}

    def link_forget(self, device_id):
        if self._link is not None:
            self._link.forget(str(device_id))
        return {"ok": True}

    def link_reply(self, key, text):
        """폰 알림에 답장한다(폰 앱이 그 알림의 답장 동작을 실행). 보낸 글은 저장·기록하지 않는다."""
        try:
            text = str(text or "").strip()
            if not text or len(text) > 1000:
                return {"ok": False, "error": "empty" if not text else "toolong"}
            s = self._link
            ids = s.connected_ids() if s else []
            if not ids:
                return {"ok": False, "error": "nolink"}
            r = s.request(ids[0], {"t": "reply", "key": str(key), "text": text}, "reply_result", timeout=8)
            if r is None:
                return {"ok": False, "error": "timeout"}
            return {"ok": bool(r.get("ok")), "error": str(r.get("error", ""))}
        except Exception as e:
            log(f"link_reply error: {type(e).__name__}")
            return {"ok": False, "error": "exception"}

    # ---- 폰 화면 보기(Dalu Link): 폰이 허용한 동안만, 같은 암호화 연결로 받은 화면을 PC 창에 보여 준다
    MIRROR_TITLE = {"ko": "Dalu · 폰 화면", "zh": "Dalu · 手机屏幕", "ja": "Dalu · スマホ画面"}
    MIRROR_KEYS = ("back", "home", "recents", "notifications", "quick", "lock")

    def _mirror_hub(self):
        if phonemirror is None:
            return None
        if self._mirror is None:
            self._mirror = phonemirror.MirrorHub(on_input=self._mirror_in, log=log)
        return self._mirror

    def _mirror_set_state(self, st):
        h = self._mirror
        if h is not None:
            try:
                h.set_state(st)
            except Exception:
                pass

    def _mirror_send(self, msg):
        s = self._link
        ids = s.connected_ids() if s else []
        return bool(ids) and bool(s.send(ids[0], msg))

    def phone_screen_open(self):
        """휴대폰 탭의 '화면 보기': 창을 열고 폰에 허용을 요청한다(폰에서 알림을 눌러 허용해야 시작된다)."""
        try:
            if not (self._prefs.get("linkOn") and self._prefs.get("linkMirror")):
                return {"ok": False, "error": "off"}
            s = self._link
            if s is None or not s.connected_ids():
                return {"ok": False, "error": "nolink"}
            hub = self._mirror_hub()
            if hub is None:
                return {"ok": False, "error": "module"}
            port, _token = hub.start()
            if not port:
                return {"ok": False, "error": "server"}
            self._mirror_ctl = bool(self._prefs.get("linkMirrorControl"))
            hub.set_state({"state": "waiting", "control": self._mirror_ctl})
            self._mirror_open_window()
            self._mirror_send({"t": "scr_start", "control": self._mirror_ctl})
            log(f"mirror: requested (control={self._mirror_ctl})")
            return {"ok": True}
        except Exception as ex:
            log(f"phone_screen_open error: {type(ex).__name__}")
            return {"ok": False, "error": "exception"}

    def phone_screen_stop(self):
        """화면 보기를 끝낸다: 폰에 알리고 창과 PC 안 서버를 닫는다."""
        try:
            self._mirror_send({"t": "scr_stop"})
            self._mirror_set_state({"state": "idle"})
            with self._mirror_lock:
                w = self._mirror_win
                self._mirror_win = None
            if w is not None:
                try:
                    w.destroy()
                except Exception:
                    pass
            h = self._mirror
            if h is not None:
                h.stop()
                self._mirror = None
            self._mirror_ctl = False
            return {"ok": True}
        except Exception as ex:
            log(f"phone_screen_stop error: {type(ex).__name__}")
            return {"ok": False}

    def mirror_info(self):
        """화면 창이 PC 안 서버에 붙는 데 쓰는 값(창마다 새로 만든 무작위 토큰)."""
        h = self._mirror
        if h is None or not h.port:
            return {"ok": False}
        return {"ok": True, "port": h.port, "token": h.token, "control": bool(self._mirror_ctl), "lang": self._prefs.get("lang") or "ko"}

    def mirror_fit(self, aw, ah):
        """화면 비율에 맞춰 창 크기를 한 번 맞춘다(가로/세로가 바뀔 때만)."""
        try:
            aw, ah = float(aw), float(ah)
            w = self._mirror_win
            if w is None or aw <= 0 or ah <= 0:
                return {"ok": False}
            key = "L" if aw > ah else "P"
            if key == self._mirror_fit_key:
                return {"ok": True}
            self._mirror_fit_key = key
            mon = self._target_monitor() or {}
            scale = self._get_scale() or 1.0
            maxh = int((mon.get("height") or 1080) / scale * 0.86)
            maxw = int((mon.get("width") or 1920) / scale * 0.8)
            chrome = 64                                                       # 아래 도구 막대
            h = min(maxh, 900 if key == "P" else 640)
            vw = int((h - chrome) * aw / ah)
            if vw > maxw:
                vw = maxw
                h = int(vw * ah / aw) + chrome
            w.resize(max(360, vw), max(420, h))
            return {"ok": True}
        except Exception as ex:
            log(f"mirror_fit error: {type(ex).__name__}")
            return {"ok": False}

    def _mirror_open_window(self):
        with self._mirror_lock:
            w = self._mirror_win
            title = self.MIRROR_TITLE.get(self._prefs.get("lang"), "Dalu · Phone screen")
            if w is not None and w in webview.windows:
                try:
                    w.restore()
                    w.show()
                    w.evaluate_js("mirrorReconnect()")
                except Exception as e:
                    log(f"mirror window focus failed: {e!r}")
                return
            self._mirror_fit_key = None
            url = Path(BASE_DIR, "mirror.html").as_uri()
            w = webview.create_window(title, url=url, js_api=self, width=400, height=820, min_size=(360, 420), background_color="#0b0b0e")
            w.events.shown += lambda: self._set_window_icon(w)
            w.events.closed += self._on_mirror_closed
            self._mirror_win = w

    def _on_mirror_closed(self):
        with self._mirror_lock:
            direct = self._mirror_win is not None                            # 창을 직접 닫았다(phone_screen_stop 이 닫은 게 아니다)
            self._mirror_win = None
        if direct:
            self.phone_screen_stop()

    def _mirror_in(self, m):
        """창이 보낸 것(PC 안 서버 스레드): 조작은 이번 화면 보기에서 조작을 요청했고 설정도 켜져 있을 때만 폰으로 보낸다."""
        t = m.get("t")
        if t == "key":
            self._mirror_send({"t": "scr_key"})
        elif t == "stop":
            threading.Thread(target=self.phone_screen_stop, daemon=True, name="mirror-stop").start()
        elif t == "in":
            if not (self._mirror_ctl and self._prefs.get("linkMirror") and self._prefs.get("linkMirrorControl")):
                return
            k = str(m.get("k") or "")

            def f(name):
                try:
                    v = float(m.get(name))
                except (TypeError, ValueError):
                    return 0.0
                return min(max(v, 0.0), 1.0) if v == v else 0.0
            out = {"t": "scr_in", "k": k}
            if k in ("tap", "long"):
                out.update(x=f("x"), y=f("y"))
            elif k == "swipe":
                try:
                    ms = int(m.get("ms") or 250)
                except (TypeError, ValueError):
                    ms = 250
                out.update(x1=f("x1"), y1=f("y1"), x2=f("x2"), y2=f("y2"), ms=min(max(ms, 60), 1500))
            elif k == "key":
                a = str(m.get("a") or "")
                if a not in self.MIRROR_KEYS:
                    return
                out["a"] = a
            elif k == "text":
                out["s"] = str(m.get("s") or "")[:500]
            elif k in ("bs", "enter"):
                pass
            else:
                return
            self._mirror_send(out)

    def _on_scr_state(self, e):
        st = str(e.get("state") or "")
        if st not in ("consent", "running", "stopped", "denied", "error", "noctl", "inputfail"):
            return
        out = {"state": st}
        for k in ("w", "h"):
            try:
                out[k] = int(e.get(k) or 0)
            except (TypeError, ValueError):
                pass
        for k in ("control", "a11y"):
            if k in e:
                out[k] = bool(e.get(k))
        for k in ("why", "error"):
            if e.get(k):
                out[k] = str(e.get(k))[:20]
        if st in ("noctl", "inputfail"):                                     # 화면은 계속 흐른다: 알림만 띄운다
            h = self._mirror
            if h is not None:
                cur = dict(getattr(h, "_state", {}) or {})
                cur["notice"] = st
                cur["a11y"] = out.get("a11y", cur.get("a11y"))
                self._mirror_set_state(cur)
            return
        if st == "running":
            out.setdefault("control", self._mirror_ctl)
        log(f"mirror: phone says {st}" + (f" ({out.get('why') or out.get('error')})" if out.get("why") or out.get("error") else ""))
        self._mirror_set_state(out)

    def _on_scr_frame(self, e):
        h = self._mirror
        if h is None or (self._mirror_win is None and not h.viewers()):      # (창은 있는데 아직 붙는 중이면 멈추지 않는다: 다시 붙을 때 마지막 키프레임부터 보여 준다)
            if time.monotonic() - self._mirror_stop_sent > 3.0:               # 보는 창이 없는데 화면이 오고 있다: 폰에 멈추라고 한다
                self._mirror_stop_sent = time.monotonic()
                self._mirror_send({"t": "scr_stop"})
            return
        d = e.get("d")
        if not isinstance(d, str) or not d or len(d) > 900000:
            return
        try:
            data = base64.b64decode(d, validate=True)
        except Exception:
            return
        try:
            ts = int(e.get("ts") or 0)
        except (TypeError, ValueError):
            ts = 0
        h.push_frame(bool(e.get("k")), ts, data)

    def link_find(self, on):
        """폰을 울린다/멈춘다(폰 찾기)."""
        try:
            s = self._link
            ids = s.connected_ids() if s else []
            if not ids:
                return {"ok": False, "error": "nolink"}
            r = s.request(ids[0], {"t": "find", "on": bool(on)}, "find_result", timeout=5)
            return {"ok": r is not None, "on": bool(r and r.get("on"))}
        except Exception as e:
            log(f"link_find error: {type(e).__name__}")
            return {"ok": False, "error": "exception"}

    # ---- 복사·붙여넣기 동기화 (PC <-> 폰). 글자만, 길이 제한, 폰이 연결돼 있을 때만, 비밀번호 관리자 '제외' 표시가 있으면 보내지 않는다
    CLIP_SYNC_MAX = 100000

    def _clip_sync_wanted(self):
        """복사한 글을 폰으로 보낼 상황인가(설정이 켜져 있고 폰이 연결됨). 아니면 클립보드를 읽지도 않는다."""
        link = getattr(self, "_link", None)
        return bool(self._prefs.get("linkClipPush") and link is not None and link.connected_ids())

    def _clip_changed(self, text):
        """이 PC 에서 새로 복사한 글: 폰으로 보낸다."""
        if not self._clip_sync_wanted():
            return
        t = str(text or "")
        if not t.strip() or len(t) > self.CLIP_SYNC_MAX or t == self._clip_from_phone:
            return
        self._link.send_any({"t": "clip", "text": t})
        log(f"clip sync: sent {len(t)} chars to the phone")          # 글자 수만 기록

    def _clip_image_changed(self, png):
        """이 PC 에서 새로 복사한 이미지: 조각으로 나눠 폰으로 보낸다(같은 이미지를 연달아 보내지 않는다)."""
        if clipimg is None or not self._clip_sync_wanted():
            return
        h = clipimg.png_hash(png)
        if h == self._img_hash_from_phone or h == self._img_hash_sent:
            return
        msgs = clipimg.split(png)
        if not msgs:
            return
        self._img_hash_sent = h
        for m in msgs:
            if not self._link.send_any(m):
                break
        log(f"clip sync: sent an image ({len(png)} bytes, {len(msgs)} pieces) to the phone")

    def _clip_image_from_phone(self, m):
        """폰이 보낸 이미지 조각. 다 모이면 이 PC 의 클립보드에 이미지로 넣는다."""
        if clipimg is None or self._img_asm is None or not self._prefs.get("linkClipPull"):
            return
        done = self._img_asm.add(m)
        if done is None:
            return
        png, _mime = done
        h = clipimg.png_hash(png)
        self._img_hash_from_phone = h
        self._clipwatch.ignore_next_change()
        if clipimg.write_png(png):
            log(f"clip sync: received an image ({len(png)} bytes) from the phone")
            thumb = clipimg.thumb_data_uri(png) if hasattr(clipimg, "thumb_data_uri") else ""          # 알림 아이콘에 쓸 작은 미리보기(실패하면 빈 문자열 = 'img' 글자)
            self._push_event({"type": "phone_clip", "chars": 0, "image": True, "thumb": thumb})

    def _clip_from_phone_set(self, text):
        """폰이 보낸 글을 이 PC 의 클립보드에 넣는다."""
        t = str(text or "")
        if not self._prefs.get("linkClipPull") or not t.strip() or len(t) > self.CLIP_SYNC_MAX:
            return False
        self._clip_from_phone = t
        self._clipwatch.ignore_next_change()
        ok = clipwatch.write_text(t)
        if ok:
            self._clip.add(t) if self._prefs.get("clipboardOn") else None
            log(f"clip sync: received {len(t)} chars from the phone")
            self._push_event({"type": "phone_clip", "chars": len(t)})
        return ok

    # ---- 전화가 오거나 통화 중일 때 PC 소리: 줄이기(duck) / 멈추기(pause) / 그대로(off). 끝나면 되돌린다
    # 줄이기는 윈도우 마스터 볼륨이 아니라 '지금 소리를 내는 앱'의 볼륨을 낮춘다: 앰프·DAC 처럼 윈도우 볼륨이 소리에 반영되지 않는 장치에서도 되고,
    # 마스터 볼륨은 그대로라서 볼륨 팝업도 뜨지 않는다. 통화·메신저 앱(디스코드·카카오톡 등)과 Dalu 자신은 건드리지 않는다.
    def _call_media_begin(self):
        if self._call_media is not None:
            return
        mode = str(self._prefs.get("phoneCallMedia") or "duck")
        if mode == "duck":
            saved = []
            for a in (audiomix.list_apps() or []):
                if a.get("system") or not a.get("active") or a.get("muted"):
                    continue
                name = str(a.get("name", ""))
                if any(w in name.lower() for w in CALL_DUCK_SKIP):
                    continue
                v = float(a.get("volume") or 0)
                if v <= 0.02:
                    continue                                              # 이미 조용하다: 건드리지 않는다
                target = round(v * CALL_DUCK_FACTOR, 4)
                if audiomix.set_app(a["id"], volume=target):
                    saved.append({"id": a["id"], "name": name, "orig": v, "set": target})
            if saved:
                self._call_media = {"mode": "duck", "apps": saved}
                try:
                    with open(CALL_MEDIA_FILE, "w", encoding="utf-8") as f:
                        json.dump(self._call_media, f)
                except Exception as e:
                    log(f"call media: could not save the state: {type(e).__name__}")
                log(f"call media: lowered {len(saved)} playing app(s) for the call")
            else:
                self._call_media = {"mode": "none"}
        elif mode == "pause":
            with self._lock:
                playing = bool(self._last_state.get("isPlaying"))
            if playing:
                self.media_action("pause")
                self._call_media = {"mode": "pause"}
                log("call media: paused the playback for the call")
            else:
                self._call_media = {"mode": "none"}
        else:
            self._call_media = {"mode": "none"}

    def _restore_ducked(self, st):
        """줄여 둔 앱들의 볼륨을 되돌린다(그 사이 사용자가 바꾼 앱은 건드리지 않는다). -> 되돌린 앱 수"""
        n = 0
        cur = {a["id"]: a for a in (audiomix.list_apps() or [])}
        for a in st.get("apps", []):
            c = cur.get(a.get("id"))
            if c and c.get("name") == a.get("name") and abs(float(c.get("volume", 0)) - float(a["set"])) <= 0.03:
                if audiomix.set_app(a["id"], volume=a["orig"]):
                    n += 1
        return n

    def _call_media_end(self):
        st, self._call_media = self._call_media, None
        try:
            os.remove(CALL_MEDIA_FILE)
        except OSError:
            pass
        if not st:
            return
        if st.get("mode") == "duck":
            n = self._restore_ducked(st)
            if n:
                log(f"call media: restored {n} app(s) after the call")
        elif st.get("mode") == "pause":
            with self._lock:
                playing = bool(self._last_state.get("isPlaying"))
            if not playing:                                              # 사용자가 직접 다시 틀지 않았을 때만 이어서 재생한다
                self.media_action("play")
                log("call media: resumed the playback after the call")

    def _call_media_recover(self):
        """앱이 통화 도중에 꺼졌다면 시작할 때 줄여 둔 볼륨을 되돌린다."""
        try:
            with open(CALL_MEDIA_FILE, encoding="utf-8") as f:
                st = json.load(f)
        except Exception:
            return
        try:
            os.remove(CALL_MEDIA_FILE)
        except OSError:
            pass
        try:
            if st.get("mode") == "duck":
                if "apps" in st:
                    n = self._restore_ducked(st)
                    if n:
                        log(f"call media: restored {n} app(s) left lowered by an earlier run")
                else:                                                    # 예전 버전이 마스터 볼륨을 줄여 두었던 기록
                    cur = audiomix.master_get()
                    if cur and not cur.get("muted") and abs(float(cur["volume"]) - float(st["set"])) <= 0.03:
                        audiomix.master_set(st["orig"])
                        log("call media: restored the master volume left lowered by an earlier run")
        except Exception as e:
            log(f"call media recover failed: {type(e).__name__}")

    def _link_phone_id(self):
        s = self._link
        ids = s.connected_ids() if s else []
        return ids[0] if ids else None

    def phone_status(self):
        """휴대폰 탭/작은 노치용: 폰 앱(Dalu Link)에서 받은 상태. state = ok(폰이 연결됨) | nolink(연결된 폰이 없음) | unavailable(이 PC 에서 폰 앱 연결을 쓸 수 없음)."""
        self._phone_asked = time.time()
        if linkserver is None:
            return {"state": "unavailable"}
        if self._link is None or not self._link.connected_ids():
            return {"state": "nolink", "enabled": bool(self._prefs.get("linkOn"))}
        i = self._link_info
        return {"state": "ok", "link": True, "battery": i.get("battery"), "charging": i.get("charging"), "ringer": i.get("ringer"), "dnd": i.get("dnd"),
                "policy": i.get("policy"), "missed": max(0, int(i.get("missed") or 0) - int(i.get("missed_ack") or 0)), "name": i.get("name", ""), "call": i.get("call"), "callAudio": i.get("call_audio"), "callRec": i.get("call_rec")}

    def _link_command(self, msg, result_type, timeout=6):
        """연결된 폰에 명령을 보내고 답을 기다린다. -> (답 dict | None, 오류 코드)"""
        pid = self._link_phone_id()
        if pid is None:
            return None, "nolink"
        r = self._link.request(pid, msg, result_type, timeout=timeout)
        return (r, "") if r is not None else (None, "timeout")

    def phone_set_ringer(self, mode):
        """폰의 벨소리 모드를 바꾼다(sound | vibrate | mute). 무음은 폰에서 '방해 금지 접근'을 허용해야 한다."""
        try:
            mode = str(mode)
            if mode not in ("sound", "vibrate", "mute"):
                return {"ok": False, "error": "mode"}
            r, err = self._link_command({"t": "ringer_set", "mode": mode}, "ringer_result")
            if r is None:
                return {"ok": False, "error": err}
            if r.get("ringer") in ("sound", "vibrate", "mute"):
                self._link_info["ringer"] = r["ringer"]
            return {"ok": bool(r.get("ok")), "error": str(r.get("error", "")), "ringer": r.get("ringer")}
        except Exception as e:
            log(f"phone_set_ringer error: {type(e).__name__}")
            return {"ok": False, "error": "exception"}

    def phone_set_dnd(self, on):
        """폰의 방해 금지를 켜거나 끈다. 폰에서 '방해 금지 접근'을 허용해야 한다."""
        try:
            r, err = self._link_command({"t": "dnd_set", "on": bool(on)}, "dnd_result")
            if r is None:
                return {"ok": False, "error": err}
            if "dnd" in r:
                self._link_info["dnd"] = bool(r.get("dnd"))
            return {"ok": bool(r.get("ok")), "error": str(r.get("error", "")), "dnd": bool(r.get("dnd"))}
        except Exception as e:
            log(f"phone_set_dnd error: {type(e).__name__}")
            return {"ok": False, "error": "exception"}

    @staticmethod
    def _clean_number(s):
        """전화번호 검증(폰 앱과 같은 규칙): 숫자와 맨 앞의 '+' 만, 3~20자리. '*'·'#' 는 막는다(서비스 코드를 PC 에서 걸 수 없게). 못 쓰면 None."""
        raw = str(s or "").strip()
        if not raw or len(raw) > 40:
            return None
        out = ""
        for i, c in enumerate(raw):
            if c.isascii() and c.isdigit():
                out += c
            elif c == "+" and not out and raw.index("+") == i:
                out += c
            elif c in " -().":
                continue
            else:
                return None
        n = sum(ch.isdigit() for ch in out)
        return out if 3 <= n <= 20 else None

    def _call_cmd(self, msg):
        r, err = self._link_command(msg, "call_result")
        if r is None:
            return {"ok": False, "error": err}
        return {"ok": bool(r.get("ok")), "error": str(r.get("error", ""))}

    def phone_call_audio(self, speaker=None, mute=None):
        """통화 중 스피커폰·음소거. 폰이 실제로 바뀌었는지 다시 읽어서 알려 준다: {ok, error, speaker, mute}. 안드로이드가 막으면 ok=False, error='refused'."""
        try:
            msg = {"t": "call_audio"}
            if speaker is not None:
                msg["speaker"] = bool(speaker)
            if mute is not None:
                msg["mute"] = bool(mute)
            if len(msg) == 1:
                return {"ok": False, "error": "nothing"}
            r, err = self._link_command(msg, "call_result", timeout=12)        # 스피커는 전화 앱 화면을 잠깐 열어 버튼을 누를 수 있어 오래 걸린다
            if r is None:
                return {"ok": False, "error": err}
            audio = {"speaker": bool(r.get("speaker")), "mute": bool(r.get("mute"))}
            self._link_info["call_audio"] = audio
            return dict(audio, ok=bool(r.get("ok")), error=str(r.get("error", "")))
        except Exception as e:
            log(f"phone_call_audio error: {type(e).__name__}")
            return {"ok": False, "error": "exception"}

    def phone_call_record(self, on=None):
        """통화 녹음: 전화 앱 통화 화면의 '녹음' 버튼을 폰이 대신 누른다(안드로이드가 다른 앱의 통화 녹음을 막아서 이 방법뿐이다). -> {ok, error, on}
        error: not_visible(폰 화면이 꺼져 있거나 통화 화면을 못 열음) / no_button(이 전화 앱에 녹음 버튼이 없음) / unavailable(폰 앱의 복사 감지(접근성)가 꺼져 있음) / refused"""
        try:
            msg = {"t": "call_ui", "what": "record"}
            if on is not None:
                msg["want"] = bool(on)
            r, err = self._link_command(msg, "call_result", timeout=12)
            if r is None:
                return {"ok": False, "error": err}
            rec = r.get("on")
            if isinstance(self._link_info.get("call"), dict) and isinstance(rec, bool):
                old = self._link_info.get("call_rec") or {}
                self._link_info["call_rec"] = {"on": rec, "t0": (old.get("t0") or int(time.time() * 1000)) if rec else 0}
            return {"ok": bool(r.get("ok")), "error": str(r.get("error", "")), "on": rec if isinstance(rec, bool) else None}
        except Exception as e:
            log(f"phone_call_record error: {type(e).__name__}")
            return {"ok": False, "error": "exception"}

    def phone_call_answer(self):
        """걸려 오는 전화를 받는다. 폰에서 '전화·연락처' 권한이 필요하다."""
        try:
            return self._call_cmd({"t": "call_answer"})
        except Exception as e:
            log(f"phone_call_answer error: {type(e).__name__}")
            return {"ok": False, "error": "exception"}

    def phone_call_end(self):
        """걸려 오는 전화는 거절, 통화 중이면 끊는다."""
        try:
            return self._call_cmd({"t": "call_end"})
        except Exception as e:
            log(f"phone_call_end error: {type(e).__name__}")
            return {"ok": False, "error": "exception"}

    def phone_dial(self, number):
        """폰으로 전화를 건다. 번호는 숫자와 맨 앞 '+' 만 허용한다."""
        try:
            n = self._clean_number(number)
            if n is None:
                return {"ok": False, "error": "number"}
            log(f"phone_dial: asked the phone to call a number of {len(n)} digits")
            return self._call_cmd({"t": "dial", "number": n})
        except Exception as e:
            log(f"phone_dial error: {type(e).__name__}")
            return {"ok": False, "error": "exception"}

    def phone_contacts(self, q):
        """연락처 검색(이름이나 번호 일부). -> {ok, items:[{name, number}], error}. 결과는 화면에만 쓰고 저장하지 않는다."""
        try:
            q = str(q or "").strip()[:60]
            if not q:
                return {"ok": True, "items": []}
            r, err = self._link_command({"t": "contacts_search", "q": q}, "contacts_result")
            if r is None:
                return {"ok": False, "items": [], "error": err}
            items = []
            for it in (r.get("items") if isinstance(r.get("items"), list) else [])[:15]:
                if isinstance(it, dict):
                    num = self._clean_number(it.get("number"))
                    if num:
                        items.append({"name": str(it.get("name", ""))[:80], "number": num})
            return {"ok": bool(r.get("ok")), "items": items, "error": "" if r.get("ok") else "perm"}
        except Exception as e:
            log(f"phone_contacts error: {type(e).__name__}")
            return {"ok": False, "items": [], "error": "exception"}

    def phone_ring(self, on):
        """폰 찾기(소리 재생)."""
        return self.link_find(on)

    # ---- 폰과 파일 주고받기
    def _file_folder(self):
        d = str(self._prefs.get("linkFileDir") or "").strip()
        if not d:
            d = os.path.join(os.path.expanduser("~"), "Downloads", "Dalu")
        return d

    def _file_mgr(self):
        if filexfer is None:
            return None
        if self._files is None:
            def emit(ev):
                if ev.get("state") == "done" and ev.get("dir") == "in" and ev.get("path"):
                    pth = os.path.normcase(os.path.abspath(ev["path"]))
                    self._file_paths.pop(pth, None)
                    self._file_paths[pth] = True          # 들어간 순서를 지킨다(방금 받은 파일이 아니라 가장 오래된 것부터 잊는다)
                    while len(self._file_paths) > 200:
                        self._file_paths.pop(next(iter(self._file_paths)))
                if ev.get("dir") == "in" and time.time() < self._pull_until:
                    self._pull_until = time.time() + 30          # 고른 사진이 차례로 오는 동안에는 '가져오기' 허용 시간을 이어 간다(여러 개면 30초를 넘긴다)
                self._push_event(ev)
                self._copy_on_file(ev)                           # '복사'로 가져오는 중이면 받은 파일을 모은다
            self._files = filexfer.Manager(lambda m: bool(self._link and self._link.send_any(m)), emit, self._file_folder, lambda: bool(self._prefs.get("linkFileAuto")) or time.time() < self._pull_until, log)
        return self._files

    def phone_send_files(self, paths):
        """파일들을 연결된 폰으로 보낸다(백그라운드로 진행; 진행은 phone_file 이벤트). -> {ok, started, failed:[{error}]}"""
        try:
            m = self._file_mgr()
            if m is None:
                return {"ok": False, "error": "unavailable"}
            if self._link_phone_id() is None:
                return {"ok": False, "error": "nolink"}
            if not isinstance(paths, (list, tuple)):
                paths = [paths]
            started, failed = 0, []
            for p in list(paths)[:50]:
                ok, err, fid = m.send_file(p)
                if ok:
                    started += 1
                else:
                    failed.append({"error": err})
            return {"ok": started > 0, "started": started, "failed": failed, "error": "" if started else (failed[0]["error"] if failed else "none")}
        except Exception as e:
            log(f"phone_send_files error: {type(e).__name__}")
            return {"ok": False, "error": "exception"}

    def phone_media_list(self, kind="all", before=0, before_id=0):
        """폰의 최근 사진·동영상 목록(24개씩, 작은 미리보기 포함). before(초)·before_id: 앞 쪽의 마지막 항목(그다음부터 잇는다). -> {ok, error, items:[{id,k,name,size,t,dur,th}], more}"""
        try:
            kind = kind if kind in ("all", "image", "video") else "all"
            try:
                before = max(0, int(before))
                before_id = max(0, int(before_id))
            except (TypeError, ValueError):
                before = before_id = 0
            r, err = self._link_command({"t": "media_list", "kind": kind, "before": before, "beforeId": before_id}, "media_result", timeout=25)
            if r is None:
                return {"ok": False, "error": err}
            items = []
            for it in (r.get("items") if isinstance(r.get("items"), list) else [])[:48]:
                if not isinstance(it, dict) or it.get("k") not in ("i", "v"):
                    continue
                try:
                    items.append({"id": int(it["id"]), "k": it["k"], "name": str(it.get("name", ""))[:120], "size": int(it.get("size") or 0), "t": int(it.get("t") or 0),
                                  "dur": int(it.get("dur") or 0), "th": ("data:image/jpeg;base64," + str(it["th"])[:60000]) if it.get("th") else ""})
                except (TypeError, ValueError, KeyError):
                    continue
            log(f"media list: {len(items)} items")
            return {"ok": bool(r.get("ok")), "error": str(r.get("error", "")), "items": items, "more": bool(r.get("more"))}
        except Exception as e:
            log(f"phone_media_list error: {type(e).__name__}")
            return {"ok": False, "error": "exception"}

    # ---- 폰 사진 '복사': 가져오기와 같은 길로 받고, 다 받으면 그 파일들을 클립보드에 파일로 올린다(붙여넣기는 Ctrl+V)
    COPY_WAIT = 180.0                   # 이 시간 안에 다 오지 않으면 온 것만 복사한다

    def _copy_begin(self):
        job = {"n": None, "paths": [], "failed": 0, "done": False, "timer": None}
        with self._copy_lock:
            old, self._copy_job = self._copy_job, job
        if old is not None and old.get("timer") is not None:
            old["timer"].cancel()
        t = threading.Timer(self.COPY_WAIT, lambda: self._copy_finish(job))
        t.daemon = True
        job["timer"] = t
        t.start()
        return job

    def _copy_cancel(self, job):
        with self._copy_lock:
            job["done"] = True
            if self._copy_job is job:
                self._copy_job = None
        if job.get("timer") is not None:
            job["timer"].cancel()

    def _copy_set_count(self, job, n):
        """폰이 보내기 시작한 파일 수를 알았다(그 사이 먼저 온 파일이 있을 수 있다)."""
        job["n"] = int(n)
        self._copy_check(job)

    def _copy_on_file(self, ev):
        """파일 전송 이벤트를 본다: 복사 중이면 받은 파일 경로를 모은다."""
        job = self._copy_job
        if job is None or job["done"] or ev.get("dir") != "in":
            return
        st = ev.get("state")
        fid = ev.get("fid")
        seen = job.setdefault("seen", set())
        if st not in ("done", "failed", "canceled") or (fid is not None and fid in seen):
            return          # 진행 중 이벤트이거나 이미 센 전송의 끝 이벤트
        if fid is not None:
            seen.add(fid)
        if st == "done" and ev.get("path"):
            job["paths"].append(ev["path"])
        else:
            job["failed"] += 1
        self._copy_check(job)

    def _copy_check(self, job):
        if job["n"] is not None and len(job["paths"]) + job["failed"] >= job["n"]:
            self._copy_finish(job)

    def _copy_finish(self, job):
        with self._copy_lock:
            if job["done"]:
                return
            job["done"] = True
            if self._copy_job is job:
                self._copy_job = None
        if job.get("timer") is not None:
            job["timer"].cancel()
        n = 0
        if job["paths"] and clipfiles is not None:
            try:
                n = int(clipfiles.write_files(job["paths"]))
            except Exception as ex:
                log(f"phone copy failed: {type(ex).__name__}")
        total = job["n"] if job["n"] is not None else len(job["paths"]) + job["failed"]
        log(f"phone copy: {n} of {total} files put on the clipboard")
        self._push_event({"type": "phone_copy", "ok": n > 0, "n": n, "total": total})

    def phone_media_pull(self, items, copy=False):
        """고른 사진·동영상(최대 20개)을 폰에서 가져온다(진행은 phone_file 이벤트). copy=True 면 다 받은 뒤 클립보드에 파일로 복사한다(phone_copy 이벤트). -> {ok, started, error}"""
        job = None
        try:
            clean = []
            for it in (items if isinstance(items, (list, tuple)) else [])[:20]:
                if isinstance(it, dict) and it.get("k") in ("i", "v"):
                    try:
                        clean.append({"id": int(it["id"]), "k": it["k"]})
                    except (TypeError, ValueError, KeyError):
                        pass
            if not clean:
                return {"ok": False, "error": "none", "started": 0}
            self._file_mgr()
            self._pull_until = time.time() + 30
            if copy:
                job = self._copy_begin()
            r, err = self._link_command({"t": "media_pull", "items": clean}, "media_pull_result", timeout=15)
            if r is None:
                if job is not None:
                    self._copy_cancel(job)
                return {"ok": False, "error": err, "started": 0}
            started = int(r.get("started") or 0)
            if job is not None:
                if bool(r.get("ok")) and started > 0:
                    self._copy_set_count(job, started)
                else:
                    self._copy_cancel(job)
            return {"ok": bool(r.get("ok")), "error": str(r.get("error", "")), "started": started}
        except Exception as e:
            log(f"phone_media_pull error: {type(e).__name__}")
            if job is not None:
                self._copy_cancel(job)
            return {"ok": False, "error": "exception", "started": 0}

    # ---- 폰에서 이 PC 조작: 허용 목록에 있는 동작만, 설정에서 켰을 때만(종료·다시 시작·로그아웃은 넣지 않았다)
    PC_CMDS = ("status", "prev", "toggle", "next", "vol_down", "vol_up", "mute", "lock", "screen_off", "sleep")

    def _on_pc_cmd(self, e):
        rid = str(e.get("rid", ""))
        cmd = str(e.get("cmd", ""))
        dev = e.get("device")
        def reply(ok, err="", **extra):
            if self._link is not None and dev is not None:
                self._link.send(dev, dict({"t": "pc_result", "rid": rid, "ok": bool(ok), "error": err}, **extra))

        def snapshot():
            """폰 화면에 보여 줄 지금 상태: 재생 중인지, 볼륨, 음소거."""
            try:
                with self._lock:
                    playing = bool(self._last_state.get("isPlaying"))
                m = audiomix.master_get() or {}
                return {"playing": playing, "vol": int(round(float(m.get("volume", 0)) * 100)), "muted": bool(m.get("muted"))}
            except Exception:
                return {}
        if not self._prefs.get("linkRemote"):
            return reply(False, "off")
        if cmd not in self.PC_CMDS:
            return reply(False, "unknown")
        ok = False
        try:
            if cmd == "status":
                return reply(True, "", **snapshot())
            if cmd in ("prev", "toggle", "next"):
                self.media_action(cmd)
                ok = True
            elif cmd == "vol_up":
                ok = audiomix.master_step(0.05) is not None
            elif cmd == "vol_down":
                ok = audiomix.master_step(-0.05) is not None
            elif cmd == "mute":
                ok = sysctl.volume_toggle_mute() is not None
            elif cmd == "lock":
                ok = bool(sysctl.power("lock"))
            elif cmd == "screen_off":
                ok = bool(sysctl.power("screenoff"))
            elif cmd == "sleep":
                ok = bool(sysctl.power("sleep"))
        except Exception as ex:
            log(f"pc command {cmd} failed: {type(ex).__name__}")
        log(f"pc command from the phone: {cmd} {'ok' if ok else 'failed'}")
        time.sleep(0.25)                                              # 바뀐 상태를 읽을 시간
        reply(ok, "" if ok else "failed", **snapshot())

    # ---- 폰 앱별로 노치에 띄울지 고른다(설정 › Dalu Link): 알림을 한 번이라도 보낸 앱이 목록에 생긴다
    def _phone_apps_file(self):
        return os.path.join(ISLAND_DIR, "phone_apps.json")

    def _phone_apps_off(self):
        return {x.strip() for x in str(self._prefs.get("phoneNotifyOff") or "").split(",") if x.strip()}

    def _phone_apps_on(self):
        return {x.strip() for x in str(self._prefs.get("phoneNotifyOn") or "").split(",") if x.strip()}

    def _phone_notify_allowed(self, pkg, imp=None):
        """이 폰 알림을 노치에 띄울까. 표시 방식 all: 끈 앱만 뺀다 / picked: 고른 앱만. '소리·진동 없는 알림 제외'는 안드로이드 중요도 1·2(최소·낮음)를 거른다."""
        if self._prefs.get("phoneNotifyQuiet") and isinstance(imp, int) and not isinstance(imp, bool) and imp in (1, 2):
            return False
        if self._prefs.get("phoneNotifyMode") == "picked":
            return pkg in self._phone_apps_on()
        return pkg not in self._phone_apps_off()

        if pkg in self._snoozed():
            return False          # 임시 차단 중인 앱
    def _link_filter_msg(self):
        return {"t": "notif_filter", "mode": "picked" if self._prefs.get("phoneNotifyMode") == "picked" else "all",
                "on": sorted(self._phone_apps_on() - self._snoozed())[:400], "off": sorted(self._phone_apps_off() | self._snoozed())[:400], "quiet": bool(self._prefs.get("phoneNotifyQuiet"))}

    def _link_push_filter(self, force=False):
        """알림 거르기 설정을 연결된 폰에 보낸다(바뀌었을 때만). 폰은 거른 앱의 알림 내용을 PC 로 아예 보내지 않는다."""
        try:
            s = self._link
            if s is None:
                return
            msg = self._link_filter_msg()
            sig = json.dumps(msg, sort_keys=True)
            if not force and sig == getattr(self, "_filter_sig", None):
                return
            ids = s.connected_ids()
            if not ids:
                return
            self._filter_sig = sig
            for i in ids:
                s.send(i, msg)
        except Exception as ex:
            log(f"link filter push failed: {type(ex).__name__}")

    def _save_phone_apps(self):
        try:
            path = self._phone_apps_file()
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(dict(self._phone_apps), f, ensure_ascii=False)
            os.replace(tmp, path)          # 쓰는 도중 꺼져도 기존 파일이 깨지지 않게 교체 방식으로
        except Exception:
            pass

    def _note_phone_app(self, pkg, app, initial):
        """알림을 보낸 앱의 이름과 횟수만 기억한다(알림 내용은 기억하지 않는다)."""
        if not self._phone_apps_loaded:          # 저장된 목록을 먼저 읽는다(pkg 가 빈 '읽기만' 호출도 여기까지는 와야 한다)
            self._phone_apps_loaded = True
            try:
                with open(self._phone_apps_file(), encoding="utf-8") as f:
                    d = json.load(f)
                if isinstance(d, dict):
                    for k, v in d.items():
                        if isinstance(v, dict) and re.fullmatch(r"[A-Za-z0-9._-]+", str(k)):
                            self._phone_apps[str(k)] = {"name": str(v.get("name", ""))[:60], "count": int(v.get("count") or 0)}
            except Exception:
                pass
        if not pkg or len(pkg) > 120 or not re.fullmatch(r"[A-Za-z0-9._-]+", pkg):
            return
        ent = self._phone_apps.get(pkg)
        changed = False
        if ent is None:
            if len(self._phone_apps) >= 600:
                return
            ent = self._phone_apps[pkg] = {"name": app[:60] or pkg, "count": 0}
            changed = True
        if app and ent.get("name") != app[:60]:
            ent["name"] = app[:60]
            changed = True
        if not initial:
            ent["count"] = int(ent.get("count", 0)) + 1
            if ent["count"] % 5 == 1:
                changed = True
        if changed:                                                   # 바뀐 게 있을 때만 쓴다(전에는 폰이 다시 연결될 때마다 떠 있는 알림 수만큼 파일을 다시 썼다)
            self._save_phone_apps()

    def phone_notify_apps(self):
        """설정 화면용: 폰에서 알림을 보낸 앱 목록 [{pkg, name, count}] (횟수 순)."""
        try:
            self._note_phone_app("", "", True)          # 파일에서 읽어 둔다(패키지가 비어 있으면 아무것도 더하지 않는다)
            out = [{"pkg": k, "name": v.get("name") or k, "count": int(v.get("count") or 0)} for k, v in list(self._phone_apps.items())]          # 복사본: 그 사이 알림이 와서 목록이 늘어도 안전하게
            out.sort(key=lambda x: (-x["count"], x["name"].lower()))
            return {"apps": out[:600]}
        except Exception as e:
            log(f"phone_notify_apps error: {type(e).__name__}")
            return {"apps": []}

    def phone_notify_app_set(self, pkg, show):
        """노치 알림 카드의 '이 앱 끄기'(또는 다시 켜기): 지금 표시 방식에 맞는 목록(모든 앱 -> 끈 앱, 고른 앱만 -> 켠 앱)에서 이 앱을 빼거나 넣고 저장한다. -> {ok, app}"""
        try:
            pkg = str(pkg or "")
            if not pkg or len(pkg) > 120 or not re.fullmatch(r"[A-Za-z0-9._-]+", pkg):
                return {"ok": False, "error": "pkg"}
            picked = self._prefs.get("phoneNotifyMode") == "picked"
            key = "phoneNotifyOn" if picked else "phoneNotifyOff"
            cur = set(self._phone_apps_on() if picked else self._phone_apps_off())
            if bool(show) == picked:                        # 고른 앱만: 켜려면 목록에 넣는다 / 모든 앱: 끄려면 목록에 넣는다
                cur.add(pkg)
            else:
                cur.discard(pkg)
            res = self.settings_patch({"settings": {key: ",".join(sorted(cur))}})
            self._note_phone_app("", "", True)
            name = str((self._phone_apps.get(pkg) or {}).get("name") or pkg)
            return {"ok": res.get("status") == "ok", "app": name}
        except Exception as e:
            log(f"phone_notify_app_set error: {type(e).__name__}")
            return {"ok": False, "error": "exception"}

    def phone_fetch_apps(self):
        """설정에서 '폰의 앱 불러오기': 폰에 설치된(실행할 수 있는) 앱의 이름을 받아 목록에 더한다. 이름과 패키지 이름만 받는다. -> {ok, added, apps}"""
        try:
            r, err = self._link_command({"t": "apps_list"}, "apps_result", timeout=20)
            if r is None:
                return {"ok": False, "error": err, "apps": []}
    # ---- 앱 알림 임시 차단(노치 알림 카드의 1시간·6시간·24시간): 시간이 지나면 저절로 풀린다. 폰에도 알려서 차단 중에는 내용이 PC 로 오지 않는다
    SNOOZE_HOURS = (1, 6, 24)

    def _snooze_file(self):
        return os.path.join(ISLAND_DIR, "phone_snooze.json")

    def _snooze_load(self):
        if self._snooze_loaded:
            return
        self._snooze_loaded = True
        try:
            with open(self._snooze_file(), encoding="utf-8") as f:
                d = json.load(f)
            if isinstance(d, dict):
                for k, v in d.items():
                    if re.fullmatch(r"[A-Za-z0-9._-]+", str(k)) and isinstance(v, (int, float)) and not isinstance(v, bool):
                        self._snooze[str(k)] = float(v)
        except Exception:
            pass
        self._snooze_arm()

    def _snooze_save(self):
        try:
            path = self._snooze_file()
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(dict(self._snooze), f)
            os.replace(tmp, path)
        except Exception:
            pass

    def _snoozed(self):
        """지금 차단 중인 앱의 패키지 모음(시간이 지난 것은 버린다)."""
        self._snooze_load()
        now = time.time()
        gone = [k for k, v in list(self._snooze.items()) if v <= now]
        for k in gone:
            self._snooze.pop(k, None)
        if gone:
            self._snooze_save()
        return set(self._snooze)

    def _snooze_arm(self):
        """가장 먼저 풀리는 앱 시각에 맞춰 타이머를 다시 건다(풀리면 폰에 거르기 설정을 다시 보낸다)."""
        t, self._snooze_timer = self._snooze_timer, None
        if t is not None:
            t.cancel()
        if not self._snooze:
            return
        wait = max(1.0, min(self._snooze.values()) - time.time() + 1.0)
        t = threading.Timer(min(wait, 25 * 3600.0), self._snooze_tick)
        t.daemon = True
        self._snooze_timer = t
        t.start()

    def _snooze_tick(self):
        self._snooze_timer = None
        self._snoozed()
        self._link_push_filter()
        self._snooze_arm()

    def phone_notify_snooze(self, pkg, hours):
        """노치 알림 카드의 '1시간·6시간·24시간 차단': 이 앱의 알림을 그 시간 동안 띄우지 않는다. -> {ok, app, until}"""
        try:
            pkg = str(pkg or "")
            if not pkg or len(pkg) > 120 or not re.fullmatch(r"[A-Za-z0-9._-]+", pkg):
                return {"ok": False, "error": "pkg"}
            try:
                h = int(hours)
            except (TypeError, ValueError):
                return {"ok": False, "error": "hours"}
            if isinstance(hours, (bool, float)) and hours != h or h not in self.SNOOZE_HOURS:          # 1.5 같은 값은 정수로 잘려 받아들여지지 않게
                return {"ok": False, "error": "hours"}
            self._snooze_load()
            until = time.time() + h * 3600.0
            self._snooze[pkg] = until
            self._snooze_save()
            self._snooze_arm()
            self._link_push_filter()
            name = str((self._phone_apps.get(pkg) or {}).get("name") or pkg)
            return {"ok": True, "app": name, "until": until}
        except Exception as e:
            log(f"phone_notify_snooze error: {type(e).__name__}")
            return {"ok": False, "error": "exception"}

            self._note_phone_app("", "", True)                # 파일에서 읽어 둔다
            added = 0
            for it in (r.get("apps") if isinstance(r.get("apps"), list) else [])[:600]:
                if not isinstance(it, dict):
                    continue
                pkg, name = str(it.get("pkg", "")), str(it.get("name", ""))[:60]
                if not pkg or len(pkg) > 120 or not re.fullmatch(r"[A-Za-z0-9._-]+", pkg):
                    continue
                ent = self._phone_apps.get(pkg)
                if ent is None:
                    if len(self._phone_apps) >= 600:
                        continue
                    self._phone_apps[pkg] = {"name": name or pkg, "count": 0}
                    added += 1
                elif name and ent.get("name") != name:
                    ent["name"] = name
            self._save_phone_apps()
            log(f"phone apps: {len(self._phone_apps)} known ({added} new)")
            out = self.phone_notify_apps()
            return {"ok": True, "added": added, "apps": out["apps"]}
        except Exception as e:
            log(f"phone_fetch_apps error: {type(e).__name__}")
            return {"ok": False, "error": "exception", "apps": []}

    def phone_sms_threads(self):
        """폰의 최근 문자 대화 목록(최대 20개). -> {ok, error, threads:[{tid, addr, name, snip, t, unread, out}]}"""
        try:
            r, err = self._link_command({"t": "sms_threads"}, "sms_result", timeout=15)
            if r is None:
                return {"ok": False, "error": err, "threads": []}
            out = []
            for it in (r.get("threads") if isinstance(r.get("threads"), list) else [])[:20]:
                if not isinstance(it, dict):
                    continue
                try:
                    out.append({"tid": int(it["tid"]), "addr": str(it.get("addr", ""))[:40], "name": str(it.get("name", ""))[:80], "snip": str(it.get("snip", ""))[:80],
                                "t": int(it.get("t") or 0), "unread": max(0, int(it.get("unread") or 0)), "out": bool(it.get("out"))})
                except (TypeError, ValueError, KeyError):
                    continue
            log(f"sms threads: {len(out)}")
            return {"ok": bool(r.get("ok")), "error": str(r.get("error", "")), "threads": out}
        except Exception as e:
            log(f"phone_sms_threads error: {type(e).__name__}")
            return {"ok": False, "error": "exception", "threads": []}

    def phone_sms_messages(self, tid):
        """한 대화의 최근 메시지(오래된 것부터). -> {ok, error, addr, name, messages:[{id, out, body, t}]}"""
        try:
            try:
                tid = int(tid)
            except (TypeError, ValueError):
                return {"ok": False, "error": "tid", "messages": []}
            r, err = self._link_command({"t": "sms_messages", "tid": tid}, "sms_result", timeout=15)
            if r is None:
                return {"ok": False, "error": err, "messages": []}
            out = []
            for it in (r.get("messages") if isinstance(r.get("messages"), list) else [])[:60]:
                if isinstance(it, dict):
                    try:
                        out.append({"id": int(it.get("id") or 0), "out": bool(it.get("out")), "body": str(it.get("body", ""))[:2000], "t": int(it.get("t") or 0)})
                    except (TypeError, ValueError):
                        continue
            log(f"sms messages: {len(out)}")
            return {"ok": bool(r.get("ok")), "error": str(r.get("error", "")), "addr": str(r.get("addr", ""))[:40], "name": str(r.get("name", ""))[:80], "messages": out}
        except Exception as e:
            log(f"phone_sms_messages error: {type(e).__name__}")
            return {"ok": False, "error": "exception", "messages": []}

    def phone_sms_send(self, to, text):
        """폰으로 문자를 보낸다(번호는 숫자와 맨 앞 + 만, 글은 1000자까지). -> {ok, error}"""
        try:
            n = self._clean_number(to)
            if n is None:
                return {"ok": False, "error": "number"}
            text = str(text or "").strip()
            if not text or len(text) > 1000:
                return {"ok": False, "error": "text"}
            r, err = self._link_command({"t": "sms_send", "to": n, "text": text}, "sms_result", timeout=15)
            if r is None:
                return {"ok": False, "error": err}
            log(f"sms send: {'ok' if r.get('ok') else 'failed ' + str(r.get('error', ''))} ({len(text)} chars)")
            return {"ok": bool(r.get("ok")), "error": str(r.get("error", ""))}
        except Exception as e:
            log(f"phone_sms_send error: {type(e).__name__}")
            return {"ok": False, "error": "exception"}

    def phone_pick_files(self):
        """파일 선택 창을 열어 고른 파일을 폰으로 보낸다."""
        try:
            if not webview.windows:
                return {"ok": False, "error": "nowindow"}
            res = webview.windows[0].create_file_dialog(webview.OPEN_DIALOG, allow_multiple=True)
            if not res:
                return {"ok": False, "error": "none", "started": 0}
            return self.phone_send_files(list(res))
        except Exception as e:
            log(f"phone_pick_files error: {type(e).__name__}")
            return {"ok": False, "error": "exception"}

    def phone_file_cancel(self, fid):
        m = self._files
        return {"ok": bool(m and m.cancel(str(fid)))}

    def phone_file_open(self, path, folder=False):
        """폰에서 받은 파일(또는 그 폴더)을 연다. 이 앱이 받은 파일의 경로만 열 수 있다."""
        try:
            p = os.path.normcase(os.path.abspath(str(path or "")))
            if p not in self._file_paths or not os.path.exists(p):
                return {"ok": False, "error": "unknown"}
            if folder:
                subprocess.Popen(["explorer", "/select,", os.path.abspath(str(path))])
            else:
                os.startfile(os.path.abspath(str(path)))
            return {"ok": True}
        except Exception as e:
            log(f"phone_file_open error: {type(e).__name__}")
            return {"ok": False, "error": "exception"}

    def phone_file_folder(self):
        """받은 파일 폴더를 연다."""
        try:
            d = self._file_folder()
            os.makedirs(d, exist_ok=True)
            os.startfile(d)
            return {"ok": True}
        except Exception as e:
            log(f"phone_file_folder error: {type(e).__name__}")
            return {"ok": False, "error": "exception"}

    def phone_ack_missed(self):
        """사용자가 부재중 표시를 봤다."""
        self._link_info["missed_ack"] = int(self._link_info.get("missed") or 0)          # 본 것으로 친다(폰의 통화 기록은 건드리지 않는다)
        return {"ok": True}

    def winnotif_apps(self):
        """설정 창용: 알림을 보낸 적 있는 앱 목록(최근 순)과 지금 무시되는지. 알림 내용은 없다."""
        try:
            if self._winnotif is None:
                return {"apps": [], "status": "unavailable"}
            return {"apps": winnotif.list_apps(self._winnotif.apps, self._prefs.get("winNotifyIgnore")), "status": self._winnotif.status}
        except Exception as e:
            log(f"winnotif_apps error: {e!r}")
            return {"apps": [], "status": "error"}

    def release_click_through(self):
        """트레이 메뉴에서 클릭 투과를 끈다(노치가 클릭을 받지 못하는 상태에서도 빠져나올 수 있는 길)."""
        self.toggle_click_through(False)
        try:
            if webview.windows:
                webview.windows[0].evaluate_js("onClickThroughReleased()")
        except Exception as e:
            log(f"release_click_through: {e!r}")

    def _click_through_watcher(self):
        """클릭 투과 중에는 창이 마우스 입력을 전혀 받지 못해 우클릭 메뉴로 해제할 방법이 없다.
        그래서 창 위에 커서를 올리고 Ctrl 을 누르면 해제되도록 한다."""
        user32 = ctypes.windll.user32
        VK_CONTROL = 0x11
        pt = wintypes.POINT()
        rc = wintypes.RECT()
        while self._running and self._click_through:
            try:
                if user32.GetAsyncKeyState(VK_CONTROL) & 0x8000:
                    hwnd = self._get_hwnd()
                    if (hwnd and user32.GetCursorPos(ctypes.byref(pt))
                            and user32.GetWindowRect(hwnd, ctypes.byref(rc))
                            and rc.left <= pt.x < rc.right and rc.top <= pt.y < rc.bottom):
                        self.toggle_click_through(False)
                        if webview.windows:
                            webview.windows[0].evaluate_js("onClickThroughReleased()")
                        log("Click-through released via Ctrl+hover.")
                        return
            except Exception as e:
                log(f"click-through watcher error: {e!r}")
            time.sleep(0.1)

    def close_app(self):
        log("close_app() called. Exiting...")
        self._running = False
        try:
            dnd.disable(DND_STATE_FILE)          # 집중 중에 종료해도 방해 금지에 갇히지 않게
        except Exception:
            pass
        try:
            self._call_media_end()               # 통화 중에 종료해도 줄여 둔(또는 멈춘) 다른 앱의 소리를 되돌린다
        except Exception:
            pass
        try:
            self._mirror_set_state({"state": "stopped", "why": "quit"})
            if getattr(self, "_mirror", None) is not None:
                self._mirror.stop()
        except Exception:
            pass
        try:
            if self._files is not None:
                self._files.link_lost()          # 받는 중이던 파일 조각을 정리한다(종료해도 .part 가 남지 않게)
        except Exception:
            pass
        self._monitor.stop()
        if getattr(self, "_tray", None) is not None:
            self._tray.stop()
        for svc in (self._clipwatch,):
            try:
                svc.stop()
            except Exception:
                pass
        if self._levels is not None:
            self._levels.stop()
        if self._buds is not None:
            self._buds.stop()
        if self._bt is not None:
            self._bt.stop()
        try:
            if webview.windows:
                webview.windows[0].destroy()
        except Exception:
            pass
        os._exit(0)

_instance_handle = None

def ensure_icon():
    """앱 아이콘(appicon.py)을 .ico 파일로 만들어 둔다. 이미 있고 appicon.py 보다 새로우면 다시 만들지 않는다. 실패하면 None."""
    try:
        src = os.path.join(BASE_DIR, "appicon.py")
        if os.path.exists(ICON_FILE) and os.path.exists(src) and os.path.getmtime(ICON_FILE) >= os.path.getmtime(src):
            return ICON_FILE
        import appicon
        appicon.save_ico(ICON_FILE)
        return ICON_FILE
    except Exception as e:
        log(f"ensure_icon failed: {e!r}")
        return None


INSTANCE_MUTEX = os.environ.get("DALU_INSTANCE_MUTEX") or r"Local\Dalu.SingleInstance"      # 환경변수는 설치본을 이미 켜 둔 앱과 나란히 시험할 때만 쓴다

def acquire_single_instance(wait=0.0, name=INSTANCE_MUTEX):
    """이미 실행 중인 노치가 있으면 False. wait 초 동안 기다려 본다(재시작 직후 옛 프로세스가 끝나기를 기다릴 때)."""
    global _instance_handle
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p]
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    deadline = time.time() + wait
    while True:
        h = kernel32.CreateMutexW(None, False, name)
        already = ctypes.get_last_error() == 183          # ERROR_ALREADY_EXISTS
        if h and not already:
            _instance_handle = h
            return True
        if h:
            kernel32.CloseHandle(h)
        if time.time() >= deadline:
            return False
        time.sleep(0.25)


def main():
    try:        # 작업 표시줄이 이 프로그램을 'python' 이 아니라 Dalu 로 묶어 보여 주게 한다
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Dalu.Notch")
    except Exception:
        pass
    if not acquire_single_instance(wait=8.0):
        log("Another instance is already running; exiting.")
        return
    log("Initializing CiderClient...")
    client = CiderClient()
    api = IslandAPI(client)

    primary = IslandAPI._primary_screen()

    # 선택한 모니터(기본: 식별 번호 2)의 가로 가운데, 맨 위. 좌표는 논리 픽셀로 바꿔 넘긴다.
    # 프레임 없는 창의 실제 크기/위치는 뜬 직후 recenter_window 가 물리 픽셀로 정확히 맞춘다.
    mon = api._target_monitor()
    scale = api._get_scale()      # 시작 위치는 UI 크기 1.0 기준으로 만들고, 뜬 직후 apply_ui_scale 이 실제 배율로 맞춘다
    if mon:
        x_center = int(monitors.placed_x(mon, int(EXPANDED_WIDTH * scale), api._prefs.get("notchPos"), scale) / scale)
        y_center = int(mon["top"] / scale)
        log(f"Target monitor {mon['number']} ({mon['device']}): {mon['width']}x{mon['height']} at ({mon['left']}, {mon['top']}); window x={x_center}, y={y_center}")
    else:
        x_center = (primary.width - EXPANDED_WIDTH) // 2
        y_center = 0
        log(f"Centered window coordinates (screen_width={primary.width}): x={x_center}, y={y_center}")

    # 실행 중인 스크립트 옆의 index.html 을 사용 (as_uri 가 공백/한글 경로를 퍼센트 인코딩)
    html_url = Path(BASE_DIR, 'index.html').as_uri()

    log("Creating frameless, transparent, on_top webview window at center...")
    w = webview.create_window(
        title="Dalu",
        url=html_url,
        js_api=api,
        width=EXPANDED_WIDTH,
        height=EXPANDED_HEIGHT,
        x=x_center,
        y=y_center,
        frameless=True,
        easy_drag=False,      # 노치는 끌어서 옮기지 못한다 (위치는 모니터 위쪽 가운데로 고정)
        transparent=True,
        on_top=True
    )

    def on_shown():
        time.sleep(0.3)
        api.hide_from_taskbar()
        api._set_window_icon(w)
        # pywebview 는 프레임 없는 창을 요청 크기보다 작게(DPI 150% 에서 높이 ~37px, 폭 ~14px) 만들고,
        # 그래서 노치가 화면 정중앙에서 벗어난다. 뜬 직후 실제 크기/위치를 정확히 맞춘다.
        api.apply_ui_scale()
        api.collapse_window()
        api._apply_desk()

    w.events.shown += on_shown

    if tray is not None:
        try:
            api._tray = tray.Tray(on_settings=api.open_settings, on_restart=api.restart_app, on_quit=api.close_app,
                                  get_lang=lambda: api._prefs.get("lang"), log=log,
                                  ct_active=lambda: api._click_through, on_ct_off=api.release_click_through)
            api._tray.start()
            log("Tray icon started.")
        except Exception as e:
            log(f"tray start failed: {e!r}")

    def on_loaded():
        api._apply_zoom()
        # 파일 드롭: 탐색기에서 끌어온 파일의 전체 경로는 pywebview DOM 이벤트로만 받을 수 있다
        try:
            from webview.dom import DOMEventHandler
            w.dom.document.events.drop += DOMEventHandler(api._on_files_dropped, prevent_default=True)
            # dragover 는 일부러 파이썬에 등록하지 않는다: 드래그하는 동안 수십 번/초 발생해, 매번 브리지를 타면
            # 화면이 ~10fps 로 떨어진다(실측). 기본 동작 방지는 JS(features.js initFileDrag)에서 한다.
            log("File drop handlers registered.")
        except Exception as e:
            log(f"drop handler registration failed: {e!r}")

    w.events.loaded += on_loaded

    log("Starting webview event loop...")
    webview.start()
    log("Webview closed.")

if __name__ == '__main__':
    main()
