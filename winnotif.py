# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Flirty_BananaMilk — 상업적 이용 금지, 자세한 내용은 LICENSE
"""윈도우 알림(토스트)이 새로 오면 알려 주는 감시자.

노치의 보조 노치(작은 동그라미)로 '알림이 왔다'는 것만 보여 주려고 쓴다. 알림의 내용(제목·본문)은 읽지도 저장하지도 않고,
새 알림이 있는지(id)와 어느 앱에서 왔는지(앱 이름)만 본다. 모두 이 PC 안에서만 처리되고 밖으로 나가지 않는다.

- 윈도우의 UserNotificationListener 를 쓴다(winrt-Windows.UI.Notifications.Management). 알림 접근 권한이 '허용'이어야 한다.
  허용이 아니면(미설정/거부) 한 번 요청해 보고, 그래도 안 되면 조용히 꺼 둔다(설정 화면에 상태가 보인다).
- 새 알림이 오면 on_new, 쌓인 새 알림이 윈도우에서 모두 처리되거나(닫음/지움) 알림 센터가 열리면 on_clear 를 부른다.
- 이벤트 방식은 설치형 앱 전용이라, 1.5초마다 알림 목록을 보고 '지난번에 없던 id' 를 새 알림으로 본다.
  켜는 순간 이미 쌓여 있던 알림은 새 알림으로 치지 않는다(처음 한 번은 기준선만 잡는다).
"""
import asyncio
import ctypes
import json
import os
import sys
import threading
import time
from ctypes import wintypes

try:
    from winrt.windows.ui.notifications.management import UserNotificationListener, UserNotificationListenerAccessStatus
    from winrt.windows.ui.notifications import NotificationKinds
    import winrt.windows.applicationmodel  # noqa: F401  (알림의 앱 이름을 읽는 데 필요)
    AVAILABLE = True
except Exception:          # 패키지가 없거나 윈도우가 지원하지 않으면 기능만 빠진다
    UserNotificationListener = None
    AVAILABLE = False

POLL_SECONDS = 1.5
RETRY_SECONDS = 30.0


# ---------------------------------------------------------------- 알림 센터
CENTER_TITLES = ("알림 센터", "notification center", "action center")


def foreground_info():
    """지금 맨 앞 창의 (실행 파일 이름 소문자, 창 클래스, 제목). 못 읽으면 ('', '', '')."""
    try:
        u = ctypes.WinDLL("user32", use_last_error=True)
        k = ctypes.WinDLL("kernel32", use_last_error=True)
        u.GetForegroundWindow.restype = wintypes.HWND
        k.OpenProcess.restype = wintypes.HANDLE
        k.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        k.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
        k.CloseHandle.argtypes = [wintypes.HANDLE]
        h = u.GetForegroundWindow()
        if not h:
            return "", "", ""
        pid = wintypes.DWORD()
        u.GetWindowThreadProcessId(h, ctypes.byref(pid))
        cls = ctypes.create_unicode_buffer(128)
        u.GetClassNameW(h, cls, 128)
        title = ctypes.create_unicode_buffer(256)
        u.GetWindowTextW(h, title, 256)
        exe = ""
        ph = k.OpenProcess(0x1000, False, pid.value)          # PROCESS_QUERY_LIMITED_INFORMATION
        if ph:
            buf = ctypes.create_unicode_buffer(520)
            n = wintypes.DWORD(520)
            if k.QueryFullProcessImageNameW(ph, 0, buf, ctypes.byref(n)):
                exe = os.path.basename(buf.value).lower()
            k.CloseHandle(ph)
        return exe, cls.value, title.value
    except Exception:
        return "", "", ""


def center_open(info=None):
    """윈도우 알림 센터가 열려 있나(맨 앞 창이 ShellExperienceHost 의 '알림 센터'). 빠른 설정·캘린더 창은 제목이 달라 해당하지 않는다."""
    exe, _cls, title = info if info is not None else foreground_info()
    return exe == "shellexperiencehost.exe" and any(t in (title or "").lower() for t in CENTER_TITLES)


def center_hotkey(build=None):
    """알림 센터를 여는 단축키의 가상 키 코드: 윈도우 11(빌드 22000 이상)은 Win+N, 윈도우 10 은 Win+A."""
    if build is None:
        try:
            build = int(sys.getwindowsversion().build)
        except Exception:
            build = 22000
    return 0x4E if build >= 22000 else 0x41


