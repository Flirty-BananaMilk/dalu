# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Flirty_BananaMilk — 상업적 이용 금지, 자세한 내용은 LICENSE
"""
Cider API Client & Lyrics Provider
Handles communication with Cider REST API on 127.0.0.1:10767,
fetches playback status, time, track info, artwork, and word-level TTML synced lyrics.
Guarantees strict track ID matching to prevent shifted lyrics across song transitions.
"""

import os
import re
import json
import time
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET

CIDER_BASE = "http://127.0.0.1:10767"
# 가사는 Cider 가 Apple 서버에서 처음 받아 오는 동안 응답이 늦을 수 있다. 일반 상태 조회(1.5초)와 같게 두면
# 그 사이 조용히 실패해 '가사 없음'으로 굳어진다.
LYRICS_TIMEOUT = 8.0
APPDATA_DIR = os.environ.get("APPDATA", "")
DATA_DIR = os.path.join(APPDATA_DIR, "Dalu")          # 사용자 데이터
LYRICS_DIR = os.path.join(DATA_DIR, "lyrics")

def clean_name(s: str) -> str:
    if not s:
        return ""
    s = re.sub(r'[\(\[\{][^\)\]\}]*[\)\]\}]', '', s)
    s = re.sub(r'[^\w\s\uac00-\ud7a3\u3040-\u30ff\u4e00-\u9fff]', ' ', s)
    return ' '.join(s.lower().split())

_ID_PREFIX_RE = re.compile(r'^(?:ra|a)\.')

def normalize_track_id(track_id: str) -> str:
    """'a.123' / 'ra.123' 접두사만 제거한다. (str.replace('a.', '')는 'ra.123'을 'r123'으로 망가뜨림)"""
    return _ID_PREFIX_RE.sub('', str(track_id).split('/')[-1].strip())

def fill_missing_line_ends(lines, tail: float = 4.0):
    """end가 없거나 start 이하인 줄을 보정한다.

    end=0 인 줄이 있으면 프론트가 '다음 줄까지 거대한 공백 = 간주 구간'으로 판단해
    노래 도중에 3-dot 카운트다운이 떠 버린다.
    """
    for i, l in enumerate(lines):
        if l['end'] > l['start']:
            continue
        word_end = max((w['end'] for w in l.get('words') or []), default=0.0)
        if word_end > l['start']:
            l['end'] = word_end
        elif i + 1 < len(lines):
            l['end'] = max(l['start'], lines[i + 1]['start'])
        else:
            l['end'] = l['start'] + tail
    return lines

def has_real_word_sync(lines) -> bool:
    """줄마다 복사된 가짜 word가 아니라 실제로 서로 다른 단어 시작 시각이 있는지 검사."""
    distinct = set()
    total = 0
    for l in lines:
        ws = l.get('words') or []
        total += len(ws)
        for w in ws:
            st = w.get('start')
            if st is not None:
                distinct.add(round(float(st), 2))
    return total > 0 and len(distinct) > 3

def normalize_repeat(value):
    """Cider 의 repeatMode 를 'none' | 'one' | 'all' 로 통일한다 (문자열 또는 MusicKit 숫자 0/1/2)."""
    if isinstance(value, str):
        v = value.strip().lower()
        if v in ('none', 'one', 'all'):
            return v
        if v in ('off', ''):
            return 'none'
        return {'0': 'none', '1': 'one', '2': 'all'}.get(v, 'none')
    if isinstance(value, bool):
        return 'all' if value else 'none'
    if isinstance(value, int):
        return {0: 'none', 1: 'one', 2: 'all'}.get(value, 'none')
    return 'none'

