# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Flirty_BananaMilk — 상업적 이용 금지, 자세한 내용은 LICENSE
"""클립보드 이미지: 윈도우 클립보드 <-> PNG 바이트, 그리고 폰과 주고받을 때의 조각 나누기/합치기.

- 이미지는 PNG 로 바꿔 보낸다. 한 번에 보내는 조각은 원본 192 KiB(base64 로 256 KiB: 한 줄 1 MiB 제한 안), 전체는 8 MiB 까지.
- 조각은 같은 TLS 연결에서 순서대로 오고, id 로 묶어 합친다. 오래 걸리거나 어긋난 조각 묶음은 버린다. 아무것도 저장하지 않는다(메모리에서만).
"""
import base64
import ctypes
import hashlib
import io
import secrets
import time
from ctypes import wintypes

CHUNK_BYTES = 192 * 1024
MAX_BYTES = 8 * 1024 * 1024
MAX_PIXELS = 40_000_000
ASSEMBLE_SECONDS = 40

CF_DIB = 8


def png_hash(png):
    return hashlib.sha256(png).hexdigest()


def split(png, mime="image/png"):
    """PNG 바이트 -> 보낼 메시지(dict) 목록. 너무 크면 빈 목록."""
    if not png or len(png) > MAX_BYTES:
        return []
    iid = secrets.token_hex(6)
    parts = [png[i:i + CHUNK_BYTES] for i in range(0, len(png), CHUNK_BYTES)] or [b""]
    return [{"t": "clip_img", "id": iid, "seq": i, "n": len(parts), "mime": mime, "b64": base64.b64encode(p).decode("ascii")} for i, p in enumerate(parts)]


class Assembler:
    """받은 조각을 id 별로 모아 다 모이면 이미지 바이트를 돌려준다. 어긋나면 그 묶음을 버린다."""

    def __init__(self):
        self._open = {}                 # id -> {"n", "parts", "size", "t", "mime"}

    def add(self, m):
        """조각 하나를 넣는다. 다 모였으면 (바이트, mime), 아니면 None."""
        try:
            iid, seq, n = str(m["id"]), int(m["seq"]), int(m["n"])
            data = base64.b64decode(str(m["b64"]), validate=True)
        except Exception:
            return None
        now = time.time()
        for k in [k for k, v in self._open.items() if now - v["t"] > ASSEMBLE_SECONDS]:
            self._open.pop(k, None)                          # 오래된 미완성 묶음 정리
        if n < 1 or n > MAX_BYTES // CHUNK_BYTES + 2 or seq < 0 or seq >= n or len(data) > CHUNK_BYTES + 16:
            self._open.pop(iid, None)
            return None
        e = self._open.get(iid)
        if e is None:
            if seq != 0:
                return None
            if len(self._open) >= 3:                          # 동시에 3개까지만
                self._open.pop(next(iter(self._open)), None)
            e = self._open[iid] = {"n": n, "parts": [], "size": 0, "t": now, "mime": str(m.get("mime", "image/png"))[:40]}
        if e["n"] != n or seq != len(e["parts"]):
            self._open.pop(iid, None)                         # 순서가 어긋남
            return None
        e["parts"].append(data)
        e["size"] += len(data)
        if e["size"] > MAX_BYTES:
            self._open.pop(iid, None)
            return None
        if len(e["parts"]) == n:
            self._open.pop(iid, None)
            return b"".join(e["parts"]), e["mime"]
        return None


# ---------------------------------------------------------------- 윈도우 클립보드 <-> PNG
_user32 = ctypes.windll.user32
_kernel32 = ctypes.windll.kernel32
_user32.IsClipboardFormatAvailable.argtypes = [wintypes.UINT]


def clipboard_has_image():
    return bool(_user32.IsClipboardFormatAvailable(CF_DIB) or _user32.IsClipboardFormatAvailable(17))      # CF_DIB / CF_DIBV5


def read_png():
    """클립보드의 이미지를 PNG 바이트로. 이미지가 아니거나 너무 크면 None."""
    try:
        from PIL import Image, ImageGrab
        img = ImageGrab.grabclipboard()
        if not isinstance(img, Image.Image):
            return None
        if img.width * img.height > MAX_PIXELS:
            return None
        out = io.BytesIO()
        img.save(out, format="PNG", optimize=False)
        png = out.getvalue()
        return png if len(png) <= MAX_BYTES else None
    except Exception:
        return None


def write_png(png):
    """PNG 바이트를 클립보드에 이미지(CF_DIB)로 넣는다. 성공 여부."""
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(png))
        if img.width * img.height > MAX_PIXELS:
            return False
        if img.mode in ("RGBA", "LA", "P"):
            rgba = img.convert("RGBA")
            bg = Image.new("RGB", rgba.size, (255, 255, 255))
            bg.paste(rgba, mask=rgba.split()[3])             # 투명한 곳은 흰색(DIB 는 투명을 못 쓰는 앱이 많다)
            img = bg
        else:
            img = img.convert("RGB")
        bmp = io.BytesIO()
        img.save(bmp, format="BMP")
        dib = bmp.getvalue()[14:]                             # BMP 파일 머리(14바이트)를 떼면 DIB
    except Exception:
        return False
    for _ in range(5):
        if _user32.OpenClipboard(None):
            break
        time.sleep(0.02)
    else:
        return False
    try:
        _user32.EmptyClipboard()
        _kernel32.GlobalAlloc.restype = ctypes.c_void_p
        _kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
        h = _kernel32.GlobalAlloc(0x0002, len(dib))
        if not h:
            return False
        _kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
        _kernel32.GlobalLock.restype = ctypes.c_void_p
        p = _kernel32.GlobalLock(h)
        if not p:
            _kernel32.GlobalFree.argtypes = [ctypes.c_void_p]
            _kernel32.GlobalFree(h)
            return False
        ctypes.memmove(p, dib, len(dib))
        _kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
        _kernel32.GlobalUnlock(h)
        _user32.SetClipboardData.argtypes = [wintypes.UINT, ctypes.c_void_p]
        _user32.SetClipboardData.restype = ctypes.c_void_p
        if _user32.SetClipboardData(CF_DIB, h):
            return True
        _kernel32.GlobalFree.argtypes = [ctypes.c_void_p]
        _kernel32.GlobalFree(h)          # 클립보드가 받지 않았으니 이 메모리는 아직 우리 것이다
        return False
    finally:
        _user32.CloseClipboard()


THUMB_PX = 96


def thumb_data_uri(png, px=THUMB_PX):
    """알림 아이콘에 쓸 정사각형 미리보기(PNG 'data:' 주소). 만들 수 없으면 빈 문자열(알림은 'img' 글자로 대신한다)."""
    try:
        from PIL import Image, ImageOps
        img = Image.open(io.BytesIO(png))
        if img.width < 1 or img.height < 1 or img.width * img.height > MAX_PIXELS:
            return ""
        img.draft("RGB", (px * 2, px * 2))
        img = ImageOps.fit(img.convert("RGBA"), (px, px), method=Image.LANCZOS)
        out = io.BytesIO()
        img.save(out, format="PNG", optimize=True)
        data = out.getvalue()
        if len(data) > 200_000:
            return ""
        return "data:image/png;base64," + base64.b64encode(data).decode("ascii")
    except Exception:
        return ""
