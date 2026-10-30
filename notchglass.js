// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
// Copyright (c) 2026 Flirty_BananaMilk — 상업적 이용 금지, 자세한 내용은 LICENSE
// ========================================================
// 노치 리퀴드 글래스 (설정 > 모양·동작 > 노치 리퀴드 글래스: 끔 / 컨트롤 / 전체)
//  - 컨트롤: 노치 안의 버튼·타일·칩에 굴절 렌즈(glass.js)를 건다. 뒤에 깔린 앨범 색 빛이 가장자리에서 휘어 보인다.
//  - 전체:   위에 더해, 노치 본체가 뒤의 화면을 비춘다. 창이 투명해서 CSS 로는 바탕을 읽을 수 없으므로 파이썬(deskcap.py)이
//            노치 뒤 화면을 작게 찍어 setDesk(url) 로 넘기고, 여기서 흐리게 깔고 가장자리를 굴절시킨다.
//  렌즈는 뒤에 칠해진 것이 있어야 보이므로, 렌즈 요소의 조상에는 backdrop-filter 를 두지 않는다(두면 그 안만 비춘다).
// ========================================================
const NOTCH_GLASS_TARGETS = ['.btn-ctrl.big', '.pill', '.mbtn', '.ltile', '.pbtn', '.pchip', '.srcbtn', '.volpop'];
let notchGlassMode = 'off';
let notchGlassObs = null;

// 굴절 세기 (설정 glassStrength 0~200%, 기본 100): 렌즈의 휘는 정도와 가장자리 폭에 곱한다. 0 이면 굴절 없이 반사광만.
let notchGlassStrength = 1;
const glassK = () => { const v = Number(store.settings.glassStrength); return Math.max(0, Math.min(2, (Number.isFinite(v) ? v : 100) / 100)); };

function notchLensOpts(el) {
  const small = el.matches('.srcbtn');
  const k = notchGlassStrength;
  return { bezel: Math.max(6, (small ? 11 : 13) * Math.sqrt(k)), scale: (small ? 12 : 15) * k, blur: 0.8, saturate: 1.5, brightness: 1.12, dispersion: 0.07 * Math.min(k, 1.5) };
}

function bodyLensOpts() {
  const k = notchGlassStrength;
  return { bezel: Math.max(10, 44 * Math.sqrt(k)), scale: 46 * k, blur: 0, saturate: 1.3, brightness: 1.08, dispersion: 0.1 * Math.min(k, 1.5), power: 1.8 };
}

// 스크롤되는 영역(overflow:auto/scroll) 안의 컨트롤은 굴절 렌즈를 쓰지 않는다: 그 안에서는 backdrop-filter 가 뒤 화면을 못 읽고
// 버튼 뒤에 네모난 영역이 그대로 비친다(실측). 대신 같은 유리 질감(테두리 반사광, 안쪽 빛)만 CSS 로 입힌다.
function inScroller(el) {
  const root = document.getElementById('island');
  for (let p = el.parentElement; p && p !== root; p = p.parentElement) {
    const cs = getComputedStyle(p);
    if (/(auto|scroll)/.test(cs.overflowX) || /(auto|scroll)/.test(cs.overflowY)) return true;
  }
  return false;
}

function lensNotchControls(root) {
  if (typeof LG === 'undefined' || !LG.supported) return;
  for (const sel of NOTCH_GLASS_TARGETS) {
    (root || document).querySelectorAll(sel).forEach((el) => {
      if (el.classList.contains('lg')) return;
      if (inScroller(el)) { el.classList.add('lg', 'lgflat'); return; }
      LG.lens(el, notchLensOpts(el));
    });
  }
}

function unlensNotchControls() {
  if (typeof LG === 'undefined') return;
  document.querySelectorAll('.island .lg').forEach((el) => { if (!el.classList.contains('glassbody')) { LG.unlens(el); el.classList.remove('lg', 'lgflat'); } });
}

// 본체: 크기가 변하는 동안은 렌즈를 풀었다가(필터 크기가 안 맞으면 가장자리가 빈다) 자리 잡으면 다시 건다
let bodyLensTimer = null;
function lensBody(on) {
  const body = document.getElementById('glassBody');
  if (!body || typeof LG === 'undefined') return;
  clearTimeout(bodyLensTimer);
  if (!on) { LG.unlens(body); return; }
  if (!LG.supported) return;
  bodyLensTimer = setTimeout(() => { LG.unlens(body); LG.lens(body, bodyLensOpts()); }, 30);
}

// 세기가 바뀌면 렌즈를 모두 다시 건다 (필터는 크기·세기별로 만들어 두므로 이전 것은 버린다)
function refreshNotchGlassStrength() {
  const k = glassK();
  if (Math.abs(k - notchGlassStrength) < 0.001) return;
  notchGlassStrength = k;
  if (notchGlassMode === 'off' || typeof LG === 'undefined') return;
  unlensNotchControls();
  lensBody(false);
  LG.reset();
  lensNotchControls(document);
  if (notchGlassMode === 'full') lensBody(true);
}

