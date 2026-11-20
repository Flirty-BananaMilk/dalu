"""내 위치(윈도우 위치 서비스)를 한 번 읽는다. 날씨 탭이 '현재 위치의 날씨'를 보여 줄 때만 쓴다.

개인정보
- 설정 › 날씨 › "내 위치의 날씨 보기"가 켜져 있고, 날씨를 실제로 보여 줄 때(탭을 열거나 작은 노치에 띄울 때)만 읽는다.
- 위치는 이 프로그램 메모리에만 두고 디스크에 저장하지 않으며 기록(log)에도 남기지 않는다. 서버로는 날씨를 받으려고 **소수 둘째 자리(약 1km)로 줄인 좌표**만 나간다(weather.py).
- 윈도우 설정 › 개인 정보 및 보안 › 위치 에서 위치 서비스와 '데스크톱 앱이 위치에 액세스하도록 허용'이 켜져 있어야 한다. 꺼져 있으면 status 가 'denied' 이다.
- winrt-Windows.Devices.Geolocation 이 없으면 'unavailable' (날씨는 고른 도시로 동작한다).
"""
import threading
import time

TTL_SECONDS = 10 * 60          # 위치는 자주 바뀌지 않으니 10분 동안 다시 읽지 않는다(노트북을 들고 다녀도 충분)
TIMEOUT_SECONDS = 12


def _read_position():
    """winrt 로 위치를 한 번 읽는다 -> ('ok', lat, lon, accuracy_m) / ('denied',) / ('unavailable',) / ('timeout',) / ('error',)"""
    try:
        import asyncio
        from winrt.windows.devices.geolocation import GeolocationAccessStatus, Geolocator, PositionAccuracy
    except Exception:
        return ("unavailable",)

    async def go():
        try:
            access = await asyncio.wait_for(Geolocator.request_access_async(), TIMEOUT_SECONDS)          # 권한 창이 응답하지 않아도 영원히 기다리지 않는다
        except Exception:
            access = None
        if access is not None and access != GeolocationAccessStatus.ALLOWED:
            return ("denied",)
        g = Geolocator()
        g.desired_accuracy = PositionAccuracy.DEFAULT
        try:
            pos = await asyncio.wait_for(g.get_geoposition_async(), TIMEOUT_SECONDS)
        except asyncio.TimeoutError:
            return ("timeout",)
        except Exception as e:
            # 0x80070005 = 액세스 거부 (위치 서비스가 꺼져 있을 때)
            return ("denied",) if "0x80070005" in str(e) or "denied" in str(e).lower() else ("error",)
        p = pos.coordinate.point.position
        return ("ok", float(p.latitude), float(p.longitude), float(pos.coordinate.accuracy or 0))

    try:
        return asyncio.run(go())
    except Exception:
        return ("error",)


class Locator:
    """위치를 10분 동안 기억한다(메모리에만). reader 는 시험용으로 바꿀 수 있다."""

    def __init__(self, reader=_read_position, clock=time.time, ttl=TTL_SECONDS):
        self._reader, self._clock, self._ttl = reader, clock, ttl
        self._lock = threading.Lock()
        self._val = None
        self._at = 0.0

    def get(self, force=False):
        """-> {'status': 'ok'|'denied'|'unavailable'|'timeout'|'error', 'lat', 'lon', 'acc'}  (ok 일 때만 좌표)"""
        with self._lock:
            if not force and self._val is not None and self._val.get("status") == "ok" and self._clock() - self._at < self._ttl:
                return dict(self._val)
        r = self._reader()
        if r and r[0] == "ok":
            out = {"status": "ok", "lat": r[1], "lon": r[2], "acc": r[3]}
        else:
            out = {"status": (r[0] if r else "error")}
        with self._lock:
            if out["status"] == "ok":
                self._val, self._at = out, self._clock()
            elif out["status"] in ("denied", "unavailable"):
                self._val = None          # 권한이 거부되면 예전에 읽은 좌표를 계속 내주지 않는다
            elif out["status"] in ("timeout", "error") and self._val is not None and self._clock() - self._at < self._ttl * 6:
                # 잠깐 못 읽었을 뿐이면 한 시간쯤은 마지막으로 알던 위치를 쓴다(거부·미지원이면 그대로 알린다)
                return dict(self._val)
        return out
