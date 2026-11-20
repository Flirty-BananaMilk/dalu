# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Flirty_BananaMilk — 상업적 이용 금지, 자세한 내용은 LICENSE
"""캘린더(.ics) 읽기: 구글/애플/아웃룩 등이 내보내는 '비공개 iCal 주소' 또는 로컬 .ics 파일을 읽어 앞으로의 일정을 만든다.

계정 연동 없이 사용자가 직접 준 주소/파일만 읽는다(읽기 전용). 반복 일정(RRULE), 제외 날짜(EXDATE), 하루종일 일정, 시간대(TZID)를 처리한다.
외부 패키지 없이 표준 라이브러리만 쓴다. 해석할 수 없는 항목은 건너뛴다.
"""
import calendar as _cal
import re
import threading
import time
import urllib.request
from datetime import date, datetime, timedelta, timezone

try:
    from zoneinfo import ZoneInfo
except Exception:       # pragma: no cover
    ZoneInfo = None

MAX_BYTES = 5 * 1024 * 1024
MAX_OCCURRENCES = 2000
_DAYS = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]


# ---------------------------------------------------------------- 텍스트 해석
def unfold(text):
    """RFC5545 줄 접기: 공백/탭으로 시작하는 줄은 앞 줄의 연속."""
    lines = []
    for raw in (text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if raw[:1] in (" ", "\t") and lines:
            lines[-1] += raw[1:]
        else:
            lines.append(raw)
    return lines


def parse_prop(line):
    """'DTSTART;TZID=Asia/Seoul:20261026T100000' -> ('DTSTART', {'TZID': 'Asia/Seoul'}, '20261026T100000')"""
    if ":" not in line:
        return None
    cut, q = -1, False
    for i, ch in enumerate(line):          # 따옴표 안의 ':' 는 건너뛴다(Outlook: TZID="(UTC+09:00) Seoul":...)
        if ch == '"':
            q = not q
        elif ch == ":" and not q:
            cut = i
            break
    if cut < 0:
        return None
    head, value = line[:cut], line[cut + 1:]
    parts = head.split(";")
    params = {}
    for p in parts[1:]:
        if "=" in p:
            k, v = p.split("=", 1)
            params[k.upper()] = v.strip('"')
    return parts[0].upper(), params, value


def unescape(s):
    """ICS 글자 이스케이프를 푼다. 앞에서부터 한 글자씩 읽어서, 역슬래시 두 개 뒤의 n 이 줄바꿈으로 바뀌지 않는다."""
    out, i, s = [], 0, (s or "")
    while i < len(s):
        c = s[i]
        if c == "\\" and i + 1 < len(s):
            n = s[i + 1]
            if n in "nN":
                out.append("\n")
            elif n in ",;\\":
                out.append(n)
            else:
                out.append(c + n)
            i += 2
        else:
            out.append(c)
            i += 1
    return "".join(out)


def _local_tz():
    return datetime.now().astimezone().tzinfo


def parse_dt(value, params, default_tz=None):
    """-> (aware datetime, all_day). 해석할 수 없으면 (None, False)."""
    value = (value or "").strip()
    try:
        if params.get("VALUE") == "DATE" or (len(value) == 8 and value.isdigit()):
            d = datetime.strptime(value[:8], "%Y%m%d")
            return (d.replace(tzinfo=default_tz) if default_tz else d.astimezone()), True          # 시간대 없는 날짜는 그 날짜의 이 컴퓨터 시간대(서머타임 반영)로
        if value.endswith("Z"):
            return datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc), False
        naive = datetime.strptime(value[:15], "%Y%m%dT%H%M%S")
        tzid = params.get("TZID")
        tz = None
        if tzid and ZoneInfo:
            try:
                tz = ZoneInfo(tzid)
            except Exception:
                tz = None
        if tz or default_tz:
            return naive.replace(tzinfo=tz or default_tz), False
        return naive.astimezone(), False          # 시간대 없는 시각: 그 날짜의 이 컴퓨터 시간대로(지금 시점의 고정 오프셋을 쓰면 서머타임 경계 일정이 1시간 어긋난다)
    except Exception:
        return None, False


def parse_duration(value):
    m = re.match(r"^([+-])?P(?:(\d+)W)?(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?$", (value or "").strip())
    if not m:
        return None
    sign = -1 if m.group(1) == "-" else 1
    w, d, h, mi, s = (int(x or 0) for x in m.groups()[1:])
    return sign * timedelta(weeks=w, days=d, hours=h, minutes=mi, seconds=s)


