# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Flirty_BananaMilk — 상업적 이용 금지, 자세한 내용은 LICENSE
"""알림음: 소리를 직접 합성해서(외부 파일 없음) 메모리에서 재생한다.

예전에는 winsound.Beep(PC 스피커 삑 소리)라서 한 음이 0.1초 남짓이고 음량을 바꿀 수 없었다. 이제는 종류(차임/벨/마림바/부드럽게),
길이(짧게/보통/길게), 음량(윈도우 음량과 별개로 소리 자체의 크기)을 설정으로 고른다. 각 알림(집중·물·할 일)은 서로 다른 가락을 가진다.
"""
import array
import io
import math
import struct
import wave

RATE = 44100
TYPES = ("chime", "bell", "marimba", "soft")
LENGTHS = {"short": 0.7, "normal": 1.0, "long": 1.7}
DEFAULT_TYPE, DEFAULT_LENGTH, DEFAULT_VOLUME = "chime", "normal", 70

# 가락: (주파수 Hz, 시작 시각 초). 집중/휴식 끝은 오르는 아르페지오, 물은 물방울처럼 내려오는 두 음, 할 일은 가볍게 두 번.
MELODIES = {
    "pomo": [(784, 0.00), (1047, 0.16), (1319, 0.32), (1568, 0.52)],
    "water": [(988, 0.00), (740, 0.22)],
    "todo": [(1175, 0.00), (1568, 0.17)],
}

# 음색: (배음 비율, 상대 크기, 감쇠 계수) 목록. 감쇠는 길이 배율(LENGTHS)에 비례해서 길어진다.
TIMBRES = {
    "chime": {"partials": [(1.0, 1.0, 1.0), (2.0, 0.32, 0.7), (3.01, 0.12, 0.45)], "decay": 0.34, "attack": 0.004, "echo": None},
    "bell": {"partials": [(1.0, 1.0, 1.0), (2.76, 0.5, 0.8), (5.4, 0.28, 0.55), (8.93, 0.14, 0.4)], "decay": 0.5, "attack": 0.002, "echo": None},
    "marimba": {"partials": [(1.0, 1.0, 1.0), (4.0, 0.34, 0.35), (9.2, 0.08, 0.15)], "decay": 0.21, "attack": 0.002, "echo": None},
    "soft": {"partials": [(1.0, 1.0, 1.0), (2.0, 0.1, 0.6)], "decay": 0.3, "attack": 0.02, "echo": (0.19, 0.38)},
}

_cache = {}


def normalize(sound_type, length, volume):
    t = sound_type if sound_type in TYPES else DEFAULT_TYPE
    ln = length if length in LENGTHS else DEFAULT_LENGTH
    try:
        v = max(0, min(100, int(volume)))
    except (TypeError, ValueError):
        v = DEFAULT_VOLUME
    return t, ln, v


def synth(kind, sound_type=DEFAULT_TYPE, length=DEFAULT_LENGTH, volume=DEFAULT_VOLUME):
    """PCM16 모노 샘플 배열(array('h')). 각 배음은 감쇠하는 사인파를 점화식(y[n] = 2r cos(w) y[n-1] - r^2 y[n-2])으로 만들어 빠르다."""
    t, ln, v = normalize(sound_type, length, volume)
    tim = TIMBRES[t]
    mult = LENGTHS[ln]
    notes = MELODIES.get(kind) or MELODIES["pomo"]
    decay = tim["decay"] * mult
    tail = decay * 3.0 + 0.1                                      # 마지막 음이 거의(-26 dB) 사라질 때까지
    echo = tim["echo"]
    total = max(n[1] for n in notes) + tail + (echo[0] if echo else 0.0)
    n_samples = int(total * RATE)
    buf = [0.0] * n_samples
    att_n = max(1, int(tim["attack"] * 5 * RATE))
    att = [1.0 - math.exp(-(i / RATE) / tim["attack"]) for i in range(att_n)]
    for freq, start in notes:
        i0 = int(start * RATE)
        n_len = min(n_samples - i0, int((decay * 3.6 + 0.05) * RATE))
        for ratio, amp, dk in tim["partials"]:
            f = freq * ratio
            if f > RATE / 2.2:
                continue
            w = 2.0 * math.pi * f / RATE
            r = math.exp(-1.0 / (decay * dk * RATE))
            c1, c2 = 2.0 * r * math.cos(w), r * r
            y2, y1 = 0.0, r * math.sin(w)
            base = i0
            buf[base] += 0.0
            for i in range(1, n_len):
                a_ = att[i] if i < att_n else 1.0
                buf[base + i] += amp * y1 * a_
                y2, y1 = y1, c1 * y1 - c2 * y2
    if echo:
        delay = int(echo[0] * RATE)
        for i in range(n_samples - 1, delay - 1, -1):
            buf[i] += buf[i - delay] * echo[1]
    peak = max(abs(x) for x in buf) or 1.0
    gain = (v / 100.0) * 0.92 / peak                              # 음량 100% = 거의 꽉 찬 크기
    out = array.array("h")
    norm = math.tanh(1.25)
    for x in buf:
        sample = math.tanh(x * gain * 1.25) / norm if gain else 0.0     # 부드러운 리미터(튀는 소리 방지)
        out.append(int(max(-1.0, min(1.0, sample)) * 32767))
    fade = min(len(out), int(0.03 * RATE))                        # 끝은 0 으로 부드럽게 닫는다
    for i in range(fade):
        out[len(out) - 1 - i] = int(out[len(out) - 1 - i] * (i / fade))
    return out


