"""성능 탭 / 작은 노치용: CPU 사용률, 메모리 사용률, 네트워크 속도. 모두 ctypes 로 윈도우 API 에서 읽고, 추가 패키지는 쓰지 않는다.

- CPU: GetSystemTimes 의 (커널+사용자-유휴) 변화량 / (커널+사용자) 변화량. 처음 부르면 기준값만 잡아 None.
- 메모리: GlobalMemoryStatusEx.
- 네트워크: GetIfTable 의 받은/보낸 바이트(32비트 카운터라 한 번 돌아간 것까지는 차이로 보정)를 실제 어댑터(이더넷·Wi-Fi)만 더해
  시간 차이로 나눈다. 가상 어댑터(Hyper-V, Docker, VPN 터널 등)는 같은 트래픽이 두 번 세지므로 뺀다.
- GPU: 윈도우 성능 카운터(PDH)의 'GPU Engine(*)/Utilization Percentage' (작업 관리자의 GPU 사용률과 같은 출처). 프로세스마다 나뉘어 나오는 값을
  엔진별로 더하고 그중 가장 바쁜 엔진을 GPU 사용률로 본다(작업 관리자와 같은 방식). 그래픽 카드나 카운터가 없으면 None 이라 화면에서 칸이 사라진다.
"""
import ctypes
import threading
import time
from ctypes import wintypes

kernel32 = ctypes.windll.kernel32

MIB_IF_TYPE_ETHERNET = 6
IF_TYPE_IEEE80211 = 71
IF_OPER_STATUS_OPERATIONAL = 5
_VIRTUAL_WORDS = ("virtual", "hyper-v", "vmware", "vbox", "loopback", "bluetooth", "tap-", "wan miniport", "pseudo", "wintun", "wireguard",
                  "vpn", "tunnel", "teredo", "isatap", "6to4", "npcap", "wsl", "docker")


class _FILETIME(ctypes.Structure):
    _fields_ = [("dwLowDateTime", wintypes.DWORD), ("dwHighDateTime", wintypes.DWORD)]


class _MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [("dwLength", wintypes.DWORD), ("dwMemoryLoad", wintypes.DWORD), ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong), ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong), ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]


class _MIB_IFROW(ctypes.Structure):
    _fields_ = [("wszName", ctypes.c_wchar * 256), ("dwIndex", wintypes.DWORD), ("dwType", wintypes.DWORD), ("dwMtu", wintypes.DWORD), ("dwSpeed", wintypes.DWORD),
                ("dwPhysAddrLen", wintypes.DWORD), ("bPhysAddr", ctypes.c_ubyte * 8), ("dwAdminStatus", wintypes.DWORD), ("dwOperStatus", wintypes.DWORD),
                ("dwLastChange", wintypes.DWORD), ("dwInOctets", wintypes.DWORD), ("dwInUcastPkts", wintypes.DWORD), ("dwInNUcastPkts", wintypes.DWORD),
                ("dwInDiscards", wintypes.DWORD), ("dwInErrors", wintypes.DWORD), ("dwInUnknownProtos", wintypes.DWORD), ("dwOutOctets", wintypes.DWORD),
                ("dwOutUcastPkts", wintypes.DWORD), ("dwOutNUcastPkts", wintypes.DWORD), ("dwOutDiscards", wintypes.DWORD), ("dwOutErrors", wintypes.DWORD),
                ("dwOutQLen", wintypes.DWORD), ("dwDescrLen", wintypes.DWORD), ("bDescr", ctypes.c_ubyte * 256)]


def is_real_adapter(if_type, oper_status, descr):
    """네트워크 속도에 더할 어댑터인가: 이더넷/Wi-Fi 이고 동작 중이며 가상 어댑터가 아닌 것."""
    if if_type not in (MIB_IF_TYPE_ETHERNET, IF_TYPE_IEEE80211) or oper_status != IF_OPER_STATUS_OPERATIONAL:
        return False
    d = str(descr or "").lower()
    return not any(w in d for w in _VIRTUAL_WORDS)