def open_center(build=None, info=None, send=None):
    """윈도우 알림 센터를 연다. 이미 열려 있으면 단축키가 '닫기'가 되므로 아무것도 하지 않는다. 눌렀으면 True."""
    if center_open(info):
        return False
    vk = center_hotkey(build)
    if send is None:
        def send(keys):
            u = ctypes.WinDLL("user32", use_last_error=True)
            for v in keys:
                u.keybd_event(v, 0, 0, 0)
            for v in reversed(keys):
                u.keybd_event(v, 0, 2, 0)
    send([0x5B, vk])
    return True


def is_ignored(app_name, ignore_list):
    """앱 이름이 무시 목록(쉼표로 구분, 대소문자 무시, 부분 일치)에 걸리는가."""
    name = str(app_name or "").lower()
    for part in str(ignore_list or "").split(","):
        part = part.strip().lower()
        if part and part in name:
            return True
    return False


MAX_APPS = 200          # 기억해 둘 앱 이름의 최대 개수(오래 안 온 것부터 잊는다)


def record_apps(apps, names, new_ids, now=None):
    """알림을 보낸 앱 이름을 모아 둔다(설정 창에서 앱별로 끌 수 있게). 이름과 횟수·마지막 시각만 기억하고 알림 내용은 보지 않는다.
    apps: {이름: {"count": 건수, "last": 마지막으로 온 시각}} (이 함수가 바꾼다), names: {id: 앱 이름}, new_ids: 이번에 새로 온 id. 바뀌었으면 True."""
    now = time.time() if now is None else now
    changed = False
    for i, n in names.items():
        n = str(n or "").strip()[:80]
        if not n:
            continue
        rec = apps.get(n)
        if rec is None:
            rec = apps[n] = {"count": 0, "last": 0}
            changed = True
        if i in new_ids:
            rec["count"] += 1
            rec["last"] = now
            changed = True
    if len(apps) > MAX_APPS:
        for n, _ in sorted(apps.items(), key=lambda kv: kv[1].get("last", 0))[:len(apps) - MAX_APPS]:
            del apps[n]
        changed = True
    return changed


def list_apps(apps, ignore_list, limit=60):
    """설정 창에 보여 줄 목록: 최근에 알림을 보낸 앱부터. ignored = 지금 설정으로 무시되는 앱인가."""
    rows = [{"name": n, "count": int(r.get("count", 0)), "last": float(r.get("last", 0)), "ignored": is_ignored(n, ignore_list)} for n, r in apps.items()]
    rows.sort(key=lambda r: (-r["last"], r["name"].lower()))
    return rows[:limit]


def diff_new(seen, current_ids):
    """seen: 지난번까지 본 id 집합, current_ids: 지금 목록의 id 들. -> (새 id 목록(정렬), 다음 seen). 닫힌 알림은 seen 에서 빠진다."""
    cur = set(current_ids)
    return sorted(cur - set(seen)), cur


