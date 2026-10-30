# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Flirty_BananaMilk — 상업적 이용 금지, 자세한 내용은 LICENSE
"""Windows 미디어 세션(SMTC)에서 '지금 재생 중인 미디어'를 읽고 제어한다.

Cider 가 아니어도 — Spotify, 브라우저(유튜브 등), 멜론 같은 앱이 윈도우 미디어 컨트롤에 올리는 곡이면 아일랜드에 똑같이 보인다.
Cider 자신의 세션은 Cider REST API 로 따로 읽으므로(가사까지 가져옴) 여기서는 제외한다.

pythonnet 과 무관하게 pywinrt 로만 동작하고(별도 스레드의 asyncio 루프), 패키지가 없으면 import 에서 실패해 기능만 꺼진다.
"""
import asyncio
import re
import base64
import hashlib
import io
import threading
import time
from datetime import datetime, timezone

from winrt.windows.media import MediaPlaybackAutoRepeatMode
from winrt.windows.media.control import (
    GlobalSystemMediaTransportControlsSessionManager as SessionManager,
    GlobalSystemMediaTransportControlsSessionPlaybackStatus as PlaybackStatus,
)
from winrt.windows.storage.streams import DataReader

POLL_SEC = 0.5
POLL_BOOST_SEC = 0.1     # 컨트롤을 누른 직후 잠시 더 자주 읽는다
ART_SIZE = 192            # 섬에서 가장 큰 앨범 아트가 76px (x2 배율) 이므로 이 정도면 충분하다
ART_RETRIES = 6           # 곡 정보가 먼저 오고 썸네일이 조금 늦게 오는 앱이 있다
TICKS_PER_SEC = 10_000_000
EXCLUDE_APPS = ("cider",)  # Cider 는 REST API 로 읽는다 (가사/반복/셔플까지 있음)

_REPEAT_TO_MODE = {"none": MediaPlaybackAutoRepeatMode.NONE, "one": MediaPlaybackAutoRepeatMode.TRACK,
                   "all": MediaPlaybackAutoRepeatMode.LIST}
_MODE_TO_REPEAT = {v: k for k, v in _REPEAT_TO_MODE.items()}

_APP_LABELS = {"spotify": "Spotify", "chrome": "Chrome", "msedge": "Edge", "firefox": "Firefox", "brave": "Brave",
               "vlc": "VLC", "melon": "Melon", "applemusic": "Apple Music", "zunemusic": "Media Player",
               "microsoft.media.player": "Media Player", "youtubemusic": "YouTube Music"}


def app_label(aumid):
    """'SpotifyAB.SpotifyMusic_zpdnekdrzrea0!Spotify' / 'chrome.exe' 같은 앱 ID 를 읽기 좋은 이름으로."""
    low = (aumid or "").lower()
    for key, name in _APP_LABELS.items():
        if key in low:
            return name
    head = (aumid or "").split("!")[0].split("_")[0]
    if head.lower().endswith(".exe"):
        head = head[:-4]
    elif "." in head:                      # 'Publisher.App' 형태의 패키지 앱 이름은 뒤쪽이 앱 이름
        head = head.rsplit(".", 1)[-1]
    return head or "Media"


def is_excluded(aumid, exclude=EXCLUDE_APPS):
    low = (aumid or "").lower()
    return any(x in low for x in exclude)


def parse_filter_list(text):
    """'spotify, chrome ; vlc' -> ['spotify', 'chrome', 'vlc'] (소문자, 빈 항목 제외)"""
    return [p.strip().lower() for p in re.split(r"[,;\n]", text or "") if p.strip()]


def passes_filter(aumid, mode, names):
    """앱 필터. mode: 'off' | 'allow'(목록에 있는 앱만) | 'block'(목록에 있는 앱은 제외). 목록이 비면 필터 없음과 같다."""
    if mode not in ("allow", "block") or not names:
        return True
    hit = any(n in (aumid or "").lower() or n in app_label(aumid).lower() for n in names)
    return hit if mode == "allow" else not hit


def pick_session(entries, current_id=None):
    """entries: [(app_id, is_playing)]. 재생 중인 세션이 있으면 그중(지금 쓰던 게 아직 재생 중이면 그것, 아니면 첫 번째),
    없으면 지금 쓰던 세션(일시정지 상태로 계속 보여 준다), 그것도 없으면 첫 번째. 비어 있으면 None."""
    if not entries:
        return None
    playing = [a for a, p in entries if p]
    if playing:
        return current_id if current_id in playing else playing[0]
    ids = [a for a, _ in entries]
    return current_id if current_id in ids else ids[0]


def project_position(position, last_updated_age, is_playing, duration):
    """SMTC 의 position 은 last_updated 시점의 값이다. 재생 중이면 그 이후 흐른 시간을 더해 지금 위치를 만든다."""
    pos = float(position)
    if is_playing and last_updated_age is not None and 0 <= last_updated_age < 6 * 3600:
        pos += last_updated_age
    pos = max(0.0, pos)
    if duration and duration > 0:
        pos = min(pos, duration)
    return pos


