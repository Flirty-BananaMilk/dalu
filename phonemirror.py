# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Flirty_BananaMilk — 상업적 이용 금지, 자세한 내용은 LICENSE
"""폰 화면 보기(Dalu Link): 폰이 같은 암호화 연결로 보낸 H.264 조각을, 이 PC 안(127.0.0.1)의 작은 웹소켓 서버를 거쳐 '폰 화면' 창에 넘긴다.

- 바깥에서는 접속할 수 없다: 127.0.0.1 에만 열고, 실행할 때마다 새로 만든 무작위 주소(토큰)를 아는 창만 연결한다. 화면 내용은 저장하지 않는다.
- 창(보는 쪽)으로 보내는 메시지(바이너리): 첫 바이트 1 = 상태(JSON), 2 = 보통 프레임, 3 = 키프레임 + 8바이트 시각 + H.264(Annex-B).
- 창이 보내는 메시지(글자): {"t":"in", ...조작} / {"t":"key"}(키프레임 요청) / {"t":"stop"}.
- 조작(on_input)은 이 모듈이 받아 전달만 한다: 허용·검증은 부르는 쪽(dalu.py)이 한다.
"""
import asyncio
import json
import secrets
import struct
import threading

SEND_QUEUE = 40          # 창이 느릴 때 쌓아 두는 프레임 수: 넘치면 보통 프레임을 버리고 다음 키프레임부터 이어 보낸다


class MirrorHub:
    def __init__(self, on_input=None, on_viewers=None, log=None):
        self._on_input = on_input or (lambda ev: None)
        self._on_viewers = on_viewers or (lambda n: None)
        self._log = log or (lambda s: None)
        self.port = 0
        self.token = ""
        self._loop = None
        self._thread = None
        self._server = None
        self._ready = threading.Event()
        self._clients = {}                     # websocket -> {"q": asyncio.Queue, "need_key": bool}
        self._state = {"state": "idle"}
        self._last_key = None                  # 마지막 키프레임(새 창이 바로 그림을 보여 주려고)
        self.error = ""

    # ---------------------------------------------------------------- 수명
    def start(self):
        """서버를 켠다(이미 켜져 있으면 그대로). -> (포트, 토큰)"""
        if self._thread is not None and self.port:
            return self.port, self.token
        self.token = secrets.token_urlsafe(18)
        self._ready.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="mirror-hub")
        self._thread.start()
        self._ready.wait(8)
        return self.port, self.token

    def stop(self):
        loop = self._loop
        if loop is not None:
            try:
                loop.call_soon_threadsafe(self._shutdown)
            except RuntimeError:
                pass          # 루프가 이미 닫혔다
        self._thread = None
        self.port = 0

    def viewers(self):
        return len(self._clients)

    def _run(self):
        try:
            from websockets.asyncio.server import serve
        except Exception as e:
            self.error = "websockets: " + type(e).__name__
            self._log("mirror: the websockets package is missing")
            self._ready.set()
            return
        loop = asyncio.new_event_loop()
        self._loop = loop
        asyncio.set_event_loop(loop)

        async def main():
            self._server = await serve(self._handler, "127.0.0.1", 0, max_size=1 << 20, ping_interval=20, ping_timeout=30, compression=None)
            self.port = self._server.sockets[0].getsockname()[1]
            self._log(f"mirror: viewer server on 127.0.0.1:{self.port}")
            self._ready.set()
            await self._server.wait_closed()

        try:
            loop.run_until_complete(main())
        except Exception as e:
            if not self._ready.is_set():
                self.error = type(e).__name__
                self._ready.set()
        finally:
            try:
                loop.close()
            except Exception:
                pass
            self._loop = None

    def _shutdown(self):
        if self._server is not None:
            self._server.close()
        for ws in list(self._clients):
            asyncio.ensure_future(ws.close())

    # ---------------------------------------------------------------- 창과의 연결
    async def _handler(self, ws):
        path = getattr(getattr(ws, "request", None), "path", "") or ""
        origin = ""
        try:
            origin = ws.request.headers.get("Origin", "") or ""
        except Exception:
            origin = "?"          # Origin 이 둘 이상이거나 읽지 못하면 검사를 건너뛰지 않고 거부한다
        if path != "/v/" + self.token or origin not in ("", "null", "file://"):          # 토큰을 모르거나, 다른 웹 페이지가 연결하려는 경우
            await ws.close(code=4403, reason="forbidden")
            return
        st = {"q": asyncio.Queue(SEND_QUEUE), "need_key": False}
        self._clients[ws] = st
        self._notify_viewers()
        try:
            await ws.send(b"\x01" + json.dumps(self._state, ensure_ascii=False).encode("utf-8"))
            if self._last_key is not None:
                await ws.send(self._last_key)
            sender = asyncio.ensure_future(self._sender(ws, st))
            try:
                async for msg in ws:
                    if isinstance(msg, bytes):
                        continue
                    try:
                        m = json.loads(msg)
                    except ValueError:
                        continue
                    if isinstance(m, dict):
                        self._on_input(m)
            finally:
                sender.cancel()
        except Exception:
            pass
        finally:
            self._clients.pop(ws, None)
            self._notify_viewers()

    async def _sender(self, ws, st):
        try:
            while True:
                data = await st["q"].get()
                await ws.send(data)
        except Exception:
            pass

    def _notify_viewers(self):
        try:
            self._on_viewers(len(self._clients))
        except Exception:
            pass

    # ---------------------------------------------------------------- 폰에서 온 것을 창으로
    def _broadcast(self, data, key, always=False):
        loop = self._loop
        if loop is None:
            return

        def put():
            for ws, st in list(self._clients.items()):
                if st["need_key"] and not key and not always:
                    continue
                if key and not always:
                    st["need_key"] = False
                try:
                    st["q"].put_nowait(data)
                except asyncio.QueueFull:
                    st["need_key"] = True                 # 느린 창: 쌓인 것을 비우고 다음 키프레임부터
                    try:
                        while True:
                            st["q"].get_nowait()
                    except asyncio.QueueEmpty:
                        pass
                    if key or always:          # 지금 온 것이 키프레임이거나 상태 프레임이면 버리지 않고 맨 앞에 둔다
                        try:
                            st["q"].put_nowait(data)
                            if key:
                                st["need_key"] = False
                        except asyncio.QueueFull:
                            pass
        try:
            loop.call_soon_threadsafe(put)
        except RuntimeError:
            pass          # 서버 루프가 이미 닫혔다(종료 중)

    def set_state(self, state):
        """상태(JSON 가능한 dict)를 기억하고 모든 창에 알린다."""
        self._state = dict(state)
        if state.get("state") not in ("running",):
            self._last_key = None          # 멈춘 화면의 옛 그림을 새 창에 보여 주지 않는다
        self._broadcast(b"\x01" + json.dumps(self._state, ensure_ascii=False).encode("utf-8"), False, always=True)

    def push_frame(self, key, ts, data):
        """폰이 보낸 한 프레임(Annex-B)."""
        if not data:
            return
        msg = (b"\x03" if key else b"\x02") + struct.pack(">Q", int(ts) & 0xFFFFFFFFFFFFFFFF) + data
        if key:
            self._last_key = msg
        self._broadcast(msg, bool(key))
