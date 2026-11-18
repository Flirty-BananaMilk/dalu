"""날씨 탭 / 작은 노치용: Open-Meteo(무료, 계정·키 없음)에서 현재 날씨와 3일 예보를 읽고, 미세먼지는 가능하면 실제 측정소 값(한국: 에어코리아)으로 보여 준다.

개인정보
- 날씨를 받는 것은 (a) 설정 › 날씨 › "내 위치의 날씨 보기"가 켜져 있어 윈도우 위치 서비스(geoloc.py)로 현재 위치를 읽었을 때, 또는 (b) 사용자가 도시를 직접 골랐을 때뿐이다.
  둘 다 아니면 아무것도 보내지 않는다(dalu.py 가 확인한다).
- 서버로 나가는 것은 **위도·경도(소수 둘째 자리로 반올림, 약 1km)** 와 단위 설정뿐이다. 이름·계정을 따로 보내지 않는다(서버는 요청의 IP 를 볼 수 있다).
- 현재 위치의 이름(예: 성남시)과 시·도를 알려고 같은 반올림 좌표를 api.bigdatacloud.net(무료, 키 없음)에 보낸다.
- 에어코리아 인증키(공공데이터포털에서 무료로 받는 키)를 사용자가 직접 넣은 경우에만 apis.data.go.kr 에 시·도 이름과 가까운 측정소 이름을 보내 실제 미세먼지를 받는다. 키는 기록하지 않는다.
- OpenAQ API 키(explore.openaq.org 에서 무료로 받는 키, 전 세계 측정소)를 사용자가 직접 넣은 경우에만 api.openaq.org 에 반올림한 좌표와 반경(25km)을 보내 가까운 측정소의 실제 미세먼지를 받는다. 키는 기록하지 않는다.
- 도시 검색(search_city)은 설정 창에서 사용자가 '검색'을 눌렀을 때만, 입력한 도시 이름을 geocoding-api.open-meteo.com 으로 보낸다.
"""
import json
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

GEO_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
AIR_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
REVERSE_URL = "https://api.bigdatacloud.net/data/reverse-geocode-client"
AIRKOREA_BASE = "https://apis.data.go.kr/B552584"
OPENAQ_BASE = "https://api.openaq.org/v3"
ALLOWED_HOSTS = ("geocoding-api.open-meteo.com", "api.open-meteo.com", "air-quality-api.open-meteo.com", "api.bigdatacloud.net", "apis.data.go.kr", "api.openaq.org")
MAX_BYTES = 200_000
TTL_SECONDS = 15 * 60

# WMO 날씨 코드 -> (조건 키, 아이콘). 조건 키는 화면 문구(wx_<키>)로 바뀐다.
_WMO = {0: ("clear", "sun"), 1: ("clear", "sun"), 2: ("partly", "cloudsun"), 3: ("cloudy", "cloud"), 45: ("fog", "fog"), 48: ("fog", "fog"),
        51: ("drizzle", "rain"), 53: ("drizzle", "rain"), 55: ("drizzle", "rain"), 56: ("drizzle", "rain"), 57: ("drizzle", "rain"),
        61: ("rain", "rain"), 63: ("rain", "rain"), 65: ("rain", "rain"), 66: ("rain", "rain"), 67: ("rain", "rain"),
        71: ("snow", "snow"), 73: ("snow", "snow"), 75: ("snow", "snow"), 77: ("snow", "snow"),
        80: ("rain", "rain"), 81: ("rain", "rain"), 82: ("rain", "rain"), 85: ("snow", "snow"), 86: ("snow", "snow"),
        95: ("thunder", "bolt"), 96: ("thunder", "bolt"), 99: ("thunder", "bolt")}


def describe(code, is_day=True):
    """WMO 코드 -> (조건 키, 아이콘 이름). 모르는 코드는 흐림. 맑은 밤은 달 대신 같은 해 아이콘을 쓴다(아이콘 세트에 달이 있으면 moon)."""
    key, icon = _WMO.get(int(code) if isinstance(code, (int, float)) else -1, ("cloudy", "cloud"))
    if key == "clear" and not is_day:
        icon = "moon"
    return key, icon


