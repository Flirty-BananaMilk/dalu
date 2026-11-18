"""무선 음향 기기(블루투스 이어폰·헤드셋·스피커)의 연결 상태와 배터리 잔량 읽기.

Windows 는 블루투스 기기의 배터리 잔량(HFP 배터리 표시, BLE 배터리 서비스 0x180F)을 기기 속성
`{104EA319-6EE2-4701-BD47-8DDBF425BBE5} 2`(바이트, 0~100)로 이미 가지고 있다(설정 › 블루투스 및 장치에 보이는 그 값).
여기서는 그 값을 읽기만 한다: 기기에 새로 연결하지도, 주변 신호를 훑지도 않는다.
- 공식 문서가 없는 속성이라 값이 없으면(기기가 알려 주지 않으면) 잔량 없이 '연결됨'만 보여 준다.
- 모드(소음 차단 등)를 바꾸는 건 하지 않는다 — 그건 기기마다 자기만의 프로토콜이 있다(갤럭시 버즈는 buds.py).

에어팟은 배터리를 윈도우에 알리지 않고 애플 전용 방식으로만 알린다(왼쪽/오른쪽/케이스는 특히). 그래서 설정에서 켠 경우에만
'지금 연결된 에어팟이 있을 때' 주변 블루투스 광고 신호(애플 제조사 데이터 0x004C, 근접 페어링 메시지)를 듣고, 가장 가깝고 센 신호 하나에서
배터리 숫자만 읽는다(메모리에서만 쓰고 저장·전송하지 않는다). 연결된 에어팟이 없으면 듣지 않는다.
"""
import ctypes
import re
import threading
import time
from ctypes import wintypes

BATTERY_KEY = ("{104EA319-6EE2-4701-BD47-8DDBF425BBE5}", 2)
CONNECTED_KEY = ("{83DA6326-97A6-4088-9453-A1923F573B29}", 15)      # DEVPKEY_Device_IsConnected
FRIENDLY_KEY = ("{A45C254E-DF1C-4EFD-8020-67D146A850E0}", 14)      # DEVPKEY_Device_FriendlyName
NAME_KEY = ("{B725F130-47EF-101A-A5F1-02608C9EEBAC}", 10)          # DEVPKEY_NAME

# 소리가 나가는 기기라는 표시: 클래식은 A2DP 싱크(110B)·핸즈프리(111E)·헤드셋(1108), LE 오디오는 ASCS(184E)·VCS(1844)
AUDIO_UUIDS = {"0000110b", "0000111e", "00001108", "0000184e", "00001844"}
POLL_SECONDS = 45.0

_cfg = None


class _GUID(ctypes.Structure):
    _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD), ("Data3", wintypes.WORD), ("Data4", ctypes.c_ubyte * 8)]


class _PropKey(ctypes.Structure):
    _fields_ = [("fmtid", _GUID), ("pid", wintypes.DWORD)]


def _guid(text):
    g = _GUID()
    ctypes.windll.ole32.CLSIDFromString(ctypes.c_wchar_p(text), ctypes.byref(g))
    return g


def _prop_key(pair):
    k = _PropKey()
    k.fmtid = _guid(pair[0])
    k.pid = pair[1]
    return k


def _load():
    global _cfg
    if _cfg is None:
        _cfg = ctypes.WinDLL("cfgmgr32", use_last_error=True)
    return _cfg


def _id_list(enumerator):
    """장치 관리자 인스턴스 ID 목록(해당 열거자만)."""
    cfg = _load()
    size = wintypes.ULONG(0)
    if cfg.CM_Get_Device_ID_List_SizeW(ctypes.byref(size), ctypes.c_wchar_p(enumerator), 1) != 0 or size.value <= 1:
        return []
    buf = ctypes.create_unicode_buffer(size.value)
    if cfg.CM_Get_Device_ID_ListW(ctypes.c_wchar_p(enumerator), buf, size, 1) != 0:
        return []
    return [s for s in buf[:size.value].split("\x00") if s]


