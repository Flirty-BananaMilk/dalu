# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Flirty_BananaMilk — 상업적 이용 금지, 자세한 내용은 LICENSE
"""플러그인: 노치의 '플러그인' 페이지에서 누르는 기능 묶음.

내장 플러그인(Cider, Spotify, Discord, 볼륨, 시스템, 곡 도구, 빠른 타이머, 웹 바로가기)과, 사용자가 폴더에 JSON 으로 만드는 플러그인을 같은 방식으로 다룬다.
각 플러그인은 {id, name, desc, icon, actions: [{id, label, icon, run}]} 이고 label/name/desc 는 {"ko","en"}.
run(ctx) 은 {"status": "ok"|"error", "message"?, "js"?} 를 돌려준다(js 는 화면이 실행할 동작: 'timer:5', 'pomo', 'stopwatch').

사용자 플러그인 JSON (%APPDATA%\\Dalu\\plugins\\*.json):
  {"id": "mytools", "name": "내 도구", "icon": "tool", "actions": [
     {"label": "메모장", "icon": "lyrics", "run": "notepad.exe"},
     {"label": "노션", "icon": "globe", "open": "https://www.notion.so"},
     {"label": "서명 복사", "copy": "홍길동 드림"},
     {"label": "작업 관리자", "keys": "Ctrl+Shift+Esc"} ]}
  동작 종류: open(주소/파일/폴더 열기) | run(프로그램 실행, 'args' 는 선택) | copy(클립보드에 글 넣기) | keys(키 조합 보내기)
"""
import json
import os
import re
import shlex
import subprocess
import urllib.parse
import webbrowser

import audiomix
import clipwatch
import keys

MAX_USER_PLUGINS = 20
MAX_ACTIONS = 24
ID_RE = re.compile(r"^[a-z0-9_-]{1,32}$")
URL_RE = re.compile(r"^https?://", re.I)


def L(ko, en=None, zh=None, ja=None):
    """언어별 문구. zh/ja 를 주면 그 문구를 쓰고, 주지 않으면 화면이 영어 원문으로 번역표(i18n_cjk.js)를 찾는다(없으면 영어로 보인다).
    f-string 처럼 값이 끼어드는 문구는 번역표로 찾을 수 없으니 zh/ja 를 직접 준다."""
    d = {"ko": ko, "en": en if en is not None else ko}
    if zh is not None:
        d["zh"] = zh
    if ja is not None:
        d["ja"] = ja
    return d


def LS(ko, en, live, zh=None, ja=None):
    """상태 문구 + 연결 여부. live 가 True 일 때만 화면의 초록불이 켜진다(연결 상태가 의미 없는 플러그인은 live 를 주지 않아 초록불이 없다)."""
    d = L(ko, en, zh, ja)
    d["live"] = bool(live)
    return d


def ok(message=None, js=None):
    out = {"status": "ok"}
    if message:
        out["message"] = message
    if js:
        out["js"] = js
    return out


def err(message):
    return {"status": "error", "message": message}


def open_target(target):
    """주소/파일/폴더/프로토콜 열기. http(s) 는 기본 브라우저로, 그 밖은 윈도우가 알아서(os.startfile)."""
    t = (target or "").strip()
    if not t or "\n" in t or "\r" in t:
        return err("empty target")
    try:
        if URL_RE.match(t):
            webbrowser.open(t)
        else:
            os.startfile(t)
        return ok()
    except Exception as e:
        return err(str(e))


def run_program(target, args=""):
    t = (target or "").strip()
    if not t or "\n" in t:
        return err("empty target")
    try:
        argv = [t] + (shlex.split(args, posix=False) if args else [])
        subprocess.Popen(argv, close_fds=True, creationflags=0x00000008)      # DETACHED_PROCESS: 노치가 꺼져도 계속 실행
        return ok()
    except FileNotFoundError:
        return open_target(t) if not args else err("not found")              # 'ms-settings:' 같은 프로토콜/문서는 열기로 시도
    except Exception as e:
        return err(str(e))


class Plugin:
    def __init__(self, pid, name, desc, icon, actions, status=None, builtin=True, states=None):
        self.id, self.name, self.desc, self.icon = pid, name, desc, icon
        self.states = states              # callable(ctx) -> {action_id: {"on": bool, "tone": "warn"?, "text": L?, "badge": str?}} (버튼에 지금 상태를 보여 줄 때)
        self.actions = actions            # [{id, label, icon, run}]
        self.status = status              # callable(ctx) -> {"ko","en"} | None
        self.builtin = builtin

    def summary(self):
        return {"id": self.id, "name": self.name, "desc": self.desc, "icon": self.icon, "builtin": self.builtin,
                "actions": [{"id": a["id"], "label": a["label"], "icon": a.get("icon", "")} for a in self.actions]}