def mark_word_spacing(words, line_text: str):
    """각 단어 뒤에 원문 공백이 있었는지(`space`)를 기록한다.

    음절 단위 가사("Hel" "lo")는 단어 사이를 무조건 띄우면 "Hel lo" 로 갈라져 보인다.
    줄 전체 텍스트에서 단어를 순서대로 찾아 바로 뒤 글자가 공백인지로 판단하고,
    찾지 못하면(정렬 불가) 기본값 True(띄움)로 둔다.
    """
    pos = 0
    for w in words:
        idx = line_text.find(w['text'], pos) if line_text else -1
        if idx == -1:
            w['space'] = True
            continue
        end = idx + len(w['text'])
        w['space'] = end < len(line_text) and line_text[end].isspace()
        pos = end
    return words

def strip_bg_parens(words, text=""):
    """백그라운드 보컬(애드립/에코)은 소괄호로 감싸 내려오는 일이 많다: 맨 앞 '(' 와 맨 뒤 ')' 만 떼어 낸다. -> (words, text)"""
    ws = [dict(w) for w in (words or [])]
    if ws:
        ws[0]["text"] = ws[0]["text"].lstrip().lstrip("(").lstrip()
        ws[-1]["text"] = ws[-1]["text"].rstrip().rstrip(")").rstrip()
        ws = [w for w in ws if w["text"]]
    t = (text or "").strip()
    if t.startswith("("):
        t = t[1:].lstrip()
    if t.endswith(")"):
        t = t[:-1].rstrip()
    if ws and not t:
        t = " ".join(w["text"] for w in ws)
    return ws, t


def is_paren_wrapped(text):
    t = (text or "").strip()
    return len(t) >= 3 and t.startswith("(") and t.endswith(")") and t.count("(") == 1 and t.count(")") == 1


def split_background(lyrics):
    """가사에서 백그라운드 보컬 줄(bg=True)을 떼어 lyrics['bg'] 로 옮긴다. 본 가사 줄(lyrics['lines'])만 남겨서
    '본 가사 끝을 따라 부르는 에코'가 본 줄을 가로채지 않게 한다. 본 가사가 하나도 없으면 손대지 않는다."""
    if not isinstance(lyrics, dict):
        return lyrics
    lines = lyrics.get("lines") or []
    main, bg = [], []
    for l in lines:
        (bg if l.get("bg") else main).append(l)
    if not bg or not main:
        for l in lines:
            l.pop("bg", None)
        return lyrics
    out = dict(lyrics)
    out["lines"] = main
    out["bg"] = sorted(bg, key=lambda x: x["start"])
    return out


def parse_time_to_seconds(t_str: str) -> float:
    if not t_str:
        return 0.0
    t_str = t_str.strip()
    if t_str.endswith('s'):
        try:
            return float(t_str[:-1])
        except ValueError:
            return 0.0
    parts = t_str.split(':')
    try:
        if len(parts) == 3:
            h, m, s = parts
            return int(h) * 3600 + int(m) * 60 + float(s)
        elif len(parts) == 2:
            m, s = parts
            return int(m) * 60 + float(s)
        else:
            return float(t_str)
    except ValueError:
        return 0.0

def parse_local_ttml_file(file_path: str):
    """Parses local TTML file into word-level line structures."""
    try:
        # utf-8-sig: BOM이 있는 파일도 XML 파싱이 깨지지 않도록
        with open(file_path, "r", encoding="utf-8-sig", errors="ignore") as f:
            content = f.read()
    except Exception:
        return None
    return parse_ttml_text(content)


def _text_without_bg(p):
    """<p> 의 글자 전체에서 백그라운드 보컬(role=x-bg) span 은 뺀다 (그 글자는 따로 bg 줄이 된다)."""
    parts = [p.text or ""]
    for ch in p:
        role = next((v for k, v in ch.attrib.items() if k.split('}')[-1] == 'role'), '')
        if role != 'x-bg':
            parts.append("".join(ch.itertext()))
        parts.append(ch.tail or "")
    return re.sub(r"\s+", " ", "".join(parts)).strip()