def choose_source(cider_has, cider_playing, other_has, other_playing, current, prefer="auto"):
    """어느 쪽(Cider 'cider' / 윈도우 미디어 'smtc')을 보여줄지. 재생 중인 쪽이 우선이고, 둘 다 재생 중이면
    prefer 가 'cider'/'other' 면 그쪽, 'auto' 면 보던 쪽을 유지한다.
    둘 다 멈춰 있으면 보던 쪽에 아직 곡이 있는 한 그대로 둔다(일시정지된 곡이 갑자기 다른 앱 곡으로 바뀌지 않게)."""
    if cider_playing and other_playing:
        if prefer == "cider":
            return "cider"
        if prefer == "other":
            return "smtc"
        return current if current in ("cider", "smtc") else "cider"
    if cider_playing:
        return "cider"
    if other_playing:
        return "smtc"
    if current == "cider" and cider_has:
        return "cider"
    if current == "smtc" and other_has:
        return "smtc"
    if cider_has:
        return "cider"
    if other_has:
        return "smtc"
    return "cider"


def _track_key(app_id, title, artist, album):
    raw = f"{app_id}|{title}|{artist}|{album}".encode("utf-8", "replace")
    return "smtc:" + hashlib.sha1(raw).hexdigest()[:16]


def _to_data_uri(data):
    """썸네일을 ART_SIZE 로 줄여 JPEG data URI 로 만든다 (매 폴링마다 화면으로 보내므로 작게)."""
    try:
        from PIL import Image
        im = Image.open(io.BytesIO(data)).convert("RGB")
        im.thumbnail((ART_SIZE, ART_SIZE))
        out = io.BytesIO()
        im.save(out, "JPEG", quality=86)
        return "data:image/jpeg;base64," + base64.b64encode(out.getvalue()).decode("ascii")
    except Exception:
        return "data:image/png;base64," + base64.b64encode(data).decode("ascii")