def wav_bytes(kind, sound_type=DEFAULT_TYPE, length=DEFAULT_LENGTH, volume=DEFAULT_VOLUME):
    """재생할 수 있는 WAV 파일 내용(메모리). 같은 설정은 한 번만 만들고 다시 쓴다."""
    key = (kind if kind in MELODIES else "pomo",) + normalize(sound_type, length, volume)
    hit = _cache.get(key)
    if hit is not None:
        return hit
    pcm = synth(*key)
    bio = io.BytesIO()
    with wave.open(bio, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(pcm.tobytes() if struct.pack("=h", 1) == b"\x01\x00" else bytes(pcm))
    data = bio.getvalue()
    if len(_cache) > 40:
        _cache.clear()
    _cache[key] = data
    return data


CUSTOM_MAX_BYTES = 10 * 1024 * 1024
CUSTOM_MAX_SECONDS = 30


def custom_info(path):
    """내 알림음 파일 검사: {'ok': True, 'seconds': 초} 또는 {'ok': False, 'why': 이유}. .wav(PCM) 만, 10MB / 30초까지."""
    import os
    try:
        if not path or not os.path.isfile(path):
            return {"ok": False, "why": "missing"}
        if not path.lower().endswith(".wav"):
            return {"ok": False, "why": "not a .wav file"}
        if os.path.getsize(path) > CUSTOM_MAX_BYTES:
            return {"ok": False, "why": "too large"}
        with wave.open(path, "rb") as w:
            sec = w.getnframes() / float(w.getframerate() or 1)
            if sec > CUSTOM_MAX_SECONDS:
                return {"ok": False, "why": "too long"}
            return {"ok": True, "seconds": sec}
    except Exception as e:
        return {"ok": False, "why": repr(e)}


def custom_bytes(path, volume=DEFAULT_VOLUME):
    """내 파일을 재생용 WAV 로. 16비트·8비트 PCM 은 음량(0~100%)만큼 소리를 줄여 준다(100% 는 원래 크기). 그 밖의 형식은 그대로 쓴다."""
    import os
    v = max(0, min(100, int(volume)))
    key = ("custom", path, os.path.getmtime(path), v)
    hit = _cache.get(key)
    if hit is not None:
        return hit
    raw = open(path, "rb").read()
    out = raw
    try:
        with wave.open(io.BytesIO(raw), "rb") as w:
            params = w.getparams()
            frames = w.readframes(w.getnframes())
        if v < 100 and params.comptype == "NONE" and params.sampwidth in (1, 2):
            g = v / 100.0
            if params.sampwidth == 2:
                a = array.array("h"); a.frombytes(frames)
                a = array.array("h", [int(x * g) for x in a])
                frames = a.tobytes()
            else:      # 8비트는 128 이 무음
                frames = bytes(int(128 + (b - 128) * g) for b in frames)
            bio = io.BytesIO()
            with wave.open(bio, "wb") as o:
                o.setparams(params)
                o.writeframes(frames)
            out = bio.getvalue()
    except Exception:
        out = raw
    if len(_cache) > 40:
        _cache.clear()
    _cache[key] = out
    return out


def play_custom(path, volume=DEFAULT_VOLUME):
    """내 파일을 재생한다(소리가 끝날 때까지 막힘 — 스레드에서 부른다). 검사에 실패하면 예외."""
    import winsound
    info = custom_info(path)
    if not info["ok"]:
        raise ValueError(info["why"])
    winsound.PlaySound(custom_bytes(path, volume), winsound.SND_MEMORY)


def play(kind, sound_type=DEFAULT_TYPE, length=DEFAULT_LENGTH, volume=DEFAULT_VOLUME):
    """메모리에서 재생한다. winsound 는 메모리 재생을 비동기로 못 하므로 소리가 끝날 때까지 이 호출이 막힌다 — 부르는 쪽이 스레드에서 부른다.
    실패하면 예외를 그대로 올린다(부르는 쪽이 옛 삑 소리로 대신한다)."""
    import winsound
    data = wav_bytes(kind, sound_type, length, volume)
    winsound.PlaySound(data, winsound.SND_MEMORY)
    return data
