# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Flirty_BananaMilk — 상업적 이용 금지, 자세한 내용은 LICENSE
"""노치 뒤의 화면을 작게 찍어 노치 본체를 '유리'처럼 보이게 하는 도구 (설정 > 노치 리퀴드 글래스 > 전체).

- 창이 투명해서 CSS 의 backdrop-filter 로는 바탕화면을 읽을 수 없다. 그래서 노치 뒤의 화면을 직접 찍어 작은 그림으로 화면(HTML)에 넘긴다.
- 노치 창 자신이 찍히면(노치가 노치를 비춤) 안 되므로 SetWindowDisplayAffinity(WDA_EXCLUDEFROMCAPTURE)로 이 창만 캡처에서 뺀다.
  (그 대가로 화면 녹화/스크린샷에 노치가 찍히지 않는다. 설정에서 '전체'를 켰을 때만 적용하고, 끄면 원래대로 되돌린다.)
- 굴절이 보일 만큼은 선명해야 해서 320px 너비로 줄여 넘긴다(수십 KB). 초당 2번이면 충분하다.
"""
import base64
import ctypes
import http.server
import secrets
import socketserver
import sys
import struct
import threading
import time
import zlib
from ctypes import wintypes

WDA_NONE = 0x0
WDA_EXCLUDEFROMCAPTURE = 0x11
SRCCOPY = 0x00CC0020
CAPTUREBLT = 0x40000000
HALFTONE = 4
DIB_RGB_COLORS = 0

_user32 = ctypes.WinDLL("user32", use_last_error=True)
_gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
_user32.GetDC.argtypes = [wintypes.HWND]
_user32.GetDC.restype = wintypes.HDC
_user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
_user32.SetWindowDisplayAffinity.argtypes = [wintypes.HWND, wintypes.DWORD]
_user32.SetWindowDisplayAffinity.restype = wintypes.BOOL
_gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
_gdi32.CreateCompatibleDC.restype = wintypes.HDC
_gdi32.DeleteDC.argtypes = [wintypes.HDC]
_gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
_gdi32.SelectObject.restype = wintypes.HGDIOBJ
_gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
_gdi32.SetStretchBltMode.argtypes = [wintypes.HDC, ctypes.c_int]
_gdi32.StretchBlt.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                              wintypes.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.DWORD]
_gdi32.StretchBlt.restype = wintypes.BOOL
_gdi32.CreateDIBSection.argtypes = [wintypes.HDC, ctypes.c_void_p, wintypes.UINT, ctypes.POINTER(ctypes.c_void_p), wintypes.HANDLE, wintypes.DWORD]
_gdi32.CreateDIBSection.restype = wintypes.HBITMAP


class _BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG), ("biPlanes", wintypes.WORD),
                ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD), ("biSizeImage", wintypes.DWORD),
                ("biXPelsPerMeter", wintypes.LONG), ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD),
                ("biClrImportant", wintypes.DWORD)]


def set_excluded(hwnd, on):
    """창을 화면 캡처에서 뺀다/되돌린다. 지원하지 않으면(Windows 10 2004 미만) False."""
    try:
        return bool(_user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE if on else WDA_NONE))
    except Exception:
        return False