def counter_delta(new, old, bits=32):
    """카운터 차이(한 번 돌아간 것은 보정)."""
    return (int(new) - int(old)) % (1 << bits)


def net_delta(new, old):
    """네트워크 바이트 합의 증가분. 합계가 줄었으면(어댑터가 빠졌다) 돌아간 것이 아니라 0 으로 본다: 진짜로 한 바퀴 돌아간 경우는 증가분이 작아 2GB 를 넘지 않는다."""
    d = counter_delta(new, old)
    return 0 if d > (1 << 31) else d


def read_cpu_times():
    idle, kern, user = _FILETIME(), _FILETIME(), _FILETIME()
    if not kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kern), ctypes.byref(user)):
        return None
    f = lambda t: (t.dwHighDateTime << 32) | t.dwLowDateTime
    return f(idle), f(kern), f(user)


def read_memory():
    """{'percent': 0~100, 'used_gb', 'total_gb'} 또는 None."""
    m = _MEMORYSTATUSEX()
    m.dwLength = ctypes.sizeof(m)
    if not kernel32.GlobalMemoryStatusEx(ctypes.byref(m)) or not m.ullTotalPhys:
        return None
    used = m.ullTotalPhys - m.ullAvailPhys
    return {"percent": int(m.dwMemoryLoad), "used_gb": round(used / 2 ** 30, 1), "total_gb": round(m.ullTotalPhys / 2 ** 30, 1)}


def read_net_octets():
    """(받은 바이트 합, 보낸 바이트 합) — 실제 어댑터만. 읽지 못하면 None."""
    try:
        ip = ctypes.WinDLL("iphlpapi")
        size = wintypes.ULONG(0)
        ip.GetIfTable(None, ctypes.byref(size), False)
        if not size.value:
            return None
        buf = (ctypes.c_ubyte * size.value)()
        if ip.GetIfTable(buf, ctypes.byref(size), False) != 0:
            return None
        n = wintypes.DWORD.from_buffer(buf, 0).value
        row_size = ctypes.sizeof(_MIB_IFROW)
        rx = tx = 0
        for i in range(n):
            row = _MIB_IFROW.from_buffer(buf, 4 + i * row_size)
            descr = bytes(row.bDescr[:min(row.dwDescrLen, 256)]).split(b"\x00")[0].decode("latin-1", "replace")
            if is_real_adapter(row.dwType, row.dwOperStatus, descr):
                rx += row.dwInOctets
                tx += row.dwOutOctets
        return rx, tx
    except Exception:
        return None


# ---------------------------------------------------------------------------------------------------------------
# GPU 사용률 (PDH 성능 카운터)
# ---------------------------------------------------------------------------------------------------------------
PDH_FMT_DOUBLE = 0x00000200
PDH_MORE_DATA = 0x800007D2
_GPU_PATH = "\\GPU Engine(*)\\Utilization Percentage"


def gpu_percent_from_items(items):
    """[(인스턴스 이름, 값)] -> GPU 사용률(0~100) 또는 None.
    인스턴스 이름은 'pid_123_luid_0x..._0x..._phys_0_eng_2_engtype_3D' 꼴이다. 같은 엔진(luid+phys+eng)의 프로세스별 값을 더하고, 가장 바쁜 엔진을 쓴다."""
    engines = {}
    for name, val in items:
        try:
            v = float(val)
        except (TypeError, ValueError):
            continue
        if v != v or v < 0:
            continue
        n = str(name)
        i = n.find("_luid_")
        if i < 0:
            continue
        eng = n[i:]                       # '_luid_0x..._0x..._phys_0_eng_2_engtype_3D' (pid 부분을 뗀다)
        engines[eng] = engines.get(eng, 0.0) + v
    if not engines:
        return None
    return max(0, min(100, int(round(max(engines.values())))))


class _CounterValueItem(ctypes.Structure):
    _fields_ = [("szName", ctypes.c_void_p), ("CStatus", wintypes.DWORD), ("pad", wintypes.DWORD), ("doubleValue", ctypes.c_double)]