def st(on, text=None, tone=None, badge=None):
    """버튼 상태 한 칸. on=켜져 있음(강조), text=버튼 이름 대신 보일 문구, tone='warn'=주의색(음소거처럼 꺼진 상태를 알릴 때), badge=모서리 작은 표시."""
    out = {"on": bool(on)}
    if text:
        out["text"] = text
    if tone:
        out["tone"] = tone
    if badge:
        out["badge"] = badge
    return out


def repeat_state(mode):
    if mode == "one":
        return st(True, L("한 곡 반복", "Repeat one"), badge="1")
    if mode == "all":
        return st(True, L("전체 반복", "Repeat all"))
    return st(False, L("반복 끔", "Repeat off"))


def action(aid, label, icon, run):
    return {"id": aid, "label": label, "icon": icon, "run": run}


# ---------------------------------------------------------------------- 내장 플러그인
def _cider_plugin():
    def cider_ok(ctx, fn):
        try:
            fn()
            return ok()
        except Exception as e:
            return err(str(e))

    def shuffle(ctx):
        cur = bool((ctx.state() or {}).get("shuffle"))
        ctx.client.set_shuffle(not cur)
        return ok()

    def repeat(ctx):
        cur = (ctx.state() or {}).get("repeat", "none")
        ctx.client.set_repeat({"none": "all", "all": "one", "one": "none"}.get(cur, "all"))
        return ok()

    def status(ctx):
        st = ctx.state() or {}
        if ctx.cider_up():
            return LS("Cider 연결됨", "Cider connected", True) if not st.get("title") or st.get("source") != "cider" else LS("재생 중: " + st["title"], "Playing: " + st["title"], True, "正在播放：" + st["title"], "再生中：" + st["title"])
        return LS("Cider가 꺼져 있어요", "Cider is not running", False)

    def states(ctx):
        s = ctx.state() or {}
        if not ctx.cider_up():
            return {}
        playing = bool(s.get("isPlaying")) and s.get("source") == "cider"
        return {"toggle": st(playing, L("재생 중", "Playing") if playing else L("일시정지", "Paused")),
                "shuffle": st(bool(s.get("shuffle")), L("셔플 켬", "Shuffle on") if s.get("shuffle") else L("셔플 끔", "Shuffle off")),
                "repeat": repeat_state(s.get("repeat", "none"))}

    return Plugin("cider", L("Cider", "Cider"), L("Cider를 직접 제어합니다. (재생 소스와 상관없이 항상 Cider에만 보냅니다)", "Controls Cider directly, whichever source the notch is showing."), "disc", [
        action("toggle", L("재생/정지", "Play/Pause"), "playpause", lambda c: cider_ok(c, c.client.toggle_playback)),
        action("prev", L("이전 곡", "Previous"), "prev", lambda c: cider_ok(c, c.client.previous_track)),
        action("next", L("다음 곡", "Next"), "next", lambda c: cider_ok(c, c.client.next_track)),
        action("restart", L("처음부터", "Restart"), "restart", lambda c: cider_ok(c, lambda: c.client.seek(0))),
        action("shuffle", L("셔플", "Shuffle"), "shuffle", shuffle),
        action("repeat", L("반복", "Repeat"), "repeat", repeat),
    ], status, states=states)


