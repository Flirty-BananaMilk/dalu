# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Flirty_BananaMilk — 상업적 이용 금지, 자세한 내용은 LICENSE
"""실시간 오디오 레벨(비주얼라이저용).

Windows 의 기본 출력 장치를 WASAPI 루프백으로 열어 '지금 스피커로 나가는 소리'를 읽고, 저음~고음 5개 대역의
크기(0~1)를 계산한다. 소리는 메모리에서 대역 크기를 뽑는 데만 쓰고 저장하거나 어디로도 보내지 않는다.

* numpy 가 없어서 대역별 Goertzel 필터를 순수 파이썬으로 계산한다 (12kHz 로 다운샘플 후 약 0.3ms/프레임).
* 화면에 비주얼라이저가 보일 때(= poll() 이 호출되는 동안)만 계산하고, 그 외에는 오디오만 비운다.
* pythonnet 을 쓰지 않는다 (감시 스레드에서 .NET 을 만지면 프로세스가 죽는다). ctypes COM 만 사용.
* 장치가 바뀌거나(헤드폰 연결 등) 오류가 나면 스스로 다시 연결한다. 실패하면 available=False.
"""

import ctypes
import math
import struct
import threading
import time
from ctypes import wintypes

from sysmon import (_CLSCTX_ALL, _CLSID_MMDeviceEnumerator, _GUID, _IID_IMMDeviceEnumerator, _guid, _release, _vcall,
                    ole32)

_IID_IAudioClient = _guid("{1CB9AD4C-DBFA-4C32-B178-C2F568A703B2}")
_IID_IAudioCaptureClient = _guid("{C8ADBD64-E71E-48A0-A4DE-185C395CD317}")

AUDCLNT_SHAREMODE_SHARED = 0
AUDCLNT_STREAMFLAGS_LOOPBACK = 0x00020000
AUDCLNT_BUFFERFLAGS_SILENT = 0x2

TARGET_RATE = 12000           # 다운샘플 후 목표 샘플레이트: 6kHz 까지의 대역만 필요하다 (48kHz->1/4, 96kHz->1/8)
WINDOW_MS = 42                # 분석 창 길이. 저음(60Hz)을 구분하려면 이 정도는 필요하다
FRAME_INTERVAL = 0.04         # 대역 계산 주기(초) = 25fps
IDLE_AFTER = 1.5              # poll() 이 이 시간 동안 없으면 계산을 멈춘다

# 대역: (이름, 주파수 3개). 낮은 대역일수록 에너지가 크므로 tilt(dB)로 고음을 끌어올려 막대 높이를 맞춘다.
BANDS = [
    ("bass",   (55, 80, 115), 0.0),
    ("lowmid", (170, 240, 340), 4.0),
    ("mid",    (500, 700, 1000), 8.0),
    ("highmid", (1500, 2100, 3000), 12.0),
    ("treble", (4000, 5000, 5800), 16.0),
]


class _WAVEFORMATEX(ctypes.Structure):
    _pack_ = 1
    _fields_ = [("wFormatTag", ctypes.c_ushort), ("nChannels", ctypes.c_ushort), ("nSamplesPerSec", ctypes.c_uint),
                ("nAvgBytesPerSec", ctypes.c_uint), ("nBlockAlign", ctypes.c_ushort),
                ("wBitsPerSample", ctypes.c_ushort), ("cbSize", ctypes.c_ushort)]


def goertzel_power(samples, coeff):
    """samples 에서 coeff=2cos(2πf/fs) 에 해당하는 주파수 성분의 파워."""
    s1 = s2 = 0.0
    for v in samples:
        s0 = v + coeff * s1 - s2
        s2 = s1
        s1 = s0
    return s1 * s1 + s2 * s2 - coeff * s1 * s2


def band_levels(samples, rate):
    """samples(모노, 다운샘플된 float 열, rate Hz)에서 BANDS 별 dB 를 계산한다. 순수 함수라 테스트할 수 있다."""
    n = len(samples)
    if n < 32:
        return [-120.0] * len(BANDS)
    # Hann 창: 가장자리 누설을 줄인다
    win = [0.5 - 0.5 * math.cos(2 * math.pi * i / (n - 1)) for i in range(n)]
    x = [a * b for a, b in zip(samples, win)]
    out = []
    for _name, freqs, tilt in BANDS:
        p = 0.0
        for f in freqs:
            p += goertzel_power(x, 2.0 * math.cos(2.0 * math.pi * f / rate))
        amp = 2.0 * math.sqrt(max(p / len(freqs), 0.0)) / (n * 0.5)   # Hann 창 평균 0.5 보정
        out.append(20.0 * math.log10(amp + 1e-9) + tilt)
    return out


class _Agc:
    """가장 큰 대역을 기준으로 느리게 이득을 맞춰, 작은 소리의 곡도 막대가 움직이게 한다."""

    def __init__(self):
        self.peak_db = -40.0

    def normalize(self, dbs):
        top = max(dbs)
        if top > self.peak_db:
            self.peak_db = top                  # 커지면 즉시
        else:
            self.peak_db = max(-70.0, self.peak_db - 0.25)   # 작아지면 천천히(프레임당 0.25dB ≈ 10dB/초)
        floor = self.peak_db - 36.0             # 기준 최대치 아래 36dB 범위를 0~1 로 매핑
        return [max(0.0, min(1.0, (d - floor) / 36.0)) for d in dbs]