class NotificationWatch:
    """백그라운드 스레드에서 알림 목록을 보다가, 새 알림이 있으면 on_new(앱 이름 목록) 을 부른다."""

    def __init__(self, on_new, enabled=lambda: True, log=None, poll=POLL_SECONDS, fetch=None, on_clear=None, center=None, center_poll=0.4, ignore=lambda: "", store_path=None):
        self._on_new = on_new
        self._ignore = ignore          # 알리지 않을 앱 이름(쉼표로 구분, 부분 일치). 호출할 때마다 읽는다(설정이 바뀌어도 바로 반영)
        self._on_clear = on_clear or (lambda reason: None)
        self._center = center or center_open          # 테스트에서 바꿀 수 있다
        self._center_poll = center_poll
        self._unread = set()           # 새로 와서 아직 처리되지 않은 알림 id
        self._enabled = enabled
        self._log = log or (lambda m: None)
        self._poll = poll
        self._fetch = fetch            # 테스트용: async () -> [(id, 앱 이름), ...]
        self._stop = threading.Event()
        self._thread = None
        self._seen = None              # None = 아직 기준선을 잡지 않음
        self.status = "off"            # off | ok | denied | unavailable
        self._store_path = store_path  # 알림을 보낸 앱 이름 목록을 저장할 파일(없으면 메모리에만)
        self.apps = self._load_apps()

    def _load_apps(self):
        try:
            if self._store_path and os.path.exists(self._store_path):
                with open(self._store_path, encoding="utf-8") as f:
                    d = json.load(f)
                if isinstance(d, dict):
                    return {str(k): {"count": int(v.get("count", 0)), "last": float(v.get("last", 0))} for k, v in d.items() if isinstance(v, dict)}
        except Exception as e:
            self._log(f"winnotif: could not read the app list: {e!r}")
        return {}

    def _save_apps(self):
        try:
            if self._store_path:
                tmp = self._store_path + ".tmp"
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(self.apps, f, ensure_ascii=False)
                os.replace(tmp, self._store_path)
        except Exception as e:
            self._log(f"winnotif: could not save the app list: {e!r}")

    def start(self):
        if self._thread is None:
            self._thread = threading.Thread(target=lambda: asyncio.run(self._main()), daemon=True, name="win-notify")
            self._thread.start()

    def stop(self):
        self._stop.set()

    def acknowledge(self):
        """사용자가 알림을 확인했다(동그라미를 눌렀다): 쌓인 새 알림을 처리된 것으로 본다."""
        self._unread = set()

    # ------------------------------------------------------------------
    async def _ensure_access(self, listener):
        """허용이면 True. 미설정이면 한 번 요청한다."""
        st = listener.get_access_status()
        if st == UserNotificationListenerAccessStatus.UNSPECIFIED:
            try:
                st = await listener.request_access_async()
            except Exception as e:
                self._log(f"winnotif: request access failed: {e!r}")
                st = listener.get_access_status()
        return st == UserNotificationListenerAccessStatus.ALLOWED

    async def _fetch_winrt(self, listener):
        items = await listener.get_notifications_async(NotificationKinds.TOAST)
        out = []
        for n in items:
            try:
                name = n.app_info.display_info.display_name
            except Exception:
                name = ""
            out.append((int(n.id), str(name or "")))
        return out

    async def _main(self):
        listener = None
        if self._fetch is None:
            if not AVAILABLE:
                self.status = "unavailable"
                self._log("winnotif: winrt notification packages are not available")
                return
            listener = UserNotificationListener.current
        while not self._stop.is_set():
            try:
                if not self._enabled():
                    self.status = "off"
                    self._seen = None            # 다시 켜면 그때 쌓여 있는 것은 새 알림으로 치지 않는다
                    await asyncio.sleep(1.0)
                    continue
                if listener is not None and self.status != "ok":
                    if not await self._ensure_access(listener):
                        if self.status != "denied":
                            self._log("winnotif: notification access is not allowed (Windows Settings > Privacy & security > Notifications)")
                        self.status = "denied"
                        await asyncio.sleep(RETRY_SECONDS)
                        continue
                    self.status = "ok"
                items = await (self._fetch() if self._fetch else self._fetch_winrt(listener))
                self.status = "ok"
                names = {i: n for i, n in items}
                if self._seen is None:
                    self._seen = set(names)       # 기준선
                    self._unread = set()
                    if record_apps(self.apps, names, set()):      # 지금 쌓여 있는 알림의 앱 이름도 목록에 올려 둔다(알림이 새로 오기 전에도 끌 수 있게)
                        self._save_apps()
                else:
                    new, self._seen = diff_new(self._seen, names)
                    if record_apps(self.apps, names, set(new)):      # 무시할 앱이어도 목록에는 올린다(다시 켤 수 있게)
                        self._save_apps()
                    new = [i for i in new if not is_ignored(names[i], self._ignore())]      # 무시할 앱의 알림은 새 알림으로도, 처리 대기로도 세지 않는다
                    had = bool(self._unread)
                    self._unread = (self._unread & set(names)) | set(new)
                    if new:
                        self._on_new([names[i] for i in new])
                    elif had and not self._unread:
                        self._on_clear("handled")          # 윈도우에서 새 알림을 모두 처리(닫음/지움)했다
            except Exception as e:
                self._log(f"winnotif error: {e!r}")
                await asyncio.sleep(RETRY_SECONDS)
                continue
            # 다음 조회까지 기다리는 동안, 새 알림이 쌓여 있으면 알림 센터가 열렸는지 자주 본다
            waited = 0.0
            while waited < self._poll and not self._stop.is_set():
                step = min(self._center_poll, self._poll - waited)
                await asyncio.sleep(step)
                waited += step
                if self._unread and self._center():
                    self._unread = set()
                    self._on_clear("opened")