def _get_prop(instance_id, pair):
    """장치 속성 하나(문자열·불·바이트). 없으면 None."""
    cfg = _load()
    devinst = wintypes.DWORD(0)
    if cfg.CM_Locate_DevNodeW(ctypes.byref(devinst), ctypes.c_wchar_p(instance_id), 0) != 0:
        return None
    key = _prop_key(pair)
    ptype = wintypes.ULONG(0)
    buf = ctypes.create_string_buffer(512)
    size = wintypes.ULONG(512)
    if cfg.CM_Get_DevNode_PropertyW(devinst, ctypes.byref(key), ctypes.byref(ptype), buf, ctypes.byref(size), 0) != 0:
        return None
    raw = buf.raw[:size.value]
    t = ptype.value
    if t == 0x03 and raw:            # DEVPROP_TYPE_BYTE
        return raw[0]
    if t == 0x11 and raw:            # DEVPROP_TYPE_BOOLEAN (0xFF/0x00)
        return raw[0] != 0
    if t == 0x12:                    # DEVPROP_TYPE_STRING
        return raw.decode("utf-16-le", "ignore").rstrip("\x00")
    return None


_ADDR_RE = re.compile(r"(?:_|&)([0-9A-F]{12})(?:_|\\|$)", re.I)
_UUID_RE = re.compile(r"\{([0-9A-F]{8})-0000-1000-8000-00805F9B34FB\}", re.I)


def _services_by_address(ids):
    """주소 → 그 기기가 가진 서비스(UUID 앞 8자리) 집합. 서비스 장치 노드의 ID 에서 읽는다."""
    out = {}
    for iid in ids:
        u = _UUID_RE.search(iid)
        if not u:
            continue
        a = _ADDR_RE.search(iid)
        if a:
            out.setdefault(a.group(1).upper(), set()).add(u.group(1).lower())
    return out


def read_devices(skip_names=()):
    """연결된 무선 음향 기기 목록. 같은 이름의 노드(클래식 + LE 왼쪽/오른쪽)는 한 기기로 묶는다.

    반환: [{"name", "connected", "batteries": [int...], "audio": bool}] — 연결된 노드의 잔량만(끊긴 노드의 잔량은 옛 값이라 쓰지 않는다).
    """
    skip = {s.lower() for s in skip_names if s}
    classic = _id_list("BTHENUM")
    le = _id_list("BTHLE")
    le_services = _id_list("BTHLEDEVICE")
    services = _services_by_address(classic + le_services)
    nodes = []
    for iid in classic:
        m = re.match(r"BTHENUM\\DEV_([0-9A-F]{12})\\", iid, re.I)
        if m:
            nodes.append((iid, m.group(1).upper()))
    for iid in le:
        m = re.match(r"BTHLE\\DEV_([0-9A-F]{12})\\", iid, re.I)
        if m:
            nodes.append((iid, m.group(1).upper()))
    groups = {}
    for iid, addr in nodes:
        name = _get_prop(iid, FRIENDLY_KEY) or _get_prop(iid, NAME_KEY) or ""
        if not name or name.lower() in skip:
            continue
        connected = bool(_get_prop(iid, CONNECTED_KEY))
        battery = _get_prop(iid, BATTERY_KEY)
        audio = bool(services.get(addr, set()) & AUDIO_UUIDS)
        g = groups.setdefault(name, {"name": name, "connected": False, "batteries": [], "audio": False})
        g["audio"] = g["audio"] or audio
        if connected:
            g["connected"] = True
            if isinstance(battery, int) and 0 <= battery <= 100:
                g["batteries"].append(battery)
    return [g for g in groups.values() if g["audio"] and g["connected"]]


