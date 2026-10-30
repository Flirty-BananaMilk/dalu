"""Dalu 웹사이트 만들기: site_src/ (문구, 스타일) -> docs/ (GitHub Pages 에 올라가는 정적 파일)

    python site_src/build.py

- 4개 언어 페이지(docs/ko, en, zh, ja)는 같은 틀에 strings.json 의 문구를 넣어 만든다.
- 모든 문구가 HTML 안에 그대로 들어 있어서 JavaScript 가 꺼져 있어도 내용이 보인다.
"""
import json
import os
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

STAMP = """/* Hallmark · shape: Pinned chapter under a wallpaper hero · genre: atmospheric · theme: custom · job: try · idea: "The page is the desktop: the real notch sits on a real wallpaper and the scroll plays its five pages." · vibe: "quiet slate, evening light, glass"
 * paper: oklch(15.5% 0.012 235) · accent: oklch(80% 0.13 78) · display: Funnel Display · body: Albert Sans · hero: the captured notch on a wallpaper, faded into the page, headline and download below · nav: two glass chips over the hero, wordmark left, languages and one action right · footer: ruled strip, wordmark, links, photo credits · imagery: screenshots 40 (rendered from the app's own UI with sample data), photographs 3 library · signature: the notch refracting a wallpaper the visitor picks
 * axes: dark/geometric-sans/warm · posture: restrained · contrast: pass · fold: pass · v2.0.0 */
/* Hallmark · pre-emit critique: P4 H4 E4 S4 R4 V4 · weakest: S, the hero first read as any desktop-tool page; led with the real notch on a real photograph instead of a feature grid */
/* Hallmark · waive 42 · nav is a wordmark left with languages and one action right, floating as two glass chips · the languages are the nav's real content on a four-language page, so the common bar shape is the honest one */
"""


def wp_credits():
    return ('<a href="https://commons.wikimedia.org/wiki/File:Mountain_lake,_Mylgval_mountain_cirque_before_sunset,_Caucasus_Mountains.jpg">Vyacheslav Argenberg</a> (CC BY 4.0), '
            '<a href="https://commons.wikimedia.org/wiki/File:Herbert_Lake_beim_Icefields_Parkway.jpg">Florian Fuchs</a> (CC BY 3.0), '
            '<a href="https://commons.wikimedia.org/wiki/File:Pumori,_Nepal,_Asia.jpg">Vyacheslav Argenberg</a> (CC BY 4.0), Wikimedia Commons')


def H(x):
    """제목: | 는 줄바꿈해도 되는 자리(<wbr>)"""
    return escape(x).replace("|", "<wbr>")


