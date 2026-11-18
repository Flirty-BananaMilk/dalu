"""시스템 탭/전원 탭이 쓰는 윈도우 조작: 배터리, 밝기, 볼륨, 마이크, Wi-Fi, 블루투스, 전원(잠금·화면 끄기·절전·로그아웃·다시 시작·종료).

원칙
- 있는 것만 보여 준다: 배터리가 없는 PC 는 battery 가 None, 밝기를 못 바꾸는 화면뿐이면 brightness 가 None.
- 추가 패키지는 무선 장치(Wi-Fi/블루투스) 켜고 끄기에 쓰는 winrt-Windows.Devices.Radios 뿐이다. 없으면 그 둘만 빠진다.
- 모든 함수는 예외를 밖으로 던지지 않는다(실패하면 None / False). 전원 동작은 runner 를 바꿔 끼울 수 있어 실제로 끄지 않고 시험한다.
"""
import asyncio
import ctypes
import re
import subprocess
import threading
from ctypes import wintypes

try:
    import sysmon
except Exception:                      # pragma: no cover
    sysmon = None
try:
    import audiomix
except Exception:                      # pragma: no cover
    audiomix = None

CREATE_NO_WINDOW = 0x08000000

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32


# ----------------------------------------------------------------------
# 밝기: 노트북 내장 패널(IOCTL) 이 있으면 그것, 없으면 DDC/CI 로 밝기를 바꿀 수 있는 모니터 전부(데스크톱·외장 모니터)

class _DISPLAY_BRIGHTNESS(ctypes.Structure):
    _fields_ = [("ucDisplayPolicy", ctypes.c_ubyte), ("ucACBrightness", ctypes.c_ubyte), ("ucDCBrightness", ctypes.c_ubyte)]


class _PHYSICAL_MONITOR(ctypes.Structure):
    _pack_ = 1
    _fields_ = [("hPhysicalMonitor", wintypes.HANDLE), ("szPhysicalMonitorDescription", ctypes.c_wchar * 128)]


_MONITORENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_int, wintypes.HMONITOR, wintypes.HDC, ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)
IOCTL_VIDEO_SET_DISPLAY_BRIGHTNESS = 0x0023049C       # CTL_CODE(FILE_DEVICE_VIDEO, 0x127, BUFFERED, ANY_ACCESS) (조회는 0x00230498)
_dxva2 = None


def _dx():
    global _dxva2
    if _dxva2 is None:
        d = ctypes.WinDLL("dxva2", use_last_error=True)
        d.GetNumberOfPhysicalMonitorsFromHMONITOR.argtypes = [wintypes.HMONITOR, ctypes.POINTER(wintypes.DWORD)]
        d.GetPhysicalMonitorsFromHMONITOR.argtypes = [wintypes.HMONITOR, wintypes.DWORD, ctypes.POINTER(_PHYSICAL_MONITOR)]
        d.DestroyPhysicalMonitors.argtypes = [wintypes.DWORD, ctypes.POINTER(_PHYSICAL_MONITOR)]
        d.GetMonitorBrightness.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.DWORD)]
        d.SetMonitorBrightness.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        _dxva2 = d
    return _dxva2


def _hmonitors():
    out = []
    cb = _MONITORENUMPROC(lambda h, dc, rc, lp: (out.append(h), 1)[1])
    user32.EnumDisplayMonitors(None, None, cb, 0)
    return out


def _for_each_physical(fn):
    """모든 물리 모니터에 fn(handle) 를 부른다. fn 이 값을 돌려주면 모아서 돌려준다."""
    dx = _dx()
    res = []
    for hm in _hmonitors():
        n = wintypes.DWORD()
        if not dx.GetNumberOfPhysicalMonitorsFromHMONITOR(hm, ctypes.byref(n)) or not n.value:
            continue
        arr = (_PHYSICAL_MONITOR * n.value)()
        if not dx.GetPhysicalMonitorsFromHMONITOR(hm, n.value, arr):
            continue
        try:
            for pm in arr:
                try:
                    v = fn(pm.hPhysicalMonitor)
                except Exception:
                    v = None
                if v is not None:
                    res.append(v)
        finally:
            dx.DestroyPhysicalMonitors(n.value, arr)
    return res


