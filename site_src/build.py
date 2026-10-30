"""Dalu 웹사이트 만들기: site_src/ (문구, 스타일, 스크립트) -> docs/ (GitHub Pages 에 올라가는 정적 파일)

    python site_src/build.py

- 4개 언어 페이지(docs/ko, en, zh, ja)는 같은 틀에 strings.json 의 문구를 넣어 만든다.
- 모든 문구가 HTML 안에 그대로 들어 있어서 JavaScript 가 꺼져 있어도 내용이 보인다.
- 스크롤 연동 장면(고정 무대)의 구간은 아래 T 의 트랙 높이(svh)에서 계산해 CSS 로 쓴다.
- 앱 화면 이미지는 환경변수로 원본을 가리키면 webp 로 변환한다(APP_SHOTS = 정지 화면 PNG 폴더, SETTINGS_SHOTS = 설정 창 PNG 폴더).
"""
import json
import os
import re
import shutil
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "site_src"
OUT = ROOT / "docs"
ASSETS = OUT / "assets"
LANGS = ["ko", "en", "zh", "ja"]
BASE = "https://flirty-bananamilk.github.io/dalu/"
ITCH = "https://flirty-bananamilk.itch.io/dalu"
GH = "https://github.com/Flirty-BananaMilk/dalu"
S = json.loads((SRC / "strings.json").read_text(encoding="utf-8"))
SCENES = ["music", "pomo", "shelf", "agenda", "buds"]
LYRICS = ["Streetlights bloom along the river.", "Every window hums a quiet tune.", "Carry me past the midnight bridges."]
# 장면별 트랙 높이(svh). 무대는 그 안에서 위에 고정된다.
T = {"hero": 320, "lyr": 360, "ch": 560, "gl": 330, "dk": 260}
HERO_FRAMES, DOCK_FRAMES = 44, 34

STAMP = """/* Hallmark · shape: Pinned scenes, each driven by the scroll · genre: atmospheric · theme: custom · job: try · idea: "The page is the desktop: the real notch opens on a real wallpaper as you scroll." · vibe: "slate dusk, amber light, moving glass"
 * paper: oklch(15.5% 0.012 235) · accent: oklch(80% 0.13 78) · display: Funnel Display · body: Albert Sans · hero: a wallpaper stage where the notch opens frame by frame while the headline rises away · nav: one plain row above the first scene, wordmark left, languages and one action right · footer: ruled strip, wordmark, links, photo credits · imagery: screenshots (rendered from the app's own UI with sample data, 78 frames in two sequences), photographs 3 library · signature: the real notch unfolding with the scroll
 * axes: dark/geometric-sans/warm · posture: restrained · contrast: pass · fold: pass · v2.0.0 */
/* Hallmark · pre-emit critique: P4 H4 E4 S4 R3 V4 · weakest: R, five pinned scenes is a lot of choreography; kept because the user asked for Apple-style scroll scenes, and each scene has one idea */
/* Hallmark · waive 42 · nav is a wordmark left with languages and one action right, a plain row above the first scene · the languages are the nav's real content on a four-language page, so the common bar shape is the honest one */
/* Hallmark · dismissed 23 · the giant 9 beside the equalizer is the page's one graphic numeral, a real count of bands, set once in the accent */
/* Hallmark · answered F8 · the user asked for Apple-style scroll scenes, so several pinned scenes share one rule: a tall track, a sticky stage, the scroll as the timeline */
"""


# ---------------------------------------------------------------- 스크롤 구간 계산
def pin(t, v=100.0):
    """트랙 높이 t(svh), 화면 v(svh) 일 때 무대가 고정되는 구간을 cover 타임라인 %로."""
    return v / (t + v) * 100, t / (t + v) * 100


def pc(scene, f):
    a, b = pin(T[scene])
    return a + (b - a) * f


def rng(scene, f0, f1):
    return f"cover {pc(scene, f0):.2f}% cover {pc(scene, f1):.2f}%"