def _spotify_plugin():
    def target(act):
        def run(ctx):
            if ctx.smtc is None or not ctx.smtc.control_app("spotify", act):
                return err("Spotify is not playing anything (open it first)")
            return ok()
        return run

    def search_current(ctx):
        st = ctx.state() or {}
        q = " ".join(x for x in (st.get("title"), st.get("artist")) if x)
        if not q:
            return err("nothing playing")
        return open_target("spotify:search:" + urllib.parse.quote(q))

    def pb(ctx):
        return ctx.smtc.app_playback("spotify") if ctx.smtc is not None else None

    def shuffle(ctx):
        cur = pb(ctx)
        if cur is None or ctx.smtc is None or not ctx.smtc.control_app("spotify", "shuffle", not bool(cur.get("shuffle"))):
            return err("Spotify is not playing anything (open it first)")
        return ok()

    def repeat(ctx):
        cur = pb(ctx)
        nxt = {"none": "all", "all": "one", "one": "none"}.get((cur or {}).get("repeat") or "none", "all")
        if cur is None or ctx.smtc is None or not ctx.smtc.control_app("spotify", "repeat", nxt):
            return err("Spotify is not playing anything (open it first)")
        return ok()

    def states(ctx):
        cur = pb(ctx)
        if cur is None:
            return {}
        out = {"toggle": st(cur["playing"], L("재생 중", "Playing") if cur["playing"] else L("일시정지", "Paused"))}
        if cur.get("shuffle") is not None:
            out["shuffle"] = st(cur["shuffle"], L("셔플 켬", "Shuffle on") if cur["shuffle"] else L("셔플 끔", "Shuffle off"))
        if cur.get("repeat") is not None:
            out["repeat"] = repeat_state(cur["repeat"])
        return out

    def status(ctx):
        found = ctx.smtc.find_app("spotify") if ctx.smtc is not None else None
        return LS("Spotify 연결됨", "Spotify connected", True) if found else LS("Spotify가 소리를 내고 있지 않아요", "Spotify is not active", False)

    return Plugin("spotify", L("Spotify", "Spotify"), L("Spotify 앱의 재생을 직접 제어합니다(윈도우 미디어 컨트롤 사용, 로그인 필요 없음).", "Controls the Spotify app through Windows media controls (no sign-in)."), "waves", [
        action("toggle", L("재생/정지", "Play/Pause"), "playpause", target("toggle")),
        action("prev", L("이전 곡", "Previous"), "prev", target("prev")),
        action("next", L("다음 곡", "Next"), "next", target("next")),
        action("shuffle", L("셔플", "Shuffle"), "shuffle", shuffle),
        action("repeat", L("반복", "Repeat"), "repeat", repeat),
        action("open", L("Spotify 열기", "Open Spotify"), "launch", lambda c: open_target("spotify:")),
        action("search", L("현재 곡 검색", "Search this song"), "search", search_current),
    ], status, states=states)


def _discord_plugin():
    def ids(ctx):
        return audiomix.apps_matching("discord")

    def toggle_mute(ctx):
        found = ids(ctx)
        if not found:
            return err("Discord is not making sound")
        apps = {a["id"]: a for a in (audiomix.list_apps() or [])}
        muted = not all(apps[i]["muted"] for i in found if i in apps)
        for i in found:
            audiomix.set_app(i, muted=muted)
        return ok(message=(L("Discord 음소거", "Discord muted") if muted else L("Discord 음소거 해제", "Discord unmuted")))

    def step(delta):
        def run(ctx):
            found = ids(ctx)
            if not found:
                return err("Discord is not making sound")
            apps = {a["id"]: a for a in (audiomix.list_apps() or [])}
            for i in found:
                if i in apps:
                    audiomix.set_app(i, volume=max(0.0, min(1.0, apps[i]["volume"] + delta)), muted=False if delta > 0 else None)
            return ok()
        return run

    def mic(ctx):
        r = audiomix.mic_toggle_mute()
        return err("no microphone") if r is None else ok(message=(L("마이크 꺼짐", "Mic muted") if r else L("마이크 켜짐", "Mic on")))

    def states(ctx):
        out = {}
        m = audiomix.mic_get()
        if m is not None:
            out["mic"] = st(m["muted"], L("마이크 꺼짐", "Mic muted") if m["muted"] else L("마이크 켜짐", "Mic on"), tone="warn" if m["muted"] else None)
        found = ids(ctx)
        if found:
            apps = {a["id"]: a for a in (audiomix.list_apps() or [])}
            vols = [apps[i] for i in found if i in apps]
            if vols:
                muted = all(a["muted"] for a in vols)
                out["mute"] = st(muted, L("음소거 중", "Muted") if muted else L("소리 켬", "Audible"), tone="warn" if muted else None)
        return out

    def status(ctx):
        return LS("Discord 소리 출력 중", "Discord is making sound", True) if ids(ctx) else LS("Discord가 소리를 내고 있지 않아요 (음성 채널에 들어가면 나타나요)", "Discord is silent (shows up in a voice channel)", False)

    return Plugin("discord", L("Discord", "Discord"), L("Discord 소리 크기/음소거와 마이크를 노치에서 조절합니다(로그인·토큰 필요 없음).", "Control Discord's volume/mute and your microphone from the notch (no login or token)."), "chat", [
        action("mic", L("마이크 끄기/켜기", "Mic mute"), "mic", mic),
        action("mute", L("Discord 음소거", "Mute Discord"), "mute", toggle_mute),
        action("down", L("소리 -10%", "Volume -10%"), "volume2", step(-0.1)),
        action("up", L("소리 +10%", "Volume +10%"), "volume", step(0.1)),
        action("open", L("Discord 열기", "Open Discord"), "launch", lambda c: open_target("discord://")),
    ], status, states=states)