class GpuReader:
    """GPU 카운터 질의를 열어 두고 부를 때마다 값을 읽는다(처음 한 번은 기준만 잡아 None). 카운터가 없으면 영원히 None."""

    def __init__(self):
        self._q = None
        self._c = None
        self._pdh = None
        self._dead = False
        self._primed = False

    def _open(self):
        try:
            pdh = ctypes.WinDLL("pdh")
            q = ctypes.c_void_p()
            if pdh.PdhOpenQueryW(None, 0, ctypes.byref(q)) != 0:
                return False
            c = ctypes.c_void_p()
            if pdh.PdhAddEnglishCounterW(q, _GPU_PATH, 0, ctypes.byref(c)) != 0:
                pdh.PdhCloseQuery(q)
                return False
            self._pdh, self._q, self._c = pdh, q, c
            return True
        except Exception:
            return False

    def read(self):
        if self._dead:
            return None
        if self._q is None and not self._open():
            self._dead = True
            return None
        try:
            pdh = self._pdh
            if pdh.PdhCollectQueryData(self._q) != 0:
                return None
            if not self._primed:
                self._primed = True
                return None
            size, count = wintypes.DWORD(0), wintypes.DWORD(0)
            r = pdh.PdhGetFormattedCounterArrayW(self._c, PDH_FMT_DOUBLE, ctypes.byref(size), ctypes.byref(count), None)
            if (r & 0xFFFFFFFF) != PDH_MORE_DATA or not size.value:
                return None
            buf = (ctypes.c_ubyte * size.value)()
            if pdh.PdhGetFormattedCounterArrayW(self._c, PDH_FMT_DOUBLE, ctypes.byref(size), ctypes.byref(count), buf) != 0:
                return None
            arr = ctypes.cast(buf, ctypes.POINTER(_CounterValueItem))
            items = []
            for i in range(count.value):
                it = arr[i]
                if it.CStatus in (0, 1) and it.szName:
                    items.append((ctypes.wstring_at(it.szName), it.doubleValue))
            return gpu_percent_from_items(items)
        except Exception:
            return None


class PerfSampler:
    """부를 때마다 이전 부름과의 차이로 CPU 사용률과 네트워크 속도를 돌려준다. 여러 곳에서 불러도 안전하다."""

    def __init__(self, cpu_reader=read_cpu_times, mem_reader=read_memory, net_reader=read_net_octets, clock=time.monotonic, gpu_reader=None):
        self._cpu_reader, self._mem_reader, self._net_reader, self._clock = cpu_reader, mem_reader, net_reader, clock
        self._gpu_reader = gpu_reader if gpu_reader is not None else GpuReader().read
        self._lock = threading.Lock()
        self._cpu = self._cpu_reader()
        self._net = self._net_reader()
        self._t = self._clock()
        self.last = None

    def sample(self):
        with self._lock:
            now = self._clock()
            out = {"cpu": None, "mem": None, "net": None, "gpu": None}
            cpu = self._cpu_reader()
            if cpu and self._cpu:
                di, dk, du = (cpu[i] - self._cpu[i] for i in range(3))
                total = dk + du
                if total > 0:
                    out["cpu"] = max(0, min(100, round((total - di) * 100.0 / total)))
            if cpu:
                self._cpu = cpu
            out["mem"] = self._mem_reader()
            net = self._net_reader()
            dt = now - self._t
            if net and self._net and dt > 0.2:
                out["net"] = {"down": net_delta(net[0], self._net[0]) / dt, "up": net_delta(net[1], self._net[1]) / dt}
                self._net = net
                self._t = now
            elif net and not self._net:
                self._net = net          # 처음 한 번은 기준만 잡는다
                self._t = now
            try:
                out["gpu"] = self._gpu_reader()
            except Exception:
                out["gpu"] = None
            if out["cpu"] is None and self.last:
                out["cpu"] = self.last.get("cpu")
            if out["net"] is None and self.last:
                out["net"] = self.last.get("net")
            if out["gpu"] is None and self.last:
                out["gpu"] = self.last.get("gpu")
            self.last = out
            return out