def grab_rgb(x, y, w, h, out_w, out_h):
    """화면의 (x,y,w,h) 물리 픽셀 영역을 out_w x out_h 로 줄여 찍는다. (위에서 아래, BGR, 줄당 out_w*3 바이트) 실패하면 None."""
    if w < 4 or h < 4 or out_w < 1 or out_h < 1:
        return None
    hdc = _user32.GetDC(None)
    if not hdc:
        return None
    mdc = hbm = old = None
    try:
        mdc = _gdi32.CreateCompatibleDC(hdc)
        bi = _BITMAPINFOHEADER(ctypes.sizeof(_BITMAPINFOHEADER), out_w, -out_h, 1, 32, 0, 0, 0, 0, 0, 0)
        bits = ctypes.c_void_p()
        hbm = _gdi32.CreateDIBSection(hdc, ctypes.byref(bi), DIB_RGB_COLORS, ctypes.byref(bits), None, 0)
        if not hbm or not bits.value:
            return None
        old = _gdi32.SelectObject(mdc, hbm)
        _gdi32.SetStretchBltMode(mdc, HALFTONE)
        if not _gdi32.StretchBlt(mdc, 0, 0, out_w, out_h, hdc, int(x), int(y), int(w), int(h), SRCCOPY | CAPTUREBLT):
            return None
        raw = ctypes.string_at(bits.value, out_w * out_h * 4)
    finally:
        if mdc and old:
            _gdi32.SelectObject(mdc, old)
        if hbm:
            _gdi32.DeleteObject(hbm)
        if mdc:
            _gdi32.DeleteDC(mdc)
        _user32.ReleaseDC(None, hdc)
    out = bytearray(out_w * out_h * 3)
    out[0::3] = raw[0::4]
    out[1::3] = raw[1::4]
    out[2::3] = raw[2::4]
    return bytes(out)


def to_png(rgb_bgr, w, h):
    """BGR 바이트를 PNG 로 (표준 라이브러리만 사용). 브라우저가 어디서나 읽는 형식이라 BMP 의 자잘한 호환 문제를 피한다."""
    rows = []
    for r in range(h):
        line = rgb_bgr[r * w * 3:(r + 1) * w * 3]
        rgb = bytearray(len(line))
        rgb[0::3] = line[2::3]
        rgb[1::3] = line[1::3]
        rgb[2::3] = line[0::3]
        rows.append(b"\x00" + bytes(rgb))

    def chunk(tag, data):
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(b"".join(rows), 1)) + chunk(b"IEND", b""))


class FrameStream:
    """가장 최근 프레임을 multipart/x-mixed-replace 스트림으로 내보내는 작은 로컬 서버(127.0.0.1, 무작위 포트, 무작위 주소).
    화면(<img>)이 이 주소를 열어 두면 브라우저가 프레임을 직접 받아 그린다 — 파이썬이 프레임마다 웹뷰에 스크립트를 실행시킬 필요가 없어 60fps 가 가능하다."""

    BOUNDARY = "deskframe"

    def __init__(self):
        self._cv = threading.Condition()
        self._frame, self._seq, self._open = None, 0, True
        self.token = secrets.token_urlsafe(12)
        outer = self

        class Handler(http.server.BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *a):
                pass

            def do_GET(self):
                if self.path.split("?")[0] != "/" + outer.token:
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=" + outer.BOUNDARY)
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                seen = 0
                try:
                    while True:
                        with outer._cv:
                            outer._cv.wait_for(lambda: not outer._open or outer._seq != seen, timeout=5)
                            if not outer._open:
                                return
                            frame, seen = outer._frame, outer._seq
                        if frame is None:
                            continue
                        self.wfile.write(b"--" + outer.BOUNDARY.encode() + b"\r\nContent-Type: image/png\r\nContent-Length: "
                                         + str(len(frame)).encode() + b"\r\n\r\n" + frame + b"\r\n")
                        self.wfile.flush()
                except (OSError, ValueError):
                    return

        class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
            daemon_threads = True

            def handle_error(self, request, client_address):
                # 화면이 새로고침되거나 닫혀서 스트림 연결이 끊기는 건 정상이다: 로그에 긴 오류를 남기지 않는다
                if isinstance(sys.exc_info()[1], (ConnectionError, TimeoutError, OSError)):
                    return
                super().handle_error(request, client_address)

        self._server = Server(("127.0.0.1", 0), Handler)
        self.port = self._server.server_address[1]
        threading.Thread(target=self._server.serve_forever, daemon=True, name="desk-stream").start()

    @property
    def url(self):
        return f"http://127.0.0.1:{self.port}/{self.token}"

    def publish(self, png):
        with self._cv:
            self._frame, self._seq = png, self._seq + 1
            self._cv.notify_all()

    def close(self):
        with self._cv:
            self._open = False
            self._cv.notify_all()
        try:
            self._server.shutdown()
            self._server.server_close()
        except Exception:
            pass


