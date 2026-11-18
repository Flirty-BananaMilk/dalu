"""가사 캐시(메모리 안에만): 한 번 받은 곡은 다시 틀 때 Cider 에 묻지 않고 바로 보여 주고, 다음 곡 가사는 현재 곡이 나오는 동안 미리 받아 둔다.

- Cider 가 가사 하나를 내주는 데 보통 1초 안팎(어떤 곡은 8초 이상)이 걸려서, 곡이 바뀔 때마다 처음부터 받으면 가사가 늦게 나온다.
- 저장하는 것은 이 프로그램이 켜져 있는 동안의 메모리뿐이다(디스크에 쓰지 않는다). 가사가 있는(줄이 있는) 결과만 기억한다.
"""
import threading
from collections import OrderedDict

from cider_client import normalize_track_id


def key_for(track_id, catalog_id=""):
    """같은 곡이면 같은 키: 카탈로그 ID 가 있으면 그것, 없으면 곡 ID ('a.123' 같은 접두사는 뗀다). 둘 다 없으면 ''."""
    cid = normalize_track_id(catalog_id) if catalog_id else ""
    return cid or (normalize_track_id(track_id) if track_id else "")


class LyricsCache:
    def __init__(self, max_items=40):
        self._max = max(1, int(max_items))
        self._items = OrderedDict()
        self._busy = set()
        self._lock = threading.Lock()

    def get(self, key):
        if not key:
            return None
        with self._lock:
            v = self._items.get(key)
            if v is not None:
                self._items.move_to_end(key)
            return v

    def put(self, key, lyrics):
        """줄이 있는 가사만 기억한다(없음·실패는 다시 시도해야 하므로 기억하지 않는다). 기억했으면 True."""
        if not key or not isinstance(lyrics, dict) or not lyrics.get("lines"):
            return False
        with self._lock:
            self._items[key] = lyrics
            self._items.move_to_end(key)
            while len(self._items) > self._max:
                self._items.popitem(last=False)
        return True

    def claim(self, key):
        """미리 받기를 시작해도 되는가: 이미 기억돼 있거나 누가 받는 중이면 False. True 를 받았으면 끝나고 release 한다."""
        if not key:
            return False
        with self._lock:
            if key in self._items or key in self._busy:
                return False
            self._busy.add(key)
            return True

    def release(self, key):
        with self._lock:
            self._busy.discard(key)

    def __len__(self):
        with self._lock:
            return len(self._items)