def clean_coords(lat, lon):
    """위도·경도를 검증하고 소수 둘째 자리로 줄인다. 이상하면 None."""
    try:
        la, lo = float(lat), float(lon)
    except (TypeError, ValueError):
        return None
    if not (-90.0 <= la <= 90.0 and -180.0 <= lo <= 180.0) or (la == 0.0 and lo == 0.0):
        return None
    return round(la, 2), round(lo, 2)


class ApiRejected(Exception):
    """서버가 요청을 거절했다(인증키가 틀림·등록 안 됨·권한 없음)."""


_REJECT_MARKS = ("SERVICE_KEY", "SERVICE KEY", "SERVICE ACCESS DENIED", "UNREGISTERED", "NOT_REGISTERED", "LIMITED_NUMBER_OF_SERVICE_REQUESTS")


def _get_json(url, opener=None, timeout=8, headers=None):
    """허용된 호스트의 HTTPS 만, 크기 제한을 두고 JSON 으로 읽는다. JSON 이 아닌 거절 응답(공공데이터포털은 XML 로 답한다)과 HTTP 401/403 은 ApiRejected."""
    p = urllib.parse.urlsplit(url)
    if p.scheme != "https" or p.hostname not in ALLOWED_HOSTS:
        raise ValueError("host not allowed")
    h = {"User-Agent": "Dalu", "Accept": "application/json"}
    h.update(headers or {})
    req = urllib.request.Request(url, headers=h)
    try:
        with (opener or urllib.request.urlopen)(req, timeout=timeout) as r:
            raw = r.read(MAX_BYTES + 1)
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            raise ApiRejected("rejected")
        raise
    if len(raw) > MAX_BYTES:
        raise ValueError("response too large")
    text = raw.decode("utf-8", "replace")
    try:
        return json.loads(text)
    except ValueError:
        if any(m in text.upper() for m in _REJECT_MARKS):
            raise ApiRejected("rejected")
        raise


_ADMIN_SUFFIX = re.compile(r"(특별자치시|특별자치도|특별시|광역시|자치시|자치도|시|군|구|도)$")


_HANGUL = re.compile(r"[가-힣]")
_KO_SUFFIXES = ("특별시", "광역시", "시", "군", "도")


def city_variants(query):
    """검색어 후보: 입력 그대로, 한국어 행정 구역 접미사('서울특별시' -> '서울')를 뗀 것, 맨 앞 단어만 남긴 것.
    한국어 이름은 서비스가 접미사 없이는 못 찾는 경우가 많아('서울' -> 없음, '서울특별시' -> 있음) 접미사를 붙인 후보도 뒤에 둔다."""
    q = " ".join(str(query or "").split())[:60]
    out = [q]
    stripped = _ADMIN_SUFFIX.sub("", q).strip()
    if len(stripped) >= 2 and stripped != q:
        out.append(stripped)
    first = q.split(" ")[0] if " " in q else ""
    if len(first) >= 2 and first not in out:
        out.append(first)
    base = stripped if len(stripped) >= 2 else q
    if _HANGUL.search(base) and not _ADMIN_SUFFIX.search(base):
        out = [base + "특별시", base + "광역시"] + out + [base + suf for suf in _KO_SUFFIXES[2:]]        # '부산' -> 부산광역시 가 작은 동네 '부산' 보다 앞에 오게
    seen, uniq = set(), []
    for v in out:
        if len(v) >= 2 and v not in seen:
            seen.add(v)
            uniq.append(v)
    return uniq


def city_label(name, admin, country):
    """'서울특별시, 서울특별시' 같은 중복 없이: 이름 + (이름과 다르고 이름에 들어 있지 않은 상위 지역) + 나라."""
    parts = [str(name or "").strip()]
    a = str(admin or "").strip()
    if a and a != parts[0] and a not in parts[0] and parts[0] not in a:
        parts.append(a)
    c = str(country or "").strip()
    if c and c not in parts:
        parts.append(c)
    return ", ".join(p for p in parts if p)


