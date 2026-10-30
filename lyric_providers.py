# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Flirty_BananaMilk — 상업적 이용 금지, 자세한 내용은 LICENSE
"""Cider 가 아닌 앱의 곡 가사를 외부 가사 서비스에서 직접 찾는다.

- NetEase(네이버 아님, 중국 NetEase Cloud Music): 단어 단위(yrc) 싱크가 있는 곡이 많고, 줄 단위(lrc)는 거의 모든 곡에 있다. 한국어/일본어/중국어 곡에 강하다.
- LRCLIB: 오픈 가사 DB. 줄 단위 싱크(LRC)와 일반 텍스트, 곡 길이로 정확히 대조된다. 서양권 곡에 강하다.

두 곳을 동시에 조회해 단어 싱크 > 줄 싱크 > 싱크 없음 순으로 가장 좋은 결과를 쓴다. 찾은 가사는 로컬에 캐시한다
(없다는 결과는 하루만). 이 서비스들에는 곡 제목/아티스트(와 길이)만 전송한다.

결과는 Cider 가사와 같은 모양이다: {"source", "timingType": "Word"|"Line", "lines": [{start, end, text, words: [...]}], "unsynced"?}
"""
import difflib
import hashlib
import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from cider_client import clean_name, fill_missing_line_ends, mark_word_spacing

UA = "Dalu/1.0 (local desktop widget)"
BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
NEGATIVE_TTL = 24 * 3600
MAX_DURATION_DEVIATION = 4.0      # 초: 곡 길이가 이 이상 다르면 다른 버전(라이브, 리믹스)으로 본다
MIN_TITLE_SIM = 0.72
CACHE_DIR = os.path.join(os.environ.get("APPDATA", ""), "Dalu", "lyrics_cache")

_CREDIT_RE = re.compile(r"^\s*(作词|作曲|编曲|制作人|混音|母带|录音|监制|和声|吉他|贝斯|鼓|策划|出品|词|曲|作詞|作曲|編曲|"
                        r"lyrics?\s*by|composed?\s*by|music\s*by|arranged?\s*by|produced?\s*by|written\s*by)\s*[:：]", re.I)
_LRC_TS = re.compile(r"\[(\d{1,3}):(\d{1,2})(?:[.:](\d{1,3}))?\]")
_LRC_WORD = re.compile(r"<(\d{1,3}):(\d{1,2})(?:[.:](\d{1,3}))?>")
_YRC_LINE = re.compile(r"^\[(\d+),(\d+)\](.*)$")
_YRC_WORD = re.compile(r"\((\d+),(\d+),-?\d+\)")


# ---------------------------------------------------------------- HTTP (테스트에서 교체 가능)
def http_get(url, headers=None, timeout=6.0):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json", **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", "replace"))


# ---------------------------------------------------------------- 파싱
def _ts_seconds(m, s, frac):
    f = (int(frac) / (10 ** len(frac))) if frac else 0.0
    return int(m) * 60 + int(s) + f


def parse_lrc(text):
    """LRC 텍스트 -> 줄 목록(start/end/text/words). 한 줄에 시각이 여럿이면 줄을 복제하고, [ar:..] 같은 메타 줄은 건너뛴다.
    <mm:ss.xx> 단어 태그(확장 LRC)가 있으면 단어 싱크로 쓴다."""
    lines = []
    for raw in (text or "").splitlines():
        stamps = list(_LRC_TS.finditer(raw))
        if not stamps:
            continue
        body = raw[stamps[-1].end():]
        starts = [_ts_seconds(*m.groups()) for m in stamps]
        words = []
        if _LRC_WORD.search(body):
            parts = _LRC_WORD.split(body)       # [텍스트0, m, s, f, 텍스트1, m, s, f, ...]
            for i in range(1, len(parts) - 3, 4):
                w_text = parts[i + 3].strip()
                if w_text:
                    words.append({"text": w_text, "start": _ts_seconds(parts[i], parts[i + 1], parts[i + 2]), "end": 0.0})
            body = " ".join(w["text"] for w in words)
            for a, b in zip(words, words[1:]):
                a["end"] = b["start"]
        text_line = body.strip()
        if not text_line or _CREDIT_RE.match(text_line):
            continue
        for st in starts:
            lines.append({"start": st, "end": 0.0, "text": text_line, "words": [dict(w) for w in words]})
    lines.sort(key=lambda l: l["start"])
    for l in lines:                                   # 마지막 단어는 줄 끝(다음 줄 시작)까지
        if l["words"] and l["words"][-1]["end"] <= l["words"][-1]["start"]:
            l["words"][-1]["end"] = l["words"][-1]["start"] + 0.5
    return fill_missing_line_ends(lines)


