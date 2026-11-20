# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Flirty_BananaMilk — 상업적 이용 금지, 자세한 내용은 LICENSE
"""새 버전 알림.

공개 웹사이트(GitHub Pages)의 작은 파일 version.json 한 개를 읽어 지금 버전보다 새 버전이 있는지 본다.
 - 자동으로 받는 것은 그 JSON 하나뿐이다(최대 8KB). 새 버전이 있으면 알려 주기만 한다.
 - 설치 파일은 사용자가 설정 › 정보에서 "지금 업데이트"를 눌렀을 때만 받는다(download_installer): GitHub 릴리스의 주소만, version.json 에 적힌 SHA-256·크기와 'MZ' 머리가 모두 맞아야 실행한다(run_installer).
 - 보내는 것은 평범한 HTTPS 요청 하나뿐이다(앱 이름과 버전만 담긴 User-Agent). 계정·기기 식별자·설정은 보내지 않는다.
 - 설정 › 일반 › "새 버전 알림" 으로 끌 수 있고, 켜 두면 앱을 켠 뒤 한 번과 그 뒤 6시간마다 확인한다. 같은 버전은 노치 알림으로는 한 번만 알리고, 노치 안 '업데이트' 칩은 업데이트할 때까지 남는다.
"""
import hashlib
import json
import os
import re
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

URL = "https://flirty-bananamilk.github.io/dalu/version.json"
DOWNLOAD_URL = "https://flirty-bananamilk.itch.io/dalu"
ALLOWED_HOSTS = ("flirty-bananamilk.itch.io", "flirty-bananamilk.github.io", "github.com")   # 알림이 열어 줄 수 있는 주소(그 밖의 주소는 버리고 기본 주소를 쓴다)
MAX_BYTES = 8192
UNPUBLISHED = {"unpublished": True}      # version.json 이 아직 공개되지 않았다(404/410): 인터넷 문제가 아니라 "알릴 새 버전이 없다"는 뜻
# 앱 안에서 설치 파일을 받을 수 있는 곳: GitHub 릴리스의 파일 주소뿐이다(받는 도중 다른 곳으로 넘겨도 아래 호스트만 따라간다)
DL_HOSTS = ("github.com", "objects.githubusercontent.com", "release-assets.githubusercontent.com")
MIN_SIZE, MAX_SIZE = 5_000_000, 200_000_000
CHECK_EVERY = 6 * 3600
FIRST_DELAY = 45          # 시작하고 이 시간(초) 뒤에 처음 확인한다: 켜지는 동안 다른 일과 겹치지 않게
WAKE_EVERY = 3600         # 확인할 때가 됐는지 이 간격(초)으로 본다


def parse_version(s):
    """'1.0.4' 또는 'v1.0.4' -> (1, 0, 4). 형식이 다르면 None."""
    m = re.match(r"^\s*v?(\d{1,4})\.(\d{1,4})\.(\d{1,4})\s*$", str(s if s is not None else ""))
    return tuple(int(x) for x in m.groups()) if m else None


def is_newer(latest, current):
    a, b = parse_version(latest), parse_version(current)
    return bool(a and b and a > b)


def safe_url(url):
    """https 이고 허용된 주소만 통과시킨다. 아니면 기본 다운로드 주소."""
    m = re.match(r"^https://([A-Za-z0-9.-]+)(?::443)?(/[^\s]*)?$", str(url or ""))
    if m and m.group(1).lower() in ALLOWED_HOSTS:
        if m.group(1).lower() == "github.com" and not (m.group(2) or "").lower().startswith("/flirty-bananamilk/"):
            return DOWNLOAD_URL          # github.com 은 우리 저장소 아래만(남의 저장소 주소를 알림이 열어 주지 않는다)
        return str(url)
    return DOWNLOAD_URL