def crossfade(scene, name, sels, bounds, h, move=True, minop=0.0):
    """sels[i] 가 bounds 의 지점에서 차례로 바뀐다. 앞 것은 사라지고 다음 것이 나타난다(겹치는 구간 2h)."""
    css, n = [], len(sels)
    for i, sel in enumerate(sels):
        cs = 0.0 if i == 0 else pc(scene, bounds[i - 1] - h)
        ce = 100.0 if i == n - 1 else pc(scene, bounds[i] + h)
        span = ce - cs
        pts = []
        tf_in, tf_out = ("translateY(2.5svh)", "translateY(-2.5svh)") if move else ("none", "none")
        if i > 0:
            a1 = pc(scene, bounds[i - 1] + h)
            pts.append((0.0, minop, tf_in))
            pts.append(((a1 - cs) / span * 100, 1, "none"))
        else:
            pts.append((0.0, 1, "none"))
        if i < n - 1:
            b0 = pc(scene, bounds[i] - h)
            pts.append(((b0 - cs) / span * 100, 1, "none"))
            pts.append((100.0, minop, tf_out))
        else:
            pts.append((100.0, 1, "none"))
        kf = f"{name}-{i}"
        body = " ".join(f"{p:.2f}% {{ opacity: {o}; transform: {tf}; }}" for p, o, tf in pts)
        css.append(f"@keyframes {kf} {{ {body} }}")
        css.append(f"{sel} {{ animation: {kf} linear both; animation-timeline: --{scene}; animation-range: cover {cs:.2f}% cover {ce:.2f}%; }}")
    return "\n    ".join(css)


def scene_css():
    words = sum(len(l.split()) for l in LYRICS)
    word_rules = []
    for j in range(words):
        f0 = 0.10 + 0.66 * j / words
        f1 = min(f0 + 0.66 / words * 1.7, 0.95)
        word_rules.append(f".lyrics .words span:nth-of-type({j + 1}) {{ animation-range: {rng('lyr', f0, f1)}; }}")
    pages = [f".chapter .pg:nth-child({i + 1})" for i in range(5)]
    rails = [f".chapter .rail li:nth-child({i + 1})" for i in range(5)]
    bounds = [(i + 1) / 5 for i in range(4)]
    gl_names = [f".glass .glass__names p:nth-child({i + 1})" for i in range(3)]
    gb = [0.36, 0.70]
    gl_imgs = "\n    ".join(
        f"@keyframes gl-img-{k} {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}\n    .glass .glass__stack img[data-wp=\"{w}\"] {{ animation: gl-img-{k} linear both; animation-timeline: --gl; animation-range: {rng('gl', gb[k - 1] - 0.07, gb[k - 1] + 0.07)}; }}"
        for k, w in ((1, "b"), (2, "c")))

    def track(s, sel):
        return f"{sel}.track {{ height: {T[s]}svh; view-timeline: --{s} block; }}"

    word_block = "\n    ".join(word_rules)
    pg_block = crossfade('ch', 'kf-pg', pages, bounds, 0.04)
    rail_block = crossfade('ch', 'kf-rail', rails, bounds, 0.04, move=False, minop=0.38)
    gl_block = crossfade('gl', 'kf-gl', gl_names, gb, 0.05)
    return f"""
/* ---- scroll scenes: only where scroll timelines exist and motion is welcome; everywhere else every scene is an ordinary block in its final state ---- */
@supports (animation-timeline: view()) {{
  @media (prefers-reduced-motion: no-preference) {{
    @keyframes fx-out {{ from {{ opacity: 1; transform: none; visibility: visible; }} to {{ opacity: 0; transform: translateY(-5svh); visibility: hidden; }} }}
    @keyframes fx-in {{ from {{ opacity: 0; transform: translateY(5svh); }} to {{ opacity: 1; transform: none; }} }}
    @keyframes fx-zoom {{ from {{ transform: scale(1); }} to {{ transform: scale(1.1); }} }}
    @keyframes word-on {{ from {{ opacity: 0.16; }} to {{ opacity: 1; }} }}
    .hero .stage, .lyrics .stage, .chapter .stage, .glass .stage, .dock .stage {{ position: sticky; top: var(--banner-height, 0px); height: 100svh; min-height: 0; }}
    {track('hero', '.hero')}
    .hero .bg {{ animation: fx-zoom linear both; animation-timeline: --hero; animation-range: cover 0% cover 100%; }}
    .hero__a {{ animation: fx-out linear both; animation-timeline: --hero; animation-range: {rng('hero', 0.36, 0.56)}; }}
    .hero__b {{ display: block; opacity: 0; animation: fx-in linear both; animation-timeline: --hero; animation-range: {rng('hero', 0.60, 0.80)}; }}

    {track('lyr', '.lyrics')}
    .lyrics .words span {{ animation: word-on linear both; animation-timeline: --lyr; }}
    {word_block}
    .lyrics__cap {{ opacity: 0; animation: fx-in linear both; animation-timeline: --lyr; animation-range: {rng('lyr', 0.80, 0.94)}; }}

    {track('ch', '.chapter')}
    .chapter .stage {{ display: grid; grid-template-rows: auto minmax(0, 1fr); gap: var(--space-lg); padding-block: var(--space-lg); }}
    .chapter__head {{ margin-bottom: 0; }}
    .chapter .pages {{ grid-template: minmax(0, 1fr) / minmax(0, 1fr); gap: 0; min-height: 0; }}
    .chapter .pg {{ grid-area: 1 / 1; grid-template-rows: minmax(0, 1fr) auto; min-height: 0; }}
    .chapter .pg figure {{ min-height: 0; display: grid; align-items: center; }}
    .chapter .pg img {{ height: auto; max-height: 100%; min-height: 0; }}
    {pg_block}
    {rail_block}

    {track('gl', '.glass')}
    .glass .stage {{ grid-template-rows: auto minmax(0, 1fr) auto; padding-block: var(--space-lg); }}
    .glass fieldset {{ display: none; }}
    .glass .glass__stack {{ min-height: 0; }}
    .glass .glass__stack img {{ height: auto; max-height: 100%; align-self: center; opacity: 0; transition: none; }}
    .glass .glass__stack img:first-child {{ opacity: 1; }}
    .glass .glass__names {{ display: grid; }}
    {gl_imgs}
    {gl_block}

    {track('dk', '.dock')}
    .dock .bg {{ animation: fx-zoom linear both; animation-timeline: --dk; animation-range: cover 0% cover 100%; }}
  }}
}}
"""