def parse_yrc(text):
    """NetEase 단어 싱크(yrc): '[줄시작ms,줄길이ms](단어시작ms,단어길이ms,0)단어...' -> 줄 목록. 못 읽으면 빈 목록."""
    lines = []
    for raw in (text or "").splitlines():
        m = _YRC_LINE.match(raw.strip())
        if not m:
            continue                                  # '{"t":0,"c":[...]}' 같은 크레딧 JSON 줄 등
        start, dur, body = int(m.group(1)) / 1000.0, int(m.group(2)) / 1000.0, m.group(3)
        marks = list(_YRC_WORD.finditer(body))
        words = []
        for i, mk in enumerate(marks):
            seg_end = marks[i + 1].start() if i + 1 < len(marks) else len(body)
            w_text = body[mk.end():seg_end]
            if w_text.strip():
                ws = int(mk.group(1)) / 1000.0
                words.append({"text": w_text.strip(), "start": ws, "end": ws + int(mk.group(2)) / 1000.0})
        line_text = "".join(body[mk.end(): (marks[i + 1].start() if i + 1 < len(marks) else len(body))]
                            for i, mk in enumerate(marks)).strip()
        if not line_text or _CREDIT_RE.match(line_text):
            continue
        mark_word_spacing(words, line_text)
        lines.append({"start": start, "end": start + dur, "text": line_text, "words": words})
    lines.sort(key=lambda l: l["start"])
    return fill_missing_line_ends(lines)


def plain_to_lines(text):
    out = []
    for raw in (text or "").splitlines():
        t = raw.strip()
        if t and not _CREDIT_RE.match(t):
            out.append({"start": 0.0, "end": 0.0, "text": t, "words": []})
    return fill_missing_line_ends(out)


def _has_word_sync(lines):
    starts = {round(w["start"], 2) for l in lines for w in l.get("words") or []}
    return len(starts) > 3


# ---------------------------------------------------------------- 곡 대조
def guess_queries(title, artist):
    """유튜브처럼 'Artist - Title' 이 제목에 들어 있거나 아티스트가 '… - Topic' 인 경우를 보정한 (제목, 아티스트) 후보."""
    title, artist = (title or "").strip(), re.sub(r"\s*-\s*Topic$", "", (artist or "").strip(), flags=re.I)
    cands = [(title, artist)]
    if " - " in title:
        left, right = [p.strip() for p in title.split(" - ", 1)]
        cands += [(right, left), (left, right)]
        if not artist:
            cands = cands[1:] + cands[:1]
    seen, out = set(), []
    for t, a in cands:
        key = (clean_name(t), clean_name(a))
        if key[0] and key not in seen:
            seen.add(key)
            out.append((t, a))
    return out


def _sim(a, b):
    a, b = clean_name(a), clean_name(b)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def _cjk(s):
    return any(ord(ch) >= 0x2E80 for ch in s or "")


