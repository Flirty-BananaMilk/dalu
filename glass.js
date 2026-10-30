// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
// Copyright (c) 2026 Flirty_BananaMilk — 상업적 이용 금지, 자세한 내용은 LICENSE
// ========================================================
// Liquid Glass (설정 창용): 흐림만 있는 반투명 유리가 아니라, 가장자리에서 뒤의 화면을 '굴절'시키는 렌즈 효과를 만든다.
//
//  1) 굴절(lensing): 둥근 사각형의 가장자리(bezel)에서 안쪽으로 휘는 변위 맵을 캔버스로 만들어 SVG feDisplacementMap 에 넣고,
//     CSS `backdrop-filter: url(#필터)` 로 요소 '뒤'에 그려진 것에 적용한다 (Chromium/WebView2 에서 동작).
//     R/G/B 를 아주 조금씩 다른 세기로 밀어 가장자리에 색 번짐(분산)이 생기게 한다.
//  2) 반사광(specular): CSS(.lg) 가 테두리에 빛줄기와, 포인터를 따라 움직이는 하이라이트를 그린다 — 여기서는 포인터 좌표만 넘긴다.
//  3) 모양 변형(morph): 이동하는 하이라이트가 늘어났다 돌아오는 연출(stretch)을 제공한다.
//
// 지원하지 않는 환경이면 조용히 건너뛰고(흐림 + 반투명 + 반사광은 CSS 만으로 남는다) 화면은 정상 동작한다.
// ========================================================
const LG = (() => {
  const NS = 'http://www.w3.org/2000/svg';
  let defs = null;
  const cache = new Map();           // 키 -> 필터 id
  const MAX_FILTERS = 400;
  const supported = (() => {
    try { return !!(window.CSS && CSS.supports && (CSS.supports('backdrop-filter', 'url(#a)') || CSS.supports('-webkit-backdrop-filter', 'url(#a)'))); } catch (e) { return false; }
  })();

  function ensureDefs() {
    if (defs) return defs;
    const svg = document.createElementNS(NS, 'svg');
    svg.setAttribute('width', '0'); svg.setAttribute('height', '0');
    svg.setAttribute('aria-hidden', 'true');
    svg.style.cssText = 'position:absolute;width:0;height:0;overflow:hidden;pointer-events:none';
    defs = document.createElementNS(NS, 'defs');
    svg.appendChild(defs);
    document.body.appendChild(svg);
    return defs;
  }

  // 둥근 사각형(w x h, 반지름 r)의 부호 있는 거리(안쪽이 음수)와 바깥쪽 법선
  function sdRoundRect(px, py, w, h, r) {
    const cx = w / 2, cy = h / 2;
    const dx = px - cx, dy = py - cy;
    const qx = Math.abs(dx) - (cx - r), qy = Math.abs(dy) - (cy - r);
    const ox = Math.max(qx, 0), oy = Math.max(qy, 0);
    const outside = Math.hypot(ox, oy);
    const sd = outside + Math.min(Math.max(qx, qy), 0) - r;
    let nx, ny;
    if (qx > 0 || qy > 0) { const len = outside || 1; nx = Math.sign(dx) * ox / len; ny = Math.sign(dy) * oy / len; }
    else if (qx > qy) { nx = Math.sign(dx) || 1; ny = 0; }
    else { nx = 0; ny = Math.sign(dy) || 1; }
    return { sd, nx, ny };
  }

  // 변위 맵: 가장자리(bezel 폭)에서 안쪽으로 향하는 벡터, 안쪽은 0. 색 128 = 이동 없음.
  const MAP_RES = 0.25;       // 맵은 1/4 해상도로 만들고 feImage 가 늘려 쓴다: 가장자리가 부드러워지고, 크기가 변하는 동안 매 프레임 만들어도 될 만큼 싸다
  function displacementMap(fw, fh, fr, fbezel, power) {
    const w = Math.max(2, Math.round(fw * MAP_RES)), h = Math.max(2, Math.round(fh * MAP_RES));
    const r = fr * MAP_RES, bezel = fbezel * MAP_RES;
    const c = document.createElement('canvas');
    c.width = w; c.height = h;
    const ctx = c.getContext('2d');
    const img = ctx.createImageData(w, h);
    const d = img.data;
    for (let y = 0; y < h; y++) {
      for (let x = 0; x < w; x++) {
        const { sd, nx, ny } = sdRoundRect(x + 0.5, y + 0.5, w, h, r);
        const depth = -sd;                                   // 가장자리에서 안쪽으로 얼마나 들어왔나
        let vx = 0, vy = 0;
        if (depth > 0 && depth < bezel) {
          const t = depth / bezel;                           // 0(가장자리) ~ 1(안쪽)
          const m = Math.pow(1 - t, power);                  // 볼록 렌즈: 가장자리에서 가장 크게 휜다
          vx = -nx * m; vy = -ny * m;                        // 안쪽으로 향함
        }
        const i = (y * w + x) * 4;
        d[i] = 128 + 127 * vx; d[i + 1] = 128 + 127 * vy; d[i + 2] = 128; d[i + 3] = 255;
      }
    }
    ctx.putImageData(img, 0, 0);
    return c.toDataURL('image/png');
  }

  // w x h 요소용 굴절 필터를 만들고 id 를 돌려준다 (같은 크기/설정은 재사용)
  let idSeq = 0;
  function filterFor(w, h, o) {
    if (!supported) return null;
    w = Math.max(8, Math.ceil(w / 2) * 2); h = Math.max(8, Math.ceil(h / 2) * 2);
    const r = Math.min(o.radius == null ? Math.min(w, h) / 2 : o.radius, w / 2, h / 2);
    const bezel = Math.min(o.bezel || Math.min(w, h) * 0.45, Math.min(w, h) / 2);
    const scale = o.scale == null ? 18 : o.scale;
    const disp = o.dispersion == null ? 0.06 : o.dispersion;
    const power = o.power || 2.2;
    const key = [w, h, Math.round(r), Math.round(bezel), scale, disp, power].join('x');
    if (cache.has(key)) return cache.get(key);
    if (cache.size >= MAX_FILTERS) return null;              // 너무 많이 만들지 않는다
    const id = 'lg' + (idSeq++) + '_' + w + 'x' + h;       // 번호는 계속 늘린다: 캐시 크기를 쓰면 gc() 로 캐시가 줄어든 뒤 서로 다른 필터(반지름이 다른 것 포함)가 같은 id 를 받아, 브라우저가 먼저 만든 엉뚱한(예: 반지름 0 인 직각) 필터를 썼다
    const f = document.createElementNS(NS, 'filter');
    f.setAttribute('id', id);
    f.setAttribute('filterUnits', 'userSpaceOnUse'); f.setAttribute('primitiveUnits', 'userSpaceOnUse');
    f.setAttribute('x', '0'); f.setAttribute('y', '0'); f.setAttribute('width', String(w)); f.setAttribute('height', String(h));
    f.setAttribute('color-interpolation-filters', 'sRGB');
    const img = document.createElementNS(NS, 'feImage');
    img.setAttribute('href', displacementMap(w, h, r, bezel, power));
    img.setAttribute('x', '0'); img.setAttribute('y', '0'); img.setAttribute('width', String(w)); img.setAttribute('height', String(h));
    img.setAttribute('preserveAspectRatio', 'none'); img.setAttribute('result', 'map');
    f.appendChild(img);
    const channels = [['R', 1 + disp, '1 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 1 0'], ['G', 1, '0 0 0 0 0  0 1 0 0 0  0 0 0 0 0  0 0 0 1 0'], ['B', 1 - disp, '0 0 0 0 0  0 0 0 0 0  0 0 1 0 0  0 0 0 1 0']];
    for (const [name, k, matrix] of channels) {
      const dm = document.createElementNS(NS, 'feDisplacementMap');
      dm.setAttribute('in', 'SourceGraphic'); dm.setAttribute('in2', 'map'); dm.setAttribute('scale', String(scale * 2 * k));
      dm.setAttribute('xChannelSelector', 'R'); dm.setAttribute('yChannelSelector', 'G'); dm.setAttribute('result', 'd' + name);
      const cm = document.createElementNS(NS, 'feColorMatrix');
      cm.setAttribute('in', 'd' + name); cm.setAttribute('type', 'matrix'); cm.setAttribute('values', matrix); cm.setAttribute('result', 'c' + name);
      f.append(dm, cm);
    }
    const b1 = document.createElementNS(NS, 'feBlend'); b1.setAttribute('in', 'cR'); b1.setAttribute('in2', 'cG'); b1.setAttribute('mode', 'screen'); b1.setAttribute('result', 'rg');
    const b2 = document.createElementNS(NS, 'feBlend'); b2.setAttribute('in', 'rg'); b2.setAttribute('in2', 'cB'); b2.setAttribute('mode', 'screen');
    f.append(b1, b2);
    ensureDefs().appendChild(f);
    cache.set(key, id);
    return id;
  }

  // 요소에 렌즈를 건다. opts: {radius, bezel, scale, dispersion, power, blur, saturate, brightness}. 크기가 바뀌면 필터를 다시 고른다.
  const watched = new WeakMap();
  const appliers = new WeakMap();
  function lens(el, opts) {
    opts = opts || {};
    const apply = () => {
      const r = el.getBoundingClientRect();
      if (r.width < 8 || r.height < 8) return;
      const o = Object.assign({}, opts);
      if (o.radius == null) {                                    // 요소의 border-radius 를 그대로 따른다 (50% 도 처리)
        const cs = getComputedStyle(el);
        let best = 0;
        for (const raw of [cs.borderTopLeftRadius, cs.borderTopRightRadius, cs.borderBottomLeftRadius, cs.borderBottomRightRadius]) {
          const n = parseFloat(raw);
          if (n > 0) best = Math.max(best, String(raw).indexOf('%') > -1 ? Math.min(r.width, r.height) * n / 100 : n);
        }
        if (best > 0) o.radius = best;           // 윗면이 평평한 노치처럼 모서리가 서로 다르면 가장 큰 것
      }
      const id = filterFor(r.width, r.height, o);
      const blur = opts.blur == null ? 1.2 : opts.blur;
      const base = `blur(${blur}px) saturate(${opts.saturate || 1.5}) brightness(${opts.brightness || 1.06})`;
      const v = id ? `blur(${blur}px) url(#${id}) saturate(${opts.saturate || 1.5}) brightness(${opts.brightness || 1.06})` : base;
      el.style.backdropFilter = v; el.style.webkitBackdropFilter = v;
    };
    appliers.set(el, apply);
    apply();
    if (!watched.has(el) && window.ResizeObserver) {
      let t = null;
      const ro = new ResizeObserver(() => { clearTimeout(t); t = setTimeout(apply, 60); });     // 애니메이션 중에는 잠잠해진 뒤 한 번만
      ro.observe(el);
      watched.set(el, ro);
    }
    el.classList.add('lg');
  }

  // 크기가 변하는 동안 쌓인 임시 필터를 치운다: 지금 어떤 요소도 쓰지 않는 것만 지운다
  function gc() {
    if (!defs) return;
    const used = new Set();
    document.querySelectorAll('.lg').forEach((el) => { const m = (el.style.backdropFilter || '').match(/#([\w-]+)/); if (m) used.add(m[1]); });
    for (const [key, id] of Array.from(cache)) {
      if (used.has(id)) continue;
      const f = defs.querySelector('#' + id);
      if (f) f.remove();
      cache.delete(key);
    }
  }

  // 세기를 바꿨을 때: 만들어 둔 필터를 모두 버린다 (슬라이더를 끌 때 필터가 한도까지 쌓이지 않게). 호출한 쪽이 렌즈를 다시 건다.
  function reset() {
    cache.clear();
    if (defs) while (defs.firstChild) defs.removeChild(defs.firstChild);
  }

  // 크기가 애니메이션 중일 때는 렌즈(고정 크기 필터)가 맞지 않아 가장자리가 비므로 잠깐 흐림만 남기고, 끝나면 refresh 로 다시 건다
  function suspend(el) { el.style.backdropFilter = 'none'; el.style.webkitBackdropFilter = 'none'; }
  function refresh(el) { const f = appliers.get(el); if (f) f(); }
  function unlens(el) {
    const ro = watched.get(el); if (ro) { ro.disconnect(); watched.delete(el); }
    appliers.delete(el);
    el.style.backdropFilter = ''; el.style.webkitBackdropFilter = '';
    el.classList.remove('lg');
  }

  // 고정 크기 렌즈(스위치/슬라이더 손잡이)용 CSS 변수로 id 를 노출한다: --lg-thumb, --lg-knob
  function defineStatic(name, w, h, o) {
    const id = filterFor(w, h, o);
    if (id) document.documentElement.style.setProperty('--lg-' + name, `url(#${id})`);
    return id;
  }

  // 포인터를 따라가는 하이라이트: .lg 요소 위에서 마우스가 움직이면 --mx/--my 를 갱신한다 (문서 전체에 리스너 하나)
  let pointerBound = false;
  function bindPointerGlow() {
    if (pointerBound) return;
    pointerBound = true;
    let raf = 0, last = null;
    document.addEventListener('pointermove', (e) => {
      last = e;
      if (raf) return;
      raf = requestAnimationFrame(() => {
        raf = 0;
        const el = last.target.closest && last.target.closest('.lg');
        if (!el) return;
        const r = el.getBoundingClientRect();
        el.style.setProperty('--mx', `${last.clientX - r.left}px`);
        el.style.setProperty('--my', `${last.clientY - r.top}px`);
      });
    }, { passive: true });
  }

  // 이동하는 하이라이트가 늘어났다가 돌아오는 연출 (액체처럼). axis: 'x' | 'y'
  function stretch(el, axis, ms) {
    if (!el.animate || (document.documentElement.dataset.anim === 'off')) return;
    const k = axis === 'y' ? ['.94 1.14', '1 1'] : ['1.16 .93', '1 1'];
    el.animate([{ scale: '1 1' }, { scale: k[0], offset: 0.42 }, { scale: k[1] }], { duration: ms || 520, easing: 'cubic-bezier(0.34, 1.3, 0.5, 1)' });
  }

  return { supported, filterFor, lens, unlens, suspend, refresh, reset, gc, defineStatic, bindPointerGlow, stretch, displacementMap, sdRoundRect };
})();

if (typeof module !== 'undefined') module.exports = { LG };
