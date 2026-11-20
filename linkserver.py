# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Flirty_BananaMilk — 상업적 이용 금지, 자세한 내용은 LICENSE
"""Dalu Link 서버: 폰 앱(Dalu Link)이 TLS 로 접속해 오면 폰의 알림·배터리를 받고, 답장·폰 찾기 같은 명령을 보낸다.

- 기본은 같은 네트워크(LAN)에서만 오간다(포트 53821~). 계정은 없다. 모바일 데이터처럼 직접 닿지 않을 때를 위해 선택적으로
  '중계 서버'(dalu-relay, Cloudflare Worker)를 쓸 수 있다: PC 가 먼저 중계 서버에 접속해 두고, 폰이 오면 그 길로 TLS 를 그대로 통과시킨다.
  중계 서버에는 암호문만 지나가므로(PC 인증서 지문을 폰이 확인) 내용을 볼 수 없다. 기본은 꺼짐.
- 인증서는 이 PC 에서 한 번 만든 자체 서명 인증서다. 폰은 QR 에 든 인증서 지문(SHA-256)으로 서버를 '고정'해서 믿는다.
- 페어링: QR 에 5분짜리 일회용 토큰이 들어 있다. 폰이 토큰으로 접속하면 기기 비밀(256비트)을 내려 주고, 이후에는 기기 id + 비밀로 접속한다.
  비밀은 PC 에 해시로만 저장한다.
- 메시지는 줄바꿈으로 구분한 UTF-8 JSON(한 줄 최대 1 MiB). 알림 내용은 메모리에서 노치로만 넘기고 저장하지 않는다(로그에는 길이만).
자세한 규약은 dalu-link/DESIGN.md.
"""
import asyncio
import datetime
import hashlib
import hmac
import http.server
import json
import os
import secrets
import socket
import ssl
import threading
import time
from urllib.parse import quote, urlparse

DEFAULT_PORT = 53821
DISCOVERY_PORT = 53823        # 폰이 'Dalu 가 어디 있지?' 하고 묻는 UDP 포트(저장된 주소가 안 맞을 때: PC 의 IP 가 바뀐 경우)
PAIR_SECONDS = 300
LINE_LIMIT = 1 << 20
HELLO_TIMEOUT = 10.0
MAX_UNAUTH = 24                # 아직 인증하지 못한 동시 연결 상한(같은 네트워크의 누군가가 연결만 잔뜩 열어 두는 것을 막는다)
IDLE_TIMEOUT = 60.0
PROTOCOL = 1
RELAY_DEFAULT = "wss://dalu-link-relay.dalu-link-relay.workers.dev"   # 설정에서 주소를 비워 두고 '모바일 데이터에서도 연결'을 켰을 때 쓰는 기본 중계 서버(제작자의 Cloudflare Worker, dalu-relay 프로젝트; 암호문만 지나간다)
RELAY_MAX_PIPES = 6           # 중계로 동시에 이어지는 폰 연결 수
RELAY_CHUNK = 16384           # 중계에 보내는 바이트 조각(서버 한도 64 KiB 보다 훨씬 작게)


# ---------------------------------------------------------------- 인증서
def ensure_cert(directory):
    """directory 에 cert.pem / key.pem 이 없으면 새로 만든다(ECDSA P-256 자체 서명, 10년). -> (cert 경로, key 경로)"""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID

    os.makedirs(directory, exist_ok=True)
    cert_path, key_path = os.path.join(directory, "cert.pem"), os.path.join(directory, "key.pem")
    if os.path.exists(cert_path) and os.path.exists(key_path):
        return cert_path, key_path
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Dalu Link")])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now - datetime.timedelta(days=1))
            .not_valid_after(now + datetime.timedelta(days=3650)).sign(key, hashes.SHA256()))
    with open(key_path, "wb") as f:
        f.write(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    with open(cert_path, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))
    return cert_path, key_path


def cert_fingerprint(cert_path):
    """인증서(DER)의 SHA-256 을 소문자 hex 64자로."""
    from cryptography import x509
    from cryptography.hazmat.primitives import serialization
    with open(cert_path, "rb") as f:
        c = x509.load_pem_x509_certificate(f.read())
    return hashlib.sha256(c.public_bytes(serialization.Encoding.DER)).hexdigest()


# ---------------------------------------------------------------- 주소 / QR 주소
def local_ips():
    """이 PC 의 사설 IPv4 주소들(폰이 접속할 후보: 같은 네트워크 주소 + Tailscale 같은 가상 사설망 주소). 기본 경로의 주소를 앞에 둔다."""
    found = []

    def add(ip):
        if ip and ip not in found and _is_private(ip):
            found.append(ip)
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))          # 실제로 보내지 않는다: 기본 경로의 출발 주소만 알아낸다
        add(s.getsockname()[0])
        s.close()
    except Exception:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            add(info[4][0])
    except Exception:
        pass
    return found


