# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Flirty_BananaMilk — 상업적 이용 금지, 자세한 내용은 LICENSE
"""폰 <-> PC 파일 전송 (Dalu Link). 같은 TLS 연결 위에서 JSON 줄로 조각(192 KiB)을 주고받는다.

메시지(양방향 같은 모양; 보내는 쪽이 offer 를 보낸다):
  {"t":"file_offer","fid","name","size"}            -> 받는 쪽이 {"t":"file_accept","fid","ok","error"} 로 답한다
  {"t":"file_chunk","fid","seq","b64"}              -> 받는 쪽이 {"t":"file_ack","fid","seq"} 로 답한다(보내는 쪽은 아직 확인 못 받은 조각을 WINDOW 개까지만 보낸다)
  {"t":"file_end","fid","n","size","sha256"}        -> 받는 쪽이 크기·SHA-256 을 확인하고 {"t":"file_done","fid","ok","error","name"} 로 답한다
  {"t":"file_cancel","fid"}                          -> 어느 쪽이든 중단
파일 이름은 받는 쪽이 안전하게 고치고(경로·예약 이름 제거) 같은 이름이 있으면 '이름 (1).확장자' 로 저장한다.
파일 내용·이름은 로그에 남기지 않는다(크기만).
"""
import base64
import hashlib
import os
import re
import secrets
import shutil
import threading
import time

CHUNK_BYTES = 192 * 1024
WINDOW = 4                          # 확인(ack)을 받지 못한 채 보낼 수 있는 조각 수
ACK_TIMEOUT = 40                    # 이 시간 동안 확인이 없으면 실패
ACCEPT_TIMEOUT = 25
DONE_TIMEOUT = 90
IDLE_DROP = 120                     # 받는 중 이 시간 조각이 안 오면 버린다
MAX_SIZE = 8 << 30                  # 8 GiB
SLOTS = 3                           # 한 번에 보내는 파일 수(나머지는 차례를 기다린다)
MAX_QUEUED = 64                     # 기다리는 것까지 합친 보내기 수
PROGRESS_EVERY = 0.25

_BAD = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED = {"CON", "PRN", "AUX", "NUL"} | {"COM%d" % i for i in range(1, 10)} | {"LPT%d" % i for i in range(1, 10)}


def safe_name(name):
    """상대가 보낸 파일 이름을 이 PC 에서 안전한 이름으로 고친다(폴더 경로·예약 이름·금지 문자 제거)."""
    name = os.path.basename(str(name or "").replace("\\", "/"))
    name = _BAD.sub("_", name).strip(" .")
    if not name:
        name = "file"
    stem, ext = os.path.splitext(name)
    if stem.upper() in _RESERVED:
        stem = "_" + stem
    if len(stem) + len(ext) > 120:
        stem = stem[:max(1, 120 - len(ext))]
    return stem + ext


def unique_path(folder, name):
    """folder 안에서 겹치지 않는 경로: 이름.확장자, 이름 (1).확장자, ..."""
    stem, ext = os.path.splitext(name)
    p = os.path.join(folder, name)
    n = 1
    while os.path.exists(p):
        p = os.path.join(folder, "%s (%d)%s" % (stem, n, ext))
        n += 1
        if n > 9999:
            break
    return p


class Incoming:
    """받는 중인 파일 하나."""

    def __init__(self, fid, name, size, folder):
        self.fid = fid
        self.name = safe_name(name)
        self.size = int(size)
        self.folder = folder
        os.makedirs(folder, exist_ok=True)
        self.part = os.path.join(folder, ".dalu-%s.part" % fid)
        self._f = open(self.part, "wb")
        self._sha = hashlib.sha256()
        self.got = 0
        self.next = 0
        self.t = time.time()
        self.t0 = self.t
        self.last_emit = 0.0
        self.path = None
        self._mu = threading.RLock()          # 조각을 쓰는 스레드와 취소·끝내기 스레드가 같은 파일을 동시에 만지지 않게

    def write(self, seq, data):
        with self._mu:
            if seq != self.next or self._f is None:
                return False
            if self.got + len(data) > self.size:
                return False
            self._f.write(data)
            self._sha.update(data)
            self.got += len(data)
            self.next += 1
            self.t = time.time()
            return True

    def finish(self, n, size, sha):
        """끝났다: 개수·크기·SHA-256 을 확인하고 최종 이름으로 옮긴다. -> (경로, 오류 이름)"""
        with self._mu:
            return self._finish(n, size, sha)

    def _finish(self, n, size, sha):
        try:
            if self._f is not None:
                self._f.close()
        except Exception:
            pass
        self._f = None
        if int(n) != self.next or int(size) != self.got or self.got != self.size:
            self.abort()
            return None, "size"
        if str(sha).lower() != self._sha.hexdigest():
            self.abort()
            return None, "hash"
        final = unique_path(self.folder, self.name)
        try:
            os.replace(self.part, final)
        except OSError:
            self.abort()
            return None, "write"
        self.path = final
        return final, ""

    def abort(self):
        with self._mu:
            try:
                if self._f is not None:
                    self._f.close()
            except Exception:
                pass
            self._f = None
            try:
                os.remove(self.part)
            except OSError:
                pass