def build_css():
    # 고정 챕터: 트랙 높이 T(svh) 안에서 스티키 무대가 고정되는 구간을 cover 타임라인 %로 계산한다
    T, V, N, M = 520.0, 100.0, len(SCENES), 2.5
    a0, b0 = V / (T + V) * 100, T / (T + V) * 100
    w = (b0 - a0) / N
    pin = []
    for i in range(N):
        a, b = a0 + w * i, a0 + w * (i + 1)
        s, e = max(a - M, 0), min(b + M, 100)
        span = e - s
        up, down = (a - s) / span * 100, (b - s) / span * 100
        if i == 0:
            pin.append(f".pg:nth-child({i + 1}) {{ animation-name: pg-first; animation-range: cover 0% cover {e:.2f}%; }}")
            first_hold = (b - 0) / e * 100
        elif i == N - 1:
            pin.append(f".pg:nth-child({i + 1}) {{ animation-name: pg-last; animation-range: cover {s:.2f}% cover 100%; }}")
            last_up = (a - s) / (100 - s) * 100
        else:
            pin.append(f".pg:nth-child({i + 1}) {{ animation-name: pg-mid; animation-range: cover {s:.2f}% cover {e:.2f}%; }}")
            mid_up, mid_down = up, down
    chapter = f"""
/* chapter, pinned: only where scroll timelines exist and motion is welcome; everywhere else the five pages simply stack */
@supports (animation-timeline: view()) {{
  @media (prefers-reduced-motion: no-preference) and (min-width: 60rem) {{
    .chapter__track {{ min-height: {T:.0f}svh; view-timeline: --chapter block; }}
    .chapter__stage {{ position: sticky; top: var(--space-md); height: calc(100svh - var(--space-xl)); display: grid; grid-template-rows: auto minmax(0, 1fr); gap: var(--space-lg); overflow: clip; }}
    .chapter__head {{ margin-bottom: 0; grid-template-columns: auto auto; justify-content: space-between; align-items: end; }}
    .chapter__head h2 {{ max-width: none; }}
    .pages {{ grid-template: minmax(0, 1fr) / minmax(0, 1fr); gap: 0; min-height: 0; }}
    .pg {{ grid-area: 1 / 1; grid-template-rows: minmax(0, 1fr) auto; min-height: 0; animation-timeline: --chapter; animation-fill-mode: both; animation-timing-function: linear; animation-duration: 1ms; }}
    .pg img {{ height: 100%; aspect-ratio: auto; min-height: 0; }}
{chr(10).join('    ' + p for p in pin)}
    @keyframes pg-first {{ 0%, {first_hold:.2f}% {{ opacity: 1; }} 100% {{ opacity: 0; }} }}
    @keyframes pg-mid {{ 0%, 0.01% {{ opacity: 0; }} {mid_up:.2f}%, {mid_down:.2f}% {{ opacity: 1; }} 100% {{ opacity: 0; }} }}
    @keyframes pg-last {{ 0% {{ opacity: 0; }} {last_up:.2f}%, 100% {{ opacity: 1; }} }}
  }}
}}
"""
    tokens = (SRC / "tokens.css").read_text(encoding="utf-8")
    base = (SRC / "base.css").read_text(encoding="utf-8")
    site = (SRC / "site.css").read_text(encoding="utf-8")
    return STAMP + "\n" + tokens + "\n" + base + "\n" + site + chapter


def img(name, lang, wp, alt, sizes, w1, w2, h2, eager=False, extra=""):
    base = f"../assets/{name}-{wp}-{lang}" if wp else f"../assets/{name}-{lang}"
    src = f"{base}-{w1}.webp"
    srcset = f"{base}-{w1}.webp {w1}w, {base}-{w2}.webp {w2}w"
    load = 'fetchpriority="high"' if eager else 'loading="lazy" decoding="async"'
    return f'<img src="{src}" srcset="{srcset}" sizes="{sizes}" width="{w2}" height="{h2}" alt="{escape(alt)}" {load}{extra}>'