def _geo_query(name, lang, opener):
    """한 번의 지오코딩 요청 -> 정리된 후보 목록(실패하면 [])."""
    url = GEO_URL + "?" + urllib.parse.urlencode({"name": name, "count": 8, "language": lang, "format": "json"})
    try:
        data = _get_json(url, opener)
    except Exception:
        return []
    out, seen = [], set()
    for r in (data.get("results") or []) if isinstance(data, dict) else []:
        c = clean_coords(r.get("latitude"), r.get("longitude"))
        if not c or not r.get("name") or c in seen:
            continue
        seen.add(c)
        out.append({"name": str(r["name"])[:60], "admin": str(r.get("admin1") or "")[:60], "country": str(r.get("country") or "")[:60],
                    "label": city_label(r["name"], r.get("admin1"), r.get("country"))[:120], "lat": c[0], "lon": c[1]})
    return out


def search_city(query, language="en", opener=None):
    """도시 이름으로 후보를 찾는다: [{'name','admin','country','label','lat','lon'}] 최대 6개. 실패하면 [].
    후보 검색어(city_variants)를 동시에 보내고(느리지 않게), 결과가 없으면 영어로도 찾는다.
    접미사 없는 한국어 이름은 '특별시/광역시' 후보의 결과를 앞에 모아서 보여 준다('부산' -> 부산광역시 가 작은 동네보다 먼저)."""
    from concurrent.futures import ThreadPoolExecutor
    variants = city_variants(query)
    if not variants:
        return []
    lang = language if language in ("ko", "en", "zh", "ja") else "en"
    jobs = [(v, lg) for v in variants for lg in ([lang] if (lang == "en" or _HANGUL.search(v)) else [lang, "en"])]
    with ThreadPoolExecutor(max_workers=min(6, len(jobs))) as ex:
        results = list(ex.map(lambda j: _geo_query(j[0], j[1], opener), jobs))
    merge_all = bool(_HANGUL.search(variants[0])) and any(v in ("특별시", "광역시") or v.endswith(("특별시", "광역시")) for v in variants[:2])
    out, seen = [], set()
    for res in results:
        if not res:
            continue
        for r in res:
            if (r["lat"], r["lon"]) not in seen:
                seen.add((r["lat"], r["lon"]))
                out.append(r)
        if not merge_all:
            break
    return out[:6]


def parse_forecast(data):
    """Open-Meteo 응답 -> 화면용 값. 모양이 이상하면 None."""
    try:
        cur = data["current"]
        daily = data["daily"]
        days = []
        for i, d in enumerate(daily["time"][:3]):
            key, icon = describe(daily["weather_code"][i])
            days.append({"date": str(d), "hi": round(daily["temperature_2m_max"][i]), "lo": round(daily["temperature_2m_min"][i]),
                         "pop": (daily.get("precipitation_probability_max") or [None] * 3)[i], "key": key, "icon": icon})
        is_day = bool(cur.get("is_day", 1))
        key, icon = describe(cur["weather_code"], is_day)
        feels = cur.get("apparent_temperature")
        return {"temp": round(cur["temperature_2m"]), "feels": round(feels if feels is not None else cur["temperature_2m"]),          # 값이 null 로 오면 기온으로 대신한다
                "humidity": int(cur.get("relative_humidity_2m") or 0), "wind": round(float(cur.get("wind_speed_10m") or 0), 1),
                "key": key, "icon": icon, "isDay": is_day, "days": days}
    except (KeyError, TypeError, ValueError, IndexError):
        return None


def air_grades(pm25, pm10):
    """한국 환경부 기준 4단계: 1 좋음 / 2 보통 / 3 나쁨 / 4 매우 나쁨. PM2.5 는 15·35·75, PM10 은 30·80·150 마이크로그램 기준."""
    def g(v, cuts):
        if v is None:
            return None
        return 1 + sum(1 for c in cuts if v > c)
    g25, g10 = g(pm25, (15, 35, 75)), g(pm10, (30, 80, 150))
    known = [x for x in (g25, g10) if x is not None]
    return {"g25": g25, "g10": g10, "grade": max(known) if known else None}