# ---------------------------------------------------------------------------------------------------------------
# 에어팟(애플 근접 페어링 광고)
# 제조사 데이터(회사 코드 0x004C)의 내용(회사 코드 뒤) 27바이트: [0]=0x07 종류, [1]=0x19(=25, 이후 길이), [3..4]=모델,
# [5]=상태 비트(0x20 방송하는 쪽이 왼쪽, 0x02 방송하는 쪽 귀에 꽂힘, 0x08 다른 쪽 귀에 꽂힘, 0x04 둘 다 케이스),
# [6]=배터리(아래 4비트 = 방송하는 쪽, 위 4비트 = 다른 쪽, 값 0~10 -> x10 %, 그 밖의 값 = 모름), [7]=아래 4비트 케이스 배터리 / 위 비트 충전
# (0x10 방송 쪽, 0x20 다른 쪽, 0x40 케이스), [8]=0x08 이면 뚜껑 닫힘. 나머지는 암호화된 값이라 쓰지 않는다.
# (구조는 오픈소스 WinPods(MIT)·OpenPods 문서의 설명을 참고했다. 실제 기기로 왼쪽/오른쪽 방향은 확인이 필요하다.)
# ---------------------------------------------------------------------------------------------------------------
APPLE_COMPANY = 0x004C


def _nib(v):
    return v * 10 if 0 <= v <= 10 else None


def parse_airpods(data):
    """애플 제조사 데이터(회사 코드 뒤)에서 에어팟 근접 페어링 메시지를 읽는다. 아니면 None."""
    if not isinstance(data, (bytes, bytearray)) or len(data) != 27 or data[0] != 0x07 or data[1] != 0x19:
        return None
    status, pods, cs, lid = data[5], data[6], data[7], data[8]
    left_is_current = bool(status & 0x20)
    cur, other = _nib(pods & 0x0F), _nib(pods >> 4)
    left, right = (cur, other) if left_is_current else (other, cur)
    cur_chg, other_chg = bool(cs & 0x10), bool(cs & 0x20)
    cur_ear, other_ear = bool(status & 0x02), bool(status & 0x08)
    return {
        "left": left, "right": right, "case": _nib(cs & 0x0F),
        "charging": {"left": cur_chg if left_is_current else other_chg, "right": other_chg if left_is_current else cur_chg, "case": bool(cs & 0x40)},
        "inEar": {"left": cur_ear if left_is_current else other_ear, "right": other_ear if left_is_current else cur_ear},
        "lidOpen": not bool(lid & 0x08),
        "model": (data[3] << 8) | data[4],
    }


