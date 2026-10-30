# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Flirty_BananaMilk — 상업적 이용 금지, 자세한 내용은 LICENSE
"""시스템 상태 감시: Caps/Num/Scroll Lock, 미디어 키 입력, 입력 언어, 볼륨/음소거, 밝기, 전원(충전기/배터리), 네트워크,
기본 오디오 출력 장치(헤드폰/이어폰 감지), 입력 유휴 시간, 전체화면 앱.

각 `read_*` 는 값을 읽는 순수한 함수이고, `SysMonitor` 는 그 값을 주기적으로 읽어
'바뀐 것'만 이벤트로 `push` 에 넘긴다. 읽기 함수는 주입할 수 있어 하드웨어 없이도 테스트된다.
모든 읽기는 실패하면 None 을 돌려주고 예외를 밖으로 내지 않는다.
"""

import ctypes
import re
import threading
import time
from ctypes import wintypes

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
ole32 = ctypes.windll.ole32


# ----------------------------------------------------------------------
# 키보드: Caps Lock / 입력 언어
# ----------------------------------------------------------------------
def read_caps():
    return bool(user32.GetKeyState(0x14) & 1)   # VK_CAPITAL, 하위 비트 = 토글 상태


def read_num():
    return bool(user32.GetKeyState(0x90) & 1)   # VK_NUMLOCK


def read_scroll():
    return bool(user32.GetKeyState(0x91) & 1)   # VK_SCROLL


# 미디어 키(재생/일시정지, 다음, 이전, 정지). 키 입력을 가로채지 않고(전역 훅 없이) 눌렸는지만 본다.
MEDIA_VKS = {0xB3: 'play_pause', 0xB0: 'next', 0xB1: 'prev', 0xB2: 'stop'}


def read_media_keys():
    """{이름: (지금 눌려 있음, 지난 확인 이후 눌린 적 있음)}"""
    out = {}
    for vk, name in MEDIA_VKS.items():
        st = user32.GetAsyncKeyState(vk)
        out[name] = (bool(st & 0x8000), bool(st & 0x0001))
    return out


def lang_label(langid: int):
    """LANGID → {'code': 'KO', 'name': '한국어'}"""
    def info(kind):
        buf = ctypes.create_unicode_buffer(85)
        return buf.value if kernel32.GetLocaleInfoW(langid, kind, buf, 85) else ''
    return {
        'code': info(0x59).upper(),   # LOCALE_SISO639LANGNAME
        'name': info(0x04),           # LOCALE_SNATIVELANGNAME
    }


def read_kb_layout():
    hwnd = user32.GetForegroundWindow()
    tid = user32.GetWindowThreadProcessId(hwnd, None) if hwnd else 0
    hkl = user32.GetKeyboardLayout(tid)
    return lang_label(hkl & 0xFFFF)


# ----------------------------------------------------------------------
# 입력 유휴 시간
# ----------------------------------------------------------------------
class _LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]


def read_idle_sec():
    info = _LASTINPUTINFO()
    info.cbSize = ctypes.sizeof(info)
    if not user32.GetLastInputInfo(ctypes.byref(info)):
        return None
    # 둘 다 32비트 틱 카운트라 49일마다 한 바퀴 돈다 -> 뺄셈 결과를 32비트로 맞춘다
    return ((kernel32.GetTickCount() - info.dwTime) & 0xFFFFFFFF) / 1000.0


# ----------------------------------------------------------------------
# 전원 / 네트워크
# ----------------------------------------------------------------------
class _SYSTEM_POWER_STATUS(ctypes.Structure):
    _fields_ = [
        ("ACLineStatus", ctypes.c_ubyte), ("BatteryFlag", ctypes.c_ubyte),
        ("BatteryLifePercent", ctypes.c_ubyte), ("SystemStatusFlag", ctypes.c_ubyte),
        ("BatteryLifeTime", wintypes.DWORD), ("BatteryFullLifeTime", wintypes.DWORD),
    ]


def read_power():
    st = _SYSTEM_POWER_STATUS()
    if not kernel32.GetSystemPowerStatus(ctypes.byref(st)):
        return None
    has_battery = st.BatteryFlag != 255 and not (st.BatteryFlag & 128)
    return {
        'ac': (st.ACLineStatus == 1) if st.ACLineStatus in (0, 1) else None,
        'percent': st.BatteryLifePercent if st.BatteryLifePercent <= 100 else None,
        'has_battery': has_battery,
    }