class MediaSessionService:
    def __init__(self, log=None, exclude=EXCLUDE_APPS):
        self._log = log or (lambda m: None)
        self._exclude = exclude
        self._lock = threading.Lock()
        self._snap = None            # 마지막으로 읽은 곡 정보 (dict) 또는 None
        self._boost_until = 0.0
        self._loop = None
        self._running = False
        self._thread = None
        # 아래는 이벤트 루프 스레드 전용
        self._session = None
        self._app_id = None
        self._key = None
        self._art = ""
        self._art_tries = 0
        self._manager = None
        self.filter_mode = "off"       # 설정에서 바꾼다 (다른 스레드에서 대입해도 안전: 단순 참조 교체)
        self.filter_names = []

    # ------------------------------------------------------------------ 외부 API
    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True, name="smtc")
        self._thread.start()
        return True

    def stop(self):
        self._running = False
        if self._loop is not None:
            self._loop.call_soon_threadsafe(self._loop.stop)

    def snapshot(self):
        """지금 위치까지 투영한 곡 정보. 재생할 미디어 세션이 없으면 None."""
        with self._lock:
            s = self._snap
        if s is None:
            return None
        out = dict(s)
        if out["isPlaying"]:
            out["position"] = project_position(s["position"], time.perf_counter() - s["read_perf"], True, s["duration"])
        return out

    def boost(self, seconds=2.0):
        """컨트롤을 누른 직후: 잠시 폴링을 빠르게 한다."""
        self._boost_until = time.monotonic() + seconds

    def control(self, action, arg=None, timeout=4.0):
        if not self._running or self._loop is None:
            return False
        fut = asyncio.run_coroutine_threadsafe(self._control(action, arg), self._loop)
        try:
            return bool(fut.result(timeout))
        except Exception as e:
            self._log(f"smtc control {action} failed: {e!r}")
            return False

    def control_app(self, match, action, arg=None, timeout=4.0):
        """이름(앱 ID 의 일부, 대소문자 무시)이 match 인 앱의 미디어 세션을 직접 제어한다. 지금 노치가 보여 주는 소스와 무관하다
        (예: Cider 를 보는 중에도 Spotify 만 일시정지). 그 앱의 세션이 없으면 False."""
        self.boost(2.0)
        if not self._running or self._loop is None:
            return False
        fut = asyncio.run_coroutine_threadsafe(self._control_app(match, action, arg), self._loop)
        try:
            return bool(fut.result(timeout))
        except Exception as e:
            self._log(f"smtc control_app {match}/{action} failed: {e!r}")
            return False

    def find_app(self, match):
        """match 에 해당하는 세션이 지금 있는가 (플러그인 상태 표시용)."""
        s = self._snap_of(match)
        return s

    def app_playback(self, match):
        """match 앱 세션의 {playing, repeat('none'|'one'|'all'|None), shuffle(bool|None)} 또는 None (플러그인 상태 표시용)."""
        mgr = self._manager
        if mgr is None:
            return None
        try:
            for s in mgr.get_sessions():
                if match.lower() in (s.source_app_user_model_id or "").lower():
                    info = s.get_playback_info()
                    return {"playing": info.playback_status == PlaybackStatus.PLAYING,
                            "repeat": _MODE_TO_REPEAT.get(info.auto_repeat_mode) if info.auto_repeat_mode is not None else None,
                            "shuffle": info.is_shuffle_active}
        except Exception:
            return None
        return None

    def _snap_of(self, match):
        mgr = self._manager
        if mgr is None:
            return None
        try:
            for s in mgr.get_sessions():
                if match.lower() in (s.source_app_user_model_id or "").lower():
                    return s.source_app_user_model_id
        except Exception:
            return None
        return None

    # ------------------------------------------------------------------ 내부
    def _run(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.create_task(self._poll_loop())
        try:
            self._loop.run_forever()
        finally:
            self._loop.close()

    async def _poll_loop(self):
        manager = None
        last_err = None
        while self._running:
            try:
                if manager is None:
                    manager = await SessionManager.request_async()
                    self._manager = manager
                await self._poll_once(manager)
                last_err = None
            except Exception as e:
                msg = repr(e)
                if msg != last_err:
                    self._log(f"smtc poll error: {msg}")
                    last_err = msg
                manager = None
            await asyncio.sleep(POLL_BOOST_SEC if time.monotonic() < self._boost_until else POLL_SEC)

    async def _poll_once(self, manager):
        entries, sessions = [], {}
        for s in manager.get_sessions():
            app_id = s.source_app_user_model_id
            if is_excluded(app_id, self._exclude) or not passes_filter(app_id, self.filter_mode, self.filter_names):
                continue
            playing = s.get_playback_info().playback_status == PlaybackStatus.PLAYING
            entries.append((app_id, playing))
            sessions[app_id] = s
        chosen = pick_session(entries, self._app_id)
        if chosen is None:
            self._session = self._app_id = self._key = None
            with self._lock:
                self._snap = None
            return
        session = sessions[chosen]
        self._session, self._app_id = session, chosen

        props = await session.try_get_media_properties_async()
        title, artist, album = props.title or "", props.artist or "", props.album_title or ""
        if not (title or artist):
            with self._lock:
                self._snap = None
            return
        key = _track_key(chosen, title, artist, album)
        if key != self._key:
            self._key, self._art, self._art_tries = key, "", 0
            self._log(f"smtc track: {title} - {artist} [{app_label(chosen)}]")
        if not self._art and self._art_tries < ART_RETRIES and props.thumbnail is not None:
            self._art_tries += 1
            self._art = await self._read_thumbnail(props.thumbnail)

        info = session.get_playback_info()
        tl = session.get_timeline_properties()
        status = info.playback_status
        is_playing = status == PlaybackStatus.PLAYING
        duration = max(0.0, (tl.end_time - tl.start_time).total_seconds())
        age = None
        try:
            age = (datetime.now(timezone.utc) - tl.last_updated_time).total_seconds()
        except Exception:
            pass
        pos = project_position(tl.position.total_seconds(), age, is_playing, duration)
        ctrl = info.controls
        snap = {
            "key": key, "app": chosen, "appName": app_label(chosen),
            "title": title, "artist": artist, "album": album, "artworkUrl": self._art,
            "isPlaying": is_playing, "state": "playing" if is_playing else ("paused" if status == PlaybackStatus.PAUSED else "stopped"),
            "position": pos, "duration": duration, "read_perf": time.perf_counter(),
            "repeat": _MODE_TO_REPEAT.get(info.auto_repeat_mode) if info.auto_repeat_mode is not None else None,
            "shuffle": info.is_shuffle_active,
            "canSeek": bool(ctrl.is_playback_position_enabled), "canNext": bool(ctrl.is_next_enabled),
            "canPrev": bool(ctrl.is_previous_enabled),
        }
        with self._lock:
            self._snap = snap

    @staticmethod
    async def _read_thumbnail(ref):
        try:
            stream = await ref.open_read_async()
            size = int(stream.size)
            if size <= 0 or size > 8 * 1024 * 1024:
                return ""
            reader = DataReader(stream)
            await reader.load_async(size)
            data = bytearray(size)
            reader.read_bytes(data)
            return _to_data_uri(bytes(data))
        except Exception:
            return ""

    async def _control_app(self, match, action, arg):
        mgr = self._manager
        if mgr is None:
            return False
        for s in mgr.get_sessions():
            if match.lower() in (s.source_app_user_model_id or "").lower():
                return await self._do(s, action, arg)
        return False

    async def _control(self, action, arg):
        return await self._do(self._session, action, arg)

    async def _do(self, s, action, arg):
        if s is None:
            return False
        if action == "toggle":
            return await s.try_toggle_play_pause_async()
        if action == "play":
            return await s.try_play_async()
        if action == "pause":
            return await s.try_pause_async()
        if action == "next":
            return await s.try_skip_next_async()
        if action == "prev":
            return await s.try_skip_previous_async()
        if action == "seek" and arg is not None:
            return await s.try_change_playback_position_async(int(float(arg) * TICKS_PER_SEC))
        if action == "repeat" and arg in _REPEAT_TO_MODE:
            return await s.try_change_auto_repeat_mode_async(_REPEAT_TO_MODE[arg])
        if action == "shuffle" and arg is not None:
            return await s.try_change_shuffle_active_async(bool(arg))
        return False