def build_css():
    tokens = (SRC / "tokens.css").read_text(encoding="utf-8")
    base = (SRC / "base.css").read_text(encoding="utf-8")
    site = (SRC / "site.css").read_text(encoding="utf-8")
    return STAMP + "\n" + tokens + "\n" + base + "\n" + site + scene_css()


# ---------------------------------------------------------------- HTML
def H(x):
    """제목: | 는 줄바꿈해도 되는 자리(<wbr>)"""
    return escape(x).replace("|", "<wbr>")


def img(name, lang, wp, alt, sizes, w1, w2, h2, eager=False, extra=""):
    base = f"../assets/{name}-{wp}-{lang}" if wp else f"../assets/{name}-{lang}"
    srcset = f"{base}-{w1}.webp {w1}w, {base}-{w2}.webp {w2}w"
    load = 'fetchpriority="high"' if eager else 'loading="lazy" decoding="async"'
    return f'<img src="{base}-{w1}.webp" srcset="{srcset}" sizes="{sizes}" width="{w2}" height="{h2}" alt="{escape(alt)}" {load}{extra}>'


def wp_credits():
    return ('<a href="https://commons.wikimedia.org/wiki/File:Mountain_lake,_Mylgval_mountain_cirque_before_sunset,_Caucasus_Mountains.jpg">Vyacheslav Argenberg</a> (CC BY 4.0), '
            '<a href="https://commons.wikimedia.org/wiki/File:Herbert_Lake_beim_Icefields_Parkway.jpg">Florian Fuchs</a> (CC BY 3.0), '
            '<a href="https://commons.wikimedia.org/wiki/File:Pumori,_Nepal,_Asia.jpg">Vyacheslav Argenberg</a> (CC BY 4.0), Wikimedia Commons')


def seq(name, n, frm, to, alt):
    last = f"../assets/seq/{name}-{n - 1:02d}.webp"
    return (f'<div class="seq"><img class="seq__still" src="{last}" width="1200" height="480" alt="{escape(alt)}" fetchpriority="low">'
            f'<canvas data-seq="{name}" data-n="{n}" data-from="{frm}" data-to="{to}" data-src="../assets/seq" width="1200" height="480" hidden aria-hidden="true"></canvas></div>')