_online_cache = {'ptr': None}


def read_online():
    """인터넷 연결 여부 (Network List Manager). 이 스레드에서 CoInitialize 가 되어 있어야 한다.

    pythonnet 은 쓰지 않는다: 웹뷰가 .NET 런타임을 초기화하는 동안 다른 스레드에서 .NET 객체를 만들면
    NullReferenceException 으로 프로세스가 죽는다.
    """
    try:
        ptr = _online_cache['ptr']
        if ptr is None:
            ptr = ctypes.c_void_p()
            hr = ole32.CoCreateInstance(ctypes.byref(_CLSID_NetworkListManager), None, _CLSCTX_ALL,
                                        ctypes.byref(_IID_INetworkListManager), ctypes.byref(ptr))
            if hr != 0 or not ptr.value:
                return None
            _online_cache['ptr'] = ptr
        flag = ctypes.c_short()
        # INetworkListManager::get_IsConnectedToInternet (IDispatch 7개 뒤 5번째 메서드 = vtable[11])
        if _vcall(ptr, 11, ctypes.c_long, ctypes.POINTER(ctypes.c_short))(ptr, ctypes.byref(flag)) != 0:
            return None
        return flag.value != 0
    except Exception:
        return None


class _DISPLAY_BRIGHTNESS(ctypes.Structure):
    _fields_ = [("ucDisplayPolicy", ctypes.c_ubyte), ("ucACBrightness", ctypes.c_ubyte), ("ucDCBrightness", ctypes.c_ubyte)]


_lcd_state = {'handle': None, 'unsupported': False}