def parse_air(data):
    """대기질 응답 -> {'pm25','pm10','g25','g10','grade'}. 모양이 이상하면 None."""
    try:
        cur = data["current"]
        pm25 = cur.get("pm2_5")
        pm10 = cur.get("pm10")
        pm25 = None if pm25 is None else round(float(pm25))
        pm10 = None if pm10 is None else round(float(pm10))
        if pm25 is None and pm10 is None:
            return None
        out = {"pm25": pm25, "pm10": pm10, "source": "model"}
        out.update(air_grades(pm25, pm10))
        return out
    except (KeyError, TypeError, ValueError):
        return None


def fetch_air(lat, lon, opener=None):
    """미세먼지(PM2.5·PM10). 좌표는 날씨와 같이 소수 둘째 자리. 모델 값(관측소 값이 아님)이다. 실패하면 None."""
    c = clean_coords(lat, lon)
    if not c:
        return None
    q = {"latitude": c[0], "longitude": c[1], "timezone": "auto", "current": "pm2_5,pm10"}
    try:
        return parse_air(_get_json(AIR_URL + "?" + urllib.parse.urlencode(q), opener))
    except Exception:
        return None


# ---------------------------------------------------------------------------------------------------------------
# 현재 위치의 이름·시도, 그리고 실제 측정소 미세먼지(에어코리아)
# ---------------------------------------------------------------------------------------------------------------
_SIDO = [("서울", "서울"), ("부산", "부산"), ("대구", "대구"), ("인천", "인천"), ("광주", "광주"), ("대전", "대전"), ("울산", "울산"), ("세종", "세종"),
         ("경기", "경기"), ("강원", "강원"), ("충청북", "충북"), ("충북", "충북"), ("충청남", "충남"), ("충남", "충남"), ("전북", "전북"), ("전라북", "전북"),
         ("전라남", "전남"), ("전남", "전남"), ("경상북", "경북"), ("경북", "경북"), ("경상남", "경남"), ("경남", "경남"), ("제주", "제주")]


def sido_key(subdivision):
    """한국어 시·도 이름('경기도', '서울특별시', '전북특별자치도') -> 에어코리아 주소 키('경기', '서울', '전북'). 모르면 None."""
    n = str(subdivision or "").strip()
    for prefix, key in _SIDO:
        if n.startswith(prefix):
            return key
    return None


def in_korea(lat, lon):
    return 33.0 <= lat <= 38.9 and 124.5 <= lon <= 132.0


_reverse_cache = {}


def reverse_place(lat, lon, lang="ko", opener=None):
    """좌표 -> {'label': '성남시, 경기도, 대한민국', 'sido': '경기'(한국일 때만)}. 같은 좌표는 한 번만 묻는다. 실패하면 None."""
    c = clean_coords(lat, lon)
    if not c:
        return None
    lg = lang if lang in ("ko", "en", "zh", "ja") else "en"
    key = (c, lg)
    if key in _reverse_cache:
        return _reverse_cache[key]
    url = REVERSE_URL + "?" + urllib.parse.urlencode({"latitude": c[0], "longitude": c[1], "localityLanguage": lg})
    try:
        d = _get_json(url, opener)
    except Exception:
        return None
    if not isinstance(d, dict):
        return None
    name = str(d.get("city") or d.get("locality") or "").strip()
    sub = str(d.get("principalSubdivision") or "").strip()
    country = str(d.get("countryName") or "").strip()
    if not (name or sub or country):
        return None
    out = {"label": city_label(name or sub, sub if name else "", country)[:120], "sido": None}
    if (d.get("countryCode") or "").upper() == "KR":
        if lg == "ko":
            out["sido"] = sido_key(sub)
        else:
            ko = reverse_place(c[0], c[1], "ko", opener)
            out["sido"] = ko and ko.get("sido")
    if len(_reverse_cache) > 50:
        _reverse_cache.clear()
    _reverse_cache[key] = out
    return out


