# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Flirty_BananaMilk — 상업적 이용 금지, 자세한 내용은 LICENSE
"""클립보드 기록 (텍스트만, 메모리에만 보관).

- 기본은 꺼져 있다: 복사한 내용에는 비밀번호 등 민감한 글이 있을 수 있어서, 설정에서 켠 경우에만 읽는다.
- 비밀번호 관리자처럼 '기록에서 제외' 표시(ExcludeClipboardContentFromMonitorProcessing 등)를 붙여 복사한 내용은 저장하지 않는다.
- 디스크에는 쓰지 않는다(앱을 끄면 사라짐). 항목 수/길이 제한이 있다.
"""
import ctypes
import threading
import time
from ctypes import wintypes

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
user32.OpenClipboard.argtypes = [wintypes.HWND]
user32.GetClipboardData.argtypes = [wintypes.UINT]
user32.GetClipboardData.restype = ctypes.c_void_p
user32.IsClipboardFormatAvailable.argtypes = [wintypes.UINT]
user32.RegisterClipboardFormatW.argtypes = [wintypes.LPCWSTR]
kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
kernel32.GlobalLock.restype = ctypes.c_void_p
kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
kernel32.GlobalSize.argtypes = [ctypes.c_void_p]

CF_UNICODETEXT = 13
MAX_ITEMS = 30
MAX_CHARS = 2000
MAX_BYTES = 256 * 1024
EXCLUDE_FORMATS = ("ExcludeClipboardContentFromMonitorProcessing", "CanIncludeInClipboardHistory", "CanUploadToCloudClipboard")


def _excluded():
    """'기록하지 말 것' 표시가 있는가. CanIncludeInClipboardHistory 는 값이 0 일 때만 제외라 존재만으로 판단하지 않는다."""
    fmt = user32.RegisterClipboardFormatW(EXCLUDE_FORMATS[0])
    if fmt and user32.IsClipboardFormatAvailable(fmt):
        return True
    fmt = user32.RegisterClipboardFormatW(EXCLUDE_FORMATS[1])
    if fmt and user32.IsClipboardFormatAvailable(fmt):
        h = user32.GetClipboardData(fmt)
        if h and kernel32.GlobalSize(h) >= 4:
            p = kernel32.GlobalLock(h)
            try:
                return ctypes.c_uint32.from_address(p).value == 0 if p else False
            finally:
                kernel32.GlobalUnlock(h)
    return False


def read_text():
    """클립보드의 텍스트. (text|None, excluded:bool). 열지 못하면(다른 프로그램이 쓰는 중) (None, False)."""
    for _ in range(5):
        if user32.OpenClipboard(None):
            break
        time.sleep(0.02)
    else:
        return None, False
    try:
        if _excluded():
            return None, True
        if not user32.IsClipboardFormatAvailable(CF_UNICODETEXT):
            return None, False
        h = user32.GetClipboardData(CF_UNICODETEXT)
        if not h or kernel32.GlobalSize(h) > MAX_BYTES:
            return None, False
        p = kernel32.GlobalLock(h)
        if not p:
            return None, False
        try:
            return ctypes.wstring_at(p), False
        finally:
            kernel32.GlobalUnlock(h)
    finally:
        user32.CloseClipboard()


def write_text(text):
    """클립보드에 텍스트를 넣는다. 성공 여부."""
    data = (text + "\0").encode("utf-16-le")
    for _ in range(5):
        if user32.OpenClipboard(None):
            break
        time.sleep(0.02)
    else:
        return False
    try:
        user32.EmptyClipboard()
        kernel32.GlobalAlloc.restype = ctypes.c_void_p
        kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
        h = kernel32.GlobalAlloc(0x0002, len(data))          # GMEM_MOVEABLE
        if not h:
            return False
        p = kernel32.GlobalLock(h)
        if not p:
            kernel32.GlobalFree.argtypes = [ctypes.c_void_p]
            kernel32.GlobalFree(h)
            return False
        ctypes.memmove(p, data, len(data))
        kernel32.GlobalUnlock(h)
        user32.SetClipboardData.argtypes = [wintypes.UINT, ctypes.c_void_p]
        user32.SetClipboardData.restype = ctypes.c_void_p
        if not user32.SetClipboardData(CF_UNICODETEXT, h):
            kernel32.GlobalFree.argtypes = [ctypes.c_void_p]
            kernel32.GlobalFree(h)          # 클립보드가 받지 않았으니 이 메모리는 아직 우리 것이다
            return False
        return True
    finally:
        user32.CloseClipboard()