def read_brightness():
    """노트북 내장 패널 밝기(0~100). 데스크톱/외장 모니터에는 \\\\.\\LCD 장치가 없어 None."""
    if _lcd_state['unsupported']:
        return None
    try:
        h = _lcd_state['handle']
        if h is None:
            kernel32.CreateFileW.restype = ctypes.c_void_p
            h = kernel32.CreateFileW("\\\\.\\LCD", 0x80000000, 3, None, 3, 0, None)   # GENERIC_READ, SHARE_READ|WRITE, OPEN_EXISTING
            if h in (None, ctypes.c_void_p(-1).value, 0xFFFFFFFF):
                _lcd_state['unsupported'] = True
                return None
            _lcd_state['handle'] = h
        out = _DISPLAY_BRIGHTNESS()
        got = wintypes.DWORD()
        IOCTL_VIDEO_QUERY_DISPLAY_BRIGHTNESS = 0x00230498
        kernel32.DeviceIoControl.argtypes = [ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD,
                                             ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
        if not kernel32.DeviceIoControl(h, IOCTL_VIDEO_QUERY_DISPLAY_BRIGHTNESS, None, 0,
                                        ctypes.byref(out), ctypes.sizeof(out), ctypes.byref(got), None):
            return None
        pw = read_power()
        on_ac = (pw or {}).get('ac', True)
        return int(out.ucACBrightness if on_ac else out.ucDCBrightness)
    except Exception:
        return None


# ----------------------------------------------------------------------
# 오디오: 볼륨 / 음소거 / 기본 출력 장치 (Core Audio, ctypes COM)
# ----------------------------------------------------------------------
class _GUID(ctypes.Structure):
    _fields_ = [("Data1", ctypes.c_ulong), ("Data2", ctypes.c_ushort),
                ("Data3", ctypes.c_ushort), ("Data4", ctypes.c_ubyte * 8)]


class _PROPERTYKEY(ctypes.Structure):
    _fields_ = [("fmtid", _GUID), ("pid", wintypes.DWORD)]


def _guid(s):
    g = _GUID()
    ole32.CLSIDFromString(ctypes.c_wchar_p(s), ctypes.byref(g))
    return g


def _vcall(ptr, index, restype, *argtypes):
    """COM 인터페이스 포인터의 vtable[index] 메서드를 호출 가능한 함수로 꺼낸다."""
    vtbl = ctypes.cast(ctypes.cast(ptr, ctypes.POINTER(ctypes.c_void_p))[0], ctypes.POINTER(ctypes.c_void_p))
    return ctypes.WINFUNCTYPE(restype, ctypes.c_void_p, *argtypes)(vtbl[index])


def _release(ptr):
    if ptr and ptr.value:
        _vcall(ptr, 2, ctypes.c_ulong)(ptr)


_CLSID_MMDeviceEnumerator = _guid("{BCDE0395-E52F-467C-8E3D-C4579291692E}")
_IID_IMMDeviceEnumerator = _guid("{A95664D2-9614-4F35-A746-DE8DB63617E6}")
_IID_IAudioEndpointVolume = _guid("{5CDF2C82-841E-4546-9722-0CF74078229A}")
_CLSID_NetworkListManager = _guid("{DCB00C01-570F-4A9B-8D69-199FDBA5723B}")
_IID_INetworkListManager = _guid("{DCB00000-570F-4A9B-8D69-199FDBA5723B}")
_PKEY_FriendlyName =_PROPERTYKEY(_guid("{A45C254E-DF1C-4EFD-8020-67D146A850E0}"), 14)
_CLSCTX_ALL = 0x17


def read_audio(with_name=False):
    """기본 재생 장치의 {'volume': 0~1, 'muted': bool, 'id': str, 'name': str|None}. 실패하면 None."""
    enum = ctypes.c_void_p()
    dev = ctypes.c_void_p()
    vol = ctypes.c_void_p()
    store = ctypes.c_void_p()
    try:
        hr = ole32.CoCreateInstance(ctypes.byref(_CLSID_MMDeviceEnumerator), None, _CLSCTX_ALL,
                                    ctypes.byref(_IID_IMMDeviceEnumerator), ctypes.byref(enum))
        if hr != 0 or not enum.value:
            return None
        # IMMDeviceEnumerator::GetDefaultAudioEndpoint(eRender=0, eMultimedia=1)
        if _vcall(enum, 4, ctypes.c_long, ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_void_p))(
                enum, 0, 1, ctypes.byref(dev)) != 0 or not dev.value:
            return None

        out = {'volume': None, 'muted': None, 'id': None, 'name': None}

        # IMMDevice::GetId
        pid = ctypes.c_wchar_p()
        if _vcall(dev, 5, ctypes.c_long, ctypes.POINTER(ctypes.c_wchar_p))(dev, ctypes.byref(pid)) == 0 and pid.value:
            out['id'] = pid.value
            ole32.CoTaskMemFree(pid)

        # IMMDevice::Activate(IAudioEndpointVolume)
        if _vcall(dev, 3, ctypes.c_long, ctypes.POINTER(_GUID), ctypes.c_ulong, ctypes.c_void_p,
                  ctypes.POINTER(ctypes.c_void_p))(
                dev, ctypes.byref(_IID_IAudioEndpointVolume), _CLSCTX_ALL, None, ctypes.byref(vol)) == 0 and vol.value:
            scalar = ctypes.c_float()
            if _vcall(vol, 9, ctypes.c_long, ctypes.POINTER(ctypes.c_float))(vol, ctypes.byref(scalar)) == 0:
                out['volume'] = round(scalar.value, 4)
            mute = ctypes.c_int()
            if _vcall(vol, 15, ctypes.c_long, ctypes.POINTER(ctypes.c_int))(vol, ctypes.byref(mute)) == 0:
                out['muted'] = bool(mute.value)

        if with_name:
            # IMMDevice::OpenPropertyStore(STGM_READ) -> IPropertyStore::GetValue(PKEY_Device_FriendlyName)
            if _vcall(dev, 4, ctypes.c_long, ctypes.c_ulong, ctypes.POINTER(ctypes.c_void_p))(
                    dev, 0, ctypes.byref(store)) == 0 and store.value:
                pv = (ctypes.c_ubyte * 24)()   # PROPVARIANT (64비트 24바이트, 32비트 16바이트)
                if _vcall(store, 5, ctypes.c_long, ctypes.POINTER(_PROPERTYKEY), ctypes.c_void_p)(
                        store, ctypes.byref(_PKEY_FriendlyName), ctypes.addressof(pv)) == 0:
                    vt = ctypes.c_ushort.from_buffer(pv).value
                    if vt == 31:   # VT_LPWSTR
                        ptr = ctypes.c_void_p.from_buffer(pv, 8).value
                        if ptr:
                            out['name'] = ctypes.wstring_at(ptr)
                    # argtypes 가 없는 함수에 64비트 주소를 int 로 넘기면 OverflowError -> byref 로 넘긴다
                    ole32.PropVariantClear(ctypes.byref(pv))
        return out
    except Exception:
        return None
    finally:
        _release(store)
        _release(vol)
        _release(dev)
        _release(enum)