class AirpodsTracker:
    """들어오는 에어팟 광고 중 '지금 연결된 내 에어팟'의 것만 고른다.

    주소는 15분마다 바뀌어서 주소로는 구별할 수 없다. 그래서 두 단계로 한다.
    1) 처음(잠기기 전)에는 신호가 가장 센(가장 가까운) 것을 고르고, 너무 약한 신호(주변 사람의 에어팟)는 버린다. SETTLE 초 동안 후보를 모은 뒤 그 기기에 '잠근다'.
    2) 잠근 뒤에는 이미 잡은 기기와 이어지는 신호만 받는다: 모델이 같고, 왼쪽·오른쪽·케이스 배터리가 직전 값과 한 단계(10%) 넘게 다르지 않아야 한다
       (같은 기기의 배터리는 천천히 변하고, 다른 사람의 에어팟은 거의 다른 값이라 걸러진다. 주소가 바뀌어도 이어지는 방법이기도 하다).
       LOCK 초 동안 이어지는 신호가 없으면 잠금을 풀고 1)로 돌아간다.
    (이 두 단계 방식은 오픈소스 AirPodsDesktop(GPL-3.0)의 설명에서 아이디어만 참고했고 코드는 가져오지 않았다.)
    """
    MIN_RSSI = -72           # dBm: 이보다 약한 신호는 내 것이 아니라고 본다
    WINDOW = 20.0            # 초: 잠기기 전에 후보로 치는 기간
    SETTLE = 4.0             # 초: 첫 후보가 들어온 뒤 이만큼 모아 보고 가장 센 것에 잠근다
    LOCK = 45.0              # 초: 잠근 기기와 이어지는 신호가 이만큼 없으면 잠금을 푼다
    KEEP = 120.0             # 초: 새 신호가 없어도 마지막 값을 이만큼은 보여 준다(케이스가 닫히면 신호가 끊긴다)
    STEP = 10                # %: 같은 기기의 두 신호 사이에서 배터리가 달라질 수 있는 최대치

    def __init__(self):
        self._mu = threading.RLock()          # WinRT 광고 콜백 스레드, 폴링 스레드, 화면 쪽 스레드가 함께 쓴다
        self.on_new = None                    # 값이 처음 생겼을 때(없다가 생김) 부르는 함수: 폴링을 바로 깨운다
        self._seen = []      # 잠기기 전 후보: (시각, rssi, 파싱 결과)
        self._lock = None    # (마지막으로 이어진 시각, 파싱 결과)
        self._last = None    # (시각, 파싱 결과): 화면에 보여 줄 값

    def _same_device(self, a, b):
        if a["model"] != b["model"]:
            return False
        for k in ("left", "right", "case"):
            if a[k] is not None and b[k] is not None and abs(a[k] - b[k]) > self.STEP:
                return False
        return True

    def feed(self, rssi, payload, now=None):
        with self._mu:
            had = self._last is not None
            ok = self._feed(rssi, payload, now)
            fresh = ok and not had and self._last is not None
        if fresh and self.on_new is not None:
            try:
                self.on_new()
            except Exception:
                pass
        return ok

    def _feed(self, rssi, payload, now=None):
        info = parse_airpods(payload)
        if info is None or rssi is None or rssi < self.MIN_RSSI:
            return False
        now = time.monotonic() if now is None else now
        if self._lock is not None and now - self._lock[0] > self.LOCK:
            self._lock = None
            self._seen = []
        if self._lock is not None:
            if not self._same_device(self._lock[1], info):
                return False            # 내 에어팟이 아닌 다른 에어팟의 신호
            self._lock = (now, info)
            self._last = (now, info)
            return True
        self._seen = [x for x in self._seen if now - x[0] <= self.WINDOW]
        self._seen.append((now, rssi, info))
        best = max(self._seen, key=lambda x: (x[1], x[0]))
        self._last = (best[0], best[2])        # 값이 들어온 시각(더 센 신호의 시각)
        if now - self._seen[0][0] >= self.SETTLE:
            self._lock = (now, best[2])
            self._seen = []
        return True

    def current(self, now=None):
        now = time.monotonic() if now is None else now
        with self._mu:
            last = self._last
        if not last or now - last[0] > self.KEEP:
            return None
        out = dict(last[1])
        out["age"] = round(now - last[0])
        return out

    def clear(self):
        with self._mu:
            self._seen = []
            self._lock = None
            self._last = None


def _is_airpods(name):
    n = (name or "").lower()
    return "airpods" in n or "beats" in n


def _locked(fn):          # 켜기·끄기가 서로 다른 스레드에서 겹쳐 불려도 한 번에 하나씩
    def wrapper(self, *a, **k):
        with self._mu:
            return fn(self, *a, **k)
    wrapper.__name__ = fn.__name__
    return wrapper


