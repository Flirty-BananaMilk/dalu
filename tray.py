# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Flirty_BananaMilk — 상업적 이용 금지, 자세한 내용은 LICENSE
"""시스템 트레이 아이콘: 노치가 접혀 있어도(또는 가려져 있어도) 설정을 열고, 재시작/종료할 수 있다.
pystray + Pillow 가 없으면 import 에서 실패하고, 앱은 트레이 없이 그대로 동작한다."""
import pystray

LABELS = {
    "ko": {"settings": "설정 열기", "restart": "재시작", "quit": "종료", "tip": "Dalu", "ct_off": "클릭 투과 끄기"},
    "en": {"settings": "Open settings", "restart": "Restart", "quit": "Quit", "tip": "Dalu", "ct_off": "Turn off click-through"},
    "zh": {"settings": "打开设置", "restart": "重新启动", "quit": "退出", "tip": "Dalu", "ct_off": "关闭点击穿透"},
    "ja": {"settings": "設定を開く", "restart": "再起動", "quit": "終了", "tip": "Dalu", "ct_off": "クリック透過をオフ"},
}


def make_icon_image(size=64):
    """앱 아이콘(appicon.py)과 같은 그림."""
    import appicon
    return appicon.make_icon_image(size)


class Tray:
    def __init__(self, on_settings, on_restart, on_quit, get_lang=lambda: "ko", log=None, ct_active=lambda: False, on_ct_off=None):
        self._on_settings, self._on_restart, self._on_quit = on_settings, on_restart, on_quit
        self._ct_active, self._on_ct_off = ct_active, on_ct_off          # 클릭 투과 중일 때만 보이는 "끄기" 항목(노치가 클릭을 받지 못해도 빠져나올 길)
        self._get_lang = get_lang
        self._log = log or (lambda m: None)
        self._icon = None

    def _t(self, key):
        return LABELS.get(self._get_lang(), LABELS["en"])[key]

    def start(self):
        menu = pystray.Menu(
            pystray.MenuItem(lambda item: self._t("settings"), lambda icon, item: self._safe(self._on_settings), default=True),
            pystray.MenuItem(lambda item: self._t("ct_off"), lambda icon, item: self._safe(self._on_ct_off), visible=lambda item: bool(self._on_ct_off and self._ct_active())),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(lambda item: self._t("restart"), lambda icon, item: self._safe(self._on_restart)),
            pystray.MenuItem(lambda item: self._t("quit"), lambda icon, item: self._safe(self._on_quit)),
        )
        self._icon = pystray.Icon("Dalu", make_icon_image(), self._t("tip"), menu)
        self._icon.run_detached()
        return True

    def _safe(self, fn):
        try:
            fn()
        except Exception as e:
            self._log(f"tray action failed: {e!r}")

    def stop(self):
        try:
            if self._icon is not None:
                self._icon.stop()
        except Exception:
            pass