def parse_download(d, version):
    """version.json 의 "download": {"url", "sha256", "size"} 를 검사한다. 주소는 GitHub 릴리스의 Dalu-<같은 버전>-Setup.exe 만, 해시는 64자리 16진수, 크기는 5~200MB 만 통과."""
    if not isinstance(d, dict):
        return None
    url, sha, size = d.get("url"), str(d.get("sha256") or "").lower(), d.get("size")
    m = re.match(r"^https://github\.com/Flirty-BananaMilk/dalu/releases/download/[A-Za-z0-9._-]+/Dalu-(\d+\.\d+\.\d+)-Setup\.exe$", str(url or ""))
    if not m or m.group(1) != version or not re.fullmatch("[0-9a-f]{64}", sha):
        return None
    if not isinstance(size, int) or isinstance(size, bool) or not MIN_SIZE <= size <= MAX_SIZE:
        return None
    return {"url": url, "sha256": sha, "size": size}


def parse_manifest(raw):
    """version.json 본문(bytes/str) -> {'version', 'url'} 또는 None."""
    try:
        if isinstance(raw, (bytes, bytearray)):
            if len(raw) > MAX_BYTES:
                return None
            raw = raw.decode("utf-8-sig")
        d = json.loads(raw.lstrip("\ufeff") if isinstance(raw, str) else raw)
    except Exception:
        return None
    if not isinstance(d, dict) or parse_version(d.get("version")) is None:
        return None
    v = ".".join(str(n) for n in parse_version(d["version"]))
    out = {"version": v, "url": safe_url(d.get("url"))}
    dl = parse_download(d.get("download"), v)
    if dl:
        out["download"] = dl
    return out


