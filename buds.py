# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Flirty_BananaMilk — 상업적 이용 금지, 자세한 내용은 LICENSE
"""블루투스 이어버드(갤럭시 버즈 등): 배터리 표시와 소음 제어 모드 설정.

* 배터리: Windows 표준 BLE GATT Battery Service(0x180F)를 읽는다. 좌/우/케이스는 각 특성의 Presentation Format
  디스크립터(0x2904)의 Bluetooth SIG 네임스페이스 값(0x010D left, 0x010E right, 0x0110 external=케이스)으로 구분한다.
* 소음 제어: 삼성 버즈의 독자 프로토콜(RFCOMM, 서비스 UUID 2e73a4ad-...)로 SET_NOISE_CONTROLS 를 보낸다.
  프레임: FD | 길이(2바이트 LE, 하위 10비트 = id+payload+CRC 길이) | id | payload | CRC16(XMODEM, LE) | DD.
  (Galaxy Buds3 Pro 실제 트래픽으로 CRC/길이 규칙을 검증했다.)
* 상태 감시: 제어 연결을 계속 열어 두면 버즈가 알아서 보내는 STATUS_UPDATED(0x60)로 좌/우/케이스 배터리와 '충전 중' 비트를(0x61 에도 같은 비트가 있다),
  STATUS_ALERT(0x57)로 '물/땀/얼룩이 감지돼 충전이 중지됨' 경고를 받는다 (GalaxyBudsClient 의 디코더를 참고, Buds3 Pro 실제 패킷으로 확인).
* WinRT 는 `winrt-*` 패키지(pywinrt)로 호출한다. 설치돼 있지 않으면 available=False 로 조용히 비활성화된다.
* asyncio 이벤트 루프를 전용 스레드에서 돌린다. 이 스레드는 pythonnet(.NET)을 쓰지 않는다.
"""

import asyncio
import threading
import time
import uuid

# ----------------------------------------------------------------------
# 프로토콜 (순수 함수)
# ----------------------------------------------------------------------
SOM = 0xFD
EOM = 0xDD
MSG_ACK = 0x42               # 요청에 대한 확인 응답: payload = [요청 id, 값]. 값은 장치 상태에 따라 0 이거나 적용된 모드 그대로(에코)다.
MSG_STATUS = 0x60
MSG_EXT_STATUS = 0x61
MSG_STATUS_ALERT = 0x57     # Buds3 Pro: 물/땀/얼룩이 감지돼 충전이 중지될 때 버즈가 보낸다 (연결이 끊기기 직전에도 온다)
MSG_SET_NOISE_CONTROLS = 0x78
MSG_EQUALIZER = 0x86          # 이퀄라이저 프리셋 설정: payload = [프리셋] (GalaxyBudsClient 의 프로토콜 정리와 같다)
MSG_CUSTOM_EQ_SEND = 0x89     # 9밴드 사용자 이퀄라이저: payload = [밴드 수][밴드별 이득(부호 있는 1바이트, -10~+10)]. 보낸 뒤 MSG_EQUALIZER 로 '사용자' 프리셋을 골라야 적용된다
MSG_CUSTOM_EQ_RECV = 0x69     # 이어버드의 프리셋 표 요청(빈 본문) -> 같은 번호로 [프리셋 수][밴드 수][표...][사용자 밴드값] 응답
MSG_ANC_ONE_EARBUD = 0x6F     # 한쪽만 착용해도 소음 제어 허용: payload = [0|1]
MSG_ADJUST_SOUND_SYNC = 0x85  # 게이밍 모드(저지연): payload = [0|1]. Buds3 Pro 로 확인: 켜면 상태 패킷 8번 자리가 1 이 된다

# 소음 제어 모드 번호 (갤럭시 버즈 계열). 실제 소리와의 대응은 장치/펌웨어마다 다를 수 있으니 한 곳에서만 정의한다.
MODE_OFF = 0
MODE_ANC = 1
MODE_AMBIENT = 2
MODE_ADAPTIVE = 3
VALID_MODES = (MODE_OFF, MODE_ANC, MODE_AMBIENT, MODE_ADAPTIVE)

# 이퀄라이저 프리셋 번호(Buds+ 이후 공통): 0 = 일반(끔), 1 = 베이스 부스트, 2 = 소프트, 3 = 다이내믹, 4 = 클리어, 5 = 트레블 부스트
EQ_PRESETS = (0, 1, 2, 3, 4, 5)
EQ_CUSTOM = 7                 # '사용자' 프리셋: MSG_CUSTOM_EQ_SEND 로 곡선을 보낸 뒤 이 값을 고른다 (Buds3 Pro 로 확인: 고르면 상태 패킷 9번 자리가 7 이 된다)
EQ_VALID = EQ_PRESETS + (EQ_CUSTOM,)
EQ_BANDS = 9
EQ_GAIN_MAX = 10              # 밴드마다 -10 ~ +10
NC_ONE_BYTE = 28              # 상태 패킷에서 '한쪽만 착용해도 소음 제어' 가 있는 자리: Buds2(개정 3 이상)·Buds2 Pro·Buds3·Buds3 Pro·FE 계열 공통 (GalaxyBudsClient 의 디코더와 같고, Buds3 Pro 로 켜고 끄며 확인)
GAME_BYTE = 8                 # Buds Live 이후 상태 패킷에서 게이밍 모드(음질 동기/저지연) 자리 (Buds3 Pro 로 확인)
EQ_BYTE = 9                   # EXTENDED_STATUS_UPDATED(0x61) 본문에서 이퀄라이저 프리셋이 있는 자리: Buds Live 이후(Buds2, Pro, Buds3 …)는 9 (실제 Buds3 Pro 패킷에서 확인한 레이아웃: 6=착용, 7=케이스 배터리, 8=음질 동기, 9=이퀄라이저, 10=터치 잠금)
EQ_BYTE_BUDS_PLUS = 11        # 오래된 Buds+ 는 11


def eq_byte_for(name: str) -> int:
    n = (name or "").lower().replace(" ", "")
    return EQ_BYTE_BUDS_PLUS if ("buds+" in n or "budsplus" in n) else EQ_BYTE