HEADPHONE_RE = re.compile(
    r'headphone|headset|earbud|earphone|buds|airpods|hands-?free|헤드폰|헤드셋|이어폰|버즈|에어팟|耳机|耳麦|耳塞|ヘッドホン|ヘッドセット|イヤホン|イヤフォン', re.I)


def is_headphone_name(name):
    return bool(name and HEADPHONE_RE.search(name))


# ----------------------------------------------------------------------
# 전체화면 앱 감지
# ----------------------------------------------------------------------
class _MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]


_SHELL_CLASSES = {'Progman', 'WorkerW', 'Shell_TrayWnd', 'Shell_SecondaryTrayWnd'}


def rect_covers(win, mon):
    """win 이 mon 전체를 덮는지. (left, top, right, bottom) 튜플."""
    return win[0] <= mon[0] and win[1] <= mon[1] and win[2] >= mon[2] and win[3] >= mon[3]


def is_fullscreen_foreground(own_hwnd=None):
    """전경 창이 모니터 전체를 덮는 전체화면 앱인지. 바탕화면/작업표시줄/자기 자신은 제외한다."""
    try:
        hwnd = user32.GetForegroundWindow()
        if not hwnd or hwnd == own_hwnd:
            return False
        cls = ctypes.create_unicode_buffer(64)
        user32.GetClassNameW(hwnd, cls, 64)
        if cls.value in _SHELL_CLASSES:
            return False
        rc = wintypes.RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(rc)):
            return False
        mi = _MONITORINFO()
        mi.cbSize = ctypes.sizeof(mi)
        mon = user32.MonitorFromWindow(hwnd, 2)   # MONITOR_DEFAULTTONEAREST
        if not mon or not user32.GetMonitorInfoW(mon, ctypes.byref(mi)):
            return False
        m = mi.rcMonitor
        if not rect_covers((rc.left, rc.top, rc.right, rc.bottom), (m.left, m.top, m.right, m.bottom)):
            return False
        # 노치가 다른 모니터에 있으면 이 전체화면 앱은 노치를 가리지 않는다
        if own_hwnd:
            own_mon = user32.MonitorFromWindow(own_hwnd, 2)
            if own_mon and own_mon != mon:
                return False
        # 작업표시줄을 숨겨 둔 환경의 '최대화' 일반 창(제목 표시줄 있음)은 전체화면이 아니다
        WS_CAPTION = 0x00C00000
        style = user32.GetWindowLongW(hwnd, -16)
        if user32.IsZoomed(hwnd) and (style & WS_CAPTION) == WS_CAPTION:
            return False
        return True
    except Exception:
        return False


# ----------------------------------------------------------------------
# 감시기
# ----------------------------------------------------------------------
def default_readers():
    return {
        'caps': read_caps,
        'num': read_num,
        'scroll': read_scroll,
        'mediakeys': read_media_keys,
        'lang': read_kb_layout,
        'audio': lambda with_name=False: read_audio(with_name),
        'brightness': read_brightness,
        'power': read_power,
        'online': read_online,
        'fullscreen': is_fullscreen_foreground,
    }