def page(lang):
    t = S[lang]
    h = t["htmllang"]
    alt_links = "\n".join(f'<link rel="alternate" hreflang="{S[l]["htmllang"]}" href="{BASE}{l}/">' for l in LANGS)
    alt_links += f'\n<link rel="alternate" hreflang="x-default" href="{BASE}en/">'
    cjk = {"ko": "Noto+Sans+KR", "zh": "Noto+Sans+SC", "ja": "Noto+Sans+JP"}.get(lang)
    fonts = "family=Funnel+Display:wght@600&family=Albert+Sans:wght@400;600" + (f"&family={cjk}:wght@400;600" if cjk else "")
    cur = ' aria-current="page"'
    nav_langs = "".join(
        '<li><a href="../%s/" hreflang="%s" lang="%s"%s>%s</a></li>' % (l, S[l]["htmllang"], S[l]["htmllang"], cur if l == lang else "", escape(S[l]["name"])) for l in LANGS)
    pages = ""
    for i, sc in enumerate(SCENES):
        p = t["pages"][i]
        pages += (f'<li class="pg"><figure class="shot">{img(sc, lang, "dusk", p["alt"], "(min-width: 60rem) 1312px, 100vw", 1140, 2280, 900)}</figure>'
                  f'<div class="pg__text"><span class="pg__name">{escape(p["name"])}</span><h3>{H(p["h"])}</h3><p>{escape(p["p"])}</p></div></li>\n')
    wps = ["a", "b", "c"]
    keys = ["dusk", "mist", "peak"]
    chips = "".join(
        f'<label class="chip"><input type="radio" name="wp" id="wp-{w}" value="{w}"{" checked" if i == 0 else ""}>{escape(t["wps"][i])}</label>' for i, w in enumerate(wps))
    gimgs = "".join(
        img("music", lang, k, t["glass_alt"] if i == 0 else "", "(min-width: 60rem) 1312px, 100vw", 1140, 2280, 900, extra=f' data-wp="{w}"')
        for i, (w, k) in enumerate(zip(wps, keys)))
    rows = "".join(f"<div><dt>{escape(a)}</dt><dd>{escape(b)}</dd></div>" for a, b in t["rows"])
    foot_links = "".join(f'<li><a href="{u}">{escape(n)}</a></li>' for n, u in [
        (t["f_itch"], ITCH), ("GitHub", GH), (t["f_license"], GH + "/blob/main/LICENSE"), (t["f_privacy"], GH + "/blob/main/PRIVACY.md"), (t["f_trademark"], GH + "/blob/main/TRADEMARK.md")])
    mark = '<svg width="22" height="14" viewBox="0 0 22 14" aria-hidden="true" focusable="false"><path d="M0 0h22v6a8 8 0 0 1-8 8H8a8 8 0 0 1-8-8z" fill="currentColor"/></svg>'
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
<link rel="stylesheet" href="../assets/site.css">
</head>
<body>
<a class="skip" href="#main">{escape(t["skip"])}</a>
<header class="hero">
  <nav class="nav" aria-label="Dalu">
    <div class="container nav__row">
      <div class="chip-bar"><a class="wordmark" href="./" aria-label="Dalu">{mark}<span>Dalu</span></a></div>
      <div class="chip-bar"><ul class="langs" aria-label="{escape(t["navlang"])}">{nav_langs}</ul><a class="btn btn--primary" href="{ITCH}">{escape(t["dl"])}</a></div>
    </div>
  </nav>
  <figure class="hero__shot">{img("music", lang, "dusk", t["pages"][0]["alt"], "100vw", 1140, 2280, 900, eager=True)}</figure>
  <div class="container hero__text">
    <h1>{H(t["h1"])}</h1>
    <div class="hero__side"><p class="lead">{escape(t["lead"])}</p>
    <div class="actions"><a class="btn btn--primary" href="{ITCH}">{escape(t["dl"])}</a><a class="btn btn--secondary" href="{GH}">{escape(t["src"])}</a></div></div>
  </div>
</header>
<main id="main">
  <section class="chapter" aria-labelledby="chapter-h">
    <div class="chapter__track">
      <div class="chapter__stage container">
        <div class="chapter__head"><h2 id="chapter-h">{H(t["chapter_h"])}</h2></div>
        <ol class="pages">
{pages}        </ol>
      </div>
    </div>
  </section>

  <section class="glass" aria-labelledby="glass-h">
    <div class="container">
      <div class="glass__grid"><h2 id="glass-h">{H(t["glass_h"])}</h2><p class="lead">{escape(t["glass_p"])}</p></div>
      <fieldset><legend>{escape(t["glass_legend"])}</legend>{chips}</fieldset>
      <figure class="shot glass__stage">{gimgs}</figure>
    </div>
  </section>

  <section class="container split split--dock" aria-labelledby="dock-h">
    <div class="split__text"><h2 id="dock-h">{H(t["dock_h"])}</h2><p class="lead">{escape(t["dock_p"])}</p></div>
    <figure class="shot">{img("dock", lang, "dusk", t["dock_alt"], "(min-width: 60rem) 760px, 100vw", 1140, 2280, 900)}</figure>
  </section>

  <section class="container split split--buds" aria-labelledby="buds-h">
    <figure class="shot shot--window"><img src="../assets/settings-buds_eq-{lang}-900.webp" srcset="../assets/settings-buds_eq-{lang}-900.webp 900w, ../assets/settings-buds_eq-{lang}-1600.webp 1600w" sizes="(min-width: 60rem) 860px, 100vw" width="1600" height="WIN_H" alt="{escape(t["buds_alt"])}" loading="lazy" decoding="async"></figure>
    <div class="split__text"><h2 id="buds-h">{H(t["buds_h"])}</h2><p class="lead">{escape(t["buds_p"])}</p></div>
  </section>

  <section class="container settings" aria-labelledby="set-h">
    <div class="settings__head"><h2 id="set-h">{H(t["set_h"])}</h2><p class="lead">{escape(t["set_p"])}</p></div>
    <figure class="shot shot--window"><img src="../assets/settings-look-{lang}-900.webp" srcset="../assets/settings-look-{lang}-900.webp 900w, ../assets/settings-look-{lang}-1600.webp 1600w" sizes="(min-width: 60rem) 1040px, 100vw" width="1600" height="WIN_H" alt="{escape(t["set_alt"])}" loading="lazy" decoding="async"></figure>
  </section>

  <section class="container get" aria-labelledby="get-h">
    <div class="get__well">
      <div><h2 id="get-h">{H(t["get_h"])}</h2><p class="lead">{escape(t["get_p"])}</p><div class="actions" style="margin-top: var(--space-xl)"><a class="btn btn--primary" href="{ITCH}">{escape(t["dl"])}</a><a class="btn btn--secondary" href="{GH}">{escape(t["src"])}</a></div></div>
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