SAMSUNG_CONTROL_UUID = "2e73a4ad-332d-41fc-90e2-16bef06523f2"
BATTERY_SERVICE = "0000180f-0000-1000-8000-00805f9b34fb"
BATTERY_LEVEL = "00002a19-0000-1000-8000-00805f9b34fb"
PRESENTATION_FORMAT = "00002904-0000-1000-8000-00805f9b34fb"
# Bluetooth SIG GATT Namespace Descriptors
NS_LEFT, NS_RIGHT, NS_EXTERNAL = 0x010D, 0x010E, 0x0110


def crc16(data: bytes) -> int:
    """CRC-16/XMODEM (poly 0x1021, init 0)."""
    crc = 0
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def build_frame(msg_id: int, payload: bytes = b"") -> bytes:
    body = bytes([msg_id]) + bytes(payload)
    crc = crc16(body)
    size = len(body) + 2
    if size > 0x3FF:
        raise ValueError("payload too large")
    return bytes([SOM, size & 0xFF, (size >> 8) & 0x03]) + body + bytes([crc & 0xFF, crc >> 8, EOM])


class FrameParser:
    """바이트 스트림에서 프레임을 잘라 낸다. 조각나 도착해도, 앞에 쓰레기 바이트가 있어도 동작한다."""

    def __init__(self):
        self._buf = bytearray()

    def feed(self, data: bytes):
        """[(msg_id, payload, crc_ok), ...]"""
        self._buf += data
        out = []
        while True:
            i = self._buf.find(SOM)
            if i < 0:
                self._buf.clear()
                break
            if i:
                del self._buf[:i]
            if len(self._buf) < 3:
                break
            size = (self._buf[1] | (self._buf[2] << 8)) & 0x3FF
            total = size + 4
            if size < 3:               # id + crc 만으로도 최소 3
                del self._buf[:1]
                continue
            if len(self._buf) < total:
                break
            frame = bytes(self._buf[:total])
            if frame[-1] != EOM:       # 잘못 맞춘 SOM: 한 바이트 건너뛰고 다시 찾는다
                del self._buf[:1]
                continue
            del self._buf[:total]
            body = frame[3:-1]
            out.append((body[0], bytes(body[1:-2]), crc16(body[:-2]) == (body[-2] | (body[-1] << 8))))
        return out


def charging_bits(byte: int):
    """충전 비트: 4=왼쪽 버드, 2=오른쪽 버드, 0=케이스. 모르는 비트가 섞여 있으면 신뢰하지 않는다(None)."""
    if byte & ~0x15:
        return None
    return {"left": bool(byte & 0x10), "right": bool(byte & 0x04), "case": bool(byte & 0x01)}


def parse_status(payload: bytes):
    """STATUS_UPDATED(0x60) 본문 -> {'battery', 'placement', 'charging'} 또는 None. (Buds2 이후 공통)

    payload[1]=왼쪽, [2]=오른쪽 배터리, [5]=착용 상태(상위 4비트 왼쪽/하위 4비트 오른쪽), [6]=케이스 배터리, [7]=충전 비트.
    실제 Galaxy Buds3 Pro 패킷으로 확인: 02 4e 4e 01 01 33 42 14 -> 78/78/66%, 두 버드 충전 중(0x14), 케이스는 충전 아님."""
    if len(payload) < 8:
        return None
    bat = {}
    for pos, v in (("left", payload[1]), ("right", payload[2]), ("case", payload[6])):
        if 0 <= v <= 100:
            bat[pos] = v
    return {"battery": bat, "placement": {"left": payload[5] >> 4, "right": payload[5] & 15}, "charging": charging_bits(payload[7])}


# EXTENDED_STATUS_UPDATED(0x61)에도 같은 충전 비트가 있다. Buds3 계열은 payload[43] (실제 패킷에서 0x60 의 값과 일치하는 걸 확인).
# 이 패킷은 연결 직후 바로 오고, 0x60 은 한참 뒤에 오므로 처음 상태를 빨리 알기 위해 쓴다. 두 값이 다르면 0x60 을 우선한다.
CHARGE_BYTE_BUDS3 = 43


def nc_one_supported(n: str, revision: int) -> bool:
    """이 모델의 상태 패킷 28번 자리가 '한쪽만 착용해도 소음 제어' 인가 (n = 공백 없는 소문자 이름)."""
    if "buds2" in n:
        return "pro" in n or revision >= 3      # 그냥 Buds2 는 개정 3 부터
    return any(k in n for k in ("buds3", "budsfe", "buds4"))


def parse_ext_status(payload: bytes, name: str = ""):
    """EXTENDED_STATUS_UPDATED(0x61) 본문 -> {'placement', 'charging', 'revision'} 또는 None.
    (배터리는 일부 패킷에서 한쪽 버드 값이 예전 값으로 남아 있어 여기서는 읽지 않는다. 배터리는 0x60 과 GATT 로 읽는다.)"""
    if len(payload) < 8:
        return None
    pos = eq_byte_for(name)
    n = (name or "").lower().replace(" ", "")
    plus = pos != EQ_BYTE
    out = {"revision": payload[0], "placement": {"left": payload[6] >> 4, "right": payload[6] & 15}, "charging": None,
           "eq": payload[pos] if len(payload) > pos and payload[pos] in EQ_VALID else None,
           "game": (payload[GAME_BYTE] == 1) if (not plus and len(payload) > GAME_BYTE and payload[GAME_BYTE] in (0, 1)) else None,
           "nc_one": (payload[NC_ONE_BYTE] == 1) if (nc_one_supported(n, payload[0]) and len(payload) > NC_ONE_BYTE and payload[NC_ONE_BYTE] in (0, 1)) else None}
    if "buds3" in (name or "").lower().replace(" ", "") and len(payload) > CHARGE_BYTE_BUDS3:
        out["charging"] = charging_bits(payload[CHARGE_BYTE_BUDS3])
    return out