class SysMonitor:
    """읽기 함수를 주기적으로 호출해 값이 '바뀐 순간'만 이벤트로 내보낸다.

    첫 읽기는 기준값으로만 쓰고 이벤트를 내지 않는다(앱을 켜자마자 알림이 쏟아지지 않게).
    `tick(now)` 가 한 번의 점검이며, 스레드는 이것을 짧은 간격으로 부를 뿐이라 가짜 시계로 테스트할 수 있다.
    """

    # 항목별 점검 주기(초)
    PERIODS = {'caps': 0.15, 'num': 0.15, 'scroll': 0.15, 'mediakeys': 0.0, 'lang': 0.4, 'volume': 0.15, 'device': 1.5, 'brightness': 1.0,
               'power': 2.0, 'online': 2.0, 'fullscreen': 0.5}
    BATTERY_LOW = 20
    BATTERY_RECOVER = 25

    def __init__(self, push, on_fullscreen=None, own_hwnd=None, readers=None):
        self._push = push
        self._on_fullscreen = on_fullscreen
        self._own_hwnd = own_hwnd or (lambda: None)
        self.readers = readers or default_readers()
        self._next = {}
        self._prev = {}
        self._started = time.monotonic()
        self._brightness_supported = True
        self._battery_low_sent = False
        self._mk_down = set()          # 지금 눌려 있는 미디어 키 (꾹 눌러 반복되는 입력을 한 번으로 세기 위해)
        self._thread = None
        self._running = False

    # -- 수명 ---------------------------------------------------------
    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True, name="sysmon")
        self._thread.start()

    def stop(self):
        self._running = False

    def _run(self):
        try:
            ole32.CoInitialize(None)   # 이 스레드에서 쓰는 COM(오디오)용
        except Exception:
            pass
        while self._running:
            try:
                self.tick(time.monotonic())
            except Exception:
                pass
            time.sleep(0.08)

    # -- 한 번의 점검 ---------------------------------------------------
    def _due(self, key, now):
        if now < self._next.get(key, 0):
            return False
        self._next[key] = now + self.PERIODS[key]
        return True

    def _changed(self, key, value):
        """기준값(첫 읽기)과 비교. 처음이면 저장만 하고 False."""
        first = key not in self._prev
        old = self._prev.get(key)
        self._prev[key] = value
        return (not first) and old != value

    def tick(self, now):
        r = self.readers

        if self._due('caps', now):
            v = r['caps']()
            if v is not None and self._changed('caps', bool(v)):
                self._push({'type': 'caps', 'on': bool(v)})

        for key in ('num', 'scroll'):            # Num Lock / Scroll Lock (읽기 함수가 없으면 건너뜀)
            if key in r and self._due(key, now):
                v = r[key]()
                if v is not None and self._changed(key, bool(v)):
                    self._push({'type': key, 'on': bool(v)})

        if 'mediakeys' in r and self._due('mediakeys', now):
            keys = r['mediakeys']() or {}
            for name, (down, pressed) in keys.items():
                was = name in self._mk_down
                if (down or pressed) and not was:
                    self._push({'type': 'media_key', 'key': name})
                if down:
                    self._mk_down.add(name)
                else:
                    self._mk_down.discard(name)

        if self._due('lang', now):
            v = r['lang']()
            if v and v.get('code') and self._changed('lang', v['code']):
                self._push({'type': 'lang', 'code': v['code'], 'name': v.get('name') or v['code']})

        if self._due('volume', now):
            a = r['audio'](False)
            if a and a.get('volume') is not None:
                last = self._prev.get('volume')
                muted = bool(a.get('muted'))
                if last is None:
                    self._prev['volume'] = (a['volume'], muted)
                elif abs(a['volume'] - last[0]) >= 0.005 or muted != last[1]:
                    self._prev['volume'] = (a['volume'], muted)
                    self._push({'type': 'volume', 'value': a['volume'], 'muted': muted})

        if self._due('device', now):
            a = r['audio'](True)
            if a and a.get('id'):
                if self._changed('device', a['id']):
                    name = a.get('name') or ''
                    self._push({'type': 'audio_device', 'name': name, 'headphones': is_headphone_name(name)})

        if self._brightness_supported and self._due('brightness', now):
            v = r['brightness']()
            if v is None:
                # 한 번도 값을 못 읽었다면 이 기기는 밝기 WMI 를 지원하지 않는 것 -> 더는 묻지 않는다
                if 'brightness' not in self._prev:
                    self._brightness_supported = False
            elif self._changed('brightness', v):
                self._push({'type': 'brightness', 'value': v})

        if self._due('power', now):
            p = r['power']()
            if p and p.get('ac') is not None:
                if self._changed('ac', p['ac']) and p.get('has_battery'):
                    self._push({'type': 'power', 'plugged': p['ac'], 'percent': p.get('percent')})
                pct = p.get('percent')
                if p.get('has_battery') and pct is not None:
                    if not p['ac'] and pct <= self.BATTERY_LOW and not self._battery_low_sent:
                        self._battery_low_sent = True
                        self._push({'type': 'battery_low', 'percent': pct})
                    elif p['ac'] or pct >= self.BATTERY_RECOVER:
                        self._battery_low_sent = False

        if self._due('online', now):
            v = r['online']()
            if v is not None and self._changed('online', bool(v)):
                self._push({'type': 'net', 'online': bool(v)})

        if self._on_fullscreen and self._due('fullscreen', now):
            v = bool(r['fullscreen'](self._own_hwnd()))
            if self._changed('fullscreen', v) or ('fullscreen_sent' not in self._prev):
                self._prev['fullscreen_sent'] = True
                self._on_fullscreen(v)