class AdvertisementWatcher:
    """블루투스 광고를 듣는다(수동 스캔: 아무것도 보내지 않는다). 켜고 끌 수 있다."""

    def __init__(self, tracker, log=None):
        self.tracker = tracker
        self._log = log or (lambda *_: None)
        self._watcher = None
        self._token = None
        self._mu = threading.RLock()

    @property
    def running(self):
        return self._watcher is not None

    @_locked
    def start(self):
        if self._watcher is not None:
            return True
        try:
            from winrt.windows.devices.bluetooth.advertisement import BluetoothLEAdvertisementWatcher, BluetoothLEScanningMode
            from winrt.windows.storage.streams import DataReader
        except Exception as e:
            self._log(f"airpods: advertisement api missing {e!r}")
            return False
        try:
            w = BluetoothLEAdvertisementWatcher()
            w.scanning_mode = BluetoothLEScanningMode.PASSIVE

            def on_received(sender, args):
                try:
                    for md in args.advertisement.manufacturer_data:
                        if md.company_id != APPLE_COMPANY:
                            continue
                        buf = md.data
                        r = DataReader.from_buffer(buf)
                        data = bytearray(buf.length)
                        r.read_bytes(data)
                        self.tracker.feed(args.raw_signal_strength_in_dbm, bytes(data))
                except Exception:
                    pass
            self._token = w.add_received(on_received)
            w.start()
            self._watcher = w
            return True
        except Exception as e:
            self._log(f"airpods: scan start failed {e!r}")
            self._watcher = None
            return False

    @_locked
    def stop(self):
        w, self._watcher = self._watcher, None
        if w is not None:
            try:
                w.stop()
                if self._token is not None:
                    w.remove_received(self._token)
            except Exception:
                pass
        self._token = None
        self.tracker.clear()


class BtDevices:
    """주기적으로 읽어서 바뀌면 알려 준다(켜져 있을 때만 돈다)."""

    def __init__(self, log=None, push=None, skip=None):
        self._log = log or (lambda *_: None)
        self._push = push or (lambda *_: None)
        self._skip = skip or (lambda: ())        # 이미 따로 다루는 기기(갤럭시 버즈) 이름
        self._lock = threading.Lock()
        self._devices = []
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._thread = None
        self.enabled = False
        self.airpods_scan = False
        self._tracker = AirpodsTracker()
        self._tracker.on_new = self._wake.set          # 에어팟 신호가 처음 잡히면 45초를 기다리지 않고 바로 배터리를 보여 준다
        self._adv = AdvertisementWatcher(self._tracker, log=self._log)

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="btdevices", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        self._wake.set()
        self._adv.stop()

    def set_airpods_scan(self, on):
        on = bool(on)
        if on == self.airpods_scan:
            return
        self.airpods_scan = on
        if not on:
            self._adv.stop()
        self._wake.set()

    def set_enabled(self, on):
        on = bool(on)
        if on == self.enabled:
            return
        self.enabled = on
        if not on:
            self._adv.stop()
            with self._lock:
                self._devices = []
        self._wake.set()

    def snapshot(self):
        with self._lock:
            return {"enabled": self.enabled, "devices": [dict(d) for d in self._devices]}

    def refresh(self):
        self._wake.set()

    def _with_airpods(self, devs):
        """연결된 에어팟이 있고 설정이 켜져 있을 때만 광고를 듣고, 그 값을 에어팟 항목에 붙인다. 아니면 듣기를 멈춘다."""
        has = any(_is_airpods(d["name"]) for d in devs)
        if not (self.airpods_scan and has):
            if self._adv.running:
                self._adv.stop()
            return devs
        if not self._adv.running:
            self._adv.start()
        cur = self._tracker.current()
        out = []
        for d in devs:
            d = dict(d)
            if _is_airpods(d["name"]):
                d["pods"] = cur
            out.append(d)
        return out

    def _run(self):
        while not self._stop.is_set():
            self._wake.clear()          # 일하기 전에 비운다(일하는 동안 들어온 깨우기 신호는 다음 대기에서 바로 처리된다)
            if self.enabled:
                try:
                    devs = read_devices(self._skip())
                except Exception as e:
                    self._log(f"btdevices read failed: {e!r}")
                    devs = None
                if devs is not None and self.enabled:          # 읽는 사이에 껐다면 결과를 버린다
                    devs = self._with_airpods(devs)
                    changed = False
                    with self._lock:
                        if devs != self._devices:
                            self._devices = devs
                            changed = True
                    if changed:
                        try:
                            self._push({"type": "btdevices", "devices": devs})
                        except Exception:
                            pass
            self._wake.wait(POLL_SECONDS if self.enabled else 5.0)