def _is_private(ip):
    try:
        a = [int(x) for x in ip.split(".")]
    except ValueError:
        return False
    if len(a) != 4:
        return False
    if a[0] == 10 or (a[0] == 192 and a[1] == 168) or (a[0] == 172 and 16 <= a[1] <= 31):
        return True
    if a[0] == 100 and 64 <= a[1] <= 127:         # 100.64.0.0/10: Tailscale 같은 가상 사설망이 주는 주소(모바일 데이터에서도 닿는다)
        return True
    return False


def normalize_relay(url):
    """사용자가 적은 중계 서버 주소를 'wss://호스트[:포트]' 로 정리한다. 안전하지 않은(ws://) 주소는 이 PC 자신(127.0.0.1/localhost, 시험용)만 허용. 못 쓰는 값이면 ''."""
    u = (url or "").strip()
    if not u or len(u) > 200:
        return ""
    if "://" not in u:
        u = "wss://" + u
    try:
        pr = urlparse(u)
    except ValueError:
        return ""
    host = (pr.hostname or "").lower()
    if not host or pr.username or pr.password or pr.path.strip("/") or pr.query or pr.fragment:
        return ""
    scheme = {"https": "wss", "wss": "wss", "http": "ws", "ws": "ws"}.get(pr.scheme)
    if scheme is None:
        return ""
    if scheme == "ws" and host not in ("127.0.0.1", "localhost", "::1"):
        return ""
    try:
        port = pr.port
    except ValueError:
        return ""
    return "%s://%s%s" % (scheme, host if ":" not in host else "[" + host + "]", ":%d" % port if port else "")


def pair_uri(hosts, port, fingerprint, token, name, relay="", room=""):
    uri = "dalulink://pair?h=%s&p=%d&f=%s&t=%s&n=%s" % (",".join(hosts), port, fingerprint, token, quote(name or "PC", safe=""))
    if relay and room:
        uri += "&r=%s&k=%s" % (quote(relay, safe=""), room)
    return uri


def qr_svg(text, scale=4):
    """text 를 QR 코드 SVG 문자열로(segno, 순수 파이썬). 크기 속성 대신 viewBox 만 두어서 화면에서 상자 크기에 맞게 커진다. 없으면 ''."""
    try:
        import io
        import segno
        buf = io.BytesIO()
        segno.make(text, error="m").save(buf, kind="svg", scale=scale, border=2, dark="#000000", light="#ffffff", xmldecl=False, nl=False, omitsize=True)
        return buf.getvalue().decode("utf-8")
    except Exception:
        return ""


# ---------------------------------------------------------------- 폰 앱 파일(APK)의 버전 읽기
def _axml_strings(d, off):
    """AXML 의 문자열 풀(chunk type 0x0001)을 읽는다 -> 문자열 목록. 형식이 이상하면 예외."""
    import struct
    _typ, hsize, size, count, _styles, flags, s_start = struct.unpack_from("<HHIIIII", d, off)[:7]
    offs = struct.unpack_from("<%dI" % count, d, off + 28)
    utf8 = bool(flags & 0x100)
    base = off + s_start
    out = []
    for o in offs:
        p = base + o
        if utf8:
            n = d[p]
            p += 1 + (1 if n & 0x80 else 0)          # 글자 수(1~2바이트)
            b = d[p]
            p += 1
            if b & 0x80:
                b = ((b & 0x7F) << 8) | d[p]
                p += 1
            out.append(d[p:p + b].decode("utf-8", "replace"))
        else:
            n = struct.unpack_from("<H", d, p)[0]
            p += 2
            if n & 0x8000:
                n = ((n & 0x7FFF) << 16) | struct.unpack_from("<H", d, p)[0]
                p += 2
            out.append(d[p:p + n * 2].decode("utf-16-le", "replace"))
    return out