def parse_ttml_text(content: str):
    """TTML 문자열(로컬 파일 또는 Cider 응답의 ttml 필드)을 단어 단위 줄 구조로 파싱한다."""
    clean_xml = re.sub(r'<\?xml[^>]*\?>', '', content, count=1).strip()
    try:
        root = ET.fromstring(clean_xml)
    except Exception:
        return None

    lines = []
    for elem in root.iter():
        tag = elem.tag.split('}')[-1].lower() if '}' in elem.tag else elem.tag.lower()
        if tag == 'p':
            p_begin = elem.attrib.get('begin') or elem.attrib.get('{http://www.w3.org/ns/ttml}begin', '')
            p_end = elem.attrib.get('end') or elem.attrib.get('{http://www.w3.org/ns/ttml}end', '')
            
            line_start = parse_time_to_seconds(p_begin)
            line_end = parse_time_to_seconds(p_end)

            words = []
            bg_groups = []
            for child in elem:
                c_tag = child.tag.split('}')[-1].lower() if '}' in child.tag else child.tag.lower()
                if c_tag != 'span':
                    continue
                role = next((v for k, v in child.attrib.items() if k.split('}')[-1] == 'role'), '')
                if role == 'x-bg':
                    # 백그라운드 보컬: 안쪽 span 들이 단어. (안쪽 span 이 없으면 글자 자체가 한 덩어리)
                    g_begin = child.attrib.get('begin', '')
                    g_end = child.attrib.get('end', '')
                    gw = []
                    inner = [x for x in child if (x.tag.split('}')[-1].lower() == 'span')]
                    for x in inner:
                        xt = (x.text or '').strip()
                        if not xt:
                            continue
                        xs = parse_time_to_seconds(x.attrib.get('begin', '')) if x.attrib.get('begin') else parse_time_to_seconds(g_begin)
                        xe = parse_time_to_seconds(x.attrib.get('end', '')) if x.attrib.get('end') else parse_time_to_seconds(g_end)
                        gw.append({"start": xs, "end": xe, "text": xt, "space": bool(x.tail and x.tail[:1].isspace())})
                    if not gw:
                        txt = "".join(child.itertext()).strip()
                        if txt:
                            gw.append({"start": parse_time_to_seconds(g_begin) or line_start, "end": parse_time_to_seconds(g_end) or line_end, "text": txt, "space": True})
                    if gw:
                        bg_groups.append(gw)
                    continue
                w_begin = child.attrib.get('begin') or child.attrib.get('{http://www.w3.org/ns/ttml}begin', '')
                w_end = child.attrib.get('end') or child.attrib.get('{http://www.w3.org/ns/ttml}end', '')
                w_text = (child.text or '').strip()
                if w_text:
                    w_s = parse_time_to_seconds(w_begin) if w_begin else line_start
                    w_e = parse_time_to_seconds(w_end) if w_end else line_end
                    words.append({
                        "start": w_s,
                        "end": w_e,
                        "text": w_text,
                        # TTML 은 단어 사이 공백이 span 의 tail 에 있다
                        "space": bool(child.tail and child.tail[:1].isspace())
                    })

            full_text = _text_without_bg(elem)
            if full_text or words:
                if not line_start and words:
                    line_start = words[0]['start']
                if not line_end and words:
                    line_end = words[-1]['end']

                lines.append({
                    "start": line_start,
                    "end": line_end,
                    "text": full_text,
                    "words": words
                })
            for gw in bg_groups:
                gw, gtext = strip_bg_parens(gw)
                if not gw:
                    continue
                lines.append({"start": min(w["start"] for w in gw), "end": max(w["end"] for w in gw), "text": gtext, "words": gw, "bg": True})

    lines.sort(key=lambda x: x['start'])
    return fill_missing_line_ends(lines)