def match_score(want_title, want_artist, want_dur, cand_title, cand_artists, cand_dur):
    """0~1 점수. 제목이 너무 다르거나 길이가 크게 다르면 0 (다른 곡/버전)."""
    t = _sim(want_title, cand_title)
    if t < MIN_TITLE_SIM:
        return 0.0
    if want_dur and cand_dur and abs(want_dur - cand_dur) > MAX_DURATION_DEVIATION:
        return 0.0
    a = max([_sim(want_artist, c) for c in cand_artists] or [0.0]) if want_artist else 0.6
    if want_artist and a < 0.4:
        # 아티스트 표기가 문자 체계부터 다르면(IU / 아이유) 제목이 거의 같고 곡 길이가 1.5초 안으로 맞을 때만 같은 곡으로 인정한다
        # (길이를 모르면 동명 다른 곡을 못 거르므로 인정하지 않는다). 같은 문자 체계인데 이름이 다르면 다른 가수의 동명 곡이다.
        if (t >= 0.95 and want_dur and cand_dur and abs(want_dur - cand_dur) <= 1.5
                and _cjk(want_artist) != any(_cjk(c) for c in cand_artists)):
            a = 0.5
        else:
            return 0.0
    d = 0.1 if (want_dur and cand_dur and abs(want_dur - cand_dur) <= 1.5) else 0.0
    return min(1.0, 0.55 * t + 0.35 * a + d)


def _best(cands):
    """cands: [(score, payload)] -> 임계값을 넘는 최고 점수의 payload 또는 None."""
    cands = [c for c in cands if c[0] >= 0.6]
    return max(cands, key=lambda c: c[0])[1] if cands else None


# ---------------------------------------------------------------- 서비스별 조회: 못 찾으면 None, 네트워크 오류는 예외
def fetch_lrclib(queries, album, duration, http=None):
    http = http or http_get
    base = "https://lrclib.net/api"
    for title, artist in queries:
        found = None
        if artist and duration:
            try:
                found = http(f"{base}/get?" + urllib.parse.urlencode(
                    {"track_name": title, "artist_name": artist, "album_name": album or "", "duration": int(round(duration))}))
            except urllib.error.HTTPError as e:
                if e.code != 404:
                    raise
        if not found:
            params = {"track_name": title}
            if artist:
                params["artist_name"] = artist
            res = http(f"{base}/search?" + urllib.parse.urlencode(params)) or []
            found = _best([(match_score(title, artist, duration, r.get("trackName", ""), [r.get("artistName", "")],
                                  r.get("duration")), r) for r in res])
        if not found or found.get("instrumental"):
            continue
        if found.get("syncedLyrics"):
            lines = parse_lrc(found["syncedLyrics"])
            if lines:
                return {"source": "LRCLIB", "timingType": "Word" if _has_word_sync(lines) else "Line", "lines": lines}
        if found.get("plainLyrics"):
            lines = plain_to_lines(found["plainLyrics"])
            if lines:
                return {"source": "LRCLIB", "timingType": "Line", "lines": lines, "unsynced": True}
    return None


def fetch_netease(queries, album, duration, http=None):
    http = http or http_get
    hdr = {"Referer": "https://music.163.com/", "Cookie": "appver=2.0.2", "User-Agent": BROWSER_UA}
    for title, artist in queries:
        song = None
        # '제목 아티스트' 로 먼저, 안 나오면 제목만으로 (아티스트 표기가 서비스마다 달라 검색에서 밀리는 곡이 있다)
        for q in ((title + " " + artist).strip(), title) if artist else (title,):
            res = http("https://music.163.com/api/search/get?" + urllib.parse.urlencode(
                {"s": q, "type": 1, "limit": 20, "offset": 0}), hdr)
            cands = []
            for s in ((res or {}).get("result") or {}).get("songs") or []:
                d = (s.get("duration") or s.get("dt") or 0) / 1000.0
                artists = [a.get("name", "") for a in (s.get("artists") or s.get("ar") or [])]
                cands.append((match_score(title, artist, duration, s.get("name", ""), artists, d), s))
            song = _best(cands)
            if song:
                break
        if not song:
            continue
        lyr = http("https://music.163.com/api/song/lyric?" + urllib.parse.urlencode(
            {"id": song["id"], "lv": -1, "kv": -1, "tv": -1, "yv": -1}), hdr) or {}
        yrc = ((lyr.get("yrc") or {}).get("lyric")) or ""
        if yrc:
            lines = parse_yrc(yrc)
            if lines and _has_word_sync(lines):
                return {"source": "NetEase", "timingType": "Word", "lines": lines}
        lrc = ((lyr.get("lrc") or {}).get("lyric")) or ""
        lines = parse_lrc(lrc)
        if lines:
            return {"source": "NetEase", "timingType": "Line", "lines": lines}
    return None