def parse_manifest_version(axml):
    """APK 안의 AndroidManifest.xml(바이너리 XML)에서 {package, code, name} 을 읽는다. 못 읽으면 None.
    (<manifest> 요소의 package, versionCode, versionName 속성만 본다. 서명은 여기서 확인하지 않는다: 설치할 때 폰이 확인한다.)"""
    import struct
    try:
        d = bytes(axml)
        if len(d) < 16 or struct.unpack_from("<H", d, 0)[0] != 0x0003:
            return None
        strings = []
        off = 8
        while off + 8 <= len(d):
            typ, hsize, size = struct.unpack_from("<HHI", d, off)
            if size < 8 or off + size > len(d):
                return None
            if typ == 0x0001:
                strings = _axml_strings(d, off)
            elif typ == 0x0102:              # 처음 나오는 시작 요소 = <manifest>
                name_i = struct.unpack_from("<I", d, off + 20)[0]
                if name_i >= len(strings) or strings[name_i] != "manifest":
                    return None
                attr_start, attr_size, attr_count = struct.unpack_from("<HHH", d, off + 24)
                out = {"package": "", "code": 0, "name": ""}
                for k in range(attr_count):
                    a = off + 16 + attr_start + k * attr_size
                    _ns, nm, raw, _sz, _r0, dtype, data = struct.unpack_from("<IIIHBBI", d, a)
                    key = strings[nm] if nm < len(strings) else ""
                    if key == "versionCode" and dtype in (0x10, 0x11):
                        out["code"] = data
                    elif key in ("package", "versionName"):
                        si = raw if raw != 0xFFFFFFFF else (data if dtype == 0x03 else 0xFFFFFFFF)
                        if si < len(strings):
                            out["package" if key == "package" else "name"] = strings[si]
                return out
            off += size
    except Exception:
        return None
    return None


_APK_CACHE = {}


def apk_meta(path):
    """폰 앱 설치 파일의 {package, code, name, size, sha256}. 없거나 앱 파일이 아니면 None. (같은 파일은 다시 읽지 않는다)"""
    try:
        st = os.stat(path)
        key = (os.path.abspath(path), st.st_mtime_ns, st.st_size)
        hit = _APK_CACHE.get(key)
        if hit is not None:
            return dict(hit)
        import zipfile
        with zipfile.ZipFile(path) as z:
            info = parse_manifest_version(z.read("AndroidManifest.xml"))
        if not info or info["code"] <= 0 or info["package"] != "app.dalu.link":
            return None
        with open(path, "rb") as f:
            sha = hashlib.sha256(f.read()).hexdigest()
        meta = {"package": info["package"], "code": int(info["code"]), "name": str(info["name"])[:20], "size": st.st_size, "sha256": sha}
        _APK_CACHE.clear()
        _APK_CACHE[key] = meta
        return dict(meta)
    except Exception:
        return None


# ---------------------------------------------------------------- 폰 앱 설치 파일을 LAN 으로 내려 주는 작은 HTTP 서버
APK_PORT = 53822
APK_MINUTES = 15
APK_NAME = "dalu-link.apk"