def _service_key(key):
    """공공데이터포털 키는 '인코딩'·'디코딩' 두 가지로 나온다. 인코딩 키(% 가 들어 있음)는 먼저 풀어서 두 번 인코딩되지 않게 한다."""
    k = str(key or "").strip()
    return urllib.parse.unquote(k) if "%" in k else k


_station_cache = {}


def air_stations(key, sido, opener=None):
    """에어코리아 측정소 목록(시·도 단위): [{'name','lat','lon'}]. 하루 동안 기억한다. 실패하면 []. 키가 거절되면 ApiRejected."""
    ck = (sido,)
    hit = _station_cache.get(ck)
    if hit and time.time() - hit[0] < 24 * 3600:
        return hit[1]
    q = {"serviceKey": _service_key(key), "returnType": "json", "numOfRows": 300, "pageNo": 1, "addr": sido}
    data = _get_json(AIRKOREA_BASE + "/MsrstnInfoInqireSvc/getMsrstnList?" + urllib.parse.urlencode(q), opener)
    items = (((data or {}).get("response") or {}).get("body") or {}).get("items") or []
    out = []
    for it in items if isinstance(items, list) else []:
        try:
            a, b = float(it.get("dmX")), float(it.get("dmY"))
        except (TypeError, ValueError):
            continue
        la, lo = (a, b) if 30 <= a <= 40 else (b, a)          # dmX 가 위도, dmY 가 경도지만 순서가 바뀌어 와도 범위로 바로잡는다
        name = str(it.get("stationName") or "").strip()
        if name and in_korea(la, lo):
            out.append({"name": name, "lat": la, "lon": lo})
    if out:
        _station_cache[ck] = (time.time(), out)
    return out


def nearest_stations(lat, lon, stations, n=3, max_km=40.0):
    """가까운 측정소 n 곳(max_km 이내)."""
    import math

    def km(s):
        dy = (s["lat"] - lat) * 111.0
        dx = (s["lon"] - lon) * 111.0 * math.cos(math.radians(lat))
        return math.hypot(dx, dy)
    ranked = sorted(((km(s), s) for s in stations), key=lambda t: t[0])
    return [s for d, s in ranked[:n] if d <= max_km]


def _num(v):
    try:
        f = float(str(v).strip())
        return None if f != f or f < 0 else int(round(f))
    except (TypeError, ValueError):
        return None          # '-' (점검·교정 중) 등


def air_reading(key, station, opener=None):
    """측정소의 가장 최근 실측값 -> {'pm25','pm10','time'} 또는 None(값이 없을 때)."""
    q = {"serviceKey": _service_key(key), "returnType": "json", "numOfRows": 3, "pageNo": 1, "stationName": station, "dataTerm": "DAILY", "ver": "1.3"}
    data = _get_json(AIRKOREA_BASE + "/ArpltnInforInqireSvc/getMsrstnAcctoRltmMesureDnsty?" + urllib.parse.urlencode(q), opener)
    items = (((data or {}).get("response") or {}).get("body") or {}).get("items") or []
    for it in items if isinstance(items, list) else []:
        p25, p10 = _num(it.get("pm25Value")), _num(it.get("pm10Value"))
        if p25 is not None or p10 is not None:
            return {"pm25": p25, "pm10": p10, "time": str(it.get("dataTime") or "")[:16]}
    return None


def fetch_air_station(lat, lon, key, opener=None):
    """한국 안에서 가까운 에어코리아 측정소의 실제 미세먼지 -> {'pm25','pm10','g25','g10','grade','source':'station','station','time'}.
    값을 못 얻으면 None, 인증키가 거절되면 ApiRejected."""
    c = clean_coords(lat, lon)
    if not c or not key or not in_korea(c[0], c[1]):
        return None
    place = reverse_place(c[0], c[1], "ko", opener)
    sido = place and place.get("sido")
    if not sido:
        return None
    try:
        stations = air_stations(key, sido, opener)
    except ApiRejected:
        raise
    except Exception:
        return None
    for st in nearest_stations(c[0], c[1], stations):
        try:
            r = air_reading(key, st["name"], opener)
        except ApiRejected:
            raise
        except Exception:
            continue
        if r:
            out = {"pm25": r["pm25"], "pm10": r["pm10"], "source": "station", "station": st["name"], "time": r["time"]}
            out.update(air_grades(r["pm25"], r["pm10"]))
            return out
    return None