def _ddc_read(handle):
    mn, cur, mx = wintypes.DWORD(), wintypes.DWORD(), wintypes.DWORD()
    if not _dx().GetMonitorBrightness(handle, ctypes.byref(mn), ctypes.byref(cur), ctypes.byref(mx)) or mx.value <= mn.value:
        return None
    return round((cur.value - mn.value) * 100 / (mx.value - mn.value))


def _ddc_write(percent):
    def one(handle):
        mn, cur, mx = wintypes.DWORD(), wintypes.DWORD(), wintypes.DWORD()
        if not _dx().GetMonitorBrightness(handle, ctypes.byref(mn), ctypes.byref(cur), ctypes.byref(mx)) or mx.value <= mn.value:
            return None
        target = int(round(mn.value + (mx.value - mn.value) * percent / 100.0))
        return True if _dx().SetMonitorBrightness(handle, target) else None
    return _for_each_physical(one)


def _lcd_set(percent):
    """노트북 내장 패널 밝기를 AC/배터리 양쪽에 같이 바꾼다."""
    kernel32.CreateFileW.restype = ctypes.c_void_p          # 기본(32비트 int)으로 두면 실패 값 -1 이 걸러지지 않는다
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    h = kernel32.CreateFileW("\\\\.\\LCD", 0xC0000000, 3, None, 3, 0, None)       # GENERIC_READ|WRITE
    if h in (None, 0, ctypes.c_void_p(-1).value):
        return False
    try:
        buf = _DISPLAY_BRIGHTNESS(3, percent, percent)                               # 3 = AC 와 DC 모두
        got = wintypes.DWORD()
        kernel32.DeviceIoControl.argtypes = [ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD,
                                             ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
        return bool(kernel32.DeviceIoControl(h, IOCTL_VIDEO_SET_DISPLAY_BRIGHTNESS, ctypes.byref(buf), ctypes.sizeof(buf), None, 0, ctypes.byref(got), None))
    finally:
        kernel32.CloseHandle(h)


def brightness_get():
    """{'percent': 0~100, 'kind': 'lcd'|'ddc'} 또는 밝기를 바꿀 수 있는 화면이 없으면 None."""
    try:
        if sysmon is not None:
            p = sysmon.read_brightness()
            if p is not None:
                return {"percent": int(p), "kind": "lcd"}
        vals = _for_each_physical(_ddc_read)
        if vals:
            return {"percent": int(vals[0]), "kind": "ddc"}
    except Exception:
        pass
    return None


def brightness_set(percent):
    try:
        p = max(0, min(100, int(round(float(percent)))))
        cur = brightness_get()
        if cur is None:
            return False
        if cur["kind"] == "lcd":
            return _lcd_set(p)
        return bool(_ddc_write(p))
    except Exception:
        return False


# ----------------------------------------------------------------------
# Wi-Fi / 블루투스: 윈도우 무선 장치(설정 > 네트워크의 켜기/끄기와 같은 것)

def _radio_run(coro_factory):
    """winrt 비동기 호출을 이 스레드에서 끝까지 돌린다(웹뷰 스레드와 겹치지 않게 새 이벤트 루프)."""
    result = {}

    def work():
        try:
            result["v"] = asyncio.run(coro_factory())
        except Exception:
            result["v"] = None
    t = threading.Thread(target=work, daemon=True)
    t.start()
    t.join(8)
    return result.get("v")


def _radios_read():
    async def go():
        from winrt.windows.devices.radios import Radio, RadioAccessStatus, RadioKind, RadioState
        if await Radio.request_access_async() != RadioAccessStatus.ALLOWED:
            return None
        out = {}
        for r in await Radio.get_radios_async():
            if r.kind == RadioKind.WI_FI:
                out["wifi"] = (r.state == RadioState.ON)
            elif r.kind == RadioKind.BLUETOOTH:
                out["bluetooth"] = (r.state == RadioState.ON)
        return out
    return _radio_run(go) or {}


def radio_set(kind, on):
    """kind: 'wifi' | 'bluetooth'. 성공하면 True."""
    want = {"wifi": "WI_FI", "bluetooth": "BLUETOOTH"}.get(kind)
    if not want:
        return False

    async def go():
        from winrt.windows.devices.radios import Radio, RadioAccessStatus, RadioKind, RadioState
        if await Radio.request_access_async() != RadioAccessStatus.ALLOWED:
            return False
        ok = False
        for r in await Radio.get_radios_async():
            if r.kind == getattr(RadioKind, want):
                res = await r.set_state_async(RadioState.ON if on else RadioState.OFF)
                ok = ok or (res == RadioAccessStatus.ALLOWED)          # 0(UNSPECIFIED)은 성공이 아니다. 아래에서 실제 상태로도 한 번 더 확인한다
                ok = ok or (r.state == (RadioState.ON if on else RadioState.OFF))
        return ok
    return bool(_radio_run(go))


class _GUID(ctypes.Structure):
    _fields_ = [("Data1", ctypes.c_ulong), ("Data2", ctypes.c_ushort), ("Data3", ctypes.c_ushort), ("Data4", ctypes.c_ubyte * 8)]


class _WLAN_INTERFACE_INFO(ctypes.Structure):
    _fields_ = [("InterfaceGuid", _GUID), ("strInterfaceDescription", ctypes.c_wchar * 256), ("isState", ctypes.c_int)]


def wifi_name():
    """지금 연결된 Wi-Fi 이름(프로필 이름). 연결돼 있지 않거나 Wi-Fi 가 없으면 None."""
    try:
        wlan = ctypes.WinDLL("wlanapi", use_last_error=True)
    except OSError:
        return None
    handle = wintypes.HANDLE()
    ver = wintypes.DWORD()
    if wlan.WlanOpenHandle(2, None, ctypes.byref(ver), ctypes.byref(handle)) != 0:
        return None
    try:
        lst = ctypes.c_void_p()
        if wlan.WlanEnumInterfaces(handle, None, ctypes.byref(lst)) != 0 or not lst.value:
            return None
        try:
            n = ctypes.c_ulong.from_address(lst.value).value
            base = lst.value + 8
            for i in range(n):
                info = _WLAN_INTERFACE_INFO.from_address(base + i * ctypes.sizeof(_WLAN_INTERFACE_INFO))
                if info.isState != 1:                      # wlan_interface_state_connected
                    continue
                size = wintypes.DWORD()
                data = ctypes.c_void_p()
                if wlan.WlanQueryInterface(handle, ctypes.byref(info.InterfaceGuid), 7, None, ctypes.byref(size), ctypes.byref(data), None) == 0 and data.value:
                    try:
                        # WLAN_CONNECTION_ATTRIBUTES: 상태(4) + 모드(4) + 프로필 이름(WCHAR 256)
                        name = ctypes.wstring_at(data.value + 8, 256).split("\x00")[0]
                        return name or None
                    finally:
                        wlan.WlanFreeMemory(data)
        finally:
            wlan.WlanFreeMemory(lst)
    except Exception:
        return None
    finally:
        wlan.WlanCloseHandle(handle, None)
    return None


# ----------------------------------------------------------------------
# Wi-Fi 선택: 주변 네트워크 목록과 연결 (윈도우 WLAN API). 저장된 네트워크는 바로, 처음 보는 개인용(WPA2/WPA3-PSK)·열린 네트워크는
# 비밀번호를 받아 프로필을 만들어 연결한다. 비밀번호는 윈도우에만 넘기고 기록하지 않는다. 기업용(802.1X) 네트워크는 지원하지 않는다.

class _DOT11_SSID(ctypes.Structure):
    _fields_ = [("uSSIDLength", ctypes.c_ulong), ("ucSSID", ctypes.c_ubyte * 32)]


class _WLAN_AVAILABLE_NETWORK(ctypes.Structure):
    _fields_ = [("strProfileName", ctypes.c_wchar * 256), ("dot11Ssid", _DOT11_SSID), ("dot11BssType", ctypes.c_int),
                ("uNumberOfBssids", ctypes.c_ulong), ("bNetworkConnectable", ctypes.c_int), ("wlanNotConnectableReason", wintypes.DWORD),
                ("uNumberOfPhyTypes", ctypes.c_ulong), ("dot11PhyTypes", ctypes.c_int * 8), ("bMorePhyTypes", ctypes.c_int),
                ("wlanSignalQuality", ctypes.c_ulong), ("bSecurityEnabled", ctypes.c_int), ("dot11DefaultAuthAlgorithm", ctypes.c_int),
                ("dot11DefaultCipherAlgorithm", ctypes.c_int), ("dwFlags", wintypes.DWORD), ("dwReserved", wintypes.DWORD)]


class _WLAN_CONNECTION_PARAMETERS(ctypes.Structure):
    _fields_ = [("wlanConnectionMode", ctypes.c_int), ("strProfile", ctypes.c_wchar_p), ("pDot11Ssid", ctypes.POINTER(_DOT11_SSID)),
                ("pDesiredBssidList", ctypes.c_void_p), ("dot11BssType", ctypes.c_int), ("dwFlags", wintypes.DWORD)]


# dot11DefaultAuthAlgorithm: 1 열림 · 4 WPA-PSK · 7 WPA2-PSK(RSNA_PSK) · 9 WPA3-SAE. 그 밖(2 공유키, 3/6/8 기업용 등)은 노치에서 연결하지 않는다.
_AUTH_OPEN, _AUTH_WPA_PSK, _AUTH_RSNA_PSK, _AUTH_WPA3_SAE = 1, 4, 7, 9


def wifi_kind(auth, cipher, secured):
    """네트워크 종류: 'open' | 'psk' | 'unsupported' (노치에서 연결 가능한가)."""
    if not secured and auth == _AUTH_OPEN:
        return "open"
    if auth in (_AUTH_WPA_PSK, _AUTH_RSNA_PSK, _AUTH_WPA3_SAE):
        return "psk"
    return "unsupported"


def _xml_escape(t):
    return (str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&apos;"))


def wifi_profile_xml(ssid, auth, password=None):
    """저장된 프로필이 없는 네트워크용 WLAN 프로필 XML. open 이면 비밀번호 없이, psk 면 비밀번호를 넣는다."""
    name = _xml_escape(ssid)
    if auth == _AUTH_OPEN:
        sec = "<authEncryption><authentication>open</authentication><encryption>none</encryption><useOneX>false</useOneX></authEncryption>"
    else:
        a, e = {_AUTH_WPA_PSK: ("WPAPSK", "TKIP"), _AUTH_RSNA_PSK: ("WPA2PSK", "AES"), _AUTH_WPA3_SAE: ("WPA3SAE", "AES")}[auth]
        sec = (f"<authEncryption><authentication>{a}</authentication><encryption>{e}</encryption><useOneX>false</useOneX></authEncryption>"
               f"<sharedKey><keyType>passPhrase</keyType><protected>false</protected><keyMaterial>{_xml_escape(password or '')}</keyMaterial></sharedKey>")
    return ('<?xml version="1.0"?><WLANProfile xmlns="http://www.microsoft.com/networking/WLAN/profile/v1">'
            f"<name>{name}</name><SSIDConfig><SSID><name>{name}</name></SSID></SSIDConfig><connectionType>ESS</connectionType>"
            f"<connectionMode>auto</connectionMode><MSM><security>{sec}</security></MSM></WLANProfile>")


def _wlan_open():
    wlan = ctypes.WinDLL("wlanapi", use_last_error=True)
    handle = wintypes.HANDLE()
    ver = wintypes.DWORD()
    if wlan.WlanOpenHandle(2, None, ctypes.byref(ver), ctypes.byref(handle)) != 0:
        return None, None
    return wlan, handle


def _first_interface(wlan, handle):
    lst = ctypes.c_void_p()
    if wlan.WlanEnumInterfaces(handle, None, ctypes.byref(lst)) != 0 or not lst.value:
        return None, None
    try:
        n = ctypes.c_ulong.from_address(lst.value).value
        if not n:
            return None, None
        info = _WLAN_INTERFACE_INFO.from_address(lst.value + 8)
        guid = _GUID()
        ctypes.memmove(ctypes.byref(guid), ctypes.byref(info.InterfaceGuid), ctypes.sizeof(_GUID))
        return guid, info.isState
    finally:
        wlan.WlanFreeMemory(lst)


def wifi_list(rescan=True):
    """주변 Wi-Fi: [{'ssid','signal'(0~100),'kind'('open'|'psk'|'unsupported'),'saved','connected','profile'}], 신호 센 순서. 같은 이름은 하나로."""
    try:
        wlan, handle = _wlan_open()
        if wlan is None:
            return []
        try:
            guid, _ = _first_interface(wlan, handle)
            if guid is None:
                return []
            if rescan:
                wlan.WlanScan(handle, ctypes.byref(guid), None, None, None)
                import time
                time.sleep(1.2)
            lst = ctypes.c_void_p()
            if wlan.WlanGetAvailableNetworkList(handle, ctypes.byref(guid), 0, None, ctypes.byref(lst)) != 0 or not lst.value:
                return []
            try:
                count = wintypes.DWORD.from_address(lst.value).value
                base = lst.value + 8
                size = ctypes.sizeof(_WLAN_AVAILABLE_NETWORK)
                best = {}
                for i in range(count):
                    net = _WLAN_AVAILABLE_NETWORK.from_address(base + i * size)
                    ssid = bytes(net.dot11Ssid.ucSSID[:net.dot11Ssid.uSSIDLength]).decode("utf-8", "replace")
                    if not ssid:
                        continue                                    # 숨김 네트워크는 이름을 몰라 목록에서 뺀다
                    row = {"ssid": ssid, "signal": int(net.wlanSignalQuality), "kind": wifi_kind(net.dot11DefaultAuthAlgorithm, net.dot11DefaultCipherAlgorithm, bool(net.bSecurityEnabled)),
                           "saved": bool(net.dwFlags & 2), "connected": bool(net.dwFlags & 1), "profile": net.strProfileName or ssid,
                           "auth": int(net.dot11DefaultAuthAlgorithm)}
                    old = best.get(ssid)
                    if old is None or row["connected"] or (not old["connected"] and row["signal"] > old["signal"]):
                        best[ssid] = row
                out = sorted(best.values(), key=lambda r: (not r["connected"], -r["signal"], r["ssid"].lower()))
                return out[:30]
            finally:
                wlan.WlanFreeMemory(lst)
        finally:
            wlan.WlanCloseHandle(handle, None)
    except Exception:
        return []


def wifi_connect(ssid, password=None):
    """ssid 에 연결을 시작한다(저장된 프로필이 있으면 그것으로). 시작에 성공하면 {'ok':True}, 아니면 {'ok':False,'error':'...'}.
    error: 'not found' | 'needs password' | 'unsupported' | 'profile' | 'connect'. 연결이 실제로 끝났는지는 wifi_name() 으로 다시 읽어 본다."""
    try:
        rows = [r for r in wifi_list(rescan=False) if r["ssid"] == ssid]
        if not rows:
            rows = [r for r in wifi_list(rescan=True) if r["ssid"] == ssid]
        if not rows:
            return {"ok": False, "error": "not found"}
        row = rows[0]
        wlan, handle = _wlan_open()
        if wlan is None:
            return {"ok": False, "error": "connect"}
        try:
            guid, _ = _first_interface(wlan, handle)
            if guid is None:
                return {"ok": False, "error": "connect"}
            profile = row["profile"]
            if not row["saved"]:
                if row["kind"] == "unsupported":
                    return {"ok": False, "error": "unsupported"}
                if row["kind"] == "psk" and not password:
                    return {"ok": False, "error": "needs password"}
                xml = wifi_profile_xml(ssid, _AUTH_OPEN if row["kind"] == "open" else row["auth"], password)
                reason = wintypes.DWORD()
                rc = wlan.WlanSetProfile(handle, ctypes.byref(guid), 2, xml, None, True, None, ctypes.byref(reason))     # 2 = 이 사용자 전용 프로필
                xml = None
                if rc != 0:
                    return {"ok": False, "error": "profile"}
                profile = ssid
            params = _WLAN_CONNECTION_PARAMETERS(0, profile, None, None, 1, 0)                                          # 0 = 프로필로 연결, 1 = infrastructure
            rc = wlan.WlanConnect(handle, ctypes.byref(guid), ctypes.byref(params), None)
            return {"ok": rc == 0, "error": "" if rc == 0 else "connect"}
        finally:
            wlan.WlanCloseHandle(handle, None)
    except Exception:
        return {"ok": False, "error": "connect"}


# ----------------------------------------------------------------------
# 블루투스 선택: 짝지은(기억된) 기기 목록과 연결/해제 (bthprops.cpl). 오디오(A2DP)·핸즈프리·키보드/마우스(HID) 서비스를 켜고 끄는 방식이라
# 윈도우 설정의 "연결/연결 끊기"와 같은 효과다. BLE 전용 기기는 이 API 로 보이지 않는다.

class _SYSTEMTIME(ctypes.Structure):
    _fields_ = [(n, ctypes.c_ushort) for n in ("wYear", "wMonth", "wDayOfWeek", "wDay", "wHour", "wMinute", "wSecond", "wMilliseconds")]


class _BLUETOOTH_DEVICE_INFO(ctypes.Structure):
    _fields_ = [("dwSize", wintypes.DWORD), ("Address", ctypes.c_ulonglong), ("ulClassofDevice", ctypes.c_ulong), ("fConnected", ctypes.c_int),
                ("fRemembered", ctypes.c_int), ("fAuthenticated", ctypes.c_int), ("stLastSeen", _SYSTEMTIME), ("stLastUsed", _SYSTEMTIME),
                ("szName", ctypes.c_wchar * 248)]


class _BLUETOOTH_DEVICE_SEARCH_PARAMS(ctypes.Structure):
    _fields_ = [("dwSize", wintypes.DWORD), ("fReturnAuthenticated", ctypes.c_int), ("fReturnRemembered", ctypes.c_int),
                ("fReturnUnknown", ctypes.c_int), ("fReturnConnected", ctypes.c_int), ("fIssueInquiry", ctypes.c_int),
                ("cTimeoutMultiplier", ctypes.c_ubyte), ("hRadio", wintypes.HANDLE)]


_BT_SERVICES = ("0000110B-0000-1000-8000-00805F9B34FB", "0000111E-0000-1000-8000-00805F9B34FB", "00001124-0000-1000-8000-00805F9B34FB")


def bt_kind(cod, name=""):
    """블루투스 기기 종류(아이콘용): headphones | speaker | mic | keyboard | mouse | gamepad | input | phone | computer | watch | other.
    클래스 코드(주 분류 + 부 분류)를 먼저 보고, 모르면 이름으로 짐작한다."""
    cod = int(cod or 0)
    major, minor = (cod >> 8) & 0x1F, (cod >> 2) & 0x3F
    kind = "other"
    if major == 4:                                    # 오디오/비디오
        kind = {5: "speaker", 7: "speaker", 8: "speaker", 4: "mic"}.get(minor, "headphones")
    elif major == 5:                                  # 입력 장치: 위 2비트 = 키보드/포인팅, 아래 4비트 = 조이스틱/게임패드 등
        top, sub = minor >> 4, minor & 0xF
        kind = "gamepad" if sub in (1, 2) else "keyboard" if top in (1, 3) else "mouse" if top == 2 else "input"
    elif major == 2:
        kind = "phone"
    elif major == 1:
        kind = "computer"
    elif major == 7:
        kind = "watch"
    if kind in ("other", "input"):
        n = str(name or "").lower()
        for pat, k in ((r"buds|pods|headset|headphone|earphone|earbud|wh-1000|wf-1000", "headphones"), (r"speaker|soundbar|boom|charge \d|flip \d|echo", "speaker"),
                       (r"controller|dualsense|dualshock|gamepad|joy-?con|xbox|wireless pad", "gamepad"), (r"keyboard|keychron|k\d{3}", "keyboard"),
                       (r"mouse|trackpad|mx master|m\d{3}", "mouse"), (r"watch|band|gear fit", "watch"), (r"iphone|galaxy [sazf]\d*|pixel \d|phone", "phone")):
            if re.search(pat, n):
                return k
    return kind


def bt_list():
    """짝지은 기기: [{'name','address'(문자열),'connected','kind'}], 연결된 것 먼저."""
    out = []
    try:
        bt = ctypes.WinDLL("bthprops.cpl", use_last_error=True)
        bt.BluetoothFindFirstDevice.restype = wintypes.HANDLE
        bt.BluetoothFindFirstDevice.argtypes = [ctypes.POINTER(_BLUETOOTH_DEVICE_SEARCH_PARAMS), ctypes.POINTER(_BLUETOOTH_DEVICE_INFO)]
        bt.BluetoothFindNextDevice.argtypes = [wintypes.HANDLE, ctypes.POINTER(_BLUETOOTH_DEVICE_INFO)]
        bt.BluetoothFindDeviceClose.argtypes = [wintypes.HANDLE]
        sp = _BLUETOOTH_DEVICE_SEARCH_PARAMS(ctypes.sizeof(_BLUETOOTH_DEVICE_SEARCH_PARAMS), 1, 1, 0, 1, 0, 1, None)
        info = _BLUETOOTH_DEVICE_INFO()
        info.dwSize = ctypes.sizeof(_BLUETOOTH_DEVICE_INFO)
        h = bt.BluetoothFindFirstDevice(ctypes.byref(sp), ctypes.byref(info))
        if not h:
            return []
        try:
            while True:
                if info.fRemembered or info.fConnected:
                    a = info.Address
                    out.append({"name": info.szName or "Bluetooth", "address": ":".join(f"{(a >> (8 * i)) & 0xFF:02X}" for i in range(5, -1, -1)),
                                "connected": bool(info.fConnected), "kind": bt_kind(info.ulClassofDevice, info.szName)})
                if not bt.BluetoothFindNextDevice(h, ctypes.byref(info)):
                    break
        finally:
            bt.BluetoothFindDeviceClose(h)
    except Exception:
        return []
    seen, uniq = set(), []
    for d in out:
        if d["address"] not in seen:
            seen.add(d["address"])
            uniq.append(d)
    try:                                   # 오디오 기기의 연결 여부는 장치 속성(PnP)이 더 정확하다(btdevices: 이어버드 배터리 읽기와 같은 값)
        import btdevices
        live = {g["name"].lower() for g in btdevices.read_devices() if g.get("connected")}
        for d in uniq:
            if d["name"].lower() in live:
                d["connected"] = True
    except Exception:
        pass
    return sorted(uniq, key=lambda d: (not d["connected"], d["name"].lower()))


def _parse_bt_address(text):
    parts = str(text).split(":")
    if len(parts) != 6:
        return None
    try:
        return int("".join(parts), 16)
    except ValueError:
        return None


def bt_set(address, on):
    """짝지은 기기의 연결(on=True)/해제(False). 서비스 중 하나라도 바뀌면 True."""
    addr = _parse_bt_address(address)
    if addr is None:
        return False
    try:
        bt = ctypes.WinDLL("bthprops.cpl", use_last_error=True)
        info = _BLUETOOTH_DEVICE_INFO()
        info.dwSize = ctypes.sizeof(_BLUETOOTH_DEVICE_INFO)
        info.Address = addr
        ok = False
        for g in _BT_SERVICES:
            guid = _GUID()
            parts = g.split("-")
            guid.Data1 = int(parts[0], 16)
            guid.Data2 = int(parts[1], 16)
            guid.Data3 = int(parts[2], 16)
            tail = bytes.fromhex(parts[3] + parts[4])
            for i, b in enumerate(tail):
                guid.Data4[i] = b
            bt.BluetoothSetServiceState.argtypes = [wintypes.HANDLE, ctypes.POINTER(_BLUETOOTH_DEVICE_INFO), ctypes.POINTER(_GUID), wintypes.DWORD]
            rc = bt.BluetoothSetServiceState(None, ctypes.byref(info), ctypes.byref(guid), 1 if on else 0)
            ok = ok or rc == 0
        return ok
    except Exception:
        return False


# ----------------------------------------------------------------------
# 한 번에 읽기 / 바꾸기

def snapshot(radios=True):
    """시스템 탭에 보여 줄 값 전부. 없는 항목은 None."""
    out = {"battery": None, "brightness": None, "volume": None, "mic": None, "wifi": None, "bluetooth": None}
    try:
        p = sysmon.read_power() if sysmon else None
        if p and p.get("has_battery") and p.get("percent") is not None:
            out["battery"] = {"percent": int(p["percent"]), "ac": p.get("ac")}
    except Exception:
        pass
    out["brightness"] = brightness_get()
    try:
        m = audiomix.master_get() if audiomix else None
        if m:
            out["volume"] = {"percent": int(round(m["volume"] * 100)), "muted": bool(m["muted"])}
        mic = audiomix.mic_get() if audiomix else None
        if mic is not None:
            out["mic"] = {"muted": bool(mic["muted"])}
    except Exception:
        pass
    if radios:
        r = _radios_read()
        if "wifi" in r:
            out["wifi"] = {"on": r["wifi"], "name": wifi_name() if r["wifi"] else None}
        if "bluetooth" in r:
            out["bluetooth"] = {"on": r["bluetooth"]}
    return out


def volume_set(percent):
    try:
        return bool(audiomix and audiomix.master_set(volume=max(0, min(100, float(percent))) / 100.0, muted=False))
    except Exception:
        return False


def volume_toggle_mute():
    try:
        cur = audiomix.master_get() if audiomix else None
        if cur is None:
            return None
        return (not cur["muted"]) if audiomix.master_set(muted=not cur["muted"]) else None          # 실패하면 None(호출하는 쪽이 실패로 안다)
    except Exception:
        return None


def mic_toggle_mute():
    try:
        return audiomix.mic_toggle_mute() if audiomix else None
    except Exception:
        return None


# ----------------------------------------------------------------------
# 전원

POWER_KINDS = ("lock", "screenoff", "sleep", "signout", "restart", "shutdown")
CONFIRM_KINDS = ("signout", "restart", "shutdown")        # 한 번 더 눌러야 실행되는 것(화면에서 확인, 여기서는 실행만)


def _run_hidden(args):
    subprocess.Popen(args, creationflags=CREATE_NO_WINDOW, close_fds=True)
    return True


def power(kind, runner=None):
    """kind 동작을 실행한다. runner(args) 를 바꿔 끼우면 실제로 실행하지 않고 어떤 명령이 나가는지만 받는다(시험용)."""
    run = runner or _run_hidden
    try:
        if kind == "lock":
            return bool(user32.LockWorkStation()) if runner is None else run(["lock"])
        if kind == "screenoff":
            if runner is not None:
                return run(["screenoff"])
            user32.PostMessageW(0xFFFF, 0x0112, 0xF170, 2)             # WM_SYSCOMMAND / SC_MONITORPOWER / 끄기
            return True
        if kind == "sleep":
            if runner is not None:
                return run(["sleep"])
            return bool(ctypes.windll.powrprof.SetSuspendState(False, True, False))
        if kind == "signout":
            return run(["shutdown", "/l"])
        if kind == "restart":
            return run(["shutdown", "/r", "/t", "0"])
        if kind == "shutdown":
            return run(["shutdown", "/s", "/t", "0"])
    except Exception:
        return False
    return False