def page(lang):
    t = S[lang]
    h = t["htmllang"]
    alt_links = "\n".join(f'<link rel="alternate" hreflang="{S[l]["htmllang"]}" href="{BASE}{l}/">' for l in LANGS)
    alt_links += f'\n<link rel="alternate" hreflang="x-default" href="{BASE}en/">'
    cjk = {"ko": "Noto+Sans+KR", "zh": "Noto+Sans+SC", "ja": "Noto+Sans+JP"}.get(lang)
    fonts = "family=Funnel+Display:wght@600&family=Albert+Sans:wght@400;600" + (f"&family={cjk}:wght@400;600" if cjk else "")
    cur = ' aria-current="page"'
    nav_langs = "".join('<li><a href="../%s/" hreflang="%s" lang="%s"%s>%s</a></li>' % (l, S[l]["htmllang"], S[l]["htmllang"], cur if l == lang else "", escape(S[l]["name"])) for l in LANGS)
    mark = '<svg width="22" height="14" viewBox="0 0 22 14" aria-hidden="true" focusable="false"><path d="M0 0h22v6a8 8 0 0 1-8 8H8a8 8 0 0 1-8-8z" fill="currentColor"/></svg>'
    words = ""
    for li, line in enumerate(LYRICS):
        words += " ".join(f"<span>{escape(w)}</span>" for w in line.split())
        if li < len(LYRICS) - 1:
            words += "<br>"
    pages = "".join(
        f'<li class="pg"><figure class="shot">{img(sc, lang, "dusk", t["pages"][i]["alt"], "(min-width: 60rem) 1312px, 100vw", 1140, 2280, 900)}</figure>'
        f'<div class="pg__text"><h3>{H(t["pages"][i]["h"])}</h3><p>{escape(t["pages"][i]["p"])}</p></div></li>\n' for i, sc in enumerate(SCENES))
    rail = "".join(f'<li>{escape(t["pages"][i]["name"])}</li>' for i in range(5))
    wps, keys = ["a", "b", "c"], ["dusk", "mist", "peak"]
    chips = "".join(f'<label class="chip"><input type="radio" name="wp" id="wp-{w}" value="{w}"{" checked" if i == 0 else ""}>{escape(t["wps"][i])}</label>' for i, w in enumerate(wps))
    gimgs = "".join(img("music", lang, k, t["glass_alt"] if i == 0 else "", "(min-width: 60rem) 1312px, 100vw", 1140, 2280, 900, extra=f' data-wp="{w}"') for i, (w, k) in enumerate(zip(wps, keys)))
    names = "".join(f"<p>{escape(n)}</p>" for n in t["wps"])
    rows = "".join(f"<div><dt>{escape(a)}</dt><dd>{escape(b)}</dd></div>" for a, b in t["rows"])
    foot_links = "".join(f'<li><a href="{u}">{escape(n)}</a></li>' for n, u in [
        (t["f_itch"], ITCH), ("GitHub", GH), (t["f_license"], GH + "/blob/main/LICENSE"), (t["f_privacy"], GH + "/blob/main/PRIVACY.md"), (t["f_trademark"], GH + "/blob/main/TRADEMARK.md")])
    dl, srcb = escape(t["dl"]), escape(t["src"])
    return f"""<!doctype html>
<html lang="{h}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(t["title"])}</title>
<meta name="description" content="{escape(t["desc"])}">
<meta name="color-scheme" content="dark">
<link rel="canonical" href="{BASE}{lang}/">
<meta property="og:type" content="website"><meta property="og:site_name" content="Dalu">
<meta property="og:title" content="{escape(t["title"])}"><meta property="og:description" content="{escape(t["desc"])}">
<meta property="og:url" content="{BASE}{lang}/"><meta property="og:image" content="{BASE}assets/music-dusk-{lang}-1140.webp">
<meta name="twitter:card" content="summary_large_image">
{alt_links}
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 22 14'%3E%3Cpath d='M0 0h22v6a8 8 0 0 1-8 8H8a8 8 0 0 1-8-8z' fill='%23f1e7d4'/%3E%3C/svg%3E">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?{fonts}&display=swap">
<link rel="preload" as="image" href="../assets/wp-dusk.webp" fetchpriority="high">
<link rel="stylesheet" href="../assets/site.css">
<script src="../assets/site.js" defer></script>
</head>
<body>
<a class="skip" href="#main">{escape(t["skip"])}</a>
<header class="nav">
  <nav class="container nav__row" aria-label="Dalu">
    <div class="chip-bar"><a class="wordmark" href="./" aria-label="Dalu">{mark}<span>Dalu</span></a></div>
    <div class="chip-bar"><ul class="langs" aria-label="{escape(t["navlang"])}">{nav_langs}</ul><a class="btn btn--primary" href="{ITCH}">{dl}</a></div>
  </nav>
</header>
<main id="main">
  <section class="track hero" aria-labelledby="hero-h">
    <div class="stage">
      <img class="bg" src="../assets/wp-dusk.webp" width="1920" height="1276" alt="" fetchpriority="high">
      <div class="scrim scrim--bottom"></div><div class="scrim scrim--top"></div>
      {seq("hero", HERO_FRAMES, 0.03, 0.52, t["seq_alt"])}
      <div class="container hero__a"><h1 id="hero-h">{H(t["h1"])}</h1><div class="hero__side"><p class="lead">{escape(t["lead"])}</p><div class="actions"><a class="btn btn--primary" href="{ITCH}">{dl}</a><a class="btn btn--secondary" href="{GH}">{srcb}</a></div></div></div>
      <div class="container hero__b" aria-hidden="true"><p class="big">{H(t["hero_b"])}</p></div>
    </div>
  </section>

  <section class="track lyrics" aria-labelledby="lyr-h">
    <div class="stage">
      <img class="bg" src="../assets/wp-mist.webp" width="1920" height="1280" alt="" loading="lazy" decoding="async">
      <div class="scrim scrim--all"></div>
      <div class="container lyrics__in"><h2 id="lyr-h">{H(t["lyr_h"])}</h2><p class="words" lang="en">{words}</p><p class="lyrics__cap">{escape(t["lyr_cap"])}</p></div>
    </div>
  </section>

  <section class="track chapter" aria-labelledby="ch-h">
    <div class="stage container">
      <div class="chapter__head"><h2 id="ch-h">{H(t["ch_h"])}</h2><ul class="rail" aria-hidden="true">{rail}</ul></div>
      <ol class="pages">
{pages}      </ol>
    </div>
  </section>

  <section class="track glass" aria-labelledby="gl-h">
    <div class="stage container">
      <div class="glass__head"><h2 id="gl-h">{H(t["gl_h"])}</h2><p class="lead">{escape(t["gl_p"])}</p><fieldset><legend>{escape(t["glass_legend"])}</legend>{chips}</fieldset></div>
      <figure class="shot glass__stack">{gimgs}</figure>
      <div class="glass__names" aria-hidden="true">{names}</div>
    </div>
  </section>

  <section class="track dock" aria-labelledby="dk-h">
    <div class="stage">
      <img class="bg" src="../assets/wp-peak.webp" width="1920" height="1353" alt="" loading="lazy" decoding="async">
      <div class="scrim scrim--bottom"></div>
      {seq("dock", DOCK_FRAMES, 0.06, 0.5, t["dock_alt"])}
      <div class="container dock__a"><h2 id="dk-h">{H(t["dk_h"])}</h2><p class="lead">{escape(t["dk_p"])}</p></div>
    </div>
  </section>

  <section class="container band buds" aria-labelledby="bd-h">
    <div class="buds__row"><p class="num-big" aria-hidden="true">{escape(t["bd_num"])}</p><div class="buds__text"><h2 id="bd-h">{H(t["bd_h"])}</h2><p class="lead">{escape(t["bd_p"])}</p></div></div>
    <figure class="shot shot--window rise"><img src="../assets/settings-buds_eq-{lang}-900.webp" srcset="../assets/settings-buds_eq-{lang}-900.webp 900w, ../assets/settings-buds_eq-{lang}-1600.webp 1600w" sizes="(min-width: 60rem) 1120px, 100vw" width="1600" height="WIN_H" alt="{escape(t["buds_alt"])}" loading="lazy" decoding="async"></figure>
  </section>

  <section class="container band" aria-labelledby="st-h">
    <div class="settings__head"><h2 id="st-h">{H(t["st_h"])}</h2><p class="lead">{escape(t["st_p"])}</p></div>
    <figure class="shot shot--window rise"><img src="../assets/settings-look-{lang}-900.webp" srcset="../assets/settings-look-{lang}-900.webp 900w, ../assets/settings-look-{lang}-1600.webp 1600w" sizes="(min-width: 60rem) 1120px, 100vw" width="1600" height="WIN_H" alt="{escape(t["set_alt"])}" loading="lazy" decoding="async"></figure>
  </section>

  <section class="container get" aria-labelledby="gt-h">
    <div class="get__well rise">
      <div><h2 id="gt-h">{H(t["gt_h"])}</h2><p class="lead">{escape(t["gt_p"])}</p><div class="actions" style="margin-top: var(--space-xl)"><a class="btn btn--primary" href="{ITCH}">{dl}</a><a class="btn btn--secondary" href="{GH}">{srcb}</a></div></div>
      <div class="get__side"><dl class="facts">{rows}</dl><p class="note">{escape(t["note"])}</p></div>
    </div>
  </section>
</main>
<footer class="container foot">
  <div class="foot__row"><a class="wordmark" href="./" aria-label="Dalu">{mark}<span>Dalu</span></a><ul>{foot_links}</ul></div>
  <p data-credits>{escape(t["f_photos"])}: {wp_credits()}.</p>
  <p>{escape(t["f_legal"])}</p>
</footer>
</body>
</html>
"""