class ApkServer:
    """설치용 APK 를 같은 네트워크의 폰에 내려 주는 아주 작은 HTTP 서버: 주소 두 개(/ 안내 페이지, /dalu-link.apk)만 있고 나머지는 404.
    설정의 '폰 앱 연결' 화면에서 요청했을 때만 켜고 15분 뒤 저절로 끈다. 파일은 누구나 받을 수 있는 앱 설치 파일일 뿐이다(개인 정보 없음)."""

    def __init__(self, apk_path, log=None):
        self._path = apk_path
        self._log = log or (lambda m: None)
        self._httpd = None
        self._thread = None
        self._timer = None
        self._mu = threading.RLock()          # start/stop 이 서로 다른 스레드(화면·타이머)에서 불린다
        self._page = b""
        self.port = 0
        self.sha256 = ""
        self.size = 0

    def available(self):
        return os.path.isfile(self._path)

    def start(self):
        """켜고 포트를 돌려준다(이미 켜져 있으면 시간만 연장). APK 가 없으면 0."""
        with self._mu:
            return self._start()

    def _start(self):
        if not self.available():
            return 0
        with open(self._path, "rb") as f:
            data = f.read()
        self.sha256 = hashlib.sha256(data).hexdigest()
        self.size = len(data)
        outer = self
        if True:
            page = ("<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'><title>Dalu Link</title>"
                    "<body style='font-family:sans-serif;padding:24px;max-width:480px;margin:auto'><h2>Dalu Link</h2>"
                    "<p>Dalu(윈도우 노치)와 이 폰을 잇는 앱이에요. 아래 버튼으로 받아 설치하세요. 설치할 때 '출처를 알 수 없는 앱' 허용이 필요할 수 있어요.</p>"
                    "<p><a href='/" + APK_NAME + "' style='display:inline-block;padding:14px 22px;background:#222;color:#fff;border-radius:10px;text-decoration:none'>앱 받기 (%.1f MB)</a></p>"
                    "<p style='font-size:12px;color:#666;word-break:break-all'>SHA-256: " % (self.size / 1048576.0) + self.sha256 + "</p></body>").encode("utf-8")
            self._page = page          # 다시 켤 때마다 새로 만든다(앱 파일이 바뀌었는데 옛 해시가 안내 페이지에 남던 것)

        if self._httpd is None:
            class H(http.server.BaseHTTPRequestHandler):
                timeout = 15          # 응답 없는 연결이 스레드를 영영 붙잡지 않게

                def log_message(self, *a):
                    pass

                def do_HEAD(self):
                    self._head = True          # 본문 없이 머리글만 돌려준다
                    self.do_GET()

                def do_GET(self):
                    path = self.path.split("?", 1)[0]
                    if path in ("/", "/index.html"):
                        self._send(200, "text/html; charset=utf-8", outer._page)
                    elif path == "/" + APK_NAME:
                        try:
                            with open(outer._path, "rb") as f:
                                body = f.read()
                        except OSError:
                            self._send(404, "text/plain", b"not found")
                            return
                        self._send(200, "application/vnd.android.package-archive", body, {"Content-Disposition": 'attachment; filename="%s"' % APK_NAME})
                    else:
                        self._send(404, "text/plain", b"not found")

                def _send(self, code, ctype, body, extra=None):
                    self.send_response(code)
                    self.send_header("Content-Type", ctype)
                    self.send_header("Content-Length", str(len(body)))
                    for k, v in (extra or {}).items():
                        self.send_header(k, v)
                    self.end_headers()
                    if not getattr(self, "_head", False):
                        self.wfile.write(body)

            httpd = None
            for p in range(APK_PORT, APK_PORT + 10):
                try:
                    httpd = http.server.ThreadingHTTPServer(("0.0.0.0", p), H)
                    self.port = p
                    break
                except OSError:
                    continue
            if httpd is None:
                return 0
            self._httpd = httpd
            self._thread = threading.Thread(target=httpd.serve_forever, daemon=True, name="link-apk")
            self._thread.start()
            self._log(f"link: serving the phone app on port {self.port} for {APK_MINUTES} minutes")
        if self._timer is not None:
            self._timer.cancel()
        self._timer = threading.Timer(APK_MINUTES * 60, self.stop)
        self._timer.daemon = True
        self._timer.start()
        return self.port

    def stop(self):
        with self._mu:
            self._stop()

    def _stop(self):
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None
        h, self._httpd = self._httpd, None
        if h is not None:
            try:
                h.shutdown()
                h.server_close()
            except Exception:
                pass
            self.port = 0


