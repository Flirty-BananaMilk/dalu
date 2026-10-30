// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
// Copyright (c) 2026 Flirty_BananaMilk — 상업적 이용 금지, 자세한 내용은 LICENSE
// ========================================================
// 설정 적용 (노치 화면). 설정 창이 바꾼 값은 파이썬이 'prefs' 이벤트로 알려 주고, 여기서 화면에 반영한다.
// 값은 store.settings 에 있고(저장도 거기서), 화면 쪽에서 매번 읽는 설정(알림 종류, 지연 시간, 눈 캐릭터 ...)은
// 쓰는 자리에서 직접 읽는다. 아래 applyPrefs 는 CSS 변수/속성처럼 '적용'이 필요한 것만 다룬다.
// ========================================================

const clampN = (v, lo, hi, d) => { const n = Number(v); return Number.isFinite(n) ? Math.max(lo, Math.min(hi, n)) : d; };

function applyPrefs() {
  const s = store.settings;
  const root = document.documentElement;

  // 애니메이션: 속도(전환 재생 배율), 탄성(스프링 곡선), 끄기, 등장 연출, 페이지 전환 방식
  const c = springCurves(s.bounce);
  root.style.setProperty('--spring', c.soft);
  root.style.setProperty('--spring-hard', c.hard);
  SPRING = c.hard;
  PREF.rate = clampN(clampN(s.animSpeed, 50, 200, 100) / 100, 0.3, 3, 1);
  PREF.animOff = !!s.animOff;
  PREF.entrance = !!s.entrance && !s.animOff;
  PREF.pageAnim = s.pageAnim === 'fade' ? 'fade' : 'slide';
  root.dataset.anim = s.animOff ? 'off' : 'on';

  // 모양
  root.dataset.theme = ['glass', 'tint'].includes(s.theme) ? s.theme : 'black';
  root.dataset.glow = s.lyricGlow ? '1' : '0';
  const gmode = ['off', 'controls', 'full'].includes(s.glassNotch) ? s.glassNotch : 'controls';
  root.dataset.rim = s.glassRim === false ? 'off' : 'on';      // 리퀴드 글래스 '전체'의 노치 테두리 선(끄면 유리만 보인다)
  if (typeof applyNotchGlass === 'function') { if (gmode !== notchGlassMode) applyNotchGlass(gmode); else refreshNotchGlassStrength(); }
  root.style.setProperty('--dkh', dockH() + 'px');
  root.style.setProperty('--dkc', (dockMargin() - 7) + 'px');
  if (typeof dockOn !== 'undefined' && dockOn) scheduleRegion();
  root.style.setProperty('--lyric-scale', String(clampN(s.lyricSize, 70, 140, 100) / 100));
  root.style.setProperty('--glow-str', String(s.artGlow ? clampN(s.glowStrength, 30, 160, 100) / 100 : 0));

  // 시계 형식이 바뀌었으면 바로 다시 그린다
  clockEl._k = '';
  if (typeof updateClock === 'function') updateClock();
  if (typeof miniIdx !== 'undefined') miniIdx = -1;                 // 단어 하이라이트 방식이 바뀌면 줄을 다시 만든다
  if (typeof listIdx !== 'undefined') { try { buildList(hasLyricLines() ? state.lyrics.lines : null); } catch (e) { /* 아직 가사 없음 */ } }
}

// 속도: CSS 전환(transition)은 시작될 때 재생 배율을 바꿔 빠르게/느리게 한다 (WAAPI 는 anim() 이 시간을 나눈다)
document.addEventListener('transitionrun', (e) => {
  if (PREF.rate === 1 || PREF.animOff || !e.target.getAnimations) return;
  for (const a of e.target.getAnimations()) {
    if (a.transitionProperty === e.propertyName && a.playbackRate !== PREF.rate) a.updatePlaybackRate(PREF.rate);
  }
}, true);

// 호버로 펼침: 지연(hoverDelay) 설정 — 스친 것만으로는 펼치지 않게
let enterTimer = null;
function onIslandEnter() {
  const d = clampN(store.settings.hoverDelay, 0, 2000, 0);
  if (!d || isExpanded) { triggerExpand(); return; }
  clearTimeout(enterTimer);
  enterTimer = setTimeout(triggerExpand, d);
}
function onIslandLeave() {
  clearTimeout(enterTimer);
  enterTimer = null;
  triggerCollapse();
}

const collapseDelayMs = () => clampN(store.settings.collapseDelay, 100, 5000, 850);
const idleAfterMs = () => clampN(store.settings.idleMin, 1, 60, 2) * 60000;
const petAfterSec = () => clampN(store.settings.petAfter, 5, 900, 45);
const petDozeSec = () => petAfterSec() + 105;          // 나타난 뒤 105초가 더 지나면 존다 (예전 45초 -> 150초 간격 그대로)

// 설정 창에서 온 패치를 store 에 합치고 화면에 반영한다 (설정 창이 파이썬에도 이미 저장했으므로 여기서는 메모리/화면만)
function mergePatch(dst, patch) {
  for (const k of Object.keys(patch || {})) {
    const v = patch[k];
    if (v && typeof v === 'object' && !Array.isArray(v) && dst[k] && typeof dst[k] === 'object') mergePatch(dst[k], v);
    else if (k in dst) dst[k] = v;
  }
}

function applyPrefPatch(patch) {
  const before = { lang: store.settings.lang, compact: store.settings.compact, lyricsOn: store.settings.lyricsOn };
  for (const sec of ['settings', 'pomo', 'water']) if (patch && patch[sec]) mergePatch(store[sec], patch[sec]);
  afterPrefsChanged(before, patch);
  saveStoreSoon();       // 메모리의 store 도 같은 값으로 저장돼 있어야, 다음 저장이 설정을 되돌리지 않는다
}

function afterPrefsChanged(before, patch) {
  const s = store.settings;
  applyPrefs();
  if (s.lang !== before.lang) { lang = normLang(s.lang); applyLang(); }
  if (s.compact !== before.compact) { compactMode = !!s.compact; island.classList.toggle('compact', compactMode); miniIdx = -1; scheduleRegion(); }
  updateLyricsButtons();
  updateSoundMenu();
  if (typeof refreshPageDots === 'function') refreshPageDots();
  if (typeof updateDockTitles === 'function') updateDockTitles();
  if (store.settings.tabDock === false && typeof setDock === 'function') setDock(false);
  if (typeof agendaPrefsChanged === 'function') agendaPrefsChanged();
  if (typeof syncFocusDnd === 'function') syncFocusDnd();       // 집중 중에 방해 금지 설정을 껐다 켰다 한 경우
  if (patch && (patch.pomo || patch.water)) {
    if (patch.pomo && typeof pomoSettingsChanged === 'function') pomoSettingsChanged();
    renderAllFeatures();
  }
  updateView();
}

// 모든 설정을 기본값으로 되돌렸다: 저장된 값을 다시 읽어 적용한다
async function reloadPrefs() {
  const before = { lang: store.settings.lang, compact: store.settings.compact, lyricsOn: store.settings.lyricsOn };
  const keep = { todos: store.todos, shelf: store.shelf, buds: store.buds };
  await loadStore();
  store.todos = keep.todos; store.shelf = keep.shelf; store.buds = keep.buds;     // 이 데이터는 설정 초기화와 무관
  afterPrefsChanged(before, { pomo: {}, water: {} });
}