def alert_kind(payload: bytes) -> str:
    """STATUS_ALERT 의 종류. 지금까지 알려진 건 물/땀/얼룩으로 충전이 중지된 경우뿐이라 모두 'water' 로 본다.
    (케이스 배터리가 없을 때도 비슷한 신호가 올 수 있다는 제보가 있어, 본문은 로그에 남겨 나중에 구분할 수 있게 한다.)"""
    return "water"


def ack_ok(value: int, mode: int) -> bool:
    """SET_NOISE_CONTROLS 확인 응답의 값이 성공을 뜻하는가.

    실제 장치(Galaxy Buds3 Pro)는 이 값으로 0 을 주거나, 적용한 모드 번호를 그대로 돌려준다
    (모드 2 -> 2, 모드 1 -> 1). 둘 다 성공이다. 이전에는 0 만 성공으로 읽어서, 모드가 정상 적용됐는데도
    끄기(0) 외에는 모두 실패로 표시했다.
    """
    return value == 0 or value == mode


def parse_eq_table(reply: bytes):
    """MSG_CUSTOM_EQ_RECV 응답 -> {'presets': 프리셋 수(일반 포함), 'bands': 밴드 수, 'table': [[밴드값...] 프리셋별(0 = 일반은 모두 0)], 'custom': [사용자 곡선]} 또는 None.
    본문: [프리셋 수][밴드 수][(프리셋 수-1)*밴드 수 표][사용자 밴드 수만큼]. 값은 부호 있는 1바이트."""
    if len(reply) < 2:
        return None
    count, bands = reply[0], reply[1]
    need = 2 + (count - 1) * bands + bands
    if count < 1 or bands < 1 or len(reply) < need:
        return None
    sg = lambda b: b - 256 if b > 127 else b
    table = [[0] * bands]
    for i in range(count - 1):
        off = 2 + i * bands
        table.append([sg(b) for b in reply[off:off + bands]])
    off = 2 + (count - 1) * bands
    return {"presets": count, "bands": bands, "table": table, "custom": [sg(b) for b in reply[off:off + bands]]}


def ack_eq_ok(value: int, preset: int) -> bool:
    """MSG_EQUALIZER 확인 응답의 값이 성공을 뜻하는가. 소음 제어와 같은 장치 계열이라 0 이거나 적용한 값(또는 그 값+1)을 돌려주는 것으로 본다."""
    return value in (0, preset, preset + 1)


def battery_position(descriptor: bytes):
    """0x2904 Presentation Format 값 -> 'left' | 'right' | 'case' | None.
    형식: format(1) exponent(1) unit(2) namespace(1) description(2, LE)."""
    if len(descriptor) < 7 or descriptor[4] != 1:   # namespace 1 = Bluetooth SIG
        return None
    desc = descriptor[5] | (descriptor[6] << 8)
    return {NS_LEFT: "left", NS_RIGHT: "right", NS_EXTERNAL: "case"}.get(desc)


def merge_battery(entries):
    """[(position|None, level)] -> {'left':n,'right':n,'case':n} (알 수 없는 위치는 'main').

    케이스 배터리는 버드마다(왼쪽/오른쪽 장치 각각) 따로 보고하는데, 케이스 수치를 모르는 쪽은 0 을 준다.
    그래서 케이스는 0 을 '모름'으로 보고, 여러 값이 있으면 가장 큰(= 알고 있는 쪽) 값을 쓴다. 전부 0 이면 보여 주지 않는다."""
    out = {}
    for pos, level in entries:
        if level is None or not (0 <= level <= 100):
            continue
        if pos == "case":
            if level > out.get("case", 0):
                out["case"] = level
            continue
        out[pos or "main"] = level
    return out


# ----------------------------------------------------------------------
# 서비스
# ----------------------------------------------------------------------
SCAN_CONNECTED = 20.0       # 연결되어 있을 때 배터리 갱신 주기(초)
SCAN_IDLE = 7.0             # 연결을 기다리는 동안 확인 주기(초)
LOW_BATTERY = 20
LOW_RECOVER = 30
ACK_TIMEOUT = 3.0
CONNECT_TIMEOUT = 8.0
REJECT_RETRIES = 2         # 0 도 요청한 모드도 아닌 값이 오면 잠깐 뒤 다시 보낸다
REJECT_RETRY_DELAY = 0.45
SESSION_IDLE = 60.0      # 마지막 사용 후 제어 연결을 유지하는 시간(초). 이 안에서는 모드 변경이 즉시 된다.
SCAN_TIMEOUT = 15.0
STATUS_FRESH = 180.0       # 감시 연결에서 마지막 상태를 받은 지 이 시간 안이면 배터리 스캔(GATT)을 건너뛴다
WATCH_RETRY = 45.0         # 감시 연결에 실패했을 때 다시 시도하기까지(초)
WATCH_RETRY_IN_USE = 120.0  # 다른 앱(삼성 Galaxy Buds 앱 등)이 연결을 쥐고 있을 때
ALERT_GAP = 20.0           # 같은 경고를 이 시간 안에는 다시 알리지 않는다
EARBUD_NAME_HINT = ("buds", "pods", "earbud", "earphone", "ear (")


