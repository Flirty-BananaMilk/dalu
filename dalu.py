# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Flirty_BananaMilk — 상업적 이용 금지, 자세한 내용은 LICENSE
import os
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
import monitors
import audiomix
import hotkeys
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
    import winnotif
except Exception:      # 없어도 앱은 돌아간다 (윈도우 알림 표시만 빠진다)
    winnotif = None
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
EXPANDED_WIDTH = 740
EXPANDED_HEIGHT = 200
NOTCH_WIDTH = 300   # 접힌(mini) 노치
NOTCH_HEIGHT = 32

POLL_INTERVAL = 0.25   # Cider 폴링 주기(초). 사이 시간은 오디오 시계 투영으로 채움
POLL_BOOST_INTERVAL = 0.05   # 재생 컨트롤을 누른 직후 잠시 이 주기로 폴링해 결과가 바로 반영되게 한다
BOOST_SECONDS = 2.0
MISS_LIMIT = 3         # 연속 N번 응답이 없어야 '정지'로 판단 (일시적 타임아웃 깜빡임 방지)
LYRICS_RETRY_DELAYS = (0, 0.5, 1, 2, 3, 5, 8, 10)  # 가사 조회 재시도 간격(초), 총 약 30초
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

APP_VERSION = "1.0.0"   # 배포 버전(MAJOR.MINOR.PATCH). 올릴 때는 CHANGELOG.md 에 같은 버전의 항목을 먼저 쓴다 (installer/build_release.py 가 확인)
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
        self._running = True
        self._misses = 0

        # 시스템 이벤트(볼륨/Caps Lock/충전기 등) 큐. 프론트가 get_state 때 한꺼번에 가져간다.
        self._events = []
        self._events_lock = threading.Lock()
        self._fullscreen = False
        self._prefs = prefs.Prefs(self.load_data())     # 파이썬이 읽는 설정 사본 (설정 창/화면이 바꾸면 갱신)
        self._settings_win = None
        self._settings_lock = threading.Lock()
        self._data_lock = threading.Lock()
        self._monitor = sysmon.SysMonitor(push=self._push_event, on_fullscreen=self._on_fullscreen,
                                         own_hwnd=self._get_hwnd)
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
        self._clipwatch = clipwatch.ClipWatcher(self._clip, log=log)
        self._clipwatch.start()
        # 캘린더(.ics)
        self._cal = calendar_ics.CalendarSource()
        self._cal_notified = set()
        threading.Thread(target=self._calendar_worker, daemon=True, name="calendar").start()
        # 전역 단축키
        self._hotkeys = hotkeys.HotkeyService({"hkToggle": self._hk_toggle, "hkSettings": lambda: self.open_settings(),
                                               "hkMixer": lambda: self.open_settings("mixer"), "hkLyrics": self._hk_lyrics,
                                               "hkCapture": lambda: self.capture_toggle()}, log=log)
        self._hotkeys.start()
        self._next_for, self._next_at = None, 0.0
        self._desk = deskcap.DeskCapture(self._get_hwnd, self._desk_rect, self._desk_push, log=log)
        self._winnotif = None
        if winnotif is not None:
            self._winnotif = winnotif.NotificationWatch(lambda apps: self._push_event({"type": "win_notify", "apps": list(apps)[:8]}),
                                                        enabled=lambda: bool(self._prefs.get("winNotify")), log=log,
                                                        ignore=lambda: self._prefs.get("winNotifyIgnore"),
                                                        store_path=os.path.join(ISLAND_DIR, "winnotif_apps.json"),
                                                        on_clear=lambda why: self._push_event({"type": "win_notify_clear", "why": why}))
            self._winnotif.start()
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
        try:
            user32 = ctypes.windll.user32
            phys_w = user32.GetSystemMetrics(0)
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
        hrgn_top = gdi32.CreateRectRgn(left, 0, right, int(18 * dpr))
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
        if self._is_playing and duration > 0:
            return min(duration, self._anchor_time + (time.perf_counter() - self._anchor_perf))
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
            self._last_state["next"] = nxt

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
        cider = self._cider_pb
        cider_has = bool(cider and cider.get("title"))
        if self._forced_source == "cider" and not cider_has or self._forced_source == "smtc" and not other:
            self._forced_source = None                      # 직접 고른 소스에 곡이 없어졌다: 자동 선택으로 돌아간다
        if self._forced_source:
            src = self._forced_source
        elif smtc is not None:
            src = smtc.choose_source(cider_has, bool(cider and cider.get("isPlaying")),
                                     bool(other), bool(other and other["isPlaying"]), self._source,
                                     self._prefs.get("mediaPriority"))
        else:
            src = "cider"
        sources = []
        if cider_has:
            sources.append({"id": "cider", "name": "Cider", "playing": bool(cider.get("isPlaying"))})
        if other:
            sources.append({"id": "smtc", "name": other.get("appName") or "Media", "playing": bool(other.get("isPlaying"))})
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
        elif src == "cider" and cider:
            self._apply_playback(cider)
            if self._prefs.get("upNext") and hasattr(self._client, "get_up_next"):
                self._refresh_up_next(cider.get("trackId"))
        elif self._last_state.get("source") == "smtc":
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
        if track_changed and pb.get("source") == "smtc":
            # Cider 가 아닌 앱의 곡: Cider 가사 API 는 쓸 수 없으니 외부 가사 서비스(NetEase, LRCLIB)에서 직접 찾는다
            log(f"Track changed: {title} - {artist} [{pb.get('appName')}] -> searching external lyrics")
            threading.Thread(target=self._external_lyrics_worker,
                             args=(t_id, title, artist, pb.get("album", ""), duration),
                             daemon=True, name="ext-lyrics").start()
        elif track_changed:
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
            if track_changed or (raw_cur_time != self._last_raw_time) or (is_playing != self._is_playing):
                self._last_raw_time = raw_cur_time
                self._anchor_time = raw_cur_time
                self._anchor_perf = now_perf
                self._is_playing = is_playing

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
        for i, delay in enumerate(delays):
            if not self._wait_on_track(track_id, delay):
                return
            result = self._try_lyrics(track_id, title, artist, catalog_id, has_lyrics, last=(i == len(delays) - 1))
            if result == "ok":
                return
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

    def buds_set_game_mode(self, on):
        """게이밍 모드(저지연) 켜기/끄기."""
        if self._buds is None:
            return {"status": "error", "message": "buds unavailable"}
        try:
            return self._buds.set_game_mode(bool(on))
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
            if hwnd:
                ctypes.windll.user32.ShowWindow(hwnd, SW_SHOWNOACTIVATE if visible else SW_HIDE)
        except Exception as e:
            log(f"_show_window error: {e!r}")

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
            ctypes.windll.user32.SetWindowPos(
                hwnd, HWND_NOTOPMOST if yielded else HWND_TOPMOST, 0, 0, 0, 0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)
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
                    return data
            if not os.path.exists(DATA_FILE):
                return {"settings": {"lang": self._system_lang()}}        # 처음 실행: 저장된 설정이 없다
        except Exception as e:
            log(f"load_data error: {e!r}")
        return {}

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
                if "launcher" not in data:
                    keep = self.load_data().get("launcher")
                    if keep is not None:
                        data["launcher"] = keep
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
            self._clipwatch.enabled = bool(self._prefs.get("clipboardOn"))
            self._cal.set_source(self._prefs.get("calendarUrl"))
            self._hotkeys.set_bindings({k: self._prefs.get(k) for k in ("hkToggle", "hkSettings", "hkMixer", "hkLyrics", "hkCapture")},
                                       bool(self._prefs.get("hotkeysOn")))
            if self._smtc is not None and smtc is not None:
                self._smtc.filter_mode = self._prefs.get("appFilterMode")
                self._smtc.filter_names = smtc.parse_filter_list(self._prefs.get("appFilterList"))
            self._apply_desk()
            if getattr(self, "_mon_key", None) is not None and abs(self._ui_scale() - getattr(self, "_ui_scale_applied", 1.0)) > 1e-6:
                threading.Thread(target=self.apply_ui_scale, daemon=True, name="ui-scale").start()
            if getattr(self, "_mon_key", None) is not None:      # 창이 이미 자리 잡은 뒤에만 (시작 중에는 on_shown 이 놓는다)
                key = monitors.monitor_key(self._target_monitor())
                if key != self._mon_key:
                    threading.Thread(target=self.recenter_window, daemon=True, name="move-notch").start()
        except Exception as e:
            log(f"_apply_prefs error: {e!r}")

    # ------------------------------------------------------------------
    # 노치 본체 유리(glassNotch = full): 노치 뒤의 화면을 찍어 화면(HTML)에 넘긴다 (deskcap.py)
    # ------------------------------------------------------------------
    def _desk_rect(self):
        """노치 뒤 화면에서 찍을 영역(물리 픽셀): 창 가운데 위쪽의 600x200(CSS px, 탭 아이콘 독이 열린 가장 큰 노치까지 덮는다). 창이 숨겨져 있으면 None."""
        hwnd = self._get_hwnd()
        if not hwnd or not ctypes.windll.user32.IsWindowVisible(hwnd):
            return None
        rc = wintypes.RECT()
        ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rc))
        dpr = self._notch_scale()
        w, h = int(600 * dpr), int(200 * dpr)
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
                "monitors": self.get_monitors(), "hotkeys": self.hotkeys_status(), "plugins": self.plugins_catalog(),
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
                data.pop("settings", None)
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

    # ---- 볼륨 믹서 (마스터 + 앱별)
    def mixer_get(self):
        return {"master": audiomix.master_get(), "apps": audiomix.list_apps() or []}

    def mixer_step(self, delta):
        """마스터 볼륨을 delta(예: 0.02)만큼 바꾸고 새 값(0~1)을 돌려준다. Ctrl+휠용."""
        try:
            return audiomix.master_step(float(delta))
        except Exception:
            return None

    def mixer_set(self, target, volume=None, muted=None):
        """target: 'master' 또는 list_apps 의 id('pid:123' / 'system')."""
        try:
            if target == "master":
                ok = audiomix.master_set(volume, muted)
            else:
                ok = audiomix.set_app(str(target), volume, muted)
            return {"status": "ok" if ok else "error"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def set_source(self, source_id):
        """노치에서 재생 소스를 직접 고른다. 'auto' 면 자동 선택으로 되돌린다."""
        sid = source_id if source_id in ("cider", "smtc") else None
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

    def _hk_toggle(self):
        self._js("hotkeyToggle()")

    def open_notification_center(self):
        """보조 노치의 알림 동그라미를 눌렀을 때: 윈도우 알림 센터를 연다(윈도우 11: Win+N, 10: Win+A). 이미 열려 있으면 그대로 둔다."""
        try:
            if self._winnotif is not None:
                self._winnotif.acknowledge()
            opened = winnotif.open_center() if winnotif is not None else False
            return {"status": "ok", "opened": bool(opened)}
        except Exception as e:
            log(f"open_notification_center error: {e!r}")
            return {"status": "error", "message": str(e)}

    MANUAL_CAPTURE_SECONDS = 4 * 3600      # '끌 때까지' 설정의 안전 한도(끄는 걸 잊어도 언젠가는 원래대로 돌아온다)
    AUTO_RECORD_SECONDS = 1800             # 엔비디아 녹화 단축키(Alt+F9)로 켠 캡처 모드의 안전 한도

    def capture_mode(self, seconds=15, quiet=False):
        """리퀴드 글래스 '전체'는 노치 창을 화면 캡처에서 빼 둔다(자기 자신을 비추지 않으려고). 스크린샷/녹화를 하고 싶을 때 이걸 부르면
        seconds 초 동안 뒤 화면을 얼려 두고 노치가 캡처에 보이게 한 뒤, 자동으로 원래대로 돌아간다. seconds 가 0 이면 '끌 때까지'(안전 한도 있음).
        (캡처에서 빠진 창이 있으면 NVIDIA 녹화가 '보호된 콘텐츠'라며 바탕화면 녹화를 거부하므로, 영상은 캡처 모드를 켜고 찍어야 한다.)"""
        try:
            hold = not seconds
            secs = self.MANUAL_CAPTURE_SECONDS if hold else float(seconds)
            on = self._desk.freeze(secs)
            if not quiet:                # 자동 캡처 모드(capturewatch)는 알림 없이 조용히 켠다
                self._push_event({"type": "capture_mode", "on": bool(on), "seconds": int(secs), "hold": bool(hold)})
            return {"status": "ok", "active": bool(on)}
        except Exception as e:
            log(f"capture_mode error: {e!r}")
            return {"status": "error", "message": str(e)}

    def capture_toggle(self):
        """단축키/설정 버튼: 켜져 있으면 끄고, 꺼져 있으면 설정한 시간(captureSeconds) 동안 켠다."""
        try:
            if getattr(self._desk, "_visible", False) and self._desk.frozen:      # 설정이 '표시'면 항상 켜져 있어서 끌 게 없다
                self._push_event({"type": "capture_mode", "on": True, "seconds": 0, "hold": True})
                return {"status": "ok", "active": True}
            if self._desk.frozen:
                self._desk.thaw()
                self._rec_hold = False
                self._push_event({"type": "capture_mode", "on": False, "off": True})
                return {"status": "ok", "active": False, "off": True}
            try:
                secs = int(self._prefs.get("captureSeconds"))
            except Exception:
                secs = 15
            return self.capture_mode(secs)
        except Exception as e:
            log(f"capture_toggle error: {e!r}")
            return {"status": "error", "message": str(e)}

    _rec_hold = False

    def _capture_auto(self, seconds, why):
        """capturewatch 가 부르는 자동 캡처 모드. 엔비디아 녹화 단축키(Alt+F9)는 눌러 시작/다시 눌러 중지라서, 켜 두었다가 다시 누르면 끈다."""
        if why == "alt+f9":
            if self._rec_hold and self._desk.frozen:
                self._rec_hold = False
                self._desk.thaw()
                self._push_event({"type": "capture_mode", "on": False, "off": True})
            else:
                self._rec_hold = bool(self._desk.freeze(self.AUTO_RECORD_SECONDS))
                if self._rec_hold:
                    self._push_event({"type": "capture_mode", "on": True, "seconds": self.AUTO_RECORD_SECONDS, "hold": True})
            return
        self.capture_mode(seconds, quiet=True)

    def _hk_lyrics(self):
        self._js("toggleLyrics()")

    def hotkeys_status(self):
        """설정 창용: 단축키별 등록 결과(ok/invalid/conflict/off)와 정규화된 표기."""
        st = self._hotkeys.status()
        return {"status": st, "combos": {k: hotkeys.format_combo(self._prefs.get(k)) for k in ("hkToggle", "hkSettings", "hkMixer", "hkLyrics", "hkCapture")}}

    # ---- 클립보드 기록
    def clip_list(self):
        return {"enabled": bool(self._prefs.get("clipboardOn")), "items": self._clip.list()}

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
                "viz": audiolevels is not None}

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
    _CHIMES = {
        "pomo": [(784, 140), (1047, 140), (1319, 260)],
        "water": [(660, 150), (880, 220)],
        "todo": [(880, 120), (880, 120), (1175, 220)],
    }

    def chime(self, kind="pomo"):
        def play():
            try:
                import winsound
                for freq, ms in self._CHIMES.get(kind, self._CHIMES["pomo"]):
                    winsound.Beep(freq, ms)
            except Exception as e:
                log(f"chime error: {e!r}")
        threading.Thread(target=play, daemon=True, name="chime").start()
        return {"status": "ok"}

    def expand_window(self, rect=None):
        """rect 가 있으면 확장된 필 영역만 클릭 가능하게, 없으면 창 전체를 상호작용 가능하게(컨텍스트 메뉴용)."""
        try:
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
            return monitors.centered_x(mon, width_px), mon["top"]
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
                log(f"Window placed on monitor {mon['number'] if mon else '?'} at ({x_phys}, {y_phys}).")
            return {"status": "ok"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _monitor_watch(self):
        """모니터가 연결/해제/재배치되거나 설정한 번호가 바뀌면 노치를 다시 그 모니터 위쪽 가운데로 옮긴다.
        (사용자가 직접 끌어 옮긴 위치는 그대로 둔다: 모니터 구성이 바뀔 때만 움직인다)"""
        while self._running:
            time.sleep(3.0)
            try:
                key = monitors.monitor_key(self._target_monitor())
                if key != getattr(self, "_mon_key", None) and self._get_hwnd():
                    log("Monitor layout/choice changed; moving the notch.")
                    self.recenter_window()
            except Exception as e:
                log(f"_monitor_watch error: {e!r}")

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
        self._monitor.stop()
        if getattr(self, "_tray", None) is not None:
            self._tray.stop()
        for svc in (self._hotkeys, self._clipwatch):
            try:
                svc.stop()
            except Exception:
                pass
        if self._levels is not None:
            self._levels.stop()
        if self._buds is not None:
            self._buds.stop()
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
        x_center = int((monitors.centered_x(mon, int(EXPANDED_WIDTH * scale))) / scale)
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