class Unavailable(Exception):
    """이 서비스를 지금은 쓸 수 없다(예: Cider 가 꺼져 있다). 오류도 '없음'도 아니라서 재시도/부정 캐시에 세지 않는다."""


CIDER_BASE = "http://127.0.0.1:10767"


def cider_get(path, timeout=6.0):
    """Cider 의 로컬 REST API(내 PC 안)를 부른다. 연결이 안 되면 Unavailable, 404 는 None."""
    try:
        req = urllib.request.Request(CIDER_BASE + path, headers={"User-Agent": UA, "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise
    except (urllib.error.URLError, ConnectionError, TimeoutError, OSError) as e:
        raise Unavailable(repr(e))


def fetch_apple_music(queries, album, duration, http=None, parse=None):
    """Cider 를 거쳐 Apple Music 가사를 찾는다: 어떤 앱에서 재생 중이든 같은 곡을 Apple Music 에서 찾아 단어 싱크 가사를 받는다.
    Apple 서버나 토큰은 직접 다루지 않는다. 로그인한 Cider 가 이미 하는 일을 로컬 API 로 부탁할 뿐이다."""
    http = http or cider_get
    if parse is None:
        from cider_client import CiderClient
        parse = CiderClient()._parse_cider_lyrics_data
    for title, artist in queries:
        song = None
        for q in ((title + " " + artist).strip(), title) if artist else (title,):
            res = http("/api/v2/amapi/search?" + urllib.parse.urlencode({"term": q, "types": "songs", "limit": 10}), 5.0)
            data = ((((res or {}).get("data") or {}).get("results") or {}).get("songs") or {}).get("data") or []
            cands = []
            for s in data:
                a = s.get("attributes") or {}
                if not a.get("hasLyrics"):
                    continue          # Apple 에 가사가 없는 곡: Cider 가 다른 곳 가사로 채우지만 그건 우리가 직접 조회한다
                cands.append((match_score(title, artist, duration, a.get("name", ""), [a.get("artistName", "")],
                                          (a.get("durationInMillis") or 0) / 1000.0), s))
            song = _best(cands)
            if song:
                break
        if not song:
            continue
        sid = str(song.get("id") or "")
        res = http(f"/api/v2/lyrics/{urllib.parse.quote(sid)}?words=true&ttml=true", 8.0)
        c_data = (res or {}).get("data") or {}
        if not c_data or (c_data.get("id") and str(c_data["id"]) != sid):
            continue
        if "apple" not in str((c_data.get("source") or {}).get("provider", "")).lower():
            continue
        lyrics = parse(c_data, sid)
        if lyrics and lyrics.get("lines"):
            lyrics = dict(lyrics, source="Apple Music")
            lyrics.pop("trackId", None)
            return lyrics
    return None


PROVIDERS = (("Apple Music", fetch_apple_music), ("NetEase", fetch_netease), ("LRCLIB", fetch_lrclib))     # 같은 품질이면 앞쪽을 쓴다


def quality(lyrics):
    if not lyrics:
        return -1
    if lyrics.get("unsynced"):
        return 0
    return 2 if lyrics.get("timingType") == "Word" else 1


# ---------------------------------------------------------------- 캐시
def _cache_path(title, artist, cache_dir):
    key = hashlib.sha1((clean_name(title) + "|" + clean_name(artist)).encode("utf-8")).hexdigest()[:20]
    return os.path.join(cache_dir, key + ".json")


def cache_load(title, artist, cache_dir=None, now=None):
    """('hit', lyrics) | ('miss_cached', None: 최근에 없다고 확인함) | ('none', None: 캐시 없음)."""
    try:
        with open(_cache_path(title, artist, cache_dir or CACHE_DIR), encoding="utf-8") as f:
            d = json.load(f)
        if d.get("lyrics"):
            return "hit", d["lyrics"]
        if (now or time.time()) - d.get("t", 0) < NEGATIVE_TTL:
            return "miss_cached", None
    except Exception:
        pass
    return "none", None


def cache_store(title, artist, lyrics, cache_dir=None):
    d = cache_dir or CACHE_DIR
    try:
        os.makedirs(d, exist_ok=True)
        with open(_cache_path(title, artist, d), "w", encoding="utf-8") as f:
            json.dump({"t": time.time(), "lyrics": lyrics}, f, ensure_ascii=False)
    except Exception:
        pass


# ---------------------------------------------------------------- 진입점
def fetch_lyrics(title, artist, album="", duration=0.0, timeout=9.0, cache_dir=None, providers=None, log=None):
    """모든 서비스를 동시에 조회해 가장 좋은 가사를 돌려준다. (lyrics 또는 None, info)
    info: {"not_found": 모든 서비스가 정상 응답했는데 없음, "errors": [...], "cached": bool, "source": ...}"""
    log = log or (lambda m: None)
    info = {"not_found": False, "errors": [], "cached": False}
    status, cached = cache_load(title, artist, cache_dir)
    if status == "hit":
        info.update(cached=True, source=cached.get("source"))
        return cached, info
    if status == "miss_cached":
        info.update(cached=True, not_found=True)
        return None, info

    queries = guess_queries(title, artist)
    if not queries:
        info["not_found"] = True
        return None, info
    results, lock = {}, threading.Lock()

    def run(name, fn):
        try:
            r = fn(queries, album, duration)
            with lock:
                results[name] = ("ok", r)
        except Unavailable as e:
            with lock:
                results[name] = ("na", repr(e))
        except Exception as e:
            with lock:
                results[name] = ("err", repr(e))

    threads = [threading.Thread(target=run, args=(n, f), daemon=True, name="lyr-" + n) for n, f in (providers or PROVIDERS)]
    for t in threads:
        t.start()
    deadline = time.time() + timeout
    for t in threads:
        t.join(max(0.0, deadline - time.time()))

    best, answered, skipped = None, 0, 0
    with lock:
        snapshot = dict(results)
    for name, _ in (providers or PROVIDERS):
        kind, val = snapshot.get(name, ("err", "timeout"))
        if kind == "na":                  # 쓸 수 없는 서비스(Cider 꺼짐 등): 오류로도 '없음'으로도 세지 않는다
            skipped += 1
            continue
        if kind == "err":
            info["errors"].append(f"{name}: {val}")
            continue
        answered += 1
        if quality(val) > quality(best):
            best = val
    if best:
        cache_store(title, artist, best, cache_dir)
        log(f"external lyrics: {best['source']} ({best['timingType']}{', unsynced' if best.get('unsynced') else ''}, {len(best['lines'])} lines) for {title} - {artist}")
        return best, info
    if answered + skipped == len(providers or PROVIDERS) and answered:      # 쓸 수 있는 서비스가 전부 정상 응답했는데 없다 -> 다시 묻지 않는다
        info["not_found"] = True
        if not skipped:                                                    # 못 쓴 서비스(Cider 꺼짐)가 있으면 하루 동안 막지 않는다
            cache_store(title, artist, None, cache_dir)
    return None, info