// 테두리(윤곽선) 두께는 화면 배율에 맞춰 '정수 물리 픽셀'로 맞춘다: 150% 배율에서 1px(=1.5칸)이면 왼쪽 선은 2칸, 오른쪽 선은 1칸으로 그려져 양쪽이 한 칸 어긋난다.
function setRimWidth() {
  const d = window.devicePixelRatio || 1;
  const phys = Math.max(1, Math.round(1.2 * d));
  document.documentElement.style.setProperty('--rim', `${(phys / d).toFixed(4)}px`);
}
window.addEventListener('resize', setRimWidth);
setRimWidth();

function applyNotchGlass(mode) {
  mode = ['off', 'controls', 'full'].includes(mode) ? mode : 'controls';
  const was = notchGlassMode;
  notchGlassMode = mode;
  notchGlassStrength = glassK();
  document.documentElement.dataset.glass = mode;
  if (mode === 'off') {
    unlensNotchControls();
    lensBody(false);
    if (notchGlassObs) { notchGlassObs.disconnect(); notchGlassObs = null; }
    setDesk(null);
    return;
  }
  if (typeof LG !== 'undefined') LG.bindPointerGlow();
  lensNotchControls(document);
  if (!notchGlassObs && window.MutationObserver) {          // 페이지가 그려질 때 새로 생기는 버튼/타일/칩에도 건다 (한 프레임에 한 번)
    let raf = 0;
    notchGlassObs = new MutationObserver(() => { if (!raf) raf = requestAnimationFrame(() => { raf = 0; if (notchGlassMode !== 'off') lensNotchControls(document); }); });
    notchGlassObs.observe(document.getElementById('island'), { childList: true, subtree: true });
  }
  if (mode === 'full') lensBody(true);
  else { lensBody(false); setDesk(null); }
}

// 파이썬이 찍어 보낸 뒤 화면(작은 PNG). null 이면 걷는다.
function setDesk(url) {
  const img = document.getElementById('deskImg');
  const root = document.documentElement;
  const sats = ['satDesk', 'satDeskL'].map((id) => document.getElementById(id)).filter(Boolean);           // 보조 노치(물방울, 오른쪽·왼쪽)도 같은 뒤 화면을 비춘다
  const goo = Array.from(document.querySelectorAll('.gimg'));    // 물방울·물줄기의 모양 레이어도 같은 화면으로 채운다(유리 모드에서 검정 얼룩이 생기지 않게)
  if (!img) return;
  if (!url || notchGlassMode !== 'full') { img.removeAttribute('src'); sats.forEach((e) => e.removeAttribute('src')); goo.forEach((g) => g.removeAttribute('src')); delete root.dataset.desk; return; }
  if (img.getAttribute('src') !== url) img.src = url;        // 같은 스트림 주소면 다시 열지 않는다
  sats.forEach((e) => { if (e.getAttribute('src') !== url) e.src = url; });
  goo.forEach((g) => { if (g.getAttribute('src') !== url) g.src = url; });
  root.dataset.desk = '1';
}

// 노치 크기가 변하는 동안(스프링 전환) 본체 렌즈가 매 프레임 지금 크기에 맞춰 따라가게 한다 — 끝난 뒤에야 생기는 '뿅' 하는 느낌이 없도록.
// 렌즈는 끄지 않고, 크기가 바뀔 때마다 그 크기에 맞는 변위 맵(1/4 해상도라 싸다)으로 바꿔 끼운다.
(function bindIslandSizeEvents() {
  const isl = document.getElementById('island');
  if (!isl) return;
  let following = false, lastW = 0, lastH = 0, settleTimer = null;
  const isSize = (e) => e.target === isl && (e.propertyName === 'width' || e.propertyName === 'height');
  const follow = () => {
    const b = document.getElementById('glassBody');
    if (!b || notchGlassMode !== 'full' || typeof LG === 'undefined') { following = false; return; }
    const w = Math.round(b.offsetWidth), h = Math.round(b.offsetHeight);      // 본체는 귀 자리까지 넓어져 있다
    if (w !== lastW || h !== lastH) { lastW = w; lastH = h; LG.refresh(b); }
    if (following) requestAnimationFrame(follow);
  };
  const start = (e) => {
    if (!isSize(e) || notchGlassMode !== 'full') return;
    clearTimeout(settleTimer);
    if (!following) { following = true; requestAnimationFrame(follow); }
  };
  const end = (e) => {
    if (!isSize(e) || notchGlassMode !== 'full') return;
    clearTimeout(settleTimer);
    settleTimer = setTimeout(() => {            // 두 속성(너비/높이)이 모두 끝난 뒤 한 번 더 맞추고 임시 필터를 치운다
      following = false;
      const b = document.getElementById('glassBody');
      if (b && typeof LG !== 'undefined') { LG.refresh(b); LG.gc(); }
    }, 80);
  };
  isl.addEventListener('transitionrun', start);
  isl.addEventListener('transitionstart', start);
  isl.addEventListener('transitionend', end);
  isl.addEventListener('transitioncancel', end);
})();