def _volume_plugin():
    def setv(v):
        return lambda ctx: ok() if audiomix.master_set(volume=v, muted=False) else err("failed")

    def step(d):
        return lambda ctx: ok() if audiomix.master_step(d) is not None else err("failed")

    def mute(ctx):
        cur = audiomix.master_get()
        if cur is None:
            return err("failed")
        return ok() if audiomix.master_set(muted=not cur["muted"]) else err("failed")

    def states(ctx):
        m = audiomix.master_get()
        if not m:
            return {}
        pct = round(m["volume"] * 100)
        out = {"mute": st(m["muted"], L("음소거 중", "Muted") if m["muted"] else L("소리 켬", "Sound on"), tone="warn" if m["muted"] else None)}
        for aid, v in (("v25", 25), ("v50", 50), ("v75", 75), ("v100", 100)):
            out[aid] = st(not m["muted"] and abs(pct - v) <= 2, L("현재", "Now") if (not m["muted"] and abs(pct - v) <= 2) else None)
        return out

    def status(ctx):
        m = audiomix.master_get()
        if not m:
            return None
        pct = round(m["volume"] * 100)
        return L(f"마스터 볼륨 {pct}%" + (" (음소거)" if m["muted"] else ""), f"Master volume {pct}%" + (" (muted)" if m["muted"] else ""),
                 f"主音量 {pct}%" + ("（已静音）" if m["muted"] else ""), f"マスター音量 {pct}%" + ("（ミュート中）" if m["muted"] else ""))

    return Plugin("volume", L("볼륨", "Volume"), L("마스터 볼륨 프리셋과 음소거.", "Master volume presets and mute."), "volume", [
        action("mute", L("음소거", "Mute"), "mute", mute),
        action("down", L("-5%", "-5%"), "minus", step(-0.05)),
        action("up", L("+5%", "+5%"), "plus", step(0.05)),
        action("v25", L("25%", "25%"), "volume1", setv(0.25)),
        action("v50", L("50%", "50%"), "volume2", setv(0.50)),
        action("v75", L("75%", "75%"), "volume", setv(0.75)),
        action("v100", L("100%", "100%"), "volume", setv(1.0)),
    ], status, states=states)


def _system_plugin():
    import ctypes
    user32 = ctypes.windll.user32

    def combo(text):
        return lambda ctx: ok() if keys.send_combo(text) else err("failed")

    def lock(ctx):
        return ok() if user32.LockWorkStation() else err("failed")

    def screen_off(ctx):
        user32.PostMessageW(0xFFFF, 0x0112, 0xF170, 2)       # WM_SYSCOMMAND / SC_MONITORPOWER / 끄기
        return ok()

    def mic(ctx):
        r = audiomix.mic_toggle_mute()
        return err("no microphone") if r is None else ok(message=(L("마이크 꺼짐", "Mic muted") if r else L("마이크 켜짐", "Mic on")))

    def states(ctx):
        m = audiomix.mic_get()
        if m is None:
            return {}
        return {"mic": st(m["muted"], L("마이크 꺼짐", "Mic muted") if m["muted"] else L("마이크 켜짐", "Mic on"), tone="warn" if m["muted"] else None)}

    def status(ctx):
        m = audiomix.mic_get()
        if m is None:
            return L("마이크를 찾지 못했어요", "No microphone found")
        return L("마이크 꺼짐" if m["muted"] else "마이크 켜짐", "Microphone muted" if m["muted"] else "Microphone on")

    return Plugin("system", L("시스템", "System"), L("마이크 음소거, 화면 잠금, 캡처, 바탕화면 보기 같은 윈도우 기능.", "Mic mute, lock screen, screenshot, show desktop and other Windows actions."), "monitor", [
        action("mic", L("마이크 끄기/켜기", "Mic mute"), "mic", mic),
        action("lock", L("PC 잠금", "Lock PC"), "lock", lock),
        action("snip", L("화면 캡처", "Screenshot"), "crop", combo("Win+Shift+S")),
        action("desktop", L("바탕화면", "Desktop"), "monitor", combo("Win+D")),
        action("taskmgr", L("작업 관리자", "Task Manager"), "gauge", combo("Ctrl+Shift+Esc")),
        action("screenoff", L("화면 끄기", "Screen off"), "moon", screen_off),
    ], status, states=states)


