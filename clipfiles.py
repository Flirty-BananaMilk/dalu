# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Flirty_BananaMilk — 상업적 이용 금지, 자세한 내용은 LICENSE
"""파일을 윈도우 클립보드에 '복사'해 둔다(탐색기에서 파일을 Ctrl+C 한 것과 같다): 폰에서 가져온 사진·동영상을 Ctrl+V 로 붙여넣을 수 있게.

 - CF_HDROP(파일 목록) + 'Preferred DropEffect'(복사): 탐색기·카카오톡·디스코드 같은 곳에 파일로 붙는다. 이동이 아니라 복사로 표시한다.
 - 파일이 사진 한 장이면 그림(CF_DIB)도 같이 넣는다: 그림판·브라우저·문서 편집기처럼 파일이 아니라 그림을 붙이는 곳을 위해서.
 - 파일 내용은 로그에 남기지 않는다. 클립보드를 쓰는 것은 사용자가 '복사'를 눌렀을 때뿐이다.
"""
import ctypes
import io
import os
import struct
import time
from ctypes import wintypes

CF_DIB = 8
CF_HDROP = 15
GMEM_MOVEABLE = 0x0002
GMEM_ZEROINIT = 0x0040
MAX_FILES = 40
MAX_PIXELS = 40_000_000           # 이보다 큰 그림은 그림 형식으로는 넣지 않는다(파일로는 붙는다)
IMAGE_EXT = (".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp")

# 윈도우 호출부: 시험에서는 바꿔 끼운다(사용자의 실제 클립보드를 건드리지 않게)
try:
    _user32 = ctypes.WinDLL("user32", use_last_error=True)
    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
except Exception:          # 윈도우가 아닌 곳(문서 생성·시험)
    _user32 = _kernel32 = None


def build_dropfiles(paths):
    """DROPFILES 구조(머리 20바이트) + 와이드 문자 경로들(각각 널로 끝나고, 마지막에 널 하나 더)."""
    body = "".join(os.path.abspath(p) + "\0" for p in paths) + "\0"
    head = struct.pack("<IiiII", 20, 0, 0, 0, 1)          # pFiles=20, pt=(0,0), fNC=0, fWide=1
    return head + body.encode("utf-16-le")


def _dib_of(path):
    """사진 파일 -> DIB 바이트(BMP 파일 머리 14바이트를 뗀 것). 그림이 아니거나 너무 크면 None."""
    if not str(path).lower().endswith(IMAGE_EXT):
        return None
    try:
        from PIL import Image
        with Image.open(path) as img:
            if img.width * img.height > MAX_PIXELS:
                return None
            try:
                from PIL import ImageOps
                img = ImageOps.exif_transpose(img)          # 폰 사진의 회전 정보를 적용한다(세로 사진이 눕혀 붙던 것)
            except Exception:
                pass
            if img.mode in ("RGBA", "LA", "P"):
                rgba = img.convert("RGBA")
                bg = Image.new("RGB", rgba.size, (255, 255, 255))
                bg.paste(rgba, mask=rgba.split()[3])          # 투명한 곳은 흰색(DIB 는 투명을 못 쓰는 앱이 많다)
                img = bg
            else:
                img = img.convert("RGB")
            bmp = io.BytesIO()
            img.save(bmp, format="BMP")
        return bmp.getvalue()[14:]
    except Exception:
        return None


def _put(fmt, data):
    """클립보드가 열려 있는 상태에서 한 가지 형식을 넣는다. 성공 여부."""
    _kernel32.GlobalAlloc.restype = ctypes.c_void_p
    _kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    h = _kernel32.GlobalAlloc(GMEM_MOVEABLE | GMEM_ZEROINIT, len(data))
    if not h:
        return False
    _kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
    _kernel32.GlobalLock.restype = ctypes.c_void_p
    _kernel32.GlobalFree.argtypes = [ctypes.c_void_p]
    p = _kernel32.GlobalLock(h)
    if not p:
        _kernel32.GlobalFree(h)
        return False
    ctypes.memmove(p, data, len(data))
    _kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    _kernel32.GlobalUnlock(h)
    _user32.SetClipboardData.argtypes = [wintypes.UINT, ctypes.c_void_p]
    _user32.SetClipboardData.restype = ctypes.c_void_p
    if _user32.SetClipboardData(fmt, h):
        return True
    _kernel32.GlobalFree(h)          # 클립보드가 받지 않았으니 이 메모리는 아직 우리 것이다
    return False


def write_files(paths):
    """파일들을 클립보드에 복사해 둔다. 반환: 올린 파일 수(실패면 0). 없는 파일은 뺀다."""
    if _user32 is None or _kernel32 is None:
        return 0
    files = [os.path.abspath(str(p)) for p in (paths or [])[:MAX_FILES] if p and os.path.isfile(str(p))]
    if not files:
        return 0
    dib = _dib_of(files[0]) if len(files) == 1 else None
    for _ in range(10):
        if _user32.OpenClipboard(None):
            break
        time.sleep(0.03)
    else:
        return 0
    try:
        _user32.EmptyClipboard()
        if not _put(CF_HDROP, build_dropfiles(files)):
            return 0
        _user32.RegisterClipboardFormatW.argtypes = [wintypes.LPCWSTR]
        _user32.RegisterClipboardFormatW.restype = wintypes.UINT
        eff = _user32.RegisterClipboardFormatW("Preferred DropEffect")
        if eff:
            _put(eff, struct.pack("<I", 1))          # DROPEFFECT_COPY: 붙여넣어도 원본이 옮겨지지 않는다
        if dib:
            _put(CF_DIB, dib)
        return len(files)
    finally:
        _user32.CloseClipboard()