class LevelMonitor:
    def __init__(self, log=None):
        self._log = log or (lambda m: None)
        self._levels = [0.0] * len(BANDS)
        self._lock = threading.Lock()
        self._running = False
        self._thread = None
        self._last_poll = 0.0
        self.available = False       # 루프백이 실제로 열렸는가
        self.rate = 0

    # -- 외부 API ---------------------------------------------------------
    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True, name="audiolevels")
        self._thread.start()

    def stop(self):
        self._running = False

    def poll(self):
        """최근 대역 레벨(0~1)과 사용 가능 여부. 호출될 때마다 '지금 필요함'으로 표시한다."""
        self._last_poll = time.monotonic()
        with self._lock:
            return {"levels": list(self._levels), "available": self.available}

    # -- 내부 -------------------------------------------------------------
    def _set(self, levels):
        with self._lock:
            self._levels = levels

    def _run(self):
        try:
            ole32.CoInitializeEx(None, 0)   # 이 스레드는 MTA
        except Exception:
            pass
        failures = 0
        while self._running:
            try:
                self._capture_session()
                failures = 0
            except Exception as e:
                failures += 1
                if failures in (1, 5, 20):
                    self._log(f"audiolevels: capture error {e!r} (#{failures})")
            self.available = False
            self._set([0.0] * len(BANDS))
            for _ in range(20 if failures < 5 else 100):   # 재시도 간격 1초(많이 실패하면 5초)
                if not self._running:
                    return
                time.sleep(0.05)

    def _capture_session(self):
        enum = ctypes.c_void_p()
        dev = ctypes.c_void_p()
        client = ctypes.c_void_p()
        capture = ctypes.c_void_p()
        pfmt = ctypes.c_void_p()
        try:
            if ole32.CoCreateInstance(ctypes.byref(_CLSID_MMDeviceEnumerator), None, _CLSCTX_ALL,
                                      ctypes.byref(_IID_IMMDeviceEnumerator), ctypes.byref(enum)) != 0:
                raise OSError("no MMDeviceEnumerator")
            if _vcall(enum, 4, ctypes.c_long, ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_void_p))(
                    enum, 0, 1, ctypes.byref(dev)) != 0 or not dev.value:
                raise OSError("no default render device")
            dev_id = self._device_id(dev)

            if _vcall(dev, 3, ctypes.c_long, ctypes.POINTER(_GUID), ctypes.c_ulong, ctypes.c_void_p,
                      ctypes.POINTER(ctypes.c_void_p))(dev, ctypes.byref(_IID_IAudioClient), _CLSCTX_ALL, None,
                                                       ctypes.byref(client)) != 0:
                raise OSError("Activate(IAudioClient) failed")
            # IAudioClient: Initialize=3, GetMixFormat=8, Start=10, Stop=11, GetService=14
            if _vcall(client, 8, ctypes.c_long, ctypes.POINTER(ctypes.c_void_p))(client, ctypes.byref(pfmt)) != 0 or not pfmt.value:
                raise OSError("GetMixFormat failed")
            fmt = _WAVEFORMATEX.from_address(pfmt.value)
            channels, rate, bits, tag = fmt.nChannels, fmt.nSamplesPerSec, fmt.wBitsPerSample, fmt.wFormatTag
            is_float = tag == 3
            if tag == 0xFFFE and fmt.cbSize >= 22:   # WAVE_FORMAT_EXTENSIBLE: SubFormat GUID 의 Data1 이 실제 형식
                sub = ctypes.c_uint.from_address(pfmt.value + ctypes.sizeof(_WAVEFORMATEX) + 6).value
                is_float = sub == 3
            if not ((is_float and bits == 32) or (not is_float and bits == 16)):
                raise OSError(f"unsupported mix format tag={tag} bits={bits}")

            hr = _vcall(client, 3, ctypes.c_long, ctypes.c_int, ctypes.c_ulong, ctypes.c_longlong, ctypes.c_longlong,
                        ctypes.c_void_p, ctypes.c_void_p)(
                client, AUDCLNT_SHAREMODE_SHARED, AUDCLNT_STREAMFLAGS_LOOPBACK, 10_000_000, 0, pfmt, None)
            if hr != 0:
                raise OSError(f"Initialize loopback failed hr={hr & 0xffffffff:#x}")
            if _vcall(client, 14, ctypes.c_long, ctypes.POINTER(_GUID), ctypes.POINTER(ctypes.c_void_p))(
                    client, ctypes.byref(_IID_IAudioCaptureClient), ctypes.byref(capture)) != 0 or not capture.value:
                raise OSError("GetService(IAudioCaptureClient) failed")
            if _vcall(client, 10, ctypes.c_long)(client) != 0:
                raise OSError("Start failed")

            self.rate = rate
            self.available = True
            self._log(f"audiolevels: loopback open ({rate}Hz, {channels}ch, {'float32' if is_float else 'int16'})")
            self._read_loop(capture, enum, dev_id, channels, rate, is_float)
            _vcall(client, 11, ctypes.c_long)(client)   # Stop
        finally:
            if pfmt.value:
                ole32.CoTaskMemFree(pfmt)
            _release(capture)
            _release(client)
            _release(dev)
            _release(enum)

    @staticmethod
    def _device_id(dev):
        pid = ctypes.c_wchar_p()
        if _vcall(dev, 5, ctypes.c_long, ctypes.POINTER(ctypes.c_wchar_p))(dev, ctypes.byref(pid)) == 0 and pid.value:
            val = pid.value
            ole32.CoTaskMemFree(pid)
            return val
        return ""

    def _default_device_id(self, enum):
        dev = ctypes.c_void_p()
        try:
            if _vcall(enum, 4, ctypes.c_long, ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_void_p))(
                    enum, 0, 1, ctypes.byref(dev)) == 0 and dev.value:
                return self._device_id(dev)
        finally:
            _release(dev)
        return None

    def _read_loop(self, capture, enum, dev_id, channels, rate, is_float):
        # IAudioCaptureClient: GetBuffer=3, ReleaseBuffer=4, GetNextPacketSize=5
        get_size = _vcall(capture, 5, ctypes.c_long, ctypes.POINTER(ctypes.c_uint))
        get_buf = _vcall(capture, 3, ctypes.c_long, ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_uint),
                         ctypes.POINTER(ctypes.c_uint), ctypes.c_void_p, ctypes.c_void_p)
        rel_buf = _vcall(capture, 4, ctypes.c_long, ctypes.c_uint)

        decimate = max(1, int(round(rate / TARGET_RATE)))
        win_len = int(rate * WINDOW_MS / 1000 / decimate)
        ring = [0.0] * win_len           # 다운샘플된 모노 샘플의 이동 창
        agc = _Agc()
        smooth = [0.0] * len(BANDS)
        next_frame = time.monotonic()
        last_packet = time.monotonic()
        last_dev_check = time.monotonic()
        carry = []                        # decimate 로 나누어떨어지지 않은 나머지 샘플
        eff_rate = rate / decimate

        while self._running:
            n = ctypes.c_uint()
            hr = get_size(capture, ctypes.byref(n))
            if hr != 0:
                raise OSError(f"GetNextPacketSize hr={hr & 0xffffffff:#x}")   # 장치 무효화 등 -> 재연결

            while n.value:
                data = ctypes.c_void_p()
                frames = ctypes.c_uint()
                flags = ctypes.c_uint()
                if get_buf(capture, ctypes.byref(data), ctypes.byref(frames), ctypes.byref(flags), None, None) != 0:
                    raise OSError("GetBuffer failed")
                nf = frames.value
                if nf:
                    last_packet = time.monotonic()
                    if self._needed() and not (flags.value & AUDCLNT_BUFFERFLAGS_SILENT):
                        raw = ctypes.string_at(data.value, nf * channels * (4 if is_float else 2))
                        mono = self._to_mono(raw, nf, channels, is_float)
                        mono = carry + mono
                        k = len(mono) // decimate * decimate
                        carry = mono[k:]
                        if k:
                            dec = [sum(mono[i:i + decimate]) / decimate for i in range(0, k, decimate)]
                            ring = (ring + dec)[-win_len:]
                rel_buf(capture, nf)
                if get_size(capture, ctypes.byref(n)) != 0:
                    raise OSError("GetNextPacketSize failed")

            now = time.monotonic()
            if now >= next_frame:
                next_frame = now + FRAME_INTERVAL
                if self._needed():
                    silent = (now - last_packet) > 0.12      # 재생이 없으면 패킷이 오지 않는다
                    if silent:
                        target = [0.0] * len(BANDS)
                        ring = [0.0] * win_len
                    else:
                        target = agc.normalize(band_levels(ring, eff_rate))
                    for i, t in enumerate(target):           # 빠르게 오르고 천천히 내려간다
                        smooth[i] += (t - smooth[i]) * (0.65 if t > smooth[i] else 0.22)
                    self._set([round(v, 3) for v in smooth])
                else:
                    smooth = [0.0] * len(BANDS)
            if now - last_dev_check > 2.0:                   # 기본 장치가 바뀌었으면 새로 연결
                last_dev_check = now
                cur = self._default_device_id(enum)
                if cur is not None and dev_id and cur != dev_id:
                    self._log("audiolevels: default device changed, reopening")
                    return
            time.sleep(0.008)

    def _needed(self):
        return (time.monotonic() - self._last_poll) < IDLE_AFTER

    @staticmethod
    def _to_mono(raw, nf, channels, is_float):
        total = nf * channels
        vals = struct.unpack(f"<{total}{'f' if is_float else 'h'}", raw)
        scale = 1.0 if is_float else 1.0 / 32768.0
        if channels == 1:
            return [v * scale for v in vals]
        return [sum(vals[i:i + channels]) * scale / channels for i in range(0, total, channels)]