def parse_rrule(value):
    r = {}
    for part in (value or "").split(";"):
        if "=" in part:
            k, v = part.split("=", 1)
            r[k.upper()] = v
    return r


# ---------------------------------------------------------------- 반복 확장
def _add_months(y, m, n):
    t = y * 12 + (m - 1) + n
    return t // 12, t % 12 + 1


def _nth_weekday(y, m, wd, n):
    """그 달의 n번째(음수면 뒤에서) wd(0=월) 요일 날짜. 없으면 None."""
    days = [d for d in range(1, _cal.monthrange(y, m)[1] + 1) if date(y, m, d).weekday() == wd]
    try:
        return days[n - 1] if n > 0 else days[n]
    except IndexError:
        return None


def _safe_expand(start, rule, until_limit, from_dt=None):
    """깨진 반복 규칙 하나가 일정 전체를 죽이지 않게: 그 일정의 반복만 건너뛴다."""
    try:
        yield from expand(start, rule, until_limit, from_dt=from_dt)
    except Exception:
        return


def expand(start, rule, until_limit, tz_aware=True, from_dt=None):
    """start(aware datetime)부터 until_limit(aware datetime)까지의 시작 시각들을 순서대로 만든다.
    벽시계 시간(start 의 시간대 기준)으로 계산해서 서머타임이 있어도 같은 시각을 유지한다."""
    freq = rule.get("FREQ")
    iv = str(rule.get("INTERVAL", "1") or "1")
    interval = max(1, int(iv)) if iv.isdigit() else 1          # 'INTERVAL=abc' 같은 깨진 값은 1 로 본다
    count = int(rule["COUNT"]) if rule.get("COUNT", "").isdigit() else None
    until = None
    if rule.get("UNTIL"):
        u, _ = parse_dt(rule["UNTIL"], {}, start.tzinfo)
        until = u
        if u is not None and len(re.sub(r"\D", "", rule["UNTIL"])) == 8:
            until = u + timedelta(days=1) - timedelta(seconds=1)          # 날짜만 있는 UNTIL 은 그날 끝까지(시각이 있는 일정의 마지막 날이 빠지지 않게)
    bydays = []
    for tok in [t for t in rule.get("BYDAY", "").split(",") if t]:
        m = re.match(r"^([+-]?\d+)?(MO|TU|WE|TH|FR|SA|SU)$", tok)
        if m:
            bydays.append((int(m.group(1)) if m.group(1) else 0, _DAYS.index(m.group(2))))
    bymonthday = [int(x) for x in rule.get("BYMONTHDAY", "").split(",") if re.match(r"^-?\d+$", x)]
    bymonth = [int(x) for x in rule.get("BYMONTH", "").split(",") if x.isdigit() and 1 <= int(x) <= 12]
    t0 = start.timetz()
    tz = start.tzinfo
    base = start.date()
    out, emitted = [], 0

    def make(d):
        return datetime(d.year, d.month, d.day, t0.hour, t0.minute, t0.second, tzinfo=tz)

    def emit(dt):
        nonlocal emitted
        if dt < start:
            return True
        if until and dt > until:
            return False
        if count is not None and emitted >= count:
            return False
        emitted += 1
        if from_dt is not None and dt < from_dt:
            return True          # 보여 줄 범위 앞의 지난 발생분: 횟수(COUNT)에는 세지만 목록에는 담지 않는다(오래된 매일 반복이 상한 2000개를 지난 날로 채우지 않게)
        out.append(dt)
        return dt <= until_limit and len(out) < MAX_OCCURRENCES

    if freq == "DAILY":
        d = base
        while True:
            if (not bymonth or d.month in bymonth) and (not bydays or d.weekday() in [w for _, w in bydays]):
                if not emit(make(d)):
                    break
            d += timedelta(days=interval)
            if make(d) > until_limit + timedelta(days=1):
                break
    elif freq == "WEEKLY":
        wkst = _DAYS.index(rule["WKST"]) if rule.get("WKST") in _DAYS else 0          # 주의 시작 요일(기본 월요일): INTERVAL>1 이면 주 묶음이 이 기준으로 정해진다
        wds = sorted({w for _, w in bydays} or {start.weekday()}, key=lambda w: (w - wkst) % 7)
        week0 = base - timedelta(days=(base.weekday() - wkst) % 7)
        wk = 0
        while True:
            ws = week0 + timedelta(weeks=wk * interval)
            for wd in wds:
                if not emit(make(ws + timedelta(days=(wd - wkst) % 7))):
                    return out
            wk += 1
            if make(ws) > until_limit + timedelta(days=7):
                break
    elif freq == "MONTHLY":
        k = 0
        while True:
            y, m = _add_months(base.year, base.month, k * interval)
            days = []
            if bydays:
                for n, wd in bydays:
                    if n:
                        d = _nth_weekday(y, m, wd, n)
                        if d:
                            days.append(d)
                    else:
                        days += [d for d in range(1, _cal.monthrange(y, m)[1] + 1) if date(y, m, d).weekday() == wd]
            elif bymonthday:
                last = _cal.monthrange(y, m)[1]
                days = [d if d > 0 else last + 1 + d for d in bymonthday]
            else:
                days = [base.day]
            for d in sorted({d for d in days if 1 <= d <= _cal.monthrange(y, m)[1]}):
                if not emit(make(date(y, m, d))):
                    return out
            k += 1
            if date(y, m, 1) > until_limit.date() + timedelta(days=31):
                break
    elif freq == "YEARLY":
        k = 0
        months = bymonth or [base.month]
        while True:
            y = base.year + k * interval
            for m in months:
                d = base.day
                if bydays and bydays[0][0]:
                    d = _nth_weekday(y, m, bydays[0][1], bydays[0][0])
                if d and d <= _cal.monthrange(y, m)[1]:
                    if not emit(make(date(y, m, d))):
                        return out
            k += 1
            if date(y, 1, 1) > until_limit.date() + timedelta(days=366):
                break
    else:
        emit(start)
    return out