def _musictools_plugin():
    def track(ctx):
        st = ctx.state() or {}
        return st.get("title") or "", st.get("artist") or ""

    def copy_info(ctx):
        title, artist = track(ctx)
        if not title:
            return err("nothing playing")
        text = f"{artist} - {title}" if artist else title
        return ok(message=text) if clipwatch.write_text(text) else err("clipboard busy")

    def web(url):
        def run(ctx):
            title, artist = track(ctx)
            if not title:
                return err("nothing playing")
            return open_target(url.format(q=urllib.parse.quote_plus((artist + " " + title).strip())))
        return run

    return Plugin("musictools", L("곡 도구", "Song tools"), L("지금 곡 정보를 복사하거나 웹에서 바로 검색합니다.", "Copy the current song or search for it on the web."), "music", [
        action("copy", L("곡 정보 복사", "Copy song"), "copy", copy_info),
        action("youtube", L("YouTube 검색", "YouTube"), "video", web("https://www.youtube.com/results?search_query={q}")),
        action("lyrics", L("가사 검색", "Find lyrics"), "lyrics", web("https://www.google.com/search?q={q}+lyrics")),
        action("genius", L("Genius", "Genius"), "mic", web("https://genius.com/search?q={q}")),
    ], None)


def _quick_plugin():
    def js(code):
        return lambda ctx: ok(js=code)

    return Plugin("quick", L("빠른 타이머", "Quick timers"), L("타이머/포모도로/스톱워치를 한 번에 시작합니다.", "Start a timer, Pomodoro or stopwatch in one tap."), "timer", [
        action("t5", L("5분", "5 min"), "timer", js("timer:5")),
        action("t10", L("10분", "10 min"), "timer", js("timer:10")),
        action("t30", L("30분", "30 min"), "timer", js("timer:30")),
        action("pomo", L("집중 시작", "Focus"), "target", js("pomo")),
        action("sw", L("스톱워치", "Stopwatch"), "stopwatch", js("stopwatch")),
    ], None)


def _web_plugin():
    sites = [("youtube", "YouTube", "video", "https://www.youtube.com"), ("gmail", "Gmail", "mail", "https://mail.google.com"),
             ("github", "GitHub", "branch", "https://github.com"), ("google", "Google", "search", "https://www.google.com"),
             ("naver", L("네이버", "Naver", "Naver", "Naver"), "globe", "https://www.naver.com"), ("calendar", L("캘린더", "Calendar", "日历", "カレンダー"), "calendar", "https://calendar.google.com")]
    return Plugin("web", L("웹 바로가기", "Web links"), L("자주 가는 사이트를 기본 브라우저로 엽니다.", "Open favorite sites in your default browser."), "globe",
                  [action(i, n if isinstance(n, dict) else L(n), ic, (lambda u: lambda ctx: open_target(u))(u)) for i, n, ic, u in sites], None)