def _km(lat1, lon1, lat2, lon2):
    import math
    dy = (lat2 - lat1) * 111.0
    dx = (lon2 - lon1) * 111.0 * math.cos(math.radians(lat1))
    return math.hypot(dx, dy)


_UG = ("µg", "ug", "μg")          # 마이크로그램(µ 기호가 두 가지로 쓰인다)


def _openaq_reading(latest, sensors, now=None):
    """OpenAQ /locations/{id}/latest 의 results + 그 측정소의 sensors -> {'pm25','pm10','time'} 또는 None(6시간 안의 PM2.5·PM10 µg/m³ 값이 없을 때)."""
    import datetime as _dt
    now = now or time.time()
    kind = {}
    for s in sensors or []:
        par = (s or {}).get("parameter") or {}
        name, units = str(par.get("name") or "").lower(), str(par.get("units") or "").lower()
        if name in ("pm25", "pm10") and any(units.startswith(u) for u in _UG):
            kind[s.get("id")] = name
    best = {}
    stamp = ""
    for r in latest or []:
        k = kind.get((r or {}).get("sensorsId"))
        v = (r or {}).get("value")
        if not k or not isinstance(v, (int, float)) or v != v or v < 0:
            continue
        dt = ((r.get("datetime") or {}).get("utc") or "")
        try:
            ts = _dt.datetime.fromisoformat(dt.replace("Z", "+00:00")).timestamp()
        except ValueError:
            continue
        if now - ts > 6 * 3600 or ts - now > 3600:
            continue
        if k not in best or ts > best[k][1]:
            best[k] = (int(round(v)), ts)
            if k == "pm25":
                stamp = str((r.get("datetime") or {}).get("local") or dt)
    if not best:
        return None
    return {"pm25": best.get("pm25", (None,))[0], "pm10": best.get("pm10", (None,))[0], "time": stamp[11:16] if len(stamp) >= 16 else ""}


def fetch_air_openaq(lat, lon, key, opener=None):
    """전 세계 측정소(OpenAQ) 중 25km 안에서 가장 가까운 곳의 실제 PM2.5·PM10 -> {'pm25','pm10','g25','g10','grade','source':'station','provider':'OpenAQ','station','time'}.
    값을 못 얻으면 None, 키가 거절되면 ApiRejected. 요청은 반올림한 좌표만 보낸다."""
    c = clean_coords(lat, lon)
    k = str(key or "").strip()
    if not c or not k:
        return None
    hdr = {"X-API-Key": k}
    q = {"coordinates": f"{c[0]},{c[1]}", "radius": 25000, "limit": 50, "parameters_id": 2}
    data = _get_json(OPENAQ_BASE + "/locations?" + urllib.parse.urlencode(q), opener, headers=hdr)
    locs = [x for x in ((data or {}).get("results") or []) if isinstance(x, dict) and x.get("id") is not None] if isinstance(data, dict) else []

    def dist(x):
        d = x.get("distance")
        if isinstance(d, (int, float)):
            return d / 1000.0
        co = x.get("coordinates") or {}
        try:
            return _km(c[0], c[1], float(co.get("latitude")), float(co.get("longitude")))
        except (TypeError, ValueError):
            return 1e9
    def fresh(x):
        """목록에 적힌 마지막 측정 시각이 6시간 안인 측정소만(멈춘 측정소가 가까이 많아도 건너뛴다: 예) 런던 도심은 2019·2020년에 멈춘 곳이 많다). 시각이 없으면 일단 후보로 둔다."""
        import datetime as _dt
        last = ((x.get("datetimeLast") or {}).get("utc") if isinstance(x.get("datetimeLast"), dict) else None)
        if not last:
            return True
        try:
            return time.time() - _dt.datetime.fromisoformat(str(last).replace("Z", "+00:00")).timestamp() <= 6 * 3600
        except ValueError:
            return True
    for loc in [x for x in sorted(locs, key=dist) if fresh(x)][:4]:
        try:
            lat_data = _get_json(OPENAQ_BASE + f"/locations/{int(loc['id'])}/latest?" + urllib.parse.urlencode({"limit": 50}), opener, headers=hdr)
        except ApiRejected:
            raise
        except Exception:
            continue
        rd = _openaq_reading((lat_data or {}).get("results") if isinstance(lat_data, dict) else [], loc.get("sensors"))
        if rd and (rd["pm25"] is not None or rd["pm10"] is not None):
            name = str(loc.get("name") or loc.get("locality") or "").strip()[:40] or "OpenAQ"
            out = {"pm25": rd["pm25"], "pm10": rd["pm10"], "source": "station", "provider": "OpenAQ", "station": name, "time": rd["time"]}
            out.update(air_grades(rd["pm25"], rd["pm10"]))
            return out
    return None


