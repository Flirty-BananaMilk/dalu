# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Flirty_BananaMilk — 상업적 이용 금지, 자세한 내용은 LICENSE
"""앱 아이콘(Dalu): 밤하늘 색 둥근 사각 바탕 위쪽에 노치(귀가 달린 검은 판)가 매달려 있고, 그 아래로 초승달이 떠 있다 (달 = 달루).
트레이 아이콘과 설치 파일 아이콘(.ico)이 같은 그림을 쓴다. Pillow 만 필요하다."""
from PIL import Image, ImageChops, ImageDraw, ImageFilter

S = 1024            # 그리는 크기(나중에 줄여서 계단을 없앤다)


def _lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(len(a)))


def _vgrad(size, top, bottom):
    col = Image.new("RGBA", (1, size[1]))
    for y in range(size[1]):
        col.putpixel((0, y), _lerp(top, bottom, y / max(1, size[1] - 1)) + (255,))
    return col.resize(size)


def _tile_mask():
    m = Image.new("L", (S, S), 0)
    ImageDraw.Draw(m).rounded_rectangle((36, 36, S - 36, S - 36), radius=232, fill=255)
    return m


def _notch_mask():
    """위는 평평하고 양쪽 위 모서리가 바깥으로 말려 올라가는(귀) 노치 모양."""
    m = Image.new("L", (S, S), 0)
    d = ImageDraw.Draw(m)
    cx, w, top, bottom, r, e = S // 2, 480, 36, 306, 120, 84
    x0, x1 = cx - w // 2, cx + w // 2
    d.rounded_rectangle((x0, top - 200, x1, bottom), radius=r, fill=255)       # 위로 길게 그려 타일 가장자리에서 잘리게 한다
    d.rectangle((x0, top - 200, x1, top + r), fill=255)                         # 윗쪽 모서리는 직각
    for sx, ex in ((x0, -1), (x1, 1)):                                            # 귀: 옆면 위쪽에 사각형을 붙이고 바깥 아래를 둥글게 파낸다
        left = sx - e if ex < 0 else sx
        d.rectangle((left, top, left + e, top + e), fill=255)
        ccx = sx - e if ex < 0 else sx + e
        d.ellipse((ccx - e, top + e - e, ccx + e, top + e + e), fill=0)
    return ImageChops.multiply(m, _tile_mask())


def _crescent_mask(cx, cy, r, bite_dx, bite_dy, bite_r):
    m = Image.new("L", (S, S), 0)
    d = ImageDraw.Draw(m)
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=255)
    d.ellipse((cx + bite_dx - bite_r, cy + bite_dy - bite_r, cx + bite_dx + bite_r, cy + bite_dy + bite_r), fill=0)
    return m


def render(size=256):
    tile = _tile_mask()
    base = _vgrad((S, S), (58, 48, 128), (16, 16, 46))                           # 밤하늘: 위 보랏빛 -> 아래 짙은 남색
    # 달 뒤의 은은한 빛무리
    halo = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(halo).ellipse((512 - 300, 640 - 300, 512 + 300, 640 + 300), fill=(176, 140, 255, 60))
    base.alpha_composite(halo.filter(ImageFilter.GaussianBlur(80)))
    # 초승달
    cm = _crescent_mask(498, 636, 232, 112, -64, 200)
    moon = _vgrad((S, S), (255, 238, 196), (255, 168, 86))
    base.paste(moon, (0, 0), cm)
    # 달 가장자리 안쪽 빛
    rim = ImageChops.subtract(cm, cm.filter(ImageFilter.MinFilter(9)))
    base.paste(Image.new("RGBA", (S, S), (255, 255, 255, 70)), (0, 0), rim)
    # 작은 별 둘
    d = ImageDraw.Draw(base)
    for (x, y, rr) in ((762, 520, 22), (820, 690, 14)):
        d.ellipse((x - rr, y - rr, x + rr, y + rr), fill=(255, 246, 220, 255))
    # 노치(검정) + 가는 테두리 빛
    nm = _notch_mask()
    base.paste(Image.new("RGBA", (S, S), (0, 0, 0, 255)), (0, 0), nm)
    edge = ImageChops.subtract(nm, nm.filter(ImageFilter.MinFilter(9)))
    base.paste(Image.new("RGBA", (S, S), (255, 255, 255, 90)), (0, 0), edge)
    # 알림 점(노치 가운데): 달과 함께 '소리가 나는 중'이라는 느낌
    d.ellipse((512 - 28, 176 - 28, 512 + 28, 176 + 28), fill=(255, 214, 140, 255))
    out = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    out.paste(base, (0, 0), tile)
    return out.resize((size, size), Image.LANCZOS)


def make_icon_image(size=64):
    return render(size)


def save_ico(path):
    big = render(256)
    big.save(path, format="ICO", sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (24, 24), (16, 16)])


if __name__ == "__main__":
    import sys
    save_ico(sys.argv[1] if len(sys.argv) > 1 else "dalu.ico")