# ---------------------------------------------------------------------- 서드파티 앱
def _media_app_plugin(pid, name, desc, icon, matches, with_modes=False, not_active_ko="소리를 내고 있지 않아요", not_active_en="is not active",
                      not_active_zh="没有在发出声音", not_active_ja="は音を出していません"):
    """윈도우 미디어 세션(SMTC)으로 어떤 앱이든 직접 제어하는 플러그인 틀. 로그인/토큰이 필요 없고, 지금 노치가 보여 주는 소스와 무관하다.
    matches: 앱 ID 에 들어 있는 이름들(앞의 것이 우선). 상태: 재생 중/일시정지, (지원하면) 셔플·반복(전체/한 곡)."""
    def first_playback(ctx):
        if ctx.smtc is None:
            return None
        for m in matches:
            pb = ctx.smtc.app_playback(m)
            if pb is not None:
                return m, pb
        return None

    def control(act, arg_fn=None):
        def run(ctx):
            cur = first_playback(ctx)
            if cur is None or ctx.smtc is None:
                return err(f"{name} is not playing anything (open it first)")
            arg = arg_fn(cur[1]) if arg_fn else None
            return ok() if ctx.smtc.control_app(cur[0], act, arg) else err(f"{name} does not support this")
        return run

    def next_repeat(pb):
        return {"none": "all", "all": "one", "one": "none"}.get(pb.get("repeat") or "none", "all")

    def states(ctx):
        cur = first_playback(ctx)
        if cur is None:
            return {}
        pb = cur[1]
        out = {"toggle": st(pb["playing"], L("재생 중", "Playing") if pb["playing"] else L("일시정지", "Paused"))}
        if with_modes and pb.get("shuffle") is not None:
            out["shuffle"] = st(pb["shuffle"], L("셔플 켬", "Shuffle on") if pb["shuffle"] else L("셔플 끔", "Shuffle off"))
        if with_modes and pb.get("repeat") is not None:
            out["repeat"] = repeat_state(pb["repeat"])
        return out

    def status(ctx):
        cur = first_playback(ctx)
        if cur is None:
            return LS(f"{name} {not_active_ko}", f"{name} {not_active_en}", False, f"{name} {not_active_zh}", f"{name}{not_active_ja}")
        return LS(f"{name} 연결됨", f"{name} connected", True, f"{name} 已连接", f"{name} に接続済み")

    actions = [action("toggle", L("재생/정지", "Play/Pause"), "playpause", control("toggle")),
               action("prev", L("이전 곡", "Previous"), "prev", control("prev")),
               action("next", L("다음 곡", "Next"), "next", control("next"))]
    if with_modes:
        actions += [action("shuffle", L("셔플", "Shuffle"), "shuffle", control("shuffle", lambda pb: not bool(pb.get("shuffle")))),
                    action("repeat", L("반복", "Repeat"), "repeat", control("repeat", next_repeat))]
    return Plugin(pid, L(name, name), desc, icon, actions, status, states=states)


def _applemusic_plugin():
    return _media_app_plugin("applemusic", "Apple Music", L("Windows용 Apple Music 앱의 재생을 제어합니다(윈도우 미디어 컨트롤, 로그인 필요 없음).", "Controls the Apple Music app for Windows through media controls (no sign-in)."),
                             "music", ["applemusic", "apple"], with_modes=True)


def _browsermedia_plugin():
    return _media_app_plugin("browsermedia", "Browser media", L("브라우저에서 재생 중인 YouTube·YouTube Music·넷플릭스 등을 제어합니다(Chrome, Edge, Firefox, Brave, Whale 등).", "Controls YouTube, YouTube Music, Netflix and more playing in your browser (Chrome, Edge, Firefox, Brave, Whale ...)."),
                             "globe", ["chrome", "msedge", "firefox", "brave", "whale", "opera", "vivaldi"], not_active_ko="미디어를 재생 중이 아니에요", not_active_en="has no media playing",
                             not_active_zh="没有在播放媒体", not_active_ja="はメディアを再生していません")


_PROTO_CACHE = {}


def protocol_installed(name, ttl=30.0):
    """윈도우에 그 주소 형식(slack: 같은)을 여는 앱이 등록돼 있는가. 없는 앱을 열면 '앱을 찾을 수 없다'는 창이 떠서 미리 확인한다."""
    import time as _t
    now = _t.monotonic()
    hit = _PROTO_CACHE.get(name)
    if hit and now - hit[0] < ttl:
        return hit[1]
    found = False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, name) as k:
            winreg.QueryValueEx(k, "URL Protocol")
            found = True
    except OSError:
        found = False
    _PROTO_CACHE[name] = (now, found)
    return found


def _protocol_action(aid, label, icon, proto, uri):
    def run(ctx):
        if not protocol_installed(proto):
            return err(f"{proto}: app is not installed")
        return open_target(uri)
    return action(aid, label, icon, run)


def _steam_plugin():
    acts = [
        _protocol_action("home", L("Steam", "Steam"), "launch", "steam", "steam://open/main"),
        _protocol_action("library", L("라이브러리", "Library"), "folder", "steam", "steam://nav/games"),
        _protocol_action("store", L("스토어", "Store"), "star", "steam", "steam://store"),
        _protocol_action("friends", L("친구", "Friends"), "chat", "steam", "steam://friends"),
        _protocol_action("downloads", L("다운로드", "Downloads"), "download", "steam", "steam://nav/downloads"),
        _protocol_action("settings", L("설정", "Settings"), "gear", "steam", "steam://open/settings"),
    ]

    def states(ctx):
        if protocol_installed("steam"):
            return {}
        return {a["id"]: st(False, L("미설치", "Not installed")) for a in acts}

    return Plugin("steam", L("Steam", "Steam"), L("Steam 라이브러리·스토어·친구·다운로드를 바로 엽니다.", "Open the Steam library, store, friends and downloads."), "target", acts, None, states=states)