def normalize(text):
    """저장할 글: 앞뒤 공백 제거, 비었으면 None, 너무 길면 자른다."""
    t = (text or "").strip("\r\n\t ")
    if not t:
        return None
    return t[:MAX_CHARS]


class ClipHistory:
    """최근 항목이 앞. add 는 중복을 맨 앞으로 올린다. 스레드 안전."""

    def __init__(self, max_items=MAX_ITEMS):
        self._max = max_items
        self._items = []
        self._seq = 0
        self._lock = threading.Lock()

    def add(self, text):
        t = normalize(text)
        if t is None:
            return None
        with self._lock:
            for it in self._items:
                if it["text"] == t:
                    self._items.remove(it)
                    self._items.insert(0, it)
                    it["t"] = time.time()
                    return it["id"]
            self._seq += 1
            self._items.insert(0, {"id": self._seq, "text": t, "t": time.time()})
            del self._items[self._max:]
            return self._seq

    def list(self):
        with self._lock:
            return [dict(it) for it in self._items]

    def get(self, item_id):
        with self._lock:
            return next((dict(it) for it in self._items if it["id"] == item_id), None)

    def delete(self, item_id):
        with self._lock:
            n = len(self._items)
            self._items = [it for it in self._items if it["id"] != item_id]
            return len(self._items) != n

    def clear(self):
        with self._lock:
            self._items = []


class ClipWatcher:
    """GetClipboardSequenceNumber 가 바뀔 때만 읽는다(읽기 자체는 가벼움). enabled 는 외부에서 바꾼다."""

    def __init__(self, history, log=None, interval=0.5, on_text=None, sync_when=None, on_image=None):
        self.history = history
        self.enabled = False                 # 클립보드 '기록'을 남기는가(설정, 기본 꺼짐)
        self.on_text = on_text               # 복사된 글을 폰으로 동기화할 때 부른다: on_text(text). None 이면 동기화하지 않는다(기록 설정과 별개)
        self.sync_when = sync_when           # 지금 동기화가 필요한가(켜져 있고 폰이 연결됨). False 면 클립보드를 아예 읽지 않는다
        self.on_image = on_image             # 복사된 이미지(PNG 바이트)를 폰으로 동기화할 때 부른다: on_image(png). None 이면 이미지는 동기화하지 않는다
        self._log = log or (lambda m: None)
        self._interval = interval
        self._last_seq = user32.GetClipboardSequenceNumber()
        self._skip_next = False
        self._running = False

    def start(self):
        self._running = True
        threading.Thread(target=self._run, daemon=True, name="clipwatch").start()

    def stop(self):
        self._running = False

    def ignore_next_change(self):
        """우리가 직접 클립보드에 쓴 변경(기록에서 다시 복사)은 새 항목으로 세지 않고 맨 앞으로만 올린다."""
        self._skip_next = True

    def poll_once(self):
        seq = user32.GetClipboardSequenceNumber()
        if seq == self._last_seq:
            return False
        self._last_seq = seq
        want_sync = self.on_text is not None and (self.sync_when is None or bool(self.sync_when()))
        if not self.enabled and not want_sync:
            self._skip_next = False          # 이번 변경을 읽지 않으니 '다음 변경 건너뛰기'도 쓴 것이다(안 지우면 나중의 진짜 복사가 건너뛰어진다)
            return False
        text, excluded = read_text()
        if excluded:                                  # 비밀번호 관리자처럼 '기록·동기화 제외' 표시가 붙은 글은 어디에도 보내지 않는다
            self._skip_next = False
            return False
        if text is None:
            skip, self._skip_next = self._skip_next, False
            if want_sync and self.on_image is not None and not skip:
                self._maybe_image()
            return False
        skip, self._skip_next = self._skip_next, False
        if want_sync and not skip:     # 우리가 직접 넣은 변경(폰에서 받은 글, 기록에서 다시 복사)은 되돌려 보내지 않는다
            try:
                self.on_text(text)
            except Exception as e:
                self._log(f"clipwatch sync error: {type(e).__name__}")
        if not self.enabled:
            return False
        return self.history.add(text) is not None

    def _maybe_image(self):
        """클립보드에 이미지가 있으면 PNG 로 바꿔 콜백에 준다(글자가 없을 때만 부른다)."""
        try:
            import clipimg
            if not clipimg.clipboard_has_image():
                return
            png = clipimg.read_png()
            if png:
                self.on_image(png)
        except Exception as e:
            self._log(f"clipwatch image error: {type(e).__name__}")

    def _run(self):
        while self._running:
            try:
                self.poll_once()
            except Exception as e:
                self._log(f"clipwatch error: {e!r}")
            time.sleep(self._interval)