class DeskCapture:
    """노치 뒤 화면을 주기적으로 찍어 push(data_url) 로 넘긴다. 바뀐 게 없으면 넘기지 않는다."""

    OUT_W, OUT_H = 320, 102         # 600x190(CSS px) 영역의 축소본 (굴절이 보이려면 너무 뭉개지면 안 된다)

    def __init__(self, get_hwnd, get_rect, push, log=None, interval=0.5):
        self._get_hwnd, self._get_rect, self._push = get_hwnd, get_rect, push
        self._log = log or (lambda *_: None)
        self._interval = interval
        self._on = False
        self._excluded_hwnd = None
        self._thread = None
        self._last = None
        self._stream = None
        self._frozen = False
        self._frozen_until = 0.0
        self._thaw_timer = None
        self._visible = False        # 설정 '캡처·영상 녹화에서 노치: 표시' — 캡처 모드를 계속 켜 둔다(뒤 화면은 정지 화면)
        self.supported = True

    def enable(self, on):
        """켜면 노치 창을 캡처에서 빼고 찍기 시작, 끄면 되돌리고 멈춘다. 켜기에 성공했는지 돌려준다."""
        if on and not self._on:
            hwnd = self._get_hwnd()
            if not hwnd:
                return False
            if not set_excluded(hwnd, True):
                self.supported = False
                self._log("deskcap: SetWindowDisplayAffinity failed — see-through notch body unavailable")
                return False
            self._excluded_hwnd = hwnd
            self._on = True
            self._last = None
            self._t_on = time.perf_counter()
            self._stream = FrameStream()
            self._thread = threading.Thread(target=self._loop, daemon=True, name="desk-capture")
            self._thread.start()
            self._log("deskcap: on (notch window excluded from screen capture)")
        elif not on and self._on:
            self._on = False
            self._frozen = False
            if self._thaw_timer is not None:
                self._thaw_timer.cancel()
                self._thaw_timer = None
            if self._stream is not None:
                self._stream.close()
                self._stream = None
            if self._excluded_hwnd:
                set_excluded(self._excluded_hwnd, False)
                self._excluded_hwnd = None
            self._log("deskcap: off")
        return self._on or not on

    def freeze(self, seconds):
        """캡처 모드: 지금 화면을 얼려 두고(뒤 화면 갱신 멈춤) 노치 창을 화면 캡처에 다시 보이게 한다. seconds 뒤에 자동으로 원래대로.
        노치가 자기 자신을 비추는 되먹임은 화면을 얼려 두는 동안 생기지 않는다. 캡처가 꺼져 있으면(전체 모드가 아니면) 할 일이 없다 -> False."""
        if not self._on or not self._excluded_hwnd:
            return False
        was = self._frozen
        self._frozen = True
        set_excluded(self._excluded_hwnd, False)
        if self._thaw_timer is not None:
            self._thaw_timer.cancel()
        now = time.monotonic()
        if self._visible:
            return True             # 이미 계속 켜져 있다
        until = max(self._frozen_until if was else 0.0, now + max(1.0, float(seconds)))      # 이미 더 길게 켜 둔 캡처 모드(녹화용)를 짧은 요청이 줄이지 않는다
        self._frozen_until = until
        self._thaw_timer = threading.Timer(until - now, self.thaw)
        self._thaw_timer.daemon = True
        self._thaw_timer.start()
        if not was:          # 이미 켜져 있을 때(자동 캡처 모드가 계속 연장할 때)는 로그를 반복하지 않는다
            self._log(f"deskcap: capture mode on for {seconds:.0f}s (notch visible to screenshots)")
        return True

    def set_visible(self, on):
        """'표시': 노치 창을 캡처에서 빼지 않고(스크린샷·녹화에 찍힘, NVIDIA 녹화도 거부하지 않음) 뒤 화면은 마지막으로 찍은 정지 화면으로 둔다.
        첫 화면이 오기 전에 얼리면 뒤 화면이 영영 안 오므로, 첫 화면이 온 뒤에 적용한다(_loop)."""
        self._visible = bool(on)
        if not self._on or not self._excluded_hwnd:
            return
        if on:
            if self._last is not None:
                self._apply_visible()
        else:
            self.thaw()

    def _apply_visible(self):
        if self._thaw_timer is not None:
            self._thaw_timer.cancel()
            self._thaw_timer = None
        if not self._frozen:
            self._log("deskcap: notch shown in captures (still background)")
        self._frozen = True
        self._frozen_until = float("inf")
        set_excluded(self._excluded_hwnd, False)

    def thaw(self):
        if self._visible and self._on and self._excluded_hwnd:
            return                  # '표시' 설정이면 캡처 모드가 끝나지 않는다
        if self._thaw_timer is not None:
            self._thaw_timer.cancel()
            self._thaw_timer = None
        was = self._frozen
        self._frozen = False
        self._frozen_until = 0.0
        if self._on and self._excluded_hwnd:
            set_excluded(self._excluded_hwnd, True)
        if was:
            self._log("deskcap: capture mode off")

    @property
    def frozen(self):
        return self._frozen

    def frame(self):
        """지금 한 장을 찍어 PNG data URL 로 (테스트/진단용)."""
        rect = self._get_rect()
        if not rect:
            return None
        rgb = grab_rgb(*rect, self.OUT_W, self.OUT_H)
        if rgb is None:
            return None
        return "data:image/png;base64," + base64.b64encode(to_png(rgb, self.OUT_W, self.OUT_H)).decode("ascii")

    ACTIVE_GAP = 1 / 60.0            # 화면이 움직이는 동안의 목표 간격 (60fps)
    IDLE_GAP = 0.1                   # 한동안 안 바뀌면 10fps 로 낮춰 CPU 를 아낀다
    IDLE_AFTER = 1.0

    def _loop(self):
        """뒤 화면이 움직이는 동안은 60fps 로 찍어 바뀐 프레임만 넘기고, 1초 넘게 안 바뀌면 10fps 로 쉰다."""
        prev, last_change = None, time.perf_counter()
        self._url_at = time.perf_counter()
        self.stats = {"frames": 0, "since": time.perf_counter()}
        while self._on:
            t0 = time.perf_counter()
            try:
                rect = self._get_rect()
                rgb = grab_rgb(*rect, self.OUT_W, self.OUT_H) if (rect and not self._frozen) else None      # 캡처 모드 중에는 찍지 않는다(되먹임 방지, 마지막 화면 유지)
                if rgb is not None and rgb != prev:
                    prev = rgb
                    last_change = t0
                    png = to_png(rgb, self.OUT_W, self.OUT_H)
                    stream = self._stream
                    if stream is not None:
                        stream.publish(png)
                    first = self._last is None
                    self._last = True
                    if first and self._visible:
                        self._apply_visible()
                    if first and stream is not None:
                        self._push(stream.url)          # 화면에 스트림 주소를 한 번 알린다 (이후 프레임은 브라우저가 직접 받는다)
                        self._log(f"deskcap: streaming at {stream.url.rsplit('/', 1)[0]}/... first frame after {t0 - self._t_on:.2f}s ({len(png)} bytes)")
                    self.stats["frames"] += 1
                if self._stream is not None and t0 - self._url_at > 3.0:
                    self._url_at = t0
                    self._push(self._stream.url)        # 화면이 새로 고쳐졌어도 다시 연결되도록 주기적으로 알린다 (같은 주소면 화면이 무시한다)
            except Exception as e:
                self._log(f"deskcap error: {e!r}")
            if t0 - self.stats["since"] >= 10.0:
                if self.stats["frames"] >= 20:                  # 움직임이 있었던 구간만 기록
                    self._log(f"deskcap: {self.stats['frames'] / (t0 - self.stats['since']):.0f} frames/s over the last {t0 - self.stats['since']:.0f}s")
                self.stats = {"frames": 0, "since": t0}
            gap = self.ACTIVE_GAP if (t0 - last_change) < self.IDLE_AFTER else self.IDLE_GAP
            time.sleep(max(0.001, gap - (time.perf_counter() - t0)))