# ---------------------------------------------------------------- 서버
class LinkServer:
    """asyncio TLS 서버를 별도 스레드에서 돌린다. on_event(dict) 는 폰이 보낸 메시지(notif / notif_gone / battery ...)와 연결 변화를 받는다."""

    def __init__(self, directory, on_event=None, log=None, pc_name=None, discovery_port=DISCOVERY_PORT):
        self._dir = directory
        self._disc_port = discovery_port
        self._disc_stop = threading.Event()
        self._disc_ready = threading.Event()
        self._disc_thread = None
        self._on_event = on_event or (lambda e: None)
        self._log = log or (lambda m: None)
        self._pc_name = pc_name or socket.gethostname()
        self._devices_path = os.path.join(directory, "devices.json")
        self._lock = threading.Lock()
        self._devices = self._load_devices()          # id -> {name, hash}
        self._pairs = []                              # 열려 있는 페어링 토큰들 [{"token", "expires"}]: 화면을 다시 열어 QR 을 새로 만들어도 아직 안 쓴 앞 QR 이 5분간 유효하다(최대 5개)
        self._sessions = {}                           # id -> _Session
        self._relay_url = ""                          # 정리된 중계 서버 주소('' = 사용 안 함)
        self._relay_room = ""
        self._room_lock = threading.Lock()
        self._relay_task = None
        self._relay_pipes = 0
        self._unauth = 0                              # 인증 전인 연결 수
        self._relay_pipe_tasks = set()                # 열려 있는 중계 데이터 연결 작업(중계를 끄면 함께 끊는다)
        self.relay_state = "off"                      # off | connecting | online | offline | error
        self._loop = None
        self._server = None
        self._thread = None
        self._ready = threading.Event()
        self.port = 0
        self.fingerprint = ""
        self.error = ""

    # ---- 저장
    def _load_devices(self):
        try:
            with open(self._devices_path, encoding="utf-8") as f:
                d = json.load(f)
            return {str(k): {"name": str(v.get("name", "")), "hash": str(v.get("hash", ""))} for k, v in d.items() if isinstance(v, dict)}
        except Exception:
            return {}

    def _save_devices(self):
        try:
            os.makedirs(self._dir, exist_ok=True)
            tmp = self._devices_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._devices, f, ensure_ascii=False)
            os.replace(tmp, self._devices_path)
        except Exception as e:
            self._log(f"link: could not save the device list: {e!r}")

    # ---- 수명
    def start(self, port=DEFAULT_PORT):
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, args=(port,), daemon=True, name="link-server")
        self._thread.start()
        self._ready.wait(10)
        if self.port and self._disc_port:
            self._disc_thread = threading.Thread(target=self._discovery_loop, daemon=True, name="link-discovery")
            self._disc_thread.start()
            self._disc_ready.wait(2)                  # 소켓이 열린 뒤에 start() 가 돌아오게(바로 묻는 폰·시험이 놓치지 않게)

    def _discovery_loop(self):
        """폰이 보낸 'dalulink?' 에 이 PC 의 포트로 답한다. 서버 인증서 지문을 아는 폰(= 페어링했던 폰)에게만 답하고, 초당 20개를 넘는 요청은 무시한다.
        답에는 포트와 PC 이름뿐이고, 어차피 폰이 지문으로 서버를 확인하므로 가짜 답으로는 아무것도 얻지 못한다."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("0.0.0.0", self._disc_port))
            s.settimeout(0.5)
        except OSError as e:
            self._log(f"link: discovery is off ({type(e).__name__})")
            self._disc_ready.set()
            return
        self._disc_ready.set()
        recent = []
        per_src = {}
        try:
            while not self._disc_stop.is_set():
                try:
                    data, addr = s.recvfrom(512)
                except socket.timeout:
                    continue
                except OSError:
                    break
                now = time.time()
                recent = [t for t in recent if now - t < 1.0]
                src = addr[0] if addr else ""
                mine = [t for t in per_src.get(src, []) if now - t < 1.0]
                if len(per_src) > 512:
                    per_src = {k: v for k, v in per_src.items() if v and now - v[-1] < 1.0}
                if len(mine) >= 20 or len(recent) >= 100:          # 한 주소가 전체 한도를 다 쓰지 못하게 주소별로도 센다(브로드캐스트 폭주로 진짜 폰이 못 찾던 것)
                    continue
                mine.append(now)
                per_src[src] = mine
                recent.append(now)
                try:
                    m = json.loads(data.decode("utf-8"))
                except Exception:
                    continue
                if (isinstance(m, dict) and m.get("t") == "dalulink?" and m.get("v") == PROTOCOL and self.port
                        and hmac.compare_digest(str(m.get("fp", "")), self.fingerprint)):
                    try:
                        s.sendto(json.dumps({"t": "dalulink!", "v": PROTOCOL, "port": self.port, "pc": self._pc_name}, ensure_ascii=False).encode("utf-8"), addr)
                    except OSError:
                        pass
        finally:
            s.close()

    def stop(self):
        self._disc_stop.set()
        loop = self._loop
        if loop is not None:
            loop.call_soon_threadsafe(self._shutdown)

    def _shutdown(self):
        if self._server is not None:
            self._server.close()
        for s in list(self._sessions.values()):
            s.close()
        tasks = list(asyncio.all_tasks(self._loop))               # 남은 연결·중계 작업을 취소하고, 정리될 시간을 준 뒤 멈춘다
        for t in tasks:
            t.cancel()
        self._loop.create_task(self._finish(tasks))

    async def _finish(self, tasks):
        if tasks:
            await asyncio.wait(tasks, timeout=2.5)
        await asyncio.sleep(0.2)                                  # 닫히는 연결(TLS)이 정리될 한 박자
        self._loop.stop()

    def _run(self, port):
        loop = asyncio.new_event_loop()
        self._loop = loop
        asyncio.set_event_loop(loop)
        try:
            cert, key = ensure_cert(os.path.join(self._dir, "tls"))
            self.fingerprint = cert_fingerprint(cert)
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ctx.minimum_version = ssl.TLSVersion.TLSv1_2
            ctx.load_cert_chain(cert, key)
            last = None
            for p in range(port, port + 20):
                try:
                    self._server = loop.run_until_complete(asyncio.start_server(self._handle, "0.0.0.0", p, ssl=ctx, limit=LINE_LIMIT))
                    self.port = p
                    break
                except OSError as e:
                    last = e
            if not self.port:
                self.error = f"port: {last!r}"
                self._log(f"link: could not listen: {last!r}")
                self._ready.set()
                return
            self._log(f"link: listening on port {self.port}")
            self._ready.set()
            self._relay_apply()
            loop.run_forever()
        except Exception as e:
            self.error = repr(e)
            self._log(f"link: server error: {e!r}")
            self._ready.set()
        finally:
            try:
                loop.close()
            except Exception:
                pass
            self._loop = None

    # ---- 중계 서버(선택): 모바일 데이터처럼 직접 닿지 않는 폰을 위해
    def _room_id(self):
        """이 PC 의 중계 '방' 번호: 처음에 한 번 무작위(128비트)로 만들어 저장한다. 이걸 아는 폰만 이 PC 방으로 들어올 수 있고, 들어와도 TLS(지문 고정)와 기기 비밀이 따로 필요하다."""
        with self._room_lock:                         # 이벤트 루프 스레드와 화면 쪽 스레드가 동시에 불러도 같은 번호가 나오게
            if self._relay_room:
                return self._relay_room
            path = os.path.join(self._dir, "relay.json")
            try:
                with open(path, encoding="utf-8") as f:
                    r = str(json.load(f).get("room", ""))
                if len(r) == 32 and all(c in "0123456789abcdef" for c in r):
                    self._relay_room = r
                    return r
            except Exception:
                pass
            r = secrets.token_hex(16)
            try:
                os.makedirs(self._dir, exist_ok=True)
                with open(path, "w", encoding="utf-8") as f:
                    json.dump({"room": r}, f)
            except Exception as e:
                self._log(f"link: could not save the relay room: {e!r}")
            self._relay_room = r
            return r

    def set_relay(self, url):
        """중계 서버 주소를 바꾼다('' 이면 끈다). 어느 스레드에서든 부를 수 있다. -> 정리된 주소('' = 꺼짐/잘못된 값)"""
        norm = normalize_relay(url)
        if norm == self._relay_url:
            return norm
        self._relay_url = norm
        if self._loop is not None:
            self._loop.call_soon_threadsafe(self._relay_apply)
        return norm

    def relay_info(self):
        return {"url": self._relay_url, "state": self.relay_state if self._relay_url else "off", "room": self._room_id() if self._relay_url else ""}

    def _relay_apply(self):
        """(이벤트 루프 안) 주소가 바뀌었으면 중계 작업을 다시 시작한다."""
        if self._relay_task is not None:
            self._relay_task.cancel()
            self._relay_task = None
        for t in list(self._relay_pipe_tasks):          # 중계를 끄거나 주소를 바꿨으면 이미 이어진 중계 연결도 끊는다(꺼도 옛 연결이 남던 것)
            t.cancel()
        self._relay_pipe_tasks.clear()
        if self._relay_url and self.port:
            self.relay_state = "connecting"
            self._relay_task = self._loop.create_task(self._relay_main(self._relay_url, self._room_id()))
        else:
            self.relay_state = "off"

    async def _relay_main(self, base, room):
        try:
            from websockets.asyncio.client import connect
        except Exception:
            self.relay_state = "error"
            self._log("link: relay is off (the websockets package is missing)")
            return
        backoff = 2.0
        while True:
            try:
                async with connect("%s/v1/%s/host" % (base, room), ping_interval=25, ping_timeout=20, max_size=1 << 16, open_timeout=15, close_timeout=1) as ws:
                    self.relay_state = "online"
                    backoff = 2.0
                    self._log("link: connected to the relay server")
                    async for raw in ws:
                        if not isinstance(raw, str):
                            continue
                        try:
                            m = json.loads(raw)
                        except ValueError:
                            continue
                        sid = m.get("sid") if isinstance(m, dict) and m.get("t") == "open" else None
                        if isinstance(sid, str) and len(sid) == 16 and all(c in "0123456789abcdef" for c in sid) and self._relay_pipes < RELAY_MAX_PIPES:
                            pt = self._loop.create_task(self._relay_pipe(base, room, sid))
                            self._relay_pipe_tasks.add(pt)
                            pt.add_done_callback(self._relay_pipe_tasks.discard)
                self.relay_state = "offline"
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.relay_state = "offline"
                self._log(f"link: relay connection failed ({type(e).__name__}); retrying in {int(backoff)} s")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 60.0)

    async def _relay_pipe(self, base, room, sid):
        """폰 한 대 분: 중계의 데이터 연결과 이 PC 의 TLS 서버(127.0.0.1)를 바이트 그대로 이어 준다(TLS 는 폰과 이 서버 사이에서 끝난다)."""
        from websockets.asyncio.client import connect
        self._relay_pipes += 1
        writer = None
        try:
            async with connect("%s/v1/%s/pipe/%s" % (base, room, sid), ping_interval=None, max_size=1 << 16, open_timeout=10, close_timeout=1) as ws:
                reader, writer = await asyncio.open_connection("127.0.0.1", self.port)

                async def up():                       # 중계 -> TLS 서버
                    async for data in ws:
                        if isinstance(data, bytes):
                            writer.write(data)
                            await writer.drain()

                async def down():                     # TLS 서버 -> 중계
                    while True:
                        data = await reader.read(RELAY_CHUNK)
                        if not data:
                            return
                        await ws.send(data)

                tasks = [asyncio.ensure_future(up()), asyncio.ensure_future(down())]
                try:
                    await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                finally:
                    for t in tasks:
                        t.cancel()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self._log(f"link: relay pipe ended ({type(e).__name__})")
        finally:
            self._relay_pipes -= 1
            if writer is not None:
                try:
                    writer.close()
                except Exception:
                    pass

    # ---- 페어링
    def pair_start(self):
        """새 일회용 토큰으로 페어링을 연다. -> {'uri', 'expires', 'hosts', 'port'}"""
        token = secrets.token_urlsafe(24)
        expires = time.time() + PAIR_SECONDS
        with self._lock:
            self._pairs = [p for p in self._pairs if time.time() < p["expires"]][-4:] + [{"token": token, "expires": expires}]
        hosts = local_ips()
        relay = self._relay_url
        room = self._room_id() if relay else ""
        return {"uri": pair_uri(hosts, self.port, self.fingerprint, token, self._pc_name, relay, room), "expires": int(expires), "hosts": hosts, "port": self.port, "relay": relay}

    def pair_cancel(self):
        with self._lock:
            self._pairs = []

    def forget(self, device_id):
        with self._lock:
            self._devices.pop(device_id, None)
            self._save_devices()
        s = self._sessions.get(device_id)
        if s is not None and self._loop is not None:
            self._loop.call_soon_threadsafe(s.close)

    def devices(self):
        with self._lock:
            out = []
            for i, d in self._devices.items():
                s = self._sessions.get(i)
                out.append({"id": i, "name": d["name"], "connected": s is not None, "app_code": getattr(s, "app_code", 0) if s else 0, "app_name": getattr(s, "app_name", "") if s else ""})
            return out

    def connected_ids(self):
        return list(self._sessions.keys())

    # ---- 명령 보내기(Dalu 쪽 스레드에서 부른다)
    def send(self, device_id, msg):
        s = self._sessions.get(device_id)
        if s is None or self._loop is None:
            return False
        asyncio.run_coroutine_threadsafe(s.send(msg), self._loop)
        return True

    def send_any(self, msg):
        """연결된 첫 기기에 보낸다(폰이 하나뿐인 보통의 경우). 보냈으면 그 기기 id, 없으면 None."""
        for i in list(self._sessions.keys()):
            if self.send(i, msg):
                return i
        return None

    def request(self, device_id, msg, result_type, timeout=8.0):
        """msg 를 보내고 같은 rid 의 result_type 답을 기다린다(차단 호출). -> 답 dict 또는 None."""
        s = self._sessions.get(device_id)
        if s is None or self._loop is None:
            return None
        rid = secrets.token_hex(6)
        msg = dict(msg, rid=rid)
        fut = asyncio.run_coroutine_threadsafe(s.request(msg, result_type, rid, timeout), self._loop)
        try:
            return fut.result(timeout + 2)
        except Exception:
            return None

    # ---- 연결 처리(asyncio)
    async def _handle(self, reader, writer):
        peer = writer.get_extra_info("peername")
        sess = None
        if self._unauth >= MAX_UNAUTH:
            try:
                writer.close()
            except Exception:
                pass
            return
        self._unauth += 1
        counted = True
        try:
            line = await asyncio.wait_for(reader.readline(), HELLO_TIMEOUT)
            hello = json.loads(line.decode("utf-8")) if line else {}
            if not isinstance(hello, dict):
                hello = {}
            if hello.get("t") != "hello" or int(hello.get("v", 0)) != PROTOCOL:
                await _write(writer, {"t": "deny", "reason": "protocol"})
                return
            dev_id = str(hello.get("id", ""))[:64]
            name = str(hello.get("name", ""))[:64] or "Android"
            if not dev_id:
                await _write(writer, {"t": "deny", "reason": "id"})
                return
            welcome = {"t": "welcome", "v": PROTOCOL, "pc": self._pc_name}
            if self._relay_url:
                welcome["relay"] = {"url": self._relay_url, "room": self._room_id()}
            token = hello.get("token")
            secret = hello.get("secret")
            if token:
                with self._lock:
                    now = time.time()
                    hit = next((p for p in self._pairs if now < p["expires"] and hmac.compare_digest(str(token), p["token"])), None)
                    ok = hit is not None
                    if ok:
                        self._pairs.remove(hit)                  # 일회용
                        new_secret = secrets.token_urlsafe(32)
                        self._devices[dev_id] = {"name": name, "hash": hashlib.sha256(new_secret.encode()).hexdigest()}
                        self._save_devices()
                if not ok:
                    await asyncio.sleep(0.5)          # 틀린 토큰을 연달아 시도하는 속도를 늦춘다
                    await _write(writer, {"t": "deny", "reason": "token"})
                    return
                welcome["secret"] = new_secret
                self._log(f"link: paired with a new phone ({name})")
            else:
                with self._lock:
                    d = self._devices.get(dev_id)
                ok = bool(d) and bool(secret) and hmac.compare_digest(hashlib.sha256(str(secret).encode()).hexdigest(), d["hash"])
                if not ok:
                    await asyncio.sleep(0.5)
                    await _write(writer, {"t": "deny", "reason": "unknown"})
                    return
                name = d["name"] or name
            await _write(writer, welcome)
            self._unauth -= 1          # 인증을 마쳤다: 이제 인증 전 연결 수에서 뺀다
            counted = False
            old = self._sessions.get(dev_id)
            sess = _Session(dev_id, name, writer)
            try:                                                  # 폰 앱의 버전(없으면 0: 업데이트 기능이 없는 옛 버전)
                sess.app_code = max(0, min(int(hello.get("ac") or 0), 10 ** 9))
            except (TypeError, ValueError):
                sess.app_code = 0
            sess.app_name = str(hello.get("an") or "")[:20] if sess.app_code else ""
            self._sessions[dev_id] = sess
            if old is not None:
                old.close()
            self._on_event({"t": "link_connected", "id": dev_id, "name": name, "app_code": sess.app_code, "app_name": sess.app_name})
            while True:
                line = await asyncio.wait_for(reader.readline(), IDLE_TIMEOUT)
                if not line:
                    break
                try:
                    m = json.loads(line.decode("utf-8"))
                except Exception:
                    continue
                if not isinstance(m, dict):                       # 문자열·숫자 같은 JSON 은 무시한다(연결을 끊지 않는다)
                    continue
                t = m.get("t")
                if t == "ping":
                    await sess.send({"t": "pong"})
                elif t == "pong":
                    pass
                elif sess.deliver(m):
                    pass
                elif t in ("link_connected", "link_disconnected"):
                    pass                                          # 이 두 종류는 서버가 스스로 만드는 안내다: 상대가 같은 이름으로 보내도 받지 않는다(파일 전송 취소·화면 공유 종료를 일으키지 못하게)
                else:
                    m["device"] = dev_id
                    self._on_event(m)
        except (asyncio.TimeoutError, asyncio.IncompleteReadError, ConnectionError, ssl.SSLError, ValueError, asyncio.LimitOverrunError):
            pass
        except Exception as e:
            self._log(f"link: connection error: {type(e).__name__}")
        finally:
            if sess is not None:
                if self._sessions.get(sess.id) is sess:
                    del self._sessions[sess.id]
                    self._on_event({"t": "link_disconnected", "id": sess.id, "name": sess.name})
                sess.close()
            if counted:
                self._unauth -= 1
            try:
                writer.close()
            except Exception:
                pass


class _Session:
    def __init__(self, dev_id, name, writer):
        self.id = dev_id
        self.name = name
        self.app_code = 0                 # 폰 앱의 버전 번호·이름(hello 의 ac/an)
        self.app_name = ""
        self._writer = writer
        self._waiters = {}                # rid -> (결과 종류, Future)
        self._lock = asyncio.Lock()

    async def send(self, msg):
        async with self._lock:
            await _write(self._writer, msg)

    async def request(self, msg, result_type, rid, timeout):
        fut = asyncio.get_running_loop().create_future()
        self._waiters[rid] = (result_type, fut)
        try:
            await self.send(msg)
            return await asyncio.wait_for(fut, timeout)
        except Exception:
            return None
        finally:
            self._waiters.pop(rid, None)

    def deliver(self, m):
        """어떤 요청의 답이면 그 요청에 넘기고 True."""
        rid = m.get("rid")
        w = self._waiters.get(rid) if rid else None
        if w and w[0] == m.get("t") and not w[1].done():
            w[1].set_result(m)
            return True
        return False

    def close(self):
        """바로 끊는다(abort): TLS 정상 종료는 상대가 응답할 때까지 기다려서, 응답 없는 폰이면 한참 걸린다."""
        for _, fut in list(self._waiters.values()):          # 답을 기다리던 요청은 시간 초과를 기다리지 않고 바로 풀어 준다
            try:
                if not fut.done():
                    fut.set_result(None)
            except Exception:
                pass
        try:
            self._writer.transport.abort()
        except Exception:
            try:
                self._writer.close()
            except Exception:
                pass


async def _write(writer, msg):
    writer.write((json.dumps(msg, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8"))
    await writer.drain()