def _apps_plugin():
    apps = [("slack", "Slack", "chat", "slack", "slack://open"), ("notion", "Notion", "note", "notion", "notion://"),
            ("telegram", "Telegram", "mail", "tg", "tg://"), ("obsidian", "Obsidian", "edit", "obsidian", "obsidian://open"),
            ("vscode", "VS Code", "code", "vscode", "vscode://"), ("teams", "Teams", "video", "msteams", "msteams:"),
            ("figma", "Figma", "brush", "figma", "figma://"), ("epic", "Epic Games", "target", "com.epicgames.launcher", "com.epicgames.launcher://apps")]
    acts = [_protocol_action(i, L(n), ic, proto, uri) for i, n, ic, proto, uri in apps]

    def states(ctx):
        return {i: st(False, L("미설치", "Not installed")) for i, n, ic, proto, uri in apps if not protocol_installed(proto)}

    return Plugin("apps", L("앱 열기", "App launcher"), L("Slack, Notion, Telegram, Obsidian, VS Code, Teams, Figma, Epic Games를 바로 엽니다. 설치돼 있지 않은 앱은 '미설치'로 표시돼요.", "Open Slack, Notion, Telegram, Obsidian, VS Code, Teams, Figma and Epic Games. Apps that are not installed are marked."), "launch", acts, None, states=states)


def builtin_plugins():
    return [_cider_plugin(), _spotify_plugin(), _discord_plugin(), _volume_plugin(), _system_plugin(), _musictools_plugin(), _quick_plugin(), _web_plugin(),
            _applemusic_plugin(), _browsermedia_plugin(), _steam_plugin(), _apps_plugin()]


# ---------------------------------------------------------------------- 사용자 플러그인 (JSON)
def _s(v, n):
    return str(v or "").strip()[:n]


def _loc(v, n=40):
    if isinstance(v, dict):
        ko = _s(v.get("ko") or v.get("en"), n)
        return L(ko, _s(v.get("en") or v.get("ko"), n), _s(v.get("zh"), n) or None, _s(v.get("ja"), n) or None)      # zh/ja 는 있으면 쓴다
    t = _s(v, n)
    return L(t, t)


def _user_action(raw, idx):
    """JSON 의 동작 하나 -> action. 종류를 알 수 없거나 값이 없으면 None."""
    if not isinstance(raw, dict):
        return None
    label = _loc(raw.get("label"), 24)
    if not label["ko"]:
        return None
    icon = _s(raw.get("icon"), 16)
    aid = f"a{idx}"
    if raw.get("open"):
        tgt = _s(raw["open"], 500)
        return action(aid, label, icon, lambda ctx, t=tgt: open_target(t))
    if raw.get("run"):
        tgt, args = _s(raw["run"], 500), _s(raw.get("args"), 300)
        return action(aid, label, icon, lambda ctx, t=tgt, a=args: run_program(t, a))
    if raw.get("copy"):
        text = _s(raw["copy"], 2000)
        return action(aid, label, icon, lambda ctx, t=text: ok() if clipwatch.write_text(t) else err("clipboard busy"))
    if raw.get("keys"):
        combo = _s(raw["keys"], 40)
        if not keys.hotkeys.parse_combo(combo):
            return None
        return action(aid, label, icon, lambda ctx, c=combo: ok() if keys.send_combo(c) else err("failed"))
    return None


def parse_user_plugin(data, builtin_ids=()):
    """JSON(dict) -> Plugin 또는 None. id 가 형식에 맞지 않거나 내장 플러그인과 같으면 거부한다."""
    if not isinstance(data, dict):
        return None
    pid = _s(data.get("id"), 32).lower()
    if not ID_RE.match(pid) or pid in builtin_ids:
        return None
    acts = [a for a in (_user_action(r, i) for i, r in enumerate((data.get("actions") or [])[:MAX_ACTIONS])) if a]
    if not acts:
        return None
    return Plugin(pid, _loc(data.get("name") or pid, 30), _loc(data.get("desc"), 160), _s(data.get("icon"), 16) or "plug", acts, None, builtin=False)