# ---------------------------------------------------------------- 일정 목록
def parse_events(text):
    """ICS 텍스트 -> 원본 이벤트 목록(반복 확장 전)."""
    events, cur = [], None
    in_alarm = False
    for line in unfold(text):
        up = line.strip().upper()
        if up == "BEGIN:VALARM":          # 알림(VALARM) 안의 SUMMARY·DURATION 이 일정의 제목·길이를 덮어쓰지 않게 건너뛴다
            in_alarm = True
            continue
        if up == "END:VALARM":
            in_alarm = False
            continue
        if in_alarm:
            continue
        if up == "BEGIN:VEVENT":
            cur = {"exdates": [], "rdates": []}
            continue
        if up == "END:VEVENT":
            if cur and cur.get("start"):
                events.append(cur)
            cur = None
            continue
        if cur is None:
            continue
        p = parse_prop(line)
        if not p:
            continue
        name, params, value = p
        if name == "SUMMARY":
            cur["title"] = unescape(value)
        elif name == "LOCATION":
            cur["location"] = unescape(value)
        elif name == "UID":
            cur["uid"] = value.strip()
        elif name == "STATUS":
            cur["status"] = value.strip().upper()
        elif name == "DTSTART":
            cur["start"], cur["allDay"] = parse_dt(value, params)
        elif name == "DTEND":
            cur["end"], _ = parse_dt(value, params)
        elif name == "DURATION":
            cur["duration"] = parse_duration(value)
        elif name == "RRULE":
            cur["rrule"] = parse_rrule(value)
        elif name == "EXDATE":
            for v in value.split(","):
                dt, _ = parse_dt(v, params)
                if dt:
                    cur["exdates"].append(dt)
        elif name == "RECURRENCE-ID":
            cur["recurrenceId"], _ = parse_dt(value, params)
    return events