def main():
    from PIL import Image, ImageDraw
    ASSETS.mkdir(parents=True, exist_ok=True)
    (ASSETS / "site.css").write_text(build_css(), encoding="utf-8")
    shot_dir = os.environ.get("APP_SHOTS")
    if shot_dir:
        for old in ASSETS.glob("*.webp"):
            if not old.name.startswith("settings-"):
                old.unlink()
        for f in sorted(Path(shot_dir).glob("site_*.png")):
            lang, wp, scene = f.stem[5:].split("_", 2)
            im = Image.open(f).convert("RGB")
            for w in (1140, 2280):
                im.resize((w, round(im.height * w / im.width)), Image.LANCZOS).save(ASSETS / f"{scene}-{wp}-{lang}-{w}.webp", "WEBP", quality=80, method=6)
    heights = set()
    for lang in LANGS:
        (OUT / lang).mkdir(exist_ok=True)
    # 설정 창 캡처: 창 둘레만 잘라 모서리를 둥글게 투명 처리한다 (한 번만, 원본 PNG 가 있을 때)
    shots = os.environ.get("SETTINGS_SHOTS")
    if shots:
        for k in ("buds_eq", "look"):
            for lang in LANGS:
                im = Image.open(Path(shots) / f"{k}_{lang}.png").convert("RGBA").crop((38, 38, 1922, 1324))
                mask = Image.new("L", im.size, 0)
                ImageDraw.Draw(mask).rounded_rectangle((0, 0, im.width - 1, im.height - 1), radius=60, fill=255)
                im.putalpha(mask)
                for w in (900, 1600):
                    o = im.resize((w, round(im.height * w / im.width)), Image.LANCZOS)
                    o.save(ASSETS / f"settings-{k}-{lang}-{w}.webp", "WEBP", quality=84, method=6)
    sample = Image.open(ASSETS / "settings-look-en-1600.webp")
    win_h = sample.height
    for lang in LANGS:
        (OUT / lang / "index.html").write_text(page(lang).replace("WIN_H", str(win_h)), encoding="utf-8")
    (OUT / "index.html").write_text(root_page(), encoding="utf-8")
    import re
    used = set()
    for f in OUT.rglob("*.html"):
        used |= set(re.findall(r"assets/([A-Za-z0-9_.-]+\.webp)", f.read_text(encoding="utf-8")))
    for f in ASSETS.glob("*.webp"):
        if f.name not in used:
            f.unlink()
    (OUT / ".nojekyll").write_text("", encoding="utf-8")
    print("built", [str(p.relative_to(ROOT)) for p in OUT.rglob("*.html")], "css", (ASSETS / "site.css").stat().st_size, "bytes; window img height", win_h)


if __name__ == "__main__":
    main()