def load_user_plugins(folder, builtin_ids=(), log=None):
    log = log or (lambda m: None)
    out, seen = [], set(builtin_ids)
    try:
        names = sorted(n for n in os.listdir(folder) if n.lower().endswith(".json"))
    except OSError:
        return out
    for n in names[:MAX_USER_PLUGINS * 2]:
        path = os.path.join(folder, n)
        try:
            if os.path.getsize(path) > 64 * 1024:
                continue
            with open(path, encoding="utf-8") as f:
                p = parse_user_plugin(json.load(f), builtin_ids)
        except Exception as e:
            log(f"plugin {n} skipped: {e!r}")
            continue
        if p is None or p.id in seen:
            log(f"plugin {n} skipped (invalid or duplicate id)")
            continue
        seen.add(p.id)
        out.append(p)
        if len(out) >= MAX_USER_PLUGINS:
            break
    return out


# 설정 창의 '예제 설치'가 폴더에 만드는 플러그인 (배포 폴더에 예제 파일이 없어도 되도록 코드에 둔다)
EXAMPLE_PLUGIN = {
    "id": "mytools", "name": {"ko": "내 도구", "en": "My tools", "zh": "我的工具", "ja": "マイツール"}, "icon": "tool",
    "desc": {"ko": "예제 플러그인: 파일을 고쳐서 나만의 도구 모음을 만들어 보세요.", "en": "Example plugin: edit this file to build your own tool set.",
             "zh": "示例插件：编辑这个文件来制作你自己的工具集。", "ja": "サンプルプラグイン：このファイルを編集して、自分用のツールセットを作ってみましょう。"},
    "actions": [
        {"label": {"ko": "메모장", "en": "Notepad", "zh": "记事本", "ja": "メモ帳"}, "icon": "note", "run": "notepad.exe"},
        {"label": {"ko": "다운로드", "en": "Downloads", "zh": "下载", "ja": "ダウンロード"}, "icon": "download", "open": "%USERPROFILE%\Downloads"},
        {"label": {"ko": "서명 복사", "en": "Copy signature", "zh": "复制签名", "ja": "署名をコピー"}, "icon": "edit", "copy": "감사합니다.\n홍길동 드림"},
        {"label": {"ko": "작업 관리자", "en": "Task Manager", "zh": "任务管理器", "ja": "タスクマネージャー"}, "icon": "gauge", "keys": "Ctrl+Shift+Esc"},
    ],
}


def install_example(folder):
    """예제 플러그인 파일을 만든다. 이미 있으면 덮어쓰지 않는다. 만든 경로(없으면 None)를 돌려준다."""
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, "my-tools.json")
    if os.path.exists(path):
        return None
    with open(path, "w", encoding="utf-8") as f:
        json.dump(EXAMPLE_PLUGIN, f, ensure_ascii=False, indent=2)
    return path


class Registry:
    def __init__(self, user_dir=None, log=None):
        self._log = log or (lambda m: None)
        self._user_dir = user_dir
        self.plugins = []
        self.reload()

    def reload(self):
        built = builtin_plugins()
        user = load_user_plugins(self._user_dir, [p.id for p in built], self._log) if self._user_dir else []
        self.plugins = built + user

    def get(self, pid):
        return next((p for p in self.plugins if p.id == pid), None)

    def enabled(self, enabled_ids):
        """추가한 플러그인을 사용자가 정한 순서(enabled_ids 의 순서)대로. 없어졌거나 모르는 id 는 건너뛴다."""
        out, seen = [], set()
        for raw in str(enabled_ids or "").split(","):
            pid = raw.strip()
            p = self.get(pid) if pid and pid not in seen else None
            if p is not None:
                seen.add(pid)
                out.append(p)
        return out

    def run(self, pid, aid, ctx):
        p = self.get(pid)
        a = next((x for x in (p.actions if p else []) if x["id"] == aid), None)
        if a is None:
            return err("unknown action")
        try:
            r = a["run"](ctx)
        except Exception as e:
            return err(str(e))
        return r if isinstance(r, dict) else ok()

    def states(self, pid, ctx):
        """{action_id: 상태} — 상태가 없는 플러그인/실패는 빈 dict."""
        p = self.get(pid)
        if p is None or p.states is None:
            return {}
        try:
            out = p.states(ctx)
        except Exception:
            return {}
        known = {a["id"] for a in p.actions}
        return {k: v for k, v in (out or {}).items() if k in known and isinstance(v, dict)}

    def status(self, pid, ctx):
        p = self.get(pid)
        if p is None or p.status is None:
            return None
        try:
            return p.status(ctx)
        except Exception:
            return None