def upcoming(text, now=None, days=14, since=None):
    """지금부터 days 일 안에 시작하는(또는 진행 중인) 일정: [{title, start, end, allDay, location}] (시작 순, epoch 초).
    since 를 주면 지금 대신 그 시각부터 센다(월/주 보기에서 지난 날의 일정까지 보여 주기 위해)."""
    now = since or now or datetime.now(timezone.utc)
    horizon = now + timedelta(days=days)
    raw = parse_events(text)
    overrides = {}
    for e in raw:
        if e.get("recurrenceId") and e.get("uid"):
            overrides[(e["uid"], e["recurrenceId"])] = e
    out = []

    def add(title, s, e, all_day, loc):
        if e is None or e <= s:
            e = s + (timedelta(days=1) if all_day else timedelta(0))
        if e < now:
            return                                   # 이미 끝난 일정(진행 중인 것은 남긴다)
        if s > horizon:
            return
        out.append({"title": title or "", "start": s.timestamp(), "end": e.timestamp(), "allDay": bool(all_day), "location": loc or ""})

    for e in raw:
        if e.get("status") == "CANCELLED":
            continue                                 # 취소된 일정(취소된 반복 일정의 한 날도 overrides 로 원본에서 빠진다)
        s, all_day = e["start"], e.get("allDay", False)
        dur = (e["end"] - s) if e.get("end") else (e.get("duration") or (timedelta(days=1) if all_day else timedelta(0)))
        if e.get("recurrenceId"):                       # 반복 일정 중 이 날만 바뀐 것: 그대로 하나로 취급
            add(e.get("title"), s, s + dur, all_day, e.get("location"))
            continue
        if e.get("rrule"):
            ex = {d for d in e["exdates"]}
            for occ in _safe_expand(s, e["rrule"], horizon, from_dt=now - max(dur, timedelta(0)) - timedelta(days=1)):
                if occ in ex or (e.get("uid"), occ) in overrides:
                    continue
                add(e.get("title"), occ, occ + dur, all_day, e.get("location"))
        else:
            add(e.get("title"), s, s + dur, all_day, e.get("location"))
    out.sort(key=lambda x: (x["start"], x["title"]))
    # 같은 일정이 겹쳐 들어오는 경우(구독 중복) 제거
    seen, uniq = set(), []
    for o in out:
        k = (o["title"], o["start"])
        if k not in seen:
            seen.add(k)
            uniq.append(o)
    return uniq


# ---------------------------------------------------------------- 가져오기
def normalize_source(src):
    """webcal:// -> https://. 허용: http(s) 주소 또는 로컬 파일 경로. 그 밖(file://, ftp 등)은 None."""
    s = (src or "").strip()
    if not s:
        return None
    low = s.lower()
    if low.startswith("webcal://"):
        return "https://" + s[9:]
    if low.startswith(("http://", "https://")):
        return s
    if re.match(r"^[a-z][a-z0-9+.-]*://", low):
        return None
    return s


def fetch_text(src, timeout=10.0, opener=None):
    """주소면 내려받고, 아니면 파일로 읽는다. 크기 제한 있음. 실패하면 예외."""
    s = normalize_source(src)
    if s is None:
        raise ValueError("unsupported source")
    if s.lower().startswith(("http://", "https://")):
        req = urllib.request.Request(s, headers={"User-Agent": "Dalu/1.0", "Accept": "text/calendar, */*"})
        with (opener or urllib.request.urlopen)(req, timeout=timeout) as r:
            data = r.read(MAX_BYTES + 1)
    else:
        with open(s, "rb") as f:
            data = f.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("calendar too large")
    return data.decode("utf-8", "replace")


class CalendarSource:
    """주기적으로 다시 읽는 캘린더. refresh()는 느릴 수 있으니 백그라운드에서 부른다."""

    def __init__(self, ttl=600.0, fetch=fetch_text):
        self.ttl = ttl
        self._fetch = fetch
        self._src = ""
        self._at = 0.0
        self._text = ""
        self.error = ""
        self._mu = threading.Lock()

    def set_source(self, src):
        with self._mu:
            if (src or "") != self._src:
                self._src, self._at, self._text, self.error = src or "", 0.0, "", ""

    def refresh(self, force=False):
        with self._mu:
            src = self._src
            if not src:
                return False
            if not force and time.time() - self._at < (self.ttl if self._text else min(self.ttl, 120)):
                return False          # 못 받은 주소는 매번 다시 요청하지 않고 2분쯤 쉰다(20초마다 무한히 두드리던 것)
        try:
            text, err = self._fetch(src), ""          # 가져오는 동안은 락을 잡지 않는다(오래 걸릴 수 있다)
        except Exception as e:
            text, err = None, type(e).__name__
        with self._mu:
            if self._src != src:
                return False          # 가져오는 사이에 주소가 바뀌었다: 옛 주소의 응답은 버린다
            if text is not None:
                self._text = text
            self.error = err
            self._at = time.time()
        return True

    def events(self, now=None, days=14, since=None):
        return upcoming(self._text, now=now, days=days, since=since) if self._text else []