def fetch_weather(lat, lon, unit="c", opener=None, air_key="", openaq_key=""):
    """현재 날씨 + 3일 예보. 실패하면 None. 좌표는 소수 둘째 자리로 줄여서 보낸다.
    미세먼지(실측 우선): ① 한국이고 에어코리아 인증키가 있으면 가까운 측정소의 실제 값 ② OpenAQ 키가 있으면 전 세계 가까운 측정소의 실제 값 ③ 예측 모델 값('source':'model')."""
    c = clean_coords(lat, lon)
    if not c:
        return None
    q = {"latitude": c[0], "longitude": c[1], "timezone": "auto", "forecast_days": 3, "wind_speed_unit": "ms",
         "temperature_unit": "fahrenheit" if unit == "f" else "celsius",
         "current": "temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,wind_speed_10m,is_day",
         "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max"}
    try:
        data = _get_json(FORECAST_URL + "?" + urllib.parse.urlencode(q), opener)
    except Exception:
        return None
    out = parse_forecast(data)
    if out:
        out["unit"] = "f" if unit == "f" else "c"
        out["updated"] = time.time()
        air, err = None, None
        if air_key:
            try:
                air = fetch_air_station(c[0], c[1], air_key, opener)
            except ApiRejected:
                err = "key"
            except Exception:
                air = None
        if air is None and openaq_key:
            try:
                air = fetch_air_openaq(c[0], c[1], openaq_key, opener)
            except ApiRejected:
                err = err or "openaq"
            except Exception:
                air = None
        if air is None:
            air = fetch_air(c[0], c[1], opener)          # 실제 측정값을 못 얻으면 모델 값(그래도 실패하면 None: 날씨는 보여 준다)
        out["air"] = air
        if err:
            out["airErr"] = err
    return out


class WeatherCache:
    """같은 좌표·단위는 15분 동안 다시 받지 않는다(여러 곳에서 불러도 서버 요청은 적게)."""

    def __init__(self, fetch=fetch_weather, clock=time.time, ttl=TTL_SECONDS):
        self._fetch, self._clock, self._ttl = fetch, clock, ttl
        self._lock = threading.Lock()
        self._key = None
        self._val = None
        self._at = 0.0
        self.error = False

    def get(self, lat, lon, unit="c", force=False, air_key="", openaq_key=""):
        c = clean_coords(lat, lon)
        if not c:
            return None
        key = (c, "f" if unit == "f" else "c", bool(air_key), bool(openaq_key))
        with self._lock:
            fresh = self._key == key and self._val is not None and self._clock() - self._at < self._ttl
            if fresh and not force:
                return self._val
        extra = {}
        if air_key:
            extra["air_key"] = air_key
        if openaq_key:
            extra["openaq_key"] = openaq_key
        got = self._fetch(c[0], c[1], key[1], **extra)
        with self._lock:
            if got:
                self._key, self._val, self._at, self.error = key, got, self._clock(), False
                return got
            self.error = True
            return self._val if self._key == key else None            # 실패하면 같은 도시의 옛 값을 계속 보여 준다