def fetch(current, timeout=8, url=URL, opener=None):
    """version.json 을 받아 파싱한다. 실패하면 None(네트워크 없음·서버 오류·잘못된 내용 모두)."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": f"Dalu/{current}", "Accept": "application/json", "Cache-Control": "no-cache"})
        op = opener or urllib.request.build_opener(_SafeRedirect(ALLOWED_HOSTS, ("https",))).open          # version.json 을 받다가 허용 밖의 주소나 http 로 넘기면 따라가지 않는다
        with op(req, timeout=timeout) as r:
            return parse_manifest(r.read(MAX_BYTES + 1))
    except urllib.error.HTTPError as e:
        return dict(UNPUBLISHED) if e.code in (404, 410) else None
    except Exception:
        return None


class UpdateChecker:
    """뒤에서 앱을 켠 뒤 한 번과 그 뒤 6시간마다 확인하고, 새 버전이면 한 번만 이벤트를 보낸다."""

    def __init__(self, current, log=None, push=None, enabled=None, state_path="", fetch_fn=None,
                 first_delay=FIRST_DELAY, wake_every=WAKE_EVERY, check_every=CHECK_EVERY, now=time.time):
        self.current = current
        self._log = log or (lambda *_: None)
        self._push = push or (lambda *_: None)
        self._enabled = enabled or (lambda: True)
        self._path = state_path
        self._fetch = fetch_fn or (lambda: fetch(self.current))
        self._first_delay, self._wake, self._every, self._now = first_delay, wake_every, check_every, now
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None
        self._state = self._load()
        # 새 버전이 마지막으로 확인된 결과{'version','url'}. 다시 켜도 설정 창에 계속 보이게 저장해 두고, 지금 버전이 그만큼 올랐으면 버린다
        lt = self._state.get("latest")
        self._latest = lt if lt and is_newer(lt["version"], self.current) else None

    # ---- 저장: 마지막 확인 시각과 이미 알린 버전
    def _load(self):
        try:
            with open(self._path, encoding="utf-8") as f:
                d = json.load(f)
            if isinstance(d, dict):
                lt = parse_manifest(json.dumps(d.get("latest"))) if isinstance(d.get("latest"), dict) else None
                return {"lastCheck": float(d.get("lastCheck") or 0), "notified": str(d.get("notified") or ""), "latest": lt}
        except Exception:
            pass
        return {"lastCheck": 0.0, "notified": "", "latest": None}

    def _save(self):
        if not self._path:
            return
        try:
            os.makedirs(os.path.dirname(self._path), exist_ok=True)
            tmp = self._path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._state, f)
            os.replace(tmp, self._path)
        except Exception as e:
            self._log(f"update state save failed: {e!r}")

    # ---- 확인
    def check(self, announce=True):
        """한 번 확인한다. 반환: {'status': 'new'|'latest'|'error', 'version', 'url'}.
        announce 가 참이면 새 버전을 아직 알리지 않았을 때 이벤트를 보낸다(사용자가 '지금 확인'을 누른 경우는 거짓: 화면에서 바로 보여 준다)."""
        res = self._fetch()
        if res is None:
            return {"status": "error"}
        if res.get("unpublished"):                           # 알릴 새 버전 정보가 아직 없다 = 지금 버전이 최신
            with self._lock:
                self._state["lastCheck"] = self._now()
                self._latest = None
                self._state["latest"] = None
                self._save()
            return {"status": "latest", "version": self.current, "url": DOWNLOAD_URL}
        with self._lock:
            self._state["lastCheck"] = self._now()
            if is_newer(res["version"], self.current):
                self._latest = res
                self._state["latest"] = res
                send = announce and self._state["notified"] != res["version"]
                if send:
                    self._state["notified"] = res["version"]
                out = {"status": "new", **res}
            else:
                self._latest = None
                self._state["latest"] = None
                send = False
                out = {"status": "latest", "version": res["version"], "url": res["url"]}
            self._save()
        if send:
            try:
                self._push({"type": "update_available", "version": res["version"], "url": res["url"]})
            except Exception as e:
                self._log(f"update push failed: {e!r}")
        return out

    def snapshot(self):
        with self._lock:
            return dict(self._latest) if self._latest else None

    def url(self):
        s = self.snapshot()
        return s["url"] if s else DOWNLOAD_URL

    def due(self):
        with self._lock:
            return self._now() - self._state["lastCheck"] >= self._every

    # ---- 뒤에서 도는 반복
    def start(self):
        if self._thread:
            return
        self._thread = threading.Thread(target=self._run, daemon=True, name="update-check")
        self._thread.start()

    def stop(self):
        self._stop.set()

    def _run(self):
        wait = self._first_delay
        first = True
        while not self._stop.wait(wait):
            wait = self._wake
            try:
                if self._enabled() and (first or self.due()):          # 앱을 켠 뒤 첫 확인은 마지막 확인 시각과 상관없이 한다(저장해 둔 옛 결과도 바로 다시 확인)
                    r = self.check(announce=True)
                    self._log(f"update check: {r.get('status')} {r.get('version', '')}")
            except Exception as e:
                self._log(f"update check failed: {e!r}")
            first = False


# ---------------------------------------------------------------- 앱 안에서 업데이트: 받기 -> 검증 -> 설치 프로그램 실행
class UpdateError(Exception):
    """code: host(허용되지 않은 주소) | size | hash | format(받은 파일이 약속과 다름) | network | run(설치 프로그램을 못 띄움) | stuck(띄웠는데 아무 일도 없음)"""

    def __init__(self, code, detail=""):
        super().__init__(f"{code} {detail}".strip())
        self.code = code


class _SafeRedirect(urllib.request.HTTPRedirectHandler):
    def __init__(self, hosts, schemes):
        self.hosts, self.schemes = hosts, schemes

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        p = urllib.parse.urlparse(newurl)
        if p.scheme not in self.schemes or (p.hostname or "").lower() not in self.hosts:
            raise UpdateError("host", newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _rm(path):
    try:
        os.remove(path)
    except OSError:
        pass


def download_installer(info, dest_dir, progress=None, current="", timeout=20, hosts=DL_HOSTS, schemes=("https",)):
    """info = {"url", "sha256", "size"}. 파일을 dest_dir 에 받아 크기·해시·'MZ' 머리를 확인한 뒤에만 최종 이름으로 바꿔 경로를 돌려준다.
    하나라도 어긋나면 받은 파일을 지우고 UpdateError. hosts/schemes 는 시험에서만 바꾼다."""
    url, want_sha, want_size = info["url"], info["sha256"], int(info["size"])
    p = urllib.parse.urlparse(url)
    name = os.path.basename(p.path)
    if p.scheme not in schemes or (p.hostname or "").lower() not in hosts or not re.fullmatch(r"Dalu-\d+\.\d+\.\d+-Setup\.exe", name):
        raise UpdateError("host", url)
    os.makedirs(dest_dir, exist_ok=True)
    for f in os.listdir(dest_dir):                         # 이 폴더는 우리 것이다: 지난번 파일을 치운다
        if f.endswith(".part") or re.fullmatch(r"Dalu-[\d.]+-Setup\.exe", f):
            _rm(os.path.join(dest_dir, f))
    final = os.path.join(dest_dir, name)
    part = final + ".part"
    opener = urllib.request.build_opener(_SafeRedirect(hosts, schemes))
    h, got = hashlib.sha256(), 0
    try:
        req = urllib.request.Request(url, headers={"User-Agent": f"Dalu/{current}" if current else "Dalu"})
        with opener.open(req, timeout=timeout) as r, open(part, "wb") as f:
            cl = r.headers.get("Content-Length")
            if cl and cl.isdigit() and int(cl) != want_size:
                raise UpdateError("size", f"announced {cl}")
            while True:
                chunk = r.read(65536)
                if not chunk:
                    break
                got += len(chunk)
                if got > want_size:
                    raise UpdateError("size", "too many bytes")
                h.update(chunk)
                f.write(chunk)
                if progress:
                    progress(got, want_size)
        if got != want_size:
            raise UpdateError("size", f"{got} of {want_size}")
        if h.hexdigest() != want_sha:
            raise UpdateError("hash")
        with open(part, "rb") as f:
            if f.read(2) != b"MZ":
                raise UpdateError("format")
        os.replace(part, final)
        return final
    except UpdateError:
        _rm(part)
        raise
    except Exception as e:
        _rm(part)
        if isinstance(e, OSError) and not isinstance(e, urllib.error.URLError) and not isinstance(e, (ConnectionError, TimeoutError)):
            raise UpdateError("disk", repr(e)) from e          # 디스크 부족·권한 오류는 인터넷 문제가 아니다(안내를 다르게)
        raise UpdateError("network", repr(e)) from e


def run_installer(path, popen=subprocess.Popen):
    """받아 검증한 Setup.exe 를 조용히(-Quiet) 따로 떼어 실행한다. 설치 프로그램이 돌고 있는 Dalu 를 끄고, 파일을 바꾸고, 다시 띄운다(설정·기록은 그대로)."""
    try:
        popen([path, "-Quiet"], creationflags=0x00000008 | 0x00000200, close_fds=True, cwd=os.path.dirname(path))    # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    except Exception as e:
        raise UpdateError("run", repr(e)) from e


class Updater:
    """'지금 업데이트' 버튼: 사용자가 눌렀을 때만 한 번 돌고, 진행 상태를 status() 로 보여 준다."""

    def __init__(self, checker, dest_dir, log=None, download=download_installer, run=run_installer, stuck_after=90):
        self._checker, self._dest, self._log = checker, dest_dir, log or (lambda *_: None)
        self._download, self._run, self._stuck = download, run, stuck_after
        self._lock = threading.Lock()
        self._st = {"state": "idle", "percent": 0, "error": ""}

    def status(self):
        with self._lock:
            return dict(self._st)

    def _set(self, **kw):
        with self._lock:
            self._st.update(kw)

    def start(self):
        """반환: started | busy | none(받을 파일 정보가 없다: 화면이 다운로드 페이지를 열어 준다)."""
        snap = self._checker.snapshot()
        info = snap.get("download") if snap else None
        if not info:
            return {"status": "none"}
        with self._lock:
            if self._st["state"] in ("downloading", "installing"):
                return {"status": "busy"}
            self._st.update(state="downloading", percent=0, error="")
        threading.Thread(target=self._work, args=(info,), daemon=True, name="update-install").start()
        return {"status": "started"}

    def _work(self, info):
        try:
            def prog(got, total):
                self._set(percent=int(got * 100 / total) if total else 0)
            path = self._download(info, self._dest, progress=prog, current=self._checker.current)
            self._set(state="installing", percent=100)
            self._log(f"update: starting installer {path}")
            self._run(path)
            time.sleep(self._stuck)                         # 설치 프로그램이 정상이면 그 사이에 이 앱이 꺼진다
            self._set(state="error", error="stuck")
        except UpdateError as e:
            self._log(f"update failed: {e}")
            self._set(state="error", error=e.code)
        except Exception as e:
            self._log(f"update failed: {e!r}")
            self._set(state="error", error="network")