class CiderClient:
    def __init__(self):
        self.trace = []
        self.cached_track_id = None
        self.cached_lyrics = None
        self.last_playback = None
        self.last_playback_fetch = 0

    def _http_get_status(self, endpoint: str, timeout: float = 1.5):
        """(HTTP 상태, 파싱된 JSON). 연결 실패/타임아웃이면 (None, None), 4xx/5xx 면 (코드, 본문 JSON 또는 None)."""
        try:
            req = urllib.request.Request(f"{CIDER_BASE}{endpoint}")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status, json.loads(resp.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            try:
                return e.code, json.loads(e.read().decode('utf-8'))
            except Exception:
                return e.code, None
        except Exception:
            return None, None

    def _http_get(self, endpoint: str, timeout: float = 1.5):
        status, data = self._http_get_status(endpoint, timeout)
        return data if status == 200 else None

    def _lget(self, ctx, endpoint: str):
        """가사용 GET. 'Cider 가 확실히 가사가 없다고 답했는지'를 ctx 에 센다 (타임아웃과 구분)."""
        ctx["calls"] += 1
        status, data = self._http_get_status(endpoint, LYRICS_TIMEOUT)
        if status == 404 and isinstance(data, dict) and (data.get("error") or {}).get("code") == "LYRICS_NOT_FOUND":
            ctx["nf"] += 1
            return None
        return data if status == 200 else None

    def _http_post(self, endpoint: str, body: dict = None, timeout: float = 1.5):
        try:
            data = json.dumps(body or {}).encode('utf-8')
            req = urllib.request.Request(
                f"{CIDER_BASE}{endpoint}",
                data=data,
                headers={'Content-Type': 'application/json'},
                method='POST'
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode('utf-8'))
        except Exception:
            return None

    def _http_put(self, endpoint: str, body: dict = None, timeout: float = 1.5):
        try:
            data = json.dumps(body or {}).encode('utf-8')
            req = urllib.request.Request(
                f"{CIDER_BASE}{endpoint}",
                data=data,
                headers={'Content-Type': 'application/json'},
                method='PUT'
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode('utf-8'))
        except Exception:
            return None

    def get_playback_state(self):
        """Fetches complete playback state from Cider."""
        res = self._http_get("/api/v2/playback")
        if not res or 'data' not in res:
            return None

        d = res['data'] or {}
        # API가 null을 돌려주는 경우(정지 직후 등)에 .get() 이 AttributeError 나지 않도록 `or {}`
        now = d.get('nowPlaying') or {}
        time_info = d.get('time') or {}

        current_time = float(time_info.get('currentTime') or 0.0)
        duration = float(time_info.get('duration') or 0.0)
        state = str(d.get('state') or 'stopped').lower()

        track_id = ""
        catalog_id = ""
        if now:
            play_params = now.get('playParams') or {}
            track_id = str(play_params.get('id') or play_params.get('catalogId') or now.get('id') or '')
            # 가사는 카탈로그 ID 로 조회해야 한다 (라이브러리 곡의 id 는 'i.xxx' 라 카탈로그와 다르다)
            catalog_id = str(play_params.get('catalogId') or play_params.get('reportingId') or '')

        artwork_url = ""
        art = now.get('artwork')
        if art and isinstance(art, dict):
            raw_url = art.get('url', '')
            if raw_url:
                artwork_url = raw_url.replace('{w}x{h}', '300x300').replace('{c}', 'bb').replace('{f}', 'png')

        return {
            "is_cider": True,
            "state": state,
            "isPlaying": state == "playing",
            "currentTime": current_time,
            "duration": duration,
            "trackId": track_id,
            "catalogId": catalog_id,
            "hasLyrics": now.get('hasLyrics'),
            "repeat": normalize_repeat(d.get('repeatMode')),
            "shuffle": bool(d.get('shuffleMode')),
            "title": now.get('name') or now.get('title') or "",
            "artist": now.get('artistName', ""),
            "album": now.get('albumName', ""),
            "artworkUrl": artwork_url,
            "timestamp": time.time()
        }

    def get_lyrics(self, *args, **kwargs):
        lyrics, info = self.get_lyrics_ex(*args, **kwargs)
        self.trace = info["trace"]
        return lyrics

    def get_lyrics_ex(self, *args, **kwargs):
        """가사를 가져오고, 백그라운드 보컬(소괄호 에코 줄)은 본 가사에서 떼어 lyrics['bg'] 로 둔다."""
        lyrics, info = self._get_lyrics_raw(*args, **kwargs)
        return split_background(lyrics), info

    def _get_lyrics_raw(self, track_id: str, track_title: str = "", artist_name: str = "",
                        catalog_id: str = "", has_lyrics=None):
        """스트리밍(Cider)이 제공하는 가사를 우선으로 가져온다.

        우선순위: 스트리밍 단어 단위 > 로컬 TTML 단어 단위 > 스트리밍 줄 단위 > 로컬 줄 단위.
        로컬 단어 단위 파일이 스트리밍의 줄 단위 가사보다 앞서는 것은 사용자가 직접 넣은 파일이
        더 정밀할 때뿐이다. 조회가 실패한 이유는 self.trace 에 남아 호출자가 로그로 볼 수 있다.
        """
        ctx = {"trace": [], "calls": 0, "nf": 0}
        if not track_id and not catalog_id:
            return None, {"trace": ctx["trace"], "not_found": False}

        # 후보 ID: 카탈로그 ID 가 가장 정확하다. 라이브러리 곡('i.xxx')은 id 로는 가사를 못 찾는다.
        ids = []
        for cand in (catalog_id, normalize_track_id(track_id) if track_id else ""):
            cand = (cand or "").strip()
            if cand and cand not in ids:
                ids.append(cand)

        streaming = self._fetch_streaming_lyrics(ids, ctx)
        local_lines = self._check_local_ttml(track_title, artist_name)
        local_words = bool(local_lines) and any(l.get('words') for l in local_lines)

        info = {"trace": ctx["trace"], "not_found": False}
        if streaming and streaming.get("timingType") == "Word":
            return streaming, info
        if local_words:
            ctx["trace"].append("local word-level TTML preferred over line-level streaming lyrics" if streaming else "using local word-level TTML")
            return {"source": "Local TTML", "timingType": "Word", "lines": local_lines, "trackId": track_id}, info
        if streaming:
            return streaming, info
        if local_lines:
            return {"source": "Local File", "timingType": "Line", "lines": local_lines, "trackId": track_id}, info
        # 보낸 가사 요청이 전부 'LYRICS_NOT_FOUND' 였다면 타임아웃이 아니라 정말 가사가 없는 곡이다
        info["not_found"] = ctx["calls"] > 0 and ctx["nf"] == ctx["calls"]
        return None, info

    def _fetch_streaming_lyrics(self, ids, ctx):
        """Cider 에서 가사를 조회한다. ID 로 직접 조회한 뒤, 안 되면 '현재 곡' 가사를 ID 검증과 함께 시도."""
        want = set(ids)

        # 1. 곡 ID 로 직접 조회 (카탈로그 ID -> 라이브러리 ID 순)
        for cid in ids:
            res = self._lget(ctx, f"/api/v2/lyrics/{cid}?words=true&ttml=true")
            if res is None:
                ctx["trace"].append(f"/lyrics/{cid}: no lyrics (404 not found) or no response")
                continue
            c_data = res.get('data') if isinstance(res, dict) else None
            if not c_data:
                ctx["trace"].append(f"/lyrics/{cid}: empty data")
                continue
            res_id = normalize_track_id(str(c_data.get('id', '')))
            if res_id and res_id not in want:
                ctx["trace"].append(f"/lyrics/{cid}: id mismatch (got {res_id})")
                continue
            parsed = self._parse_cider_lyrics_data(c_data, cid)
            if parsed:
                return parsed
            ctx["trace"].append(f"/lyrics/{cid}: no usable lines")

        # 2. 현재 곡 가사. 곡이 바뀐 직후엔 이전 곡 가사를 돌려줄 수 있으므로 ID 가 맞을 때만 쓴다.
        res = self._lget(ctx, "/api/v2/lyrics/current?words=true&ttml=true")
        c_data = res.get('data') if isinstance(res, dict) else None
        if c_data:
            res_id = normalize_track_id(str(c_data.get('id', '')))
            if res_id and want and res_id not in want:
                ctx["trace"].append(f"/lyrics/current: still previous song (got {res_id}, want {sorted(want)})")
            else:
                parsed = self._parse_cider_lyrics_data(c_data, next(iter(ids), ""))
                if parsed:
                    return parsed
                ctx["trace"].append("/lyrics/current: no usable lines")
        else:
            ctx["trace"].append("/lyrics/current: no response" if res is None else "/lyrics/current: empty data")
        return None

    def _parse_cider_lyrics_data(self, c_data: dict, clean_id: str):
        source = c_data.get('source')
        if not isinstance(source, dict):
            source = {}
        timing_type = str(source.get('timingType', 'Line')).strip()
        lines = c_data.get('lines') or []
        timing = timing_type.lower()

        # lines 에 단어 타이밍이 없어도, 같이 내려온 원본 TTML 에는 있을 수 있다
        if timing in ('word', 'syllable') and not has_real_word_sync(lines) and c_data.get('ttml'):
            ttml_lines = parse_ttml_text(str(c_data['ttml']))
            if ttml_lines and has_real_word_sync(ttml_lines):
                lines = ttml_lines

        # Real word-level sync requires explicit Word/Syllable timing AND actual distinct per-word timestamps
        is_word_sync = timing in ('word', 'syllable') and has_real_word_sync(lines)

        # 1. Word-level lyrics directly available
        if is_word_sync:
            return {
                "source": "Cider Word",
                "timingType": "Word",
                "lines": self._normalize_lines(lines, is_word_sync=True),
                "trackId": clean_id
            }

        # 2. Check community variations ONLY for a genuine syllable/word variation
        if clean_id:
            syllable_lines = self._fetch_variation_lyrics(clean_id)
            if syllable_lines:
                return {
                    "source": "Cider Variation",
                    "timingType": "Word",
                    "lines": syllable_lines,
                    "trackId": clean_id
                }

        # 3. Clean Line-level sync (strip any pseudo-words so it renders cleanly as line sync)
        if lines:
            formatted_lines = self._normalize_lines(lines, is_word_sync=False)
            if not formatted_lines:
                return None
            result = {
                "source": source.get('provider', 'Cider Line'),
                "timingType": "Line",
                "lines": formatted_lines,
                "trackId": clean_id
            }
            # 시간 정보가 없는(전부 같은 시작 시각) 가사는 줄을 따라 하이라이트할 수 없다 -> 정적 표시로 표기
            if len(formatted_lines) >= 2 and len({round(l['start'], 1) for l in formatted_lines}) <= 1:
                result["unsynced"] = True
            return result

        return None

    def _fetch_variation_lyrics(self, track_id: str):
        """Checks if Cider community has a genuine syllable/word-timed lyric variation."""
        clean_id = normalize_track_id(track_id)
        var_res = self._http_get(f"/api/v2/lyrics/{clean_id}/variations", LYRICS_TIMEOUT)
        if not var_res or not var_res.get('data'):
            return None

        variations = var_res['data'].get('variations') or []
        target_var = None
        for v in variations:
            st = str(v.get('syncType', '')).lower()
            if st in ('syllable', 'word'):
                target_var = v
                break

        # ONLY proceed if there is an explicit syllable or word variation!
        if not target_var:
            return None

        v_id = target_var.get('variationId')
        if v_id is None:
            return None
        var_data = self._http_get(f"/api/v2/lyrics/{clean_id}/variations/{v_id}?words=true&ttml=true", LYRICS_TIMEOUT)
        if var_data and var_data.get('data'):
            lines = var_data['data'].get('lines') or []
            if has_real_word_sync(lines):
                return self._normalize_lines(lines, is_word_sync=True)

        return None

    def _check_local_ttml(self, title: str, artist: str):
        if not os.path.exists(LYRICS_DIR):
            return None
        c_title = clean_name(title)
        c_artist = clean_name(artist)
        if not c_title:
            return None

        # 예전 조건은 `title in 파일명` 만으로 통과해서(아티스트 검사는 사실상 죽은 코드)
        # 제목이 짧은 곡("Love" 등)에 엉뚱한 가사 파일이 붙을 수 있었다.
        # 1순위: 제목+아티스트가 모두 파일명에 포함, 2순위: 파일명이 제목과 정확히 일치.
        exact = None
        for fn in os.listdir(LYRICS_DIR):
            if not fn.lower().endswith('.ttml'):
                continue
            c_stem = clean_name(os.path.splitext(fn)[0])
            if c_artist and c_title in c_stem and c_artist in c_stem:
                return parse_local_ttml_file(os.path.join(LYRICS_DIR, fn))
            if exact is None and c_stem == c_title:
                exact = fn
        if exact:
            return parse_local_ttml_file(os.path.join(LYRICS_DIR, exact))
        return None

    def _normalize_lines(self, raw_lines, is_word_sync: bool = False):
        out = []
        for l in raw_lines:
            text = (l.get('text') or '').strip()
            # 키는 있는데 값이 null인 경우 float(None)이 터지지 않도록 `or`
            start = float(l.get('start') or 0.0)
            end = float(l.get('end') or 0.0)
            raw_words = l.get('words') or []

            words = []
            if is_word_sync and raw_words:
                for w in raw_words:
                    w_text = (w.get('text') or '').strip()
                    if w_text:
                        w_start = w.get('start')
                        w_end = w.get('end')
                        words.append({
                            "text": w_text,
                            "start": float(start if w_start is None else w_start),
                            "end": float(end if w_end is None else w_end)
                        })

            mark_word_spacing(words, text)
            # 백그라운드 보컬: Cider 가 isBackground 로 알려 주거나, 앞 줄과 겹쳐 시작하는 '(...)' 줄
            prev_end = out[-1]["end"] if out else -1.0
            is_bg = bool(l.get('isBackground')) or (is_paren_wrapped(text) and start < prev_end + 0.25)
            if is_bg:
                words, text = strip_bg_parens(words, text)
            if text or words:
                item = {
                    "start": start,
                    "end": end,
                    "text": text,
                    "words": words
                }
                if is_bg:
                    item["bg"] = True
                out.append(item)
        out.sort(key=lambda x: x['start'])
        return fill_missing_line_ends(out)

    def get_up_next(self):
        """재생 대기열에서 '다음 곡' (제목/아티스트/앨범 아트). 없거나 읽지 못하면 None."""
        res = self._http_get("/api/v2/queue", 2.0)
        data = (res or {}).get('data') or {}
        items = data.get('items') or []
        pos = data.get('position')
        if not isinstance(pos, int) or pos < 0 or pos + 1 >= len(items):
            return None
        attrs = ((items[pos + 1] or {}).get('track') or {}).get('attributes') or {}
        title = attrs.get('name') or ''
        if not title:
            return None
        art = (attrs.get('artwork') or {}).get('url') or ''
        art = art.replace('{w}x{h}', '120x120').replace('{c}', 'bb').replace('{f}', 'png')
        return {"title": title, "artist": attrs.get('artistName') or '', "artworkUrl": art}

    # Playback Controls
    def toggle_playback(self):
        return self._http_post("/api/v2/playback/toggle")

    def play(self):
        return self._http_post("/api/v2/playback/play")

    def pause(self):
        return self._http_post("/api/v2/playback/pause")

    def next_track(self):
        return self._http_post("/api/v2/playback/next")

    def previous_track(self):
        return self._http_post("/api/v2/playback/previous")

    def set_repeat(self, mode: str):
        """mode: 'none' | 'one' | 'all'"""
        if mode not in ('none', 'one', 'all'):
            return None
        return self._http_put("/api/v2/playback/repeat", {"mode": mode})

    def set_shuffle(self, enabled: bool):
        return self._http_put("/api/v2/playback/shuffle", {"enabled": bool(enabled)})

    def seek(self, position_sec: float):
        return self._http_post("/api/v2/playback/seek", {"position": position_sec})