def root_page():
    links = "".join(f'<li><a href="{l}/" hreflang="{S[l]["htmllang"]}" lang="{S[l]["htmllang"]}">{escape(S[l]["name"])}</a></li>' for l in LANGS)
    alt = "\n".join(f'<link rel="alternate" hreflang="{S[l]["htmllang"]}" href="{BASE}{l}/">' for l in LANGS)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Dalu</title>
<meta name="description" content="{escape(S["en"]["desc"])}">
<meta name="color-scheme" content="dark">
<link rel="canonical" href="{BASE}">
{alt}
<link rel="stylesheet" href="assets/site.css">
<script>try {{ var m = {{ ko: 'ko', zh: 'zh', ja: 'ja' }}[(navigator.language || 'en').slice(0, 2).toLowerCase()] || 'en'; location.replace(m + '/'); }} catch (e) {{}}</script>
</head>
<body>
<main class="container" style="min-height:100svh;display:grid;align-content:center;gap:var(--space-xl)">
  <h1>Dalu</h1>
  <ul class="langs" style="font-size:var(--text-lg)">{links}</ul>
</main>
</body>
</html>
"""


def convert_assets():
    from PIL import Image, ImageDraw
    shot_dir = os.environ.get("APP_SHOTS")
    if shot_dir:
        for old in ASSETS.glob("*.webp"):
            if not old.name.startswith(("settings-", "wp-")):
                old.unlink()
        for f in sorted(Path(shot_dir).glob("site_*.png")):
            lang, wp, scene = f.stem[5:].split("_", 2)
            im = Image.open(f).convert("RGB")
            for w in (1140, 2280):
                im.resize((w, round(im.height * w / im.width)), Image.LANCZOS).save(ASSETS / f"{scene}-{wp}-{lang}-{w}.webp", "WEBP", quality=80, method=6)
    shots = os.environ.get("SETTINGS_SHOTS")
    if shots:
        for k in ("buds_eq", "look"):
            for lang in LANGS:
                im = Image.open(Path(shots) / f"{k}_{lang}.png").convert("RGBA").crop((38, 38, 1922, 1324))
                mask = Image.new("L", im.size, 0)
                ImageDraw.Draw(mask).rounded_rectangle((0, 0, im.width - 1, im.height - 1), radius=60, fill=255)
                im.putalpha(mask)
                for w in (900, 1600):
                    im.resize((w, round(im.height * w / im.width)), Image.LANCZOS).save(ASSETS / f"settings-{k}-{lang}-{w}.webp", "WEBP", quality=84, method=6)
    wps = SRC / "wallpapers"
    names = {"dusk": "mountain-lake-mylgval-mountain-cirque-before-sunset-caucasus-1920.jpg", "mist": "herbert-lake-beim-icefields-parkway-1920.jpg", "peak": "pumori-nepal-asia-1920.jpg"}
    if wps.exists():
        for k, f in names.items():
            if (wps / f).exists():
                im = Image.open(wps / f).convert("RGB")
                im.save(ASSETS / f"wp-{k}.webp", "WEBP", quality=58 if k == "dusk" else 66, method=6)


def main():
    from PIL import Image
    ASSETS.mkdir(parents=True, exist_ok=True)
    convert_assets()
    (ASSETS / "site.css").write_text(build_css(), encoding="utf-8")
    shutil.copyfile(SRC / "site.js", ASSETS / "site.js")
    for lang in LANGS:
        (OUT / lang).mkdir(exist_ok=True)
    win_h = Image.open(ASSETS / "settings-look-en-1600.webp").height
    for lang in LANGS:
        (OUT / lang / "index.html").write_text(page(lang).replace("WIN_H", str(win_h)), encoding="utf-8")
    (OUT / "index.html").write_text(root_page(), encoding="utf-8")
    (OUT / ".nojekyll").write_text("", encoding="utf-8")
    used = set()
    for f in OUT.rglob("*.html"):
        used |= set(re.findall(r"assets/([A-Za-z0-9_.-]+\.webp)", f.read_text(encoding="utf-8")))
    for f in ASSETS.glob("*.webp"):
        if f.name not in used:
            f.unlink()
    print("built", len(list(OUT.rglob("*.html"))), "pages; css", (ASSETS / "site.css").stat().st_size, "bytes")


if __name__ == "__main__":
    main()