class _Out:
    """보내는 중인 파일 하나."""

    def __init__(self, fid, path, purpose=""):
        self.fid = fid
        self.path = path
        self.purpose = purpose              # "" 이면 보통 파일, "app_update" 면 폰 앱 업데이트(폰이 따로 검사해서 받는다)
        self.name = os.path.basename(path)
        self.size = os.path.getsize(path)
        self.cond = threading.Condition()
        self.acked = -1
        self.accepted = None            # None: 대기, True/False
        self.accept_error = ""
        self.done = None                # None: 대기, (ok, error, name)
        self.canceled = False
        self.lost = False               # 연결이 끊겨서 중단됨
        self.sent = 0
        self.last_emit = 0.0
        self.t0 = time.time()


class Manager:
    """파일 전송 전체. send(msg)->bool 로 상대에게 보내고, emit(event) 로 화면에 알린다.
    folder_fn() -> 받은 파일 저장 폴더, auto_fn() -> 상대가 보낸 파일을 묻지 않고 받는가."""

    def __init__(self, send, emit, folder_fn, auto_fn=lambda: True, log=lambda s: None):
        self._send = send
        self._emit = emit
        self._folder = folder_fn
        self._auto = auto_fn
        self._log = log
        self._lock = threading.Lock()
        self._in = {}
        self._out = {}
        self._slots = threading.BoundedSemaphore(SLOTS)

    # ------------------------------------------------------------ 이벤트
    def _event(self, fid, d, name, size, done, state, error="", path=None, bps=0):
        e = {"type": "phone_file", "fid": fid, "dir": d, "name": name, "size": size, "done": done, "state": state, "error": error, "bps": int(bps)}
        if path:
            e["path"] = path
        try:
            self._emit(e)
        except Exception:
            pass

    def active(self):
        with self._lock:
            return len(self._in) + len(self._out)

    # ------------------------------------------------------------ 보내기
    def send_file(self, path, purpose=""):
        """파일 하나를 폰으로 보낸다(백그라운드). -> (성공, 오류 이름, fid)"""
        try:
            path = os.path.abspath(str(path))
            if not os.path.isfile(path):
                return False, "notfile", ""
            size = os.path.getsize(path)
            if size > MAX_SIZE:
                return False, "toobig", ""
            fid = secrets.token_hex(6)
            o = _Out(fid, path, str(purpose or "")[:20])
        except OSError:
            return False, "read", ""
        with self._lock:
            if len(self._out) >= MAX_QUEUED:
                return False, "busy", ""
            self._out[fid] = o
        threading.Thread(target=self._run_out, args=(o,), daemon=True, name="filexfer-out").start()
        return True, "", fid

    def _fail_out(self, o, error):
        with self._lock:
            self._out.pop(o.fid, None)
        self._event(o.fid, "out", o.name, o.size, o.sent, "canceled" if error == "canceled" else "failed", error)

    def _run_out(self, o):
        slot = False
        offered = False

        def cancel_msg():
            self._send({"t": "file_cancel", "fid": o.fid})

        def stop():
            """취소(이쪽·폰)나 연결 끊김으로 그만둔다. 폰에 알린 뒤였다면 폰도 정리하게 취소를 알린다."""
            if offered and not o.lost:
                cancel_msg()
            self._fail_out(o, "nolink" if o.lost else "canceled")
        try:
            self._event(o.fid, "out", o.name, o.size, 0, "waiting")
            # 한 번에 SLOTS 개만 보낸다: 많이 골라도 빠지는 것 없이 차례로 간다(전에는 8개를 넘으면 '바쁨'으로 빠졌다)
            while not slot:
                if o.canceled:
                    return stop()
                slot = self._slots.acquire(timeout=0.3)
            if o.canceled:
                return stop()
            offer = {"t": "file_offer", "fid": o.fid, "name": o.name, "size": o.size}
            if o.purpose:
                offer["purpose"] = o.purpose
            if not self._send(offer):
                return self._fail_out(o, "nolink")
            offered = True
            with o.cond:
                o.cond.wait_for(lambda: o.accepted is not None or o.canceled, ACCEPT_TIMEOUT)
            if o.canceled:
                return stop()
            if o.accepted is None:
                cancel_msg()
                return self._fail_out(o, "timeout")
            if not o.accepted:
                return self._fail_out(o, o.accept_error or "declined")
            o.t0 = time.time()              # 속도는 실제로 보내기 시작한 때부터 잰다(차례를 기다린 시간 제외)
            sha = hashlib.sha256()
            seq = 0
            with open(o.path, "rb") as f:
                while True:
                    data = f.read(CHUNK_BYTES)
                    if not data:
                        break
                    with o.cond:
                        ok = o.cond.wait_for(lambda: seq - o.acked <= WINDOW or o.canceled, ACK_TIMEOUT)
                        if o.canceled:
                            break
                        if not ok:
                            cancel_msg()
                            return self._fail_out(o, "timeout")
                    sha.update(data)
                    if not self._send({"t": "file_chunk", "fid": o.fid, "seq": seq, "b64": base64.b64encode(data).decode("ascii")}):
                        return self._fail_out(o, "nolink")
                    seq += 1
                    o.sent += len(data)
                    now = time.time()
                    if now - o.last_emit >= PROGRESS_EVERY:
                        o.last_emit = now
                        self._event(o.fid, "out", o.name, o.size, o.sent, "sending", bps=o.sent / max(0.1, now - o.t0))
            if o.canceled:
                return stop()
            if not self._send({"t": "file_end", "fid": o.fid, "n": seq, "size": o.sent, "sha256": sha.hexdigest()}):
                return self._fail_out(o, "nolink")
            with o.cond:
                o.cond.wait_for(lambda: o.done is not None or o.canceled, DONE_TIMEOUT)
            if o.canceled:
                return stop()
            if o.done is None:
                return self._fail_out(o, "timeout")
            ok, err, name = o.done
            with self._lock:
                self._out.pop(o.fid, None)
            self._event(o.fid, "out", o.name, o.size, o.sent if not ok else o.size, "done" if ok else "failed", "" if ok else (err or "failed"))
            self._log("file sent: %d bytes, %s" % (o.size, "ok" if ok else "failed " + str(err)))
        except Exception as e:
            self._log("file send error: %s" % type(e).__name__)
            if offered and not o.lost:
                cancel_msg()
            self._fail_out(o, "error")
        finally:
            if slot:
                self._slots.release()

    def cancel(self, fid):
        with self._lock:
            o = self._out.get(fid)
            i = self._in.pop(fid, None)
        if o is not None:
            with o.cond:
                o.canceled = True
                o.cond.notify_all()
            return True
        if i is not None:
            i.abort()
            self._send({"t": "file_cancel", "fid": fid})
            self._event(fid, "in", i.name, i.size, i.got, "canceled", "canceled")
            return True
        return False

    # ------------------------------------------------------------ 받기·응답
    def handle(self, m):
        """상대가 보낸 file_* 메시지 하나를 처리한다."""
        t = m.get("t")
        fid = str(m.get("fid", ""))[:32]
        try:
            if t == "file_offer":
                self._on_offer(fid, m)
            elif t == "file_chunk":
                self._on_chunk(fid, m)
            elif t == "file_end":
                self._on_end(fid, m)
            elif t == "file_accept":
                o = self._out.get(fid)
                if o:
                    with o.cond:
                        o.accepted = bool(m.get("ok"))
                        o.accept_error = str(m.get("error", ""))[:20]
                        o.cond.notify_all()
            elif t == "file_ack":
                o = self._out.get(fid)
                if o:
                    with o.cond:
                        try:
                            o.acked = max(o.acked, int(m.get("seq")))
                        except (TypeError, ValueError):
                            pass
                        o.cond.notify_all()
            elif t == "file_done":
                o = self._out.get(fid)
                if o:
                    with o.cond:
                        o.done = (bool(m.get("ok")), str(m.get("error", ""))[:20], str(m.get("name", ""))[:200])
                        o.cond.notify_all()
            elif t == "file_cancel":
                with self._lock:
                    o = self._out.get(fid)
                    i = self._in.pop(fid, None)
                if o:
                    with o.cond:
                        o.canceled = True
                        o.cond.notify_all()
                if i:
                    i.abort()
                    self._event(fid, "in", i.name, i.size, i.got, "canceled", "canceled")
        except Exception as e:
            self._log("file message error: %s" % type(e).__name__)
        self._janitor()

    def _janitor(self):
        now = time.time()
        with self._lock:
            stale = [i for i in self._in.values() if now - i.t > IDLE_DROP]
            for i in stale:
                self._in.pop(i.fid, None)
        for i in stale:
            i.abort()
            self._event(i.fid, "in", i.name, i.size, i.got, "failed", "timeout")

    def _on_offer(self, fid, m):
        def refuse(err):
            self._send({"t": "file_accept", "fid": fid, "ok": False, "error": err})
        try:
            size = int(m.get("size"))
        except (TypeError, ValueError):
            return refuse("bad")
        name = safe_name(m.get("name"))
        if not fid or size < 0:
            return refuse("bad")
        if size > MAX_SIZE:
            return refuse("toobig")
        if not self._auto():
            return refuse("declined")
        folder = self._folder()
        try:
            os.makedirs(folder, exist_ok=True)
            if shutil.disk_usage(folder).free < size + (64 << 20):
                return refuse("space")
        except OSError:
            return refuse("write")
        with self._lock:
            if fid in self._in or len(self._in) >= 8:
                return refuse("busy")
            try:
                inc = Incoming(fid, name, size, folder)
            except OSError:
                return refuse("write")
            self._in[fid] = inc
        self._send({"t": "file_accept", "fid": fid, "ok": True})
        self._event(fid, "in", inc.name, size, 0, "receiving")

    def _on_chunk(self, fid, m):
        inc = self._in.get(fid)
        if inc is None:
            return
        try:
            data = base64.b64decode(str(m.get("b64", "")), validate=True)
            seq = int(m.get("seq"))
        except Exception:
            return self._abort_in(inc, "bad")
        if len(data) > CHUNK_BYTES + 16 or not inc.write(seq, data):
            return self._abort_in(inc, "order")
        self._send({"t": "file_ack", "fid": fid, "seq": seq})
        now = time.time()
        if now - inc.last_emit >= PROGRESS_EVERY:
            inc.last_emit = now
            self._event(fid, "in", inc.name, inc.size, inc.got, "receiving", bps=inc.got / max(0.1, now - inc.t0))

    def _abort_in(self, inc, error):
        with self._lock:
            self._in.pop(inc.fid, None)
        inc.abort()
        self._send({"t": "file_done", "fid": inc.fid, "ok": False, "error": error})
        self._event(inc.fid, "in", inc.name, inc.size, inc.got, "failed", error)

    def _on_end(self, fid, m):
        with self._lock:
            inc = self._in.pop(fid, None)
        if inc is None:
            return
        path, err = inc.finish(m.get("n", -1), m.get("size", -1), m.get("sha256", ""))
        if path:
            self._send({"t": "file_done", "fid": fid, "ok": True, "name": os.path.basename(path)})
            self._event(fid, "in", os.path.basename(path), inc.size, inc.size, "done", path=path)
            self._log("file received: %d bytes" % inc.size)
        else:
            self._send({"t": "file_done", "fid": fid, "ok": False, "error": err})
            self._event(fid, "in", inc.name, inc.size, inc.got, "failed", err)

    def link_lost(self):
        """폰 연결이 끊겼다: 진행 중인 전송을 모두 실패로 정리한다."""
        with self._lock:
            outs = list(self._out.values())
            ins = list(self._in.values())
            self._in.clear()
        for o in outs:
            with o.cond:
                o.lost = True
                o.canceled = True
                o.cond.notify_all()
        for i in ins:
            i.abort()
            self._event(i.fid, "in", i.name, i.size, i.got, "failed", "nolink")