class BudsService:
    def __init__(self, log=None, push=None):
        self._log = log or (lambda m: None)
        self._push = push or (lambda e: None)
        self._lock = threading.Lock()
        self._snap = {"available": False, "connected": False, "name": "", "battery": {}, "control": False, "charging": None}
        self.watch = True              # 제어 연결을 계속 열어 두고 충전 상태/경고를 받는다 (설정 budsWatch)
        self._last_status = 0.0
        self._watch_retry_at = 0.0
        self._alert_at = 0.0
        self._seen_ids = set()
        self._status60 = False         # 이 연결에서 0x60 을 받았는가
        self._ext_logged = False       # 이 연결에서 0x61 본문을 한 번 로그에 남겼는가
        self._ext_prev = None          # 직전 0x61 본문 (바뀐 자리를 로그로 남기기 위해)
        self._loop = None
        self._thread = None
        self._running = False
        self._control_addr = None      # 삼성 제어 채널이 있는 클래식 장치 주소(int)
        self._control_cache = {}       # 이름 -> 주소(int) | None
        self._low_sent = set()
        self.low_battery = LOW_BATTERY    # 배터리 부족 알림 기준(%): 설정에서 바꾼다
        self._was_connected = False
        self._cmd_lock = None
        self._imports_ok = False
        self._target = None            # (HostName, service name) — SDP 결과 캐시 (매번 UNCACHED 조회는 1.5~5초 걸리고 간헐적으로 실패한다)
        self._target_svc = None
        self._target_addr = None
        self._sess = None              # 열려 있는 제어 연결
        self._idle_handle = None
        self._busy = False             # 연결/명령 중에는 배터리 스캔을 건너뛴다 (블루투스 라디오 경합 방지)
        self._pos_cache = {}           # (장치 id, 서비스 핸들) -> 배터리 위치: 디스크립터는 한 번만 읽는다

    # -- 외부 ----------------------------------------------------------
    def start(self):
        try:
            self._import_winrt()
        except Exception as e:
            self._log(f"buds: pywinrt unavailable ({e!r}); earbuds feature disabled")
            return False
        with self._lock:
            self._snap["available"] = True
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True, name="buds")
        self._thread.start()
        return True

    def stop(self):
        self._running = False
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)

    def snapshot(self):
        with self._lock:
            s = dict(self._snap)
            s["battery"] = dict(s["battery"])
            return s

    def set_noise_mode(self, mode, timeout=CONNECT_TIMEOUT + ACK_TIMEOUT + 3):
        """소음 제어 모드를 설정한다. {'status': 'ok'|'error', 'message': ...} (최대 timeout 초 블로킹)"""
        if mode not in VALID_MODES:
            return {"status": "error", "message": "invalid mode"}
        if not self._running or self._loop is None:
            return {"status": "error", "message": "buds service not running"}
        fut = asyncio.run_coroutine_threadsafe(self._set_mode(mode), self._loop)
        try:
            return fut.result(timeout)
        except Exception as e:
            fut.cancel()
            return {"status": "error", "message": f"timeout or error: {e!r}"}

    def set_equalizer(self, preset, timeout=CONNECT_TIMEOUT + ACK_TIMEOUT + 3):
        """이퀄라이저 프리셋(0~5)을 설정한다. {'status': 'ok'|'error', 'message': ...} (최대 timeout 초 블로킹)"""
        if preset not in EQ_VALID:
            return {"status": "error", "message": "invalid preset"}
        if not self._running or self._loop is None:
            return {"status": "error", "message": "buds service not running"}
        fut = asyncio.run_coroutine_threadsafe(self._send_setting(MSG_EQUALIZER, preset, lambda c: ack_eq_ok(c, preset), "eq", "eq"), self._loop)
        try:
            return fut.result(timeout)
        except Exception as e:
            fut.cancel()
            return {"status": "error", "message": f"timeout or error: {e!r}"}

    def set_custom_eq(self, bands):
        """9밴드 사용자 곡선(각 -10~+10)을 보내고 '사용자' 프리셋을 고른다. {'status': 'ok'|'error', ...}"""
        try:
            vals = [int(b) for b in bands]
        except Exception:
            return {"status": "error", "message": "invalid bands"}
        if len(vals) != EQ_BANDS:
            return {"status": "error", "message": "need 9 bands"}
        vals = [max(-EQ_GAIN_MAX, min(EQ_GAIN_MAX, v)) for v in vals]
        r = self.request(MSG_CUSTOM_EQ_SEND, bytes([EQ_BANDS]) + bytes(v & 0xFF for v in vals))
        if r.get("status") != "ok":
            return r
        out = self.set_equalizer(EQ_CUSTOM)
        if out.get("status") == "ok":
            out["bands"] = vals
            with self._lock:
                self._snap["eq_custom"] = list(vals)
        return out

    def eq_table(self):
        """이어버드의 프리셋 표와 사용자 곡선을 읽는다 (읽기만, 설정은 바뀌지 않는다). {'status','presets','bands','table','custom'}"""
        r = self.request(MSG_CUSTOM_EQ_RECV, b"", reply=MSG_CUSTOM_EQ_RECV)
        if r.get("status") != "ok" or not r.get("reply"):
            return {"status": "error", "message": r.get("message") or "no reply"}
        t = parse_eq_table(bytes.fromhex(r["reply"]))
        if t is None:
            return {"status": "error", "message": "unexpected reply"}
        t["status"] = "ok"
        with self._lock:
            self._snap["eq_custom"] = list(t["custom"])      # 설정 창이 다시 그려져도 곡선을 바로 보여 줄 수 있게 기억해 둔다
        return t

    def set_game_mode(self, on, timeout=CONNECT_TIMEOUT + ACK_TIMEOUT + 3):
        """게이밍 모드(저지연) 켜기/끄기."""
        return self._set_flag(MSG_ADJUST_SOUND_SYNC, bool(on), "game", timeout)

    def set_nc_one_earbud(self, on, timeout=CONNECT_TIMEOUT + ACK_TIMEOUT + 3):
        """한쪽만 착용해도 소음 제어 허용 켜기/끄기."""
        return self._set_flag(MSG_ANC_ONE_EARBUD, bool(on), "nc_one", timeout)

    def _set_flag(self, msg_id, on, key, timeout):
        if not self._running or self._loop is None:
            return {"status": "error", "message": "buds service not running"}
        v = 1 if on else 0
        fut = asyncio.run_coroutine_threadsafe(self._send_setting(msg_id, v, lambda c: c in (0, v), key, key), self._loop)
        try:
            return fut.result(timeout)
        except Exception as e:
            fut.cancel()
            return {"status": "error", "message": f"timeout or error: {e!r}"}

    def request(self, msg_id, payload=b"", reply=None, timeout=CONNECT_TIMEOUT + ACK_TIMEOUT * 2 + 3):
        """메시지 하나를 보내고 확인 응답(ack)과, reply 를 주면 같은 번호의 응답 본문(hex)을 기다린다.
        {'status': 'ok'|'error', 'ack': 값|None, 'reply': hex|None}. 새 기능을 이어버드로 확인할 때와 설정 창에서 쓴다."""
        if not self._running or self._loop is None:
            return {"status": "error", "message": "buds service not running"}
        fut = asyncio.run_coroutine_threadsafe(self._transact(msg_id, bytes(payload), reply), self._loop)
        try:
            return fut.result(timeout)
        except Exception as e:
            fut.cancel()
            return {"status": "error", "message": f"timeout or error: {e!r}"}

    def set_watch(self, on):
        """감시(제어 연결 유지) 켜기/끄기. 끄면 마지막 사용 후 일정 시간 뒤 연결을 닫는다."""
        on = bool(on)
        if on == self.watch:
            return
        self.watch = on
        if self._loop is not None:
            self._loop.call_soon_threadsafe(self._touch)

    def prepare_control(self):
        """페이지를 열 때 미리 제어 연결을 맺어 둔다 (기다리지 않는다). 첫 모드 변경의 연결 지연을 없앤다."""
        if self._running and self._loop is not None and self._control_addr is not None:
            asyncio.run_coroutine_threadsafe(self._warm(), self._loop)

    async def _warm(self):
        try:
            async with self._cmd_lock:
                await self._ensure_session()
        except Exception as e:
            self._log(f"buds: prepare failed {e!r}")

    # -- 내부: WinRT 가져오기 -------------------------------------------
    def _import_winrt(self):
        global BluetoothDevice, BluetoothLEDevice, BluetoothCacheMode, BluetoothConnectionStatus
        global RfcommServiceId, StreamSocket, SocketProtectionLevel, DataReader, DataWriter, InputStreamOptions
        global DeviceInformation, GattCommunicationStatus
        from winrt.windows.devices.bluetooth import (BluetoothCacheMode, BluetoothConnectionStatus, BluetoothDevice,
                                                    BluetoothLEDevice)
        from winrt.windows.devices.bluetooth.genericattributeprofile import GattCommunicationStatus
        from winrt.windows.devices.bluetooth.rfcomm import RfcommServiceId
        from winrt.windows.devices.enumeration import DeviceInformation
        from winrt.windows.networking.sockets import SocketProtectionLevel, StreamSocket
        from winrt.windows.storage.streams import DataReader, DataWriter, InputStreamOptions
        self._imports_ok = True

    def _run(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._cmd_lock = asyncio.Lock()
        self._loop.create_task(self._scan_loop())
        try:
            self._loop.run_forever()
        finally:
            self._loop.close()

    def _session_alive(self):
        return self._sess is not None and self._sess["alive"]

    async def _scan_loop(self):
        while self._running:
            try:
                fresh = self._session_alive() and (time.time() - self._last_status) < STATUS_FRESH
                # 연결이 열려 있고 상태가 들어오는 동안에는 GATT 스캔을 하지 않는다 (배터리는 상태 패킷에 들어 있고, 블루투스 라디오 경합도 피한다)
                if not self._busy and not fresh and not self._session_alive():
                    await asyncio.wait_for(self._scan_once(), SCAN_TIMEOUT)
                snap = self.snapshot()
                if (self.watch and snap["connected"] and snap["control"] and not self._busy and not self._session_alive()
                        and time.time() >= self._watch_retry_at):
                    await self._watch_connect()
            except Exception as e:
                self._log(f"buds: scan error {e!r}")
            snap = self.snapshot()
            for _ in range(int((SCAN_CONNECTED if snap["connected"] else SCAN_IDLE) * 4)):
                if not self._running:
                    return
                await asyncio.sleep(0.25)
                if self.watch and snap["connected"] and not self._session_alive() and self._sess is not None:
                    break          # 연결이 방금 끊겼다: 기다리지 않고 바로 다시 확인

    async def _watch_connect(self):
        """제어 연결을 열어 둔다 (충전 상태/경고 수신용). 실패하면 한동안 쉰다."""
        try:
            async with self._cmd_lock:
                await asyncio.wait_for(self._ensure_session(), CONNECT_TIMEOUT * 2 + 5)
            self._log("buds: watching status (control session kept open)")
        except Exception as e:
            in_use = getattr(e, "errno", None) == 10048
            self._watch_retry_at = time.time() + (WATCH_RETRY_IN_USE if in_use else WATCH_RETRY)
            self._log(f"buds: watch connect failed ({e!r}){' - another app holds the earbuds control channel' if in_use else ''}; retry later")

    async def _read_gatt_batteries(self, dev):
        """연결된 BLE 장치의 배터리 서비스 -> [(position, level)]. 서비스 탐색은 캐시, 값만 장치에서 읽는다."""
        res = await dev.get_gatt_services_for_uuid_with_cache_mode_async(uuid.UUID(BATTERY_SERVICE), BluetoothCacheMode.CACHED)
        if res.status != GattCommunicationStatus.SUCCESS or not res.services.size:
            res = await dev.get_gatt_services_for_uuid_async(uuid.UUID(BATTERY_SERVICE))
            if res.status != GattCommunicationStatus.SUCCESS:
                return []
        entries = []
        for svc in res.services:
            chs = await svc.get_characteristics_for_uuid_async(uuid.UUID(BATTERY_LEVEL))
            if chs.status != GattCommunicationStatus.SUCCESS:
                continue
            for ch in chs.characteristics:
                key = (dev.device_id, svc.attribute_handle)
                if key not in self._pos_cache:
                    pos = None
                    try:
                        ds = await ch.get_descriptors_for_uuid_async(uuid.UUID(PRESENTATION_FORMAT))
                        if ds.status == GattCommunicationStatus.SUCCESS and ds.descriptors.size:
                            r = await ds.descriptors[0].read_value_async()
                            if r.status == GattCommunicationStatus.SUCCESS:
                                pos = battery_position(self._buf_bytes(r.value))
                    except Exception:
                        pass
                    self._pos_cache[key] = pos
                # 항상 장치에서 직접 읽는다. 케이스 배터리 특성은 알림이 꺼져 있어 기본(캐시 허용) 읽기는 옛 값을 계속 돌려준다
                # (실측: 캐시 58% 고정, 실제 값은 92%)
                r = await ch.read_value_with_cache_mode_async(BluetoothCacheMode.UNCACHED)
                if r.status == GattCommunicationStatus.SUCCESS:
                    b = self._buf_bytes(r.value)
                    if b:
                        entries.append((self._pos_cache[key], b[0]))
        return entries

    @staticmethod
    def _buf_bytes(buf):
        reader = DataReader.from_buffer(buf)
        data = bytearray(buf.length)
        reader.read_bytes(data)
        return bytes(data)

    async def _scan_once(self):
        infos = await DeviceInformation.find_all_async_aqs_filter(BluetoothLEDevice.get_device_selector_from_pairing_state(True))
        groups = {}
        for info in infos:
            dev = None
            try:
                dev = await BluetoothLEDevice.from_id_async(info.id)
                if dev is None or dev.connection_status != BluetoothConnectionStatus.CONNECTED:
                    continue
                entries = await self._read_gatt_batteries(dev)
                if entries:
                    groups.setdefault(dev.name or "", []).extend(entries)
            except Exception as e:
                self._log(f"buds: device read error {e!r}")
            finally:
                if dev is not None:
                    try:
                        dev.close()
                    except Exception:
                        pass

        # 이어버드만 고른다: 좌/우 위치가 있거나 이름이 이어버드처럼 보이는 장치
        best = None
        for name, entries in groups.items():
            bat = merge_battery(entries)
            if "left" in bat or "right" in bat or any(h in name.lower() for h in EARBUD_NAME_HINT):
                best = (name, bat)
                break

        if best is None:
            self._update(False, "", {}, False)
            return
        name, bat = best
        control = await self._find_control_addr(name)
        self._update(True, name, bat, control)

    async def _find_control_addr(self, name):
        """같은 이름으로 페어링된 클래식 장치 중 삼성 제어 서비스를 가진 것의 주소 (이름별로 캐시)."""
        if name in self._control_cache:
            self._control_addr = self._control_cache[name]
            return self._control_addr is not None
        addr = None
        try:
            infos = await DeviceInformation.find_all_async_aqs_filter(BluetoothDevice.get_device_selector_from_pairing_state(True))
            sid = RfcommServiceId.from_uuid(uuid.UUID(SAMSUNG_CONTROL_UUID))
            for info in infos:
                if (info.name or "") != name:
                    continue
                d = await BluetoothDevice.from_id_async(info.id)
                if d is None:
                    continue
                try:
                    r = await d.get_rfcomm_services_for_id_with_cache_mode_async(sid, BluetoothCacheMode.CACHED)
                    if r.services.size:
                        addr = d.bluetooth_address
                        break
                finally:
                    d.close()
        except Exception as e:
            self._log(f"buds: control lookup error {e!r}")
        self._control_cache[name] = addr
        self._control_addr = addr
        return addr is not None

    def _update(self, connected, name, battery, control, charging="keep"):
        with self._lock:
            before = self._was_connected
            self._snap.update({"connected": connected, "name": name, "battery": battery, "control": control})
            if not connected:
                self._snap["charging"] = None
            elif charging != "keep":
                self._snap["charging"] = charging
        if connected and not before:
            self._log(f"buds: connected {name} {battery} control={control}")
            self._push({"type": "buds", "name": name, "battery": battery, "control": control})
        elif before and not connected:
            self._log("buds: disconnected")
            self._push({"type": "buds_gone"})
        self._was_connected = connected
        # 배터리 부족 알림: 위치별로 한 번만, 충분히 오르면 다시 무장
        for pos, lv in battery.items():
            key = pos
            if lv <= self.low_battery and key not in self._low_sent:
                self._low_sent.add(key)
                if pos != "case":
                    self._push({"type": "buds_low", "name": name, "position": pos, "percent": lv})
            elif lv >= self.low_battery + (LOW_RECOVER - LOW_BATTERY):
                self._low_sent.discard(key)

    # -- 소음 제어 (세션) ------------------------------------------------
    async def _resolve_target(self, uncached=False):
        """제어 서비스의 연결 대상을 찾는다. 결과는 캐시한다 (UNCACHED SDP 조회는 느리고 간헐적으로 실패한다)."""
        addr = self._control_addr
        if addr is None:
            raise RuntimeError("no Samsung control channel (not paired / unsupported)")
        if self._target is not None and self._target_addr == addr and not uncached:
            return self._target
        dev = await BluetoothDevice.from_bluetooth_address_async(addr)
        sid = RfcommServiceId.from_uuid(uuid.UUID(SAMSUNG_CONTROL_UUID))
        try:
            res = await dev.get_rfcomm_services_for_id_with_cache_mode_async(
                sid, BluetoothCacheMode.UNCACHED if uncached else BluetoothCacheMode.CACHED)
            if not res.services.size and not uncached:
                res = await dev.get_rfcomm_services_for_id_with_cache_mode_async(sid, BluetoothCacheMode.UNCACHED)
        finally:
            dev.close()
        if not res.services.size:
            raise RuntimeError("control service not found")
        svc = res.services[0]
        self._target_svc = svc          # 참조를 유지해 연결 정보가 무효화되지 않게 한다
        self._target = (svc.connection_host_name, svc.connection_service_name)
        self._target_addr = addr
        return self._target

    async def _connect_socket(self):
        host, name = await self._resolve_target()
        sock = StreamSocket()
        try:
            await asyncio.wait_for(sock.connect_with_protection_level_async(
                host, name, SocketProtectionLevel.BLUETOOTH_ENCRYPTION_ALLOW_NULL_AUTHENTICATION), CONNECT_TIMEOUT)
            return sock
        except Exception:
            try:
                sock.close()
            except Exception:
                pass
            raise

    async def _ensure_session(self):
        sess = self._sess
        if sess is not None and sess["alive"]:
            self._touch()
            return sess
        await self._close_session()
        self._busy = True
        t0 = time.perf_counter()
        try:
            try:
                sock = await self._connect_socket()
            except Exception as e:
                self._log(f"buds: connect failed ({e!r}); re-resolving service and retrying once")
                self._target = None
                await self._resolve_target(uncached=True)
                sock = await self._connect_socket()
            reader = DataReader(sock.input_stream)
            reader.input_stream_options = InputStreamOptions.PARTIAL
            writer = DataWriter(sock.output_stream)
            sess = {"sock": sock, "reader": reader, "writer": writer, "alive": True, "waiters": {}, "replies": {}}
            self._status60 = False
            self._ext_logged = False
            self._ext_prev = None
            sess["task"] = self._loop.create_task(self._reader_loop(sess))
            self._sess = sess
            self._log(f"buds: control session open in {(time.perf_counter() - t0) * 1000:.0f}ms")
            self._touch()
            return sess
        finally:
            self._busy = False

    async def _reader_loop(self, sess):
        """세션이 열려 있는 동안 계속 읽으며 확인 응답(ACK)을 기다리는 쪽에 전달한다."""
        parser = FrameParser()
        try:
            while sess["alive"]:
                n = await sess["reader"].load_async(1024)
                if n == 0:
                    break
                data = bytearray(n)
                sess["reader"].read_bytes(data)
                for mid, payload, ok in parser.feed(bytes(data)):
                    if not ok:
                        continue
                    rep = sess["replies"].pop(mid, None) if mid != MSG_ACK else None      # 요청에 대한 같은 번호의 응답 메시지(프리셋 표 등)
                    if rep is not None and not rep.done():
                        rep.set_result(bytes(payload))
                    if mid == MSG_ACK and len(payload) >= 2:
                        fut = sess["waiters"].pop(payload[0], None)
                        if fut is not None and not fut.done():
                            fut.set_result(payload[1])
                    elif mid == MSG_STATUS:
                        self._on_status(payload)
                    elif mid == MSG_EXT_STATUS:
                        self._on_ext_status(payload)
                    elif mid == MSG_STATUS_ALERT:
                        self._on_alert(payload)
                    else:
                        self._note_frame(mid, payload)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            if sess["alive"]:
                self._log(f"buds: control session read ended ({e!r})")
        finally:
            sess["alive"] = False
            for fut in sess["waiters"].values():
                if not fut.done():
                    fut.set_exception(ConnectionError("control session closed"))
            sess["waiters"].clear()

    def _apply_status(self, battery, charging, placement, source):
        with self._lock:
            bat = dict(self._snap["battery"])
            name = self._snap["name"]
            prev = self._snap.get("charging")
        for pos, v in battery.items():
            if pos == "case" and v == 0:
                continue            # 케이스 수치를 모르면 0 을 보낸다
            bat[pos] = v
        self._update(True, name, bat, True, charging="keep" if charging is None else charging)
        if charging is not None and charging != prev:
            self._log(f"buds: charging {charging} placement={placement} battery={bat} (from {source})")

    def _on_status(self, payload):
        """STATUS_UPDATED(0x60): 배터리와 충전 중 표시. 주기적으로 오고 값이 믿을 만하다."""
        try:
            st = parse_status(payload)
            if st is None:
                return
            self._last_status = time.time()
            self._status60 = True
            self._apply_status(st["battery"], st["charging"], st["placement"], "0x60")
        except Exception as e:
            self._log(f"buds: status parse error {e!r}")

    def _on_ext_status(self, payload):
        """EXTENDED_STATUS_UPDATED(0x61): 연결 직후 바로 오는 패킷이라 첫 충전 상태에만 쓴다 (0x60 을 받은 뒤에는 0x60 우선)."""
        try:
            st = parse_ext_status(payload, self._snap.get("name", ""))
            if st is None:
                return
            self._last_status = time.time()
            raw = bytes(payload)
            if not self._ext_logged:
                self._ext_logged = True
                self._log(f"buds: ext status len={len(raw)} payload={raw[:40].hex()}")       # 이퀄라이저 등 값이 있는 자리를 확인하는 단서
            elif self._ext_prev is not None and raw != self._ext_prev and len(raw) == len(self._ext_prev):
                diff = [f"[{i}] {self._ext_prev[i]:02x}->{raw[i]:02x}" for i in range(len(raw)) if raw[i] != self._ext_prev[i] and i not in (2, 3, 7)]      # 배터리 자리는 자주 바뀌어 뺀다
                if diff:
                    self._log("buds: ext status changed " + " ".join(diff))
            self._ext_prev = raw
            for key in ("game", "nc_one"):
                if st.get(key) is not None:
                    with self._lock:
                        self._snap[key] = st[key]
            if st.get("eq") is not None:
                with self._lock:
                    changed = self._snap.get("eq") != st["eq"]
                    self._snap["eq"] = st["eq"]
                if changed:
                    self._log(f"buds: equalizer preset {st['eq']} (from 0x61)")
            if not self._status60:
                self._apply_status({}, st["charging"], st["placement"], "0x61")
        except Exception as e:
            self._log(f"buds: ext status parse error {e!r}")

    def _on_alert(self, payload):
        """STATUS_ALERT: 물/땀/얼룩이 감지돼 충전이 중지됐다는 경고. 연결이 끊기기 직전에도 온다."""
        self._log(f"buds: STATUS_ALERT payload={bytes(payload).hex()}")
        now = time.time()
        if now - self._alert_at < ALERT_GAP:
            return
        self._alert_at = now
        self._push({"type": "buds_alert", "name": self._snap.get("name", ""), "kind": alert_kind(payload), "hex": bytes(payload).hex()})

    def _note_frame(self, mid, payload):
        """모르는 메시지는 종류별로 한 번만 로그에 남긴다 (새 신호를 알아내는 단서)."""
        if mid in self._seen_ids or len(self._seen_ids) > 80:
            return
        self._seen_ids.add(mid)
        self._log(f"buds: frame 0x{mid:02x} len={len(payload)} {bytes(payload[:24]).hex()}")

    def _touch(self):
        """마지막 사용 시각 갱신: SESSION_IDLE 동안 쓰지 않으면 연결을 닫는다 (폰의 Galaxy Wearable 과 덜 충돌하도록)."""
        if self._idle_handle is not None:
            self._idle_handle.cancel()
            self._idle_handle = None
        if self.watch and self._control_addr is not None:
            return                      # 감시 중에는 연결을 닫지 않는다 (충전 상태/경고를 계속 받으려고)
        self._idle_handle = self._loop.call_later(SESSION_IDLE, lambda: self._loop.create_task(self._close_session()))

    async def _close_session(self):
        sess, self._sess = self._sess, None
        if self._idle_handle is not None:
            self._idle_handle.cancel()
            self._idle_handle = None
        if sess is None:
            return
        sess["alive"] = False
        try:
            sess["task"].cancel()
        except Exception:
            pass
        try:
            sess["sock"].close()
        except Exception:
            pass

    async def _transact(self, msg_id, payload, reply):
        async with self._cmd_lock:
            if self._control_addr is None:
                return {"status": "error", "message": "no Samsung control channel (not paired / unsupported)"}
            last_err, last_code = "unknown", None
            for attempt in (1, 2):
                try:
                    sess = await self._ensure_session()
                    ack = self._loop.create_future()
                    sess["waiters"][msg_id] = ack
                    rep = None
                    if reply is not None:
                        rep = self._loop.create_future()
                        sess["replies"][reply] = rep
                    self._busy = True
                    try:
                        sess["writer"].write_bytes(build_frame(msg_id, payload))
                        await sess["writer"].store_async()
                        out = {"status": "ok", "ack": None, "reply": None}
                        if rep is not None:      # 같은 번호의 응답을 기다리는 요청(프리셋 표 등)은 확인 응답(ack)이 오지 않는다: 응답이 오면 곧바로 끝낸다
                            try:
                                out["reply"] = (await asyncio.wait_for(rep, ACK_TIMEOUT)).hex()
                            except asyncio.TimeoutError:
                                pass
                            if ack.done():
                                out["ack"] = ack.result()
                        else:
                            try:
                                out["ack"] = await asyncio.wait_for(ack, ACK_TIMEOUT)
                            except asyncio.TimeoutError:
                                pass
                    finally:
                        self._busy = False
                        sess["waiters"].pop(msg_id, None)
                        if reply is not None:
                            sess["replies"].pop(reply, None)
                    self._touch()
                    self._log(f"buds: request 0x{msg_id:02x} {payload.hex() or '-'} -> ack={out['ack']} reply={(out['reply'] or '-')[:80]}")
                    return out
                except Exception as e:
                    last_err = repr(e) or type(e).__name__
                    last_code = "in_use" if getattr(e, "errno", None) == 10048 else None
                    await self._close_session()
            return {"status": "error", "message": last_err, "code": last_code}

    async def _set_mode(self, mode):
        return await self._send_setting(MSG_SET_NOISE_CONTROLS, mode, lambda code: ack_ok(code, mode), "mode", "mode")

    async def _send_setting(self, msg_id, mode, ok, what, key):
        """값 하나를 보내고 확인 응답을 기다린다 (소음 제어 모드, 이퀄라이저 프리셋 공통). ok(응답 값) -> 성공인가."""
        async with self._cmd_lock:
            t0 = time.perf_counter()
            marks = {}

            def finish(result):
                total = (time.perf_counter() - t0) * 1000
                detail = " ".join(f"{k}={v:.0f}ms" for k, v in marks.items())
                self._log(f"buds: set {what} {mode} -> {result.get('status')} in {total:.0f}ms ({detail})"
                          + (f" [{result.get('message')}]" if result.get("status") != "ok" else ""))
                return result

            if self._control_addr is None:
                return finish({"status": "error", "message": "no Samsung control channel (not paired / unsupported)"})
            last_err, last_code = "unknown", None
            for attempt in (1, 2):          # 세션이 죽어 있었다면 한 번 다시 연결해서 시도
                try:
                    sess = await self._ensure_session()
                    marks[f"session{attempt}"] = (time.perf_counter() - t0) * 1000
                    fut = self._loop.create_future()
                    sess["waiters"][msg_id] = fut
                    self._busy = True
                    codes = []
                    try:
                        for tries in range(1 + REJECT_RETRIES):
                            if tries:
                                await asyncio.sleep(REJECT_RETRY_DELAY)
                                fut = self._loop.create_future()
                            sess["waiters"][msg_id] = fut
                            sess["writer"].write_bytes(build_frame(msg_id, bytes([mode])))
                            await sess["writer"].store_async()
                            marks.setdefault("sent", (time.perf_counter() - t0) * 1000)
                            code = await asyncio.wait_for(fut, ACK_TIMEOUT)
                            codes.append(code)
                            if ok(code):
                                break
                    finally:
                        self._busy = False
                        sess["waiters"].pop(msg_id, None)
                    marks["ack"] = (time.perf_counter() - t0) * 1000
                    self._touch()
                    if ok(codes[-1]):
                        if len(codes) > 1:
                            self._log(f"buds: {what} {mode} accepted after {len(codes) - 1} rejection(s) {codes[:-1]}")
                        if key in ("eq", "game", "nc_one"):
                            with self._lock:
                                self._snap[key] = mode if key == "eq" else bool(mode)
                        return finish({"status": "ok", key: mode})
                    return finish({"status": "error", "message": f"device rejected (codes {codes})"})
                except Exception as e:
                    last_err = repr(e) or type(e).__name__
                    # WSAEADDRINUSE(10048): 이어버드는 제어 연결을 한 곳에만 허용한다. 삼성 'Galaxy Buds' Windows 앱 등
                    # 다른 프로그램이 이미 잡고 있으면 이렇게 거절된다 -> 화면이 이유를 알려 줄 수 있게 코드로 구분한다
                    last_code = "in_use" if getattr(e, "errno", None) == 10048 else None
                    await self._close_session()
            return finish({"status": "error", "message": last_err, "code": last_code})
