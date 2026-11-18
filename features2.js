// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
// Copyright (c) 2026 Flirty_BananaMilk — 상업적 이용 금지, 자세한 내용은 LICENSE
// ========================================================
// 추가 기능: 타이머/스톱워치 페이지, 클립보드 기록 페이지, 일정(캘린더) 페이지,
//           노치 안 볼륨 조절(팝오버 / Ctrl+휠), 재생 소스 전환 버튼
// (features.js 다음, prefs.js 앞에 로드된다)
// ========================================================

// ---------------------------------------------------------------- 페이지 사용 가능 여부 / 도트
// 이어버드는 연결됐을 때만, 클립보드는 설정에서 켰을 때만, 일정은 캘린더 주소가 있을 때만 넘길 수 있다.
function pageAvailable(p) {
  if (p === 'plugins') return pluginsEnabled().length > 0;
  if (p === 'buds') return typeof budsConnected === 'function' && budsConnected();
  if (p === 'clip') return !!store.settings.clipboardOn;
  if (p === 'agenda') return !!String(store.settings.calendarUrl || '').trim() || (typeof ddayAll === 'function' && ddayAll().length > 0);
  return true;
}

// 설정(tabOrder/tabHidden)에 맞춰 도트를 순서대로 놓고, 숨기거나 쓸 수 없는 탭의 도트는 감춘다
let tabSig = '';
// 탭 아이콘 독: 점마다 아이콘을 넣어 두고(평소엔 점이라 보이지 않는다), 점 위에 마우스를 올리면 점들이 큰 아이콘으로 바뀐다
const DOCK_ICON = { music: 'music', pomo: 'target', timer: 'timer', water: 'drop', shelf: 'folder', todo: 'checklist', clip: 'clipboard', agenda: 'calendar', launcher: 'launch', sys: 'sliders', power: 'power', perf: 'gauge', weather: 'cloudsun', phone: 'phone', dday: 'hourglass', plugins: 'plug', buds: 'headphones' };
let dockTimer = null;
function initDock() {
  const dots = $('pageDots');
  for (const d of $$('#pageDots i')) d.innerHTML = uiIconHtml(DOCK_ICON[d.dataset.p] || 'puzzle', d.dataset.p);
  updateDockTitles();
  const near = (e, pad) => { const r = dots.getBoundingClientRect(); return e.clientX >= r.left - pad && e.clientX <= r.right + pad && e.clientY >= r.top - pad && e.clientY <= r.bottom + pad; };
  island.addEventListener('mousemove', (e) => {
    if (!isExpanded || !isPageView(view || '')) return;
    const hit = near(e, dockOn ? 12 : 4);
    clearTimeout(dockTimer);
    if (hit && !dockOn) dockTimer = setTimeout(() => setDock(true), clampN(store.settings.tabDockDelay, 0, 1000, 130));          // 스치기만 해서는 열리지 않는다
    else if (!hit && dockOn) dockTimer = setTimeout(() => setDock(false), clampN(store.settings.tabDockLeave, 0, 2000, 260));
  });
  island.addEventListener('mouseleave', () => { clearTimeout(dockTimer); if (dockOn) dockTimer = setTimeout(() => setDock(false), clampN(store.settings.tabDockLeave, 0, 2000, 260)); });
}
function updateDockTitles() {
  for (const d of $$('#pageDots i')) d.title = t('tab_' + d.dataset.p);
}

function refreshPageDots() {
  const order = parseTabOrder(store.settings.tabOrder);
  const sig = order.join(',');
  const dots = $('pageDots');
  if (sig !== tabSig) {
    tabSig = sig;
    for (const id of order) { const d = dots.querySelector(`i[data-p="${id}"]`); if (d) dots.appendChild(d); }     // DOM 순서 = 탭 순서
  }
  const shown = new Set(availablePages());
  for (const dot of $$('#pageDots i')) {
    dot.classList.toggle('hidden', !shown.has(dot.dataset.p) || shown.size === 1);
    dot.classList.toggle('on', dot.dataset.p === page);
  }
  if (!shown.has(page) && isPageView(view || '')) setPage([...shown][0] || 'music', -1);   // 지금 보던 페이지가 숨겨졌다
}

// ---------------------------------------------------------------- 타이머 / 스톱워치
// 타이머와 스톱워치는 서로 독립이다: 하나를 돌려 둔 채 다른 탭에서 다른 하나를 쓸 수 있다. 탭(tmrMode)은 지금 보고 있는 쪽일 뿐이다.
const tmrS = {
  timer: { total: 300, remaining: 300, running: false, endsAt: 0 },
  stopwatch: { elapsed: 0, running: false, startedAt: 0, baseElapsed: 0, laps: [] },      // laps: 구간 기록 [{n, total, split}] (초, 화면에만 있고 저장하지 않는다)
};
const LAP_MAX = 99;
let tmrMode = 'timer';

function tmrMinutes() { return clampN(store.timer && store.timer.minutes, 1, 600, 5); }

function tmrActiveOf(mode) {
  if (mode === 'timer') { const s = tmrS.timer; return s.running || s.remaining < s.total; }
  const s = tmrS.stopwatch;
  return s.running || s.elapsed > 0;
}
function tmrActive() { return tmrActiveOf('timer') || tmrActiveOf('stopwatch'); }
function tmrRunning(mode) { return tmrS[mode === 'stopwatch' ? 'stopwatch' : 'timer'].running; }

function tmrSetMode(mode) {      // 보는 탭만 바꾼다 (돌아가던 것은 그대로 계속 돈다)
  tmrMode = mode === 'stopwatch' ? 'stopwatch' : 'timer';
  tmrPickClose();
  if (store.timer) store.timer.mode = tmrMode;
  renderTimer();
}

// 시간 직접 설정: 큰 시간 글자를 누르면 선택기(시간 : 분)가 열린다. 할 일 탭의 선택기와 같은 모양(− 값 + 버튼, 휠, 확인/취소).
// 분은 5분 단위로 오르내리고(미세 조정은 −1/+1/+5 버튼), 시간은 0~10, 전체는 1분~10시간이다. 진행 중인 타이머는 건드리지 않는다.
const tk = { h: 0, m: 25 };
function tmrPickRender() { setText($('tkH'), String(tk.h)); setText($('tkM'), pad2(tk.m)); }
function tmrPickOpen() {
  if (tmrMode !== 'timer' || tmrActiveOf('timer')) return;
  const min = tmrMinutes();
  tk.h = Math.floor(min / 60); tk.m = min % 60;
  tmrPickRender();
  $('timerLayer').classList.add('picking');
}
function tmrPickClose() { const l = $('timerLayer'); if (l) l.classList.remove('picking'); }
function tmrPickStep(which, dir) {
  if (which === 'h') tk.h = (tk.h + dir + 11) % 11;
  else tk.m = ((dir > 0 ? Math.floor(tk.m / 5) + 1 : Math.ceil(tk.m / 5) - 1) * 5 + 60) % 60;
  if (tk.h >= 10) tk.m = 0;      // 최대 10시간
  tmrPickRender();
}
function tmrPickOk() {
  store.timer.minutes = clampN(tk.h * 60 + tk.m, 1, 600, 5);
  saveStoreSoon();
  tmrReset('timer');
  tmrPickClose();
}

function tmrReset(mode) {
  mode = mode || tmrMode;
  if (mode === 'timer') {
    const s = tmrS.timer;
    s.running = false;
    s.total = Math.round(tmrMinutes() * 60);
    s.remaining = s.total;
  } else {
    const s = tmrS.stopwatch;
    s.running = false; s.elapsed = 0; s.baseElapsed = 0; s.laps = [];
  }
  renderTimer();
}

function tmrStartPause(mode) {
  mode = mode || tmrMode;
  if (mode === 'timer') {
    const s = tmrS.timer;
    if (s.running) { s.remaining = Math.max(0, Math.ceil((s.endsAt - Date.now()) / 1000)); s.running = false; }
    else {
      if (s.remaining <= 0) s.remaining = s.total;
      s.endsAt = Date.now() + s.remaining * 1000; s.running = true;
    }
  } else {
    const s = tmrS.stopwatch;
    if (s.running) { s.elapsed = s.baseElapsed + (Date.now() - s.startedAt) / 1000; s.running = false; }
    else { s.baseElapsed = s.elapsed; s.startedAt = Date.now(); s.running = true; }
  }
  renderTimer();
}

// 스톱워치 구간 기록: 돌아가는 동안 누르면 지금까지의 시간(total)과 앞 기록 이후의 시간(split)을 남긴다. 새 기록이 맨 위에 보인다.
function tmrLap() {
  const s = tmrS.stopwatch;
  if (!s.running) return;
  const total = s.baseElapsed + (Date.now() - s.startedAt) / 1000;
  const prev = s.laps.length ? s.laps[s.laps.length - 1].total : 0;
  s.laps.push({ n: (s.laps.length ? s.laps[s.laps.length - 1].n : 0) + 1, total, split: Math.max(0, total - prev) });
  if (s.laps.length > LAP_MAX) s.laps.shift();
  renderTimer();
  const box = $('lapList');
  if (box) box.scrollTop = 0;
}

// 기록 시간은 소수 첫째 자리까지 (mm:ss.t, 한 시간이 넘으면 h:mm:ss.t)
function fmtLap(sec) {
  const tenth = Math.floor(Math.max(0, sec) * 10);
  const t10 = tenth % 10, s = Math.floor(tenth / 10);
  const h = Math.floor(s / 3600);
  return (h ? `${h}:${pad2(Math.floor(s / 60) % 60)}` : pad2(Math.floor(s / 60))) + ':' + pad2(s % 60) + '.' + t10;
}

let lapSig = '';
function renderLaps() {
  const laps = tmrS.stopwatch.laps;
  const box = $('lapList');
  if (!box) return;
  setText($('lapEmpty'), t('lapEmpty'));
  $('lapEmpty').style.display = laps.length ? 'none' : '';
  const sig = laps.length + ':' + (laps.length ? laps[laps.length - 1].total : 0) + ':' + lang;
  if (sig === lapSig) return;
  lapSig = sig;
  // 가장 빠른/느린 구간 표시: 구간이 셋 이상일 때만 (둘뿐이면 항상 하나씩 되어 의미가 없다)
  let best = -1, worst = -1;
  if (laps.length >= 3) {
    let lo = Infinity, hi = -Infinity;
    laps.forEach((l, i) => { if (l.split < lo) { lo = l.split; best = i; } if (l.split >= hi) { hi = l.split; worst = i; } });
  }
  box.textContent = '';
  for (let i = laps.length - 1; i >= 0; i--) {
    const l = laps[i];
    const row = document.createElement('div');
    row.className = 'laprow' + (i === best ? ' best' : i === worst ? ' worst' : '');
    const n = document.createElement('span'); n.className = 'lapn'; n.textContent = String(l.n);
    const tot = document.createElement('span'); tot.className = 'lapt'; tot.textContent = fmtLap(l.total);
    const sp = document.createElement('span'); sp.className = 'laps'; sp.textContent = '+' + fmtLap(l.split);
    row.append(n, tot, sp);
    box.appendChild(row);
  }
}

function tmrAdjust(deltaMin) {
  if (tmrMode !== 'timer') return;
  const s = tmrS.timer;
  if (tmrActiveOf('timer')) {              // 진행 중이면 남은 시간에 더하거나 뺀다
    const left = s.running ? Math.max(0, (s.endsAt - Date.now()) / 1000) : s.remaining;
    const next = Math.max(1, Math.round(left + deltaMin * 60));
    s.total = Math.max(s.total, next);
    s.remaining = next;
    if (s.running) s.endsAt = Date.now() + next * 1000;
  } else {
    store.timer.minutes = clampN(tmrMinutes() + deltaMin, 1, 600, 5);
    saveStoreSoon();
    tmrReset('timer');
    return;
  }
  renderTimer();
}

function tmrTick() {
  const t1 = tmrS.timer, sw = tmrS.stopwatch;
  if (t1.running) {
    const left = Math.max(0, Math.ceil((t1.endsAt - Date.now()) / 1000));
    if (left !== t1.remaining) { t1.remaining = left; renderTimer(); }
    if (left <= 0) tmrComplete();
  }
  if (sw.running) {
    const e = sw.baseElapsed + (Date.now() - sw.startedAt) / 1000;
    if (Math.floor(e) !== Math.floor(sw.elapsed)) { sw.elapsed = e; renderTimer(); } else sw.elapsed = e;
  }
}

function tmrComplete() {
  const s = tmrS.timer;
  s.running = false;
  s.remaining = 0;
  playChime('pomo');
  notify({ icon: 'timer', tone: 'green', ms: 6000, title: t('timerDone'), sub: t('timerDoneSub', { n: Math.round(s.total / 60) }) });
  renderTimer();
  setTimeout(() => tmrReset('timer'), 100);      // 다음 사용을 위해 처음 값으로 되돌린다 (알림은 이미 떴다). 스톱워치는 건드리지 않는다
}

function fmtClock(sec) {
  const s = Math.max(0, Math.floor(sec));
  const h = Math.floor(s / 3600);
  return (h ? `${h}:${pad2(Math.floor(s / 60) % 60)}` : pad2(Math.floor(s / 60))) + ':' + pad2(s % 60);
}

// 접힌 노치의 칩: 진행 중인 것 중 가장 앞선 하나(포모도로 > 타이머 > 스톱워치)를 보여 준다
function renderChip() {
  const info = chipInfo();
  const active = info.active;
  if (info.text) setTextAll($$('.tchip .js-ttime'), info.text);
  for (const el of $$('.tchip')) { el.dataset.k = info.kind === 'stopwatch' ? 'sw' : ''; el.dataset.run = info.running ? '1' : '0'; }
  for (const el of $$('.tring')) if (!el.classList.contains('sat-ring')) el.style.setProperty('--p', info.pct.toFixed(2));
  const chipChanged = island.dataset.chip !== (active ? '1' : '0');
  island.dataset.chip = active ? '1' : '0';
  island.dataset.timer = active ? '1' : '0';
  if (chipChanged) { updateView(); scheduleRegion(); } else if (typeof renderSat === 'function') renderSat();
}

// 선택 타원: 선택된 탭 버튼의 위치/폭에 맞춘다. 버튼 폭은 글꼴이 늦게 바뀌거나(웹/시스템 글꼴 로딩) 페이지가 숨겨져 있다 나타나는 때에
// 뒤늦게 달라질 수 있어서(그러면 타원이 옛 폭으로 남아 어긋났다), 크기가 바뀔 때마다 다시 맞춘다 (initTimer 의 ResizeObserver).
function tmrPlaceHl() {
  const hl = $('tmHl'), on = document.querySelector('#tmModes button.on');
  if (!hl || !on || !on.offsetWidth) return;
  hl.style.width = `${on.offsetWidth}px`;
  hl.style.transform = `translateX(${on.offsetLeft}px)`;
}

function renderTimer() {
  const timerMode = tmrMode === 'timer';
  setText($('tmTime'), fmtClock(timerMode ? tmrS.timer.remaining : tmrS.stopwatch.elapsed));
  $('timerLayer').dataset.m = tmrMode;
  $('timerLayer').dataset.act = tmrActiveOf('timer') ? '1' : '0';
  for (const b of $$('#tmModes button')) {
    b.classList.toggle('on', b.dataset.m === tmrMode);
    b.classList.toggle('run', b.dataset.m !== tmrMode && tmrRunning(b.dataset.m));      // 다른 탭에서 돌고 있다는 작은 점
  }
  tmrPlaceHl();
  const running = tmrRunning(tmrMode);
  setText($('tmStartText'), t(running ? 'pause' : (tmrActiveOf(tmrMode) ? 'resume' : 'start')));
  $('tmStartIcon').setAttribute('d', running ? ICONS.pause : ICONS.play);
  $('tmAdj').style.visibility = timerMode ? 'visible' : 'hidden';
  $('tmLap').disabled = !(tmrMode === 'stopwatch' && tmrS.stopwatch.running);      // 돌아가는 동안만 기록할 수 있다
  renderLaps();
  $('timerLayer').dataset.run = running ? '1' : '0';
  renderChip();
}

function initTimer() {
  store.timer = store.timer || { minutes: 5, mode: 'timer' };
  tmrMode = store.timer.mode === 'stopwatch' ? 'stopwatch' : 'timer';
  tmrReset('timer'); tmrReset('stopwatch');
  $('tmStart').addEventListener('click', () => tmrStartPause());
  $('tmReset').addEventListener('click', () => tmrReset());
  $('tmLap').addEventListener('click', () => tmrLap());
  $('tmTime').addEventListener('click', tmrPickOpen);
  for (const st of $$('#tmPick .stepper')) {
    for (const b of st.querySelectorAll('button')) b.addEventListener('click', () => tmrPickStep(st.dataset.t, Number(b.dataset.d)));
    st.addEventListener('wheel', (e) => { e.preventDefault(); e.stopPropagation(); tmrPickStep(st.dataset.t, e.deltaY < 0 ? 1 : -1); }, { passive: false });      // 휠: 위로 올리면 커진다
  }
  $('tkOk').addEventListener('click', tmrPickOk);
  $('tkCancel').addEventListener('click', tmrPickClose);
  $('tmPick').addEventListener('keydown', (e) => {
    if (e.key === 'Escape') { e.stopPropagation(); tmrPickClose(); }
    else if (e.key === 'Enter') { e.preventDefault(); tmrPickOk(); }
  });
  for (const b of $$('#tmModes button')) b.addEventListener('click', () => tmrSetMode(b.dataset.m));
  for (const b of $$('#tmAdj [data-d]')) b.addEventListener('click', () => tmrAdjust(Number(b.dataset.d)));
  langHooks.push(renderTimer);
  if (window.ResizeObserver) {          // 버튼/탭 줄의 크기가 바뀌면(글꼴 로딩, 페이지가 보이기 시작) 선택 타원을 다시 맞춘다
    const ro = new ResizeObserver(() => tmrPlaceHl());
    ro.observe($('tmModes'));
    for (const b of $$('#tmModes button')) ro.observe(b);
  }
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(tmrPlaceHl);
}

// ---------------------------------------------------------------- 클립보드 기록 페이지
let clipSig = '';
function fmtAgo(ts) {
  const s = Math.max(0, Math.floor(Date.now() / 1000 - ts));
  if (s < 60) return t('agoNow');
  if (s < 3600) return t('agoMin', { n: Math.floor(s / 60) });
  return t('agoHour', { n: Math.floor(s / 3600) });
}

async function clipRefresh(force) {
  const api = getApi();
  if (!api || !api.clip_list) return;
  let d; try { d = await api.clip_list(); } catch (e) { return; }
  if (!d) return;
  const sig = JSON.stringify([d.enabled, d.items.map((i) => i.id)]);
  if (sig === clipSig && !force) return;
  clipSig = sig;
  const list = $('clipList'), empty = $('clipEmpty');
  list.textContent = '';
  setText($('clipCount'), d.enabled ? String(d.items.length) : '');
  $('clipClear').style.display = d.items.length ? '' : 'none';
  empty.style.display = d.items.length ? 'none' : '';
  empty.textContent = '';
  if (!d.enabled) {
    empty.append(t('clipOff'), document.createElement('br'));
    const b = document.createElement('button');
    b.className = 'pill'; b.style.marginTop = '8px'; b.textContent = t('openSettings');
    b.addEventListener('click', (e) => { e.stopPropagation(); const a = getApi(); if (a) a.open_settings('tools'); });
    empty.appendChild(b);
  } else if (!d.items.length) empty.textContent = t('clipEmpty');
  for (const it of d.items) {
    const row = document.createElement('div');
    row.className = 'trow cliprow';
    row.title = it.text.length > 300 ? it.text.slice(0, 300) + '…' : it.text;
    const tx = document.createElement('span'); tx.className = 'tx'; tx.textContent = it.text.replace(/\s+/g, ' ');
    const ago = document.createElement('span'); ago.className = 'due'; ago.textContent = fmtAgo(it.t);
    const del = document.createElement('button'); del.className = 'del'; del.title = t('delete');
    del.innerHTML = `<svg viewBox="0 0 24 24"><path d="${ICONS.close}"/></svg>`;
    del.addEventListener('click', async (e) => { e.stopPropagation(); await api.clip_delete(it.id); clipRefresh(true); });
    row.addEventListener('click', async () => { const r = await api.clip_use(it.id); showToast(t(r && r.status === 'ok' ? 'clipCopied' : 'failed')); clipRefresh(true); });
    row.append(tx, ago, del);
    list.appendChild(row);
  }
  enterLate('clip', '.l-clip .trow', RISE, 260, 45, { duration: 480 });
  enterLate('clip', '.l-clip .tempty', FADE, 280, 0, { duration: 500 });
}

function initClip() {
  $('clipClear').addEventListener('click', async () => { const api = getApi(); if (api) { await api.clip_clear(); clipRefresh(true); } });
  setInterval(() => { if (page === 'clip' && isExpanded) clipRefresh(false); }, 900);
}

// ---------------------------------------------------------------- 일정: 목록 / 주 / 월 보기
const AG_SIZE = { list: { w: 420, h: 140, e: 22 }, week: { w: 420, h: 140, e: 22 }, month: { w: 480, h: 176, e: 22 } };
const ag = { view: 'list', anchor: null, sel: null, events: [], key: '', at: 0, error: '' };
const agStart = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate());
const agAdd = (d, n) => new Date(d.getFullYear(), d.getMonth(), d.getDate() + n);
const agKey = (d) => `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`;
const agLocale = () => ({ ko: 'ko-KR', en: 'en-US', zh: 'zh-CN', ja: 'ja-JP' }[lang] || 'en-US');
const agWeekFirst = (d) => agAdd(d, -((d.getDay() - (store.settings.weekStart === 'mon' ? 1 : 0) + 7) % 7));       // 그 날이 속한 주의 첫 날
const AG_ARROW_L = 'M15.41 7.41 14 6l-6 6 6 6 1.41-1.41L10.83 12z', AG_ARROW_R = 'M8.59 16.59 13.17 12 8.59 7.41 10 6l6 6-6 6z';

// 지금 보이는 칸들이 덮는 기간(월 보기: 6주, 주 보기: 7일)
function agRange() {
  if (ag.view === 'week') return { s: agWeekFirst(ag.anchor), days: 7 };
  return { s: agWeekFirst(new Date(ag.anchor.getFullYear(), ag.anchor.getMonth(), 1)), days: 42 };
}

// 날짜별 일정 (여러 날에 걸친 일정은 걸친 날마다 넣는다. 종일 일정의 끝은 다음 날 0시라 그 전 날까지)
function agBuckets() {
  const m = new Map();
  for (const ev of ag.events) {
    const sMs = ev.start * 1000, eMs = Math.max(ev.end, ev.start) * 1000;
    let d = agStart(new Date(sMs));
    const last = agStart(new Date(eMs > sMs ? eMs - 1 : sMs));
    for (let i = 0; i < 62 && d <= last; i++, d = agAdd(d, 1)) {
      const k = agKey(d);
      if (!m.has(k)) m.set(k, []);
      m.get(k).push(ev);
    }
  }
  return m;
}

function agSetView(v, opts) {
  if (!AG_SIZE[v]) v = 'list';
  const changed = ag.view !== v;
  ag.view = v;
  if (!ag.anchor) { ag.anchor = agStart(new Date()); ag.sel = ag.anchor; }
  $('agendaLayer').classList.remove('v-list', 'v-week', 'v-month');
  $('agendaLayer').classList.add('v-' + v);
  for (const b of $$('#agendaSeg button')) b.classList.toggle('on', b.dataset.v === v);
  Object.assign(STATES.agenda, AG_SIZE[v]);       // 월 보기는 칸이 많아 노치가 조금 더 커진다 (실제 크기는 island.css 의 data-ag)
  island.dataset.ag = v;
  if (changed && !(opts && opts.quiet)) {
    store.settings.agendaView = v; saveStoreSoon();
    if (page === 'agenda' && isExpanded) { updateView(); scheduleRegion(); }
  }
  ag.key = '';
  if (v === 'list') { if (page === 'agenda') agendaRefresh(true); }
  else { agCalRender(); agCalFetch(true); }
}

function agNav(dir) {
  if (ag.view === 'week') { ag.anchor = agAdd(ag.anchor, 7 * dir); ag.sel = agAdd(ag.sel, 7 * dir); }
  else {
    const a = new Date(ag.anchor.getFullYear(), ag.anchor.getMonth() + dir, 1), now = agStart(new Date());
    ag.anchor = a;
    ag.sel = (a.getFullYear() === now.getFullYear() && a.getMonth() === now.getMonth()) ? now : a;
  }
  agCalRender(); agCalFetch(false);
}

function agToday() { ag.anchor = agStart(new Date()); ag.sel = ag.anchor; agCalRender(); agCalFetch(false); }

async function agCalFetch(force) {
  const api = getApi();
  if (!api || !api.calendar_range || ag.view === 'list') return;
  const r = agRange(), key = `${r.s.getTime()}|${r.days}`;
  if (!force && key === ag.key && Date.now() - ag.at < 15000) return;
  let d; try { d = await api.calendar_range(r.s.getTime() / 1000, r.days); } catch (e) { return; }
  if (!d) return;
  const r2 = agRange();
  if (`${r2.s.getTime()}|${r2.days}` !== key) return;        // 기다리는 동안 다른 달로 넘어갔다면 버린다
  ag.key = key; ag.at = Date.now(); ag.error = d.error || ''; ag.events = d.events || [];
  agCalRender();
}

function agNavBtn(path, dir, title, cls) {
  const b = document.createElement('button');
  if (cls) b.className = cls;
  b.title = title; b.innerHTML = `<svg viewBox="0 0 24 24"><path d="${path}"/></svg>`;
  b.addEventListener('click', (e) => { e.stopPropagation(); agNav(dir); });
  return b;
}

function agCalRender() {
  if (ag.view === 'list' || !ag.anchor) return;
  const loc = agLocale(), grid = $('agGrid'), buckets = agBuckets(), today = agStart(new Date()), r = agRange();
  grid.textContent = '';
  const wdFmt = new Intl.DateTimeFormat(loc, { weekday: lang === 'en' ? 'short' : 'narrow' });
  if (ag.view === 'month') {
    const nav = document.createElement('div'); nav.className = 'agnav';
    const lab = document.createElement('span'); lab.className = 'agt'; lab.title = t('agendaToday');
    lab.textContent = new Intl.DateTimeFormat(loc, { year: 'numeric', month: 'long' }).format(ag.anchor);
    lab.addEventListener('click', (e) => { e.stopPropagation(); agToday(); });
    nav.append(agNavBtn(AG_ARROW_L, -1, t('agendaPrev')), lab, agNavBtn(AG_ARROW_R, 1, t('agendaNext')));
    const wd = document.createElement('div'); wd.className = 'agwd';
    for (let i = 0; i < 7; i++) { const s = document.createElement('span'); s.textContent = wdFmt.format(agAdd(r.s, i)); wd.append(s); }
    const g = document.createElement('div'); g.className = 'agg';
    for (let i = 0; i < 42; i++) {
      const d = agAdd(r.s, i), c = document.createElement('button');
      c.className = 'cell' + (d.getMonth() !== ag.anchor.getMonth() ? ' out' : '') + (buckets.has(agKey(d)) ? ' has' : '') + (agKey(d) === agKey(today) ? ' today' : '') + (agKey(d) === agKey(ag.sel) ? ' sel' : '');
      c.textContent = String(d.getDate());
      c.addEventListener('click', (e) => {
        e.stopPropagation(); ag.sel = d;
        if (d.getMonth() !== ag.anchor.getMonth()) { ag.anchor = new Date(d.getFullYear(), d.getMonth(), 1); agCalFetch(false); }
        agCalRender();
      });
      g.append(c);
    }
    grid.append(nav, wd, g);
  } else {
    const wk = document.createElement('div'); wk.className = 'agwk';
    wk.append(agNavBtn(AG_ARROW_L, -1, t('agendaPrev'), 'wnav'));
    for (let i = 0; i < 7; i++) {
      const d = agAdd(r.s, i), c = document.createElement('button');
      c.className = 'wcell' + (buckets.has(agKey(d)) ? ' has' : '') + (agKey(d) === agKey(today) ? ' today' : '') + (agKey(d) === agKey(ag.sel) ? ' sel' : '');
      c.innerHTML = '<small></small><b></b>';
      c.querySelector('small').textContent = wdFmt.format(d); c.querySelector('b').textContent = String(d.getDate());
      c.addEventListener('click', (e) => { e.stopPropagation(); ag.sel = d; agCalRender(); });
      wk.append(c);
    }
    wk.append(agNavBtn(AG_ARROW_R, 1, t('agendaNext'), 'wnav'));
    grid.append(wk);
  }
  // 고른 날의 일정
  const evs = (buckets.get(agKey(ag.sel)) || []).slice();
  const dayMs = agStart(ag.sel).getTime(), nowSec = Date.now() / 1000;
  setText($('agDayHead'), new Intl.DateTimeFormat(loc, { month: 'long', day: 'numeric', weekday: 'short' }).format(ag.sel));
  const list = $('agDayList'); list.textContent = '';
  if (!evs.length) { const n = document.createElement('div'); n.className = 'none'; n.textContent = ag.error ? t('agendaError') : t('agendaDayEmpty'); list.append(n); }
  for (const ev of evs) {
    const row = document.createElement('div');
    row.className = 'trow agenda' + (ev.start <= nowSec && ev.end >= nowSec ? ' now' : '');
    const title = ev.title || t('agendaNoTitle');
    row.title = ev.location ? `${title} — ${ev.location}` : title;
    const when = document.createElement('span'); when.className = 'due'; when.style.minWidth = '40px';
    const sd = new Date(ev.start * 1000);
    when.textContent = ev.allDay ? t('agendaAllDay') : (ev.start * 1000 < dayMs ? t('agendaCont') : fmtHM(sd.getHours(), sd.getMinutes()));
    const tx = document.createElement('span'); tx.className = 'tx'; tx.textContent = title;
    row.append(when, tx, ddayStarButton(title, ev.start));
    list.append(row);
  }
}

// 설정 창에서 보기/주 시작 요일을 바꿨을 때
function agendaPrefsChanged() {
  const v = store.settings.agendaView || 'list';
  if (v !== ag.view) { agSetView(v, { quiet: true }); if (page === 'agenda' && isExpanded && typeof scheduleRegion === 'function') scheduleRegion(); }          // 보기가 바뀌면 노치 크기도 바뀌니 창 영역을 다시 맞춘다
  else if (ag.view !== 'list') { ag.key = ''; agCalRender(); agCalFetch(true); }
}

// ---------------------------------------------------------------- 일정 페이지
let agendaSig = '';
function agendaWhen(ev, now) {
  if (ev.allDay) return t('agendaAllDay');
  const d = new Date(ev.start * 1000);
  return fmtHM(d.getHours(), d.getMinutes());
}
function agendaDay(ev) {
  const d = new Date(ev.start * 1000), today = new Date();
  const dayDiff = Math.round((new Date(d.getFullYear(), d.getMonth(), d.getDate()) - new Date(today.getFullYear(), today.getMonth(), today.getDate())) / 86400000);
  if (dayDiff <= 0) return '';
  if (dayDiff === 1) return t('agendaTomorrow');
  return `${d.getMonth() + 1}/${d.getDate()}`;
}

async function agendaRefresh(force) {
  if (ag.view !== 'list') { agCalFetch(force); return; }
  const api = getApi();
  if (!api || !api.calendar_get) return;
  let d; try { d = await api.calendar_get(!!force); } catch (e) { return; }
  if (!d) return;
  const nowSec = Date.now() / 1000;
  const sig = JSON.stringify([d.configured, d.error, d.events.map((e) => [e.title, e.start]), Math.floor(nowSec / 60), ddS.items.map((x) => [x.id, x.date, x.done]), lang]);
  if (sig === agendaSig && !force) return;
  agendaSig = sig;
  const list = $('agendaList'), empty = $('agendaEmpty');
  list.textContent = '';
  const evs = d.events.filter((e) => e.end >= nowSec);
  const ddRows = ddayRows();
  for (const r of ddRows) list.appendChild(r);
  setText($('agendaCount'), evs.length ? String(evs.length) : '');
  empty.style.display = (evs.length || ddRows.length) ? 'none' : '';
  empty.textContent = d.error ? t('agendaError') : (d.configured ? t('agendaEmpty') : t('agendaNoSource'));
  for (const ev of evs) {
    const row = document.createElement('div');
    row.className = 'trow agenda' + (ev.start <= nowSec ? ' now' : '');
    const evTitle = ev.title || t('agendaNoTitle');      // 제목이 없는 일정
    row.title = ev.location ? `${evTitle} — ${ev.location}` : evTitle;
    const day = agendaDay(ev);
    const when = document.createElement('span'); when.className = 'due';
    when.textContent = (day ? day + ' ' : '') + agendaWhen(ev, nowSec);
    when.style.minWidth = '58px';
    const tx = document.createElement('span'); tx.className = 'tx'; tx.textContent = evTitle;
    const rel = document.createElement('span'); rel.className = 'due';
    const mins = Math.round((ev.start - nowSec) / 60);
    rel.textContent = ev.start <= nowSec ? t('agendaNow') : (mins < 60 ? t('agendaInMin', { n: mins }) : '');
    row.append(when, tx, rel, ddayStarButton(evTitle, ev.start));
    list.appendChild(row);
  }
  enterLate('agenda', '.l-agenda .trow', RISE, 260, 45, { duration: 480 });
  enterLate('agenda', '.l-agenda .tempty', FADE, 280, 0, { duration: 500 });
}

function initAgenda() {
  for (const b of $$('#agendaSeg button')) b.addEventListener('click', (e) => { e.stopPropagation(); agSetView(b.dataset.v); });
  agSetView(store.settings.agendaView || 'list', { quiet: true });
  $('agendaRefresh').addEventListener('click', () => {
    if (ag.view !== 'list') { const a = getApi(); if (a && a.calendar_get) a.calendar_get(true); setTimeout(() => agCalFetch(true), 900); }       // 주소를 다시 읽게 한 뒤 새로 그린다
    else agendaRefresh(true);
    showToast(t('agendaRefreshing'));
  });
  setInterval(() => { if (page === 'agenda' && isExpanded) agendaRefresh(false); }, 5000);
}

// ---------------------------------------------------------------- 볼륨 팝오버 / Ctrl+휠
const vol = { v: 0.5, muted: false, open: false, dragging: false, timer: null, sendTimer: null };

function volIconPath(v, muted) {
  return muted || v === 0 ? ICONS.volumeOff : ICONS.volume;
}

function volRender() {
  const pct = Math.round(vol.v * 100);
  const slider = $('volSlider');
  if (!vol.dragging) slider.value = pct;
  slider.style.setProperty('--fill', `${vol.dragging ? slider.value : pct}%`);
  setText($('volOut'), `${vol.dragging ? slider.value : pct}%`);
  const p = volIconPath(vol.v, vol.muted);
  $('volIcon').setAttribute('d', p);
  $('volMuteIcon').setAttribute('d', p);
}

function volKeepOpen() {
  clearTimeout(vol.timer);
  vol.timer = setTimeout(() => { if (!vol.dragging) volClose(); else volKeepOpen(); }, 2600);
}

async function volOpen() {
  const api = getApi();
  vol.open = true;
  $('playerLayer').classList.add('voling');
  volKeepOpen();
  if (api && api.mixer_get) {
    try { const d = await api.mixer_get(); if (d && d.master) { vol.v = d.master.volume; vol.muted = d.master.muted; } } catch (e) { /* 이전 값 유지 */ }
  }
  volRender();
}

function volClose() {
  vol.open = false;
  clearTimeout(vol.timer);
  $('playerLayer').classList.remove('voling');
}

function volSend(v, muted) {
  const api = getApi();
  if (!api || !api.mixer_set) return;
  api.mixer_set('master', v === undefined ? null : v, muted === undefined ? null : muted);
}

// 팝오버가 열려 있을 때 시스템에서 볼륨이 바뀌면(키보드 볼륨 키 등) 슬라이더가 따라간다. 알림 대신 이걸 보여 준다.
function volFromSystem(e) {
  vol.v = e.value; vol.muted = !!e.muted;
  if (vol.open) { volRender(); volKeepOpen(); return true; }
  return false;
}

// Ctrl+휠: 어느 상태에서든 마스터 볼륨을 2%씩. 펼쳐져 있으면 팝오버가, 접혀 있으면 볼륨 알림이 보여 준다.
let wheelVolBusy = false;
async function volWheel(dir) {
  const api = getApi();
  if (!api || !api.mixer_step || wheelVolBusy) return;
  wheelVolBusy = true;
  try {
    const nv = await api.mixer_step(dir * 0.02);
    if (typeof nv === 'number') {
      vol.v = nv; vol.muted = false;
      if (isExpanded && (view === 'music' || view === 'lyrics')) { vol.open = true; $('playerLayer').classList.add('voling'); volKeepOpen(); volRender(); }
    }
  } finally { setTimeout(() => { wheelVolBusy = false; }, 40); }
}

// 지금 볼륨/음소거를 읽어 버튼 아이콘을 그린다. HTML 의 아이콘 path 는 비어 있어서(d="") 한 번도 그리지 않으면 볼륨 버튼이 빈 칸으로 보였다.
async function volSync() {
  const api = getApi();
  if (api && api.mixer_get && !vol.dragging && !vol.open) {
    try { const d = await api.mixer_get(); if (d && d.master) { vol.v = d.master.volume; vol.muted = d.master.muted; } } catch (e) { /* 이전 값 유지 */ }
  }
  volRender();
}

function initVolume() {
  const slider = $('volSlider');
  volRender();      // 일단 기본 아이콘을 그려 둔다(실제 값은 곧 volSync 가 읽어 온다)
  volSync();
  $('volBtn').addEventListener('click', (e) => { e.stopPropagation(); vol.open ? volClose() : volOpen(); });
  slider.addEventListener('input', () => {
    vol.dragging = true; volRender(); volKeepOpen();
    clearTimeout(vol.sendTimer);
    vol.sendTimer = setTimeout(() => { volSend(Number(slider.value) / 100, false); }, 35);
  });
  slider.addEventListener('change', () => { vol.dragging = false; vol.v = Number(slider.value) / 100; volRender(); });
  $('volMute').addEventListener('click', (e) => { e.stopPropagation(); vol.muted = !vol.muted; volRender(); volSend(undefined, vol.muted); volKeepOpen(); });
  $('volPop').addEventListener('mousedown', (e) => e.stopPropagation());
}

// ---------------------------------------------------------------- 재생 소스 전환 버튼
let sourceSig = '';
let srcOnTimer = null;
function updateSourceBtn(res) {
  const sources = res.sources || [];
  const sig = JSON.stringify([sources.map((s) => s.id), res.source]);
  if (sig === sourceSig) return;
  sourceSig = sig;
  const btn = $('srcBtn');
  const cur = sources.find((s) => s.id === res.source);
  // 소스가 둘 이상으로 보이는 순간이 잠깐 스쳐 가도(다른 앱의 미디어 세션이 순간적으로 잡혔다 사라질 때) 버튼이 번쩍 보이지 않게,
  // 1.2초 이상 계속 둘 이상일 때만 켠다(없어지면 바로 끈다)
  clearTimeout(srcOnTimer);
  if (sources.length <= 1) btn.classList.remove('on');
  else if (!btn.classList.contains('on')) srcOnTimer = setTimeout(() => btn.classList.add('on'), 1200);
  if (cur) setText($('srcName'), cur.name);
  // 버튼 폭을 재서 곡 제목이 그 앞에서 끝나게 한다(island.css 의 --srcw). 이름 글자가 바뀐 다음 프레임에 잰다
  requestAnimationFrame(() => { const w = btn.offsetWidth; if (w > 0) document.documentElement.style.setProperty('--srcw', Math.ceil(w) + 'px'); });
  const ci = sources.findIndex((s) => s.id === res.source);          // 소스가 셋이면(Cider·PC 의 다른 앱·폰) 차례대로 돌아가며 고른다
  btn.dataset.next = (sources.length > 1 ? sources[(ci + 1) % sources.length] : {}).id || '';
}

function initSource() {
  $('srcBtn').addEventListener('click', async (e) => {
    e.stopPropagation();
    const next = $('srcBtn').dataset.next;
    const api = getApi();
    if (!next || !api) return;
    const r = await api.set_source(next);
    if (r && r.status === 'ok') { sourceSig = ''; showToast(t('sourceSwitched')); pollNow(); }
  });
}

// ---------------------------------------------------------------- 사용자 바로가기 페이지
function launcherItems() { return (store.launcher && store.launcher.items) || []; }

function renderLauncher() {
  const grid = $('launcherGrid'), empty = $('launcherEmpty');
  const items = launcherItems();
  grid.textContent = '';
  setText($('launcherCount'), items.length ? String(items.length) : '');
  empty.style.display = items.length ? 'none' : '';
  empty.textContent = '';
  if (!items.length) {
    empty.append(t('launcherEmpty'), document.createElement('br'));
    const b = document.createElement('button');
    b.className = 'pill'; b.style.marginTop = '8px'; b.textContent = t('openSettings');
    b.addEventListener('click', (e) => { e.stopPropagation(); const a = getApi(); if (a) a.open_settings('plugins'); });
    empty.appendChild(b);
  }
  for (const it of items) {
    const b = document.createElement('button');
    b.className = 'ltile'; b.title = it.target;
    b.innerHTML = '<span class="ic"></span><span class="nm"></span>';
    b.querySelector('.ic').innerHTML = uiIconHtml(it.icon, it.name);
    b.querySelector('.nm').textContent = it.name;
    b.addEventListener('click', async (e) => {
      e.stopPropagation();
      const api = getApi(); if (!api) return;
      const r = await api.launcher_run(it.id);
      if (!r || r.status !== 'ok') { b.classList.add('fail'); setTimeout(() => b.classList.remove('fail'), 900); showToast(t('launcherFailed')); }
    });
    grid.appendChild(b);
  }
}

async function launcherLoad() {
  const api = getApi();
  if (!api || !api.launcher_get) return;
  try { const d = await api.launcher_get(); store.launcher = { items: d.items || [] }; } catch (e) { /* 이전 값 유지 */ }
  renderLauncher();
  enterLate('launcher', '.l-launcher .ltile', POP, 260, 28, { duration: 500, easing: SPRING });
  enterLate('launcher', '.l-launcher .tempty', FADE, 280, 0, { duration: 500 });
}

// ---------------------------------------------------------------- 플러그인 페이지
function pluginsEnabled() { return String(store.settings.pluginsEnabled || '').split(',').map((x) => x.trim()).filter(Boolean); }
const plug = { list: [], sel: '', states: {} };
const locText = (o) => locOf(o, lang);      // 언어별 문구({ko, en, zh?, ja?}): 해당 언어 -> 중·일은 영어 원문의 번역표 -> 영어 -> 한국어 (locOf: i18n_cjk.js)

async function pluginsLoad() {
  const api = getApi();
  if (!api || !api.plugins_list) return;
  try { plug.list = (await api.plugins_list()) || []; } catch (e) { plug.list = []; }
  if (!plug.list.some((p) => p.id === plug.sel)) plug.sel = plug.list.length ? plug.list[0].id : '';
  renderPlugins();
  enterLate('plugins', '.l-plugins .pchip', RISE, 190, 35, { duration: 440 });
  enterLate('plugins', '.l-plugins .pbtn', POP, 280, 30, { duration: 500, easing: SPRING });
}

// 플러그인마다 고유한 강조 색: 잘 알려진 것은 서비스 색, 직접 만든 것은 이름에서 색상을 뽑는다
const PLUGIN_COLORS = { cider: '#ff4d6a', spotify: '#1ed760', discord: '#7c85ff', volume: '#4da3ff', system: '#9aa7ff', musictools: '#ffb340', quick: '#ffd24d', web: '#3dd6c8', applemusic: '#ff375f', browsermedia: '#ffb340', steam: '#66c0f4', apps: '#9aa7ff' };
function pluginAccent(p) {
  if (!p) return '#8aa0ff';
  if (PLUGIN_COLORS[p.id]) return PLUGIN_COLORS[p.id];
  let h = 0; for (const ch of String(p.id)) h = (h * 31 + ch.charCodeAt(0)) % 360;
  return `hsl(${h} 80% 62%)`;
}

function renderPlugins() {
  const chips = $('pluginChips'), grid = $('pluginGrid');
  chips.textContent = ''; grid.textContent = '';
  $('pluginsEmpty').style.display = plug.list.length ? 'none' : '';
  $('pluginsEmpty').textContent = plug.list.length ? '' : t('pluginsEmpty');
  for (const p of plug.list) {
    const c = document.createElement('button');
    c.className = 'pchip' + (p.id === plug.sel ? ' on' : '');
    c.innerHTML = '<span class="ic"></span><span class="nm"></span>';
    c.querySelector('.ic').innerHTML = uiIconHtml(p.icon, locText(p.name));
    c.querySelector('.nm').textContent = locText(p.name);
    c.title = locText(p.name);
    c.addEventListener('click', (e) => { e.stopPropagation(); plug.sel = p.id; renderPlugins(); pluginStatusRefresh(); });
    chips.appendChild(c);
  }
  const cur = plug.list.find((p) => p.id === plug.sel);
  $('pluginsLayer').style.setProperty('--pc', pluginAccent(cur));
  $('pluginsLayer').classList.toggle('has', !!cur);
  $('plugOrb').innerHTML = cur ? uiIconHtml(cur.icon, locText(cur.name)) : '';
  setText($('plugName'), cur ? locText(cur.name) : '');
  for (const a of (cur ? cur.actions : [])) {
    const b = document.createElement('button');
    b.className = 'pbtn'; b.title = locText(a.label); b.dataset.aid = a.id; b.dataset.label = locText(a.label);
    b.innerHTML = '<span class="ic"></span><span class="nm"></span><i class="bdg"></i>';
    b.querySelector('.ic').innerHTML = uiIconHtml(a.icon, locText(a.label));
    b.querySelector('.nm').textContent = locText(a.label);
    b.addEventListener('click', (e) => { e.stopPropagation(); pluginRun(cur.id, a.id, b); });
    grid.appendChild(b);
  }
  const on = chips.querySelector('.pchip.on');
  // 선택한 칩이 보이게 독만 옆으로 민다. (scrollIntoView 는 노치 전체를 감싼 상위 요소까지 스크롤시켜 페이지가 위로 밀렸다)
  if (on) {
    if (on.offsetLeft < chips.scrollLeft) chips.scrollLeft = on.offsetLeft - 8;
    else if (on.offsetLeft + on.offsetWidth > chips.scrollLeft + chips.clientWidth) chips.scrollLeft = on.offsetLeft + on.offsetWidth - chips.clientWidth + 8;
  }
  chipEdges();
  applyPluginStates();
  setText($('pluginStatus'), '');
  $('pluginStatus').classList.remove('live');
  $('pluginsLayer').classList.remove('live');
  $('pluginsLayer').classList.remove('conn');
  $('plugOrb').title = '';
}

// 칩 줄이 넘칠 때 왼쪽/오른쪽에 더 있다는 표시(가장자리 페이드)
function chipEdges() {
  const el = $('pluginChips');
  el.classList.toggle('more-l', el.scrollLeft > 2);
  el.classList.toggle('more-r', el.scrollLeft + el.clientWidth < el.scrollWidth - 2);
}

// 버튼마다 지금 상태를 바로 알 수 있게: 켜짐(강조) / 주의(음소거처럼 꺼진 상태) / 이름 대신 상태 문구 / 모서리 표시(한 곡 반복의 "1")
function applyPluginStates() {
  const stt = plug.states[plug.sel] || {};
  for (const b of $$('#pluginGrid .pbtn')) {
    const s = stt[b.dataset.aid];
    b.classList.toggle('on', !!(s && s.on));
    b.classList.toggle('warn', !!(s && s.tone === 'warn'));
    const nm = b.querySelector('.nm');
    const text = s && s.text ? locText(s.text) : b.dataset.label;
    if (nm.textContent !== text) nm.textContent = text;
    const bd = b.querySelector('.bdg');
    bd.textContent = s && s.badge ? s.badge : '';
    bd.classList.toggle('show', !!(s && s.badge));
  }
}

async function pluginStatesRefresh() {
  const api = getApi();
  if (!api || !api.plugin_states || !plug.sel) return;
  const id = plug.sel;
  let s = null; try { s = await api.plugin_states(id); } catch (e) { /* 다음 주기 */ }
  plug.states[id] = s || {};
  if (id === plug.sel) applyPluginStates();
}

async function pluginStatusRefresh() {
  pluginStatesRefresh();
  const api = getApi();
  if (!api || !api.plugin_status || !plug.sel) return;
  const id = plug.sel;
  let st = null; try { st = await api.plugin_status(id); } catch (e) { /* 다음 주기 */ }
  if (id === plug.sel) { setText($('pluginStatus'), st ? locText(st) : ''); const live = !!(st && st.live);      // 초록불은 '연결됨'일 때만(연결 상태가 의미 없는 플러그인은 live 가 없어 켜지지 않는다)
    $('pluginStatus').classList.toggle('live', live); $('pluginsLayer').classList.toggle('live', live);
    // live 값이 있는(연결 상태가 의미 있는) 플러그인만 점을 보인다
    $('pluginsLayer').classList.toggle('conn', !!(st && typeof st.live === 'boolean')); $('plugOrb').title = st ? locText(st) : ''; }
}

async function pluginRun(pid, aid, btn) {
  const api = getApi();
  if (!api) return;
  const r = await api.plugin_run(pid, aid);
  if (r && r.status === 'ok') {
    btn.classList.add('okflash'); setTimeout(() => btn.classList.remove('okflash'), 500);
    if (r.message) showToast(locText(r.message));      // 문구는 문자열이거나 언어별 {ko, en, ...}
    if (r.js) runPluginJs(r.js);
    pollBoostUntil = performance.now() + 1800; pollNow();          // 곡/재생 상태가 바뀌는 동작이면 노치도 바로 따라가게
    setTimeout(pluginStatusRefresh, 250);
    setTimeout(pluginStatusRefresh, 900);          // 앱에 따라 상태가 늦게 바뀐다
  } else {
    btn.classList.add('fail'); setTimeout(() => btn.classList.remove('fail'), 900);
    showToast(t('pluginFailed'));
  }
}

// 플러그인이 화면에 시키는 동작(타이머 시작 등)
function runPluginJs(code) {
  if (code.startsWith('timer:')) {
    store.timer.minutes = clampN(Number(code.slice(6)), 1, 600, 5);
    tmrSetMode('timer'); tmrReset('timer'); if (!tmrRunning('timer')) tmrStartPause('timer'); setPage('timer');
  } else if (code === 'stopwatch') { tmrSetMode('stopwatch'); if (!tmrRunning('stopwatch')) tmrStartPause('stopwatch'); setPage('timer'); }
  else if (code === 'pomo') { pomoSetMode('focus'); if (!pomo.running) pomoStartPause(); setPage('pomo'); }
}

function initLauncherPlugins() {
  // 칩이 많아 넘칠 때: 휠로 좌우 스크롤 (페이지가 넘어가지 않게 막는다) + 가장자리에 더 있다는 표시
  const chips = $('pluginChips');
  chips.addEventListener('wheel', (e) => {
    if (chips.scrollWidth <= chips.clientWidth) return;
    e.preventDefault(); e.stopPropagation();
    chips.scrollLeft += (Math.abs(e.deltaX) > Math.abs(e.deltaY) ? e.deltaX : e.deltaY);
    chipEdges();
  }, { passive: false });
  chips.addEventListener('scroll', chipEdges);
  $('launcherEdit').addEventListener('click', (e) => { e.stopPropagation(); const a = getApi(); if (a) a.open_settings('plugins'); });
  setInterval(() => { if (page === 'plugins' && isExpanded) pluginStatusRefresh(); }, 2000);
  renderLauncher();
}

// ---------------------------------------------------------------- 일정 알림 (이벤트) / 시작
function agendaAlert(e) {
  const mins = Math.max(0, Math.round((e.start - Date.now() / 1000) / 60));
  playChime('todo');
  notify({ icon: 'timer', tone: 'blue', ms: 7000, title: e.title || t('agendaNoTitle'), sub: mins <= 0 ? t('agendaNow') : t('agendaStartsIn', { n: mins }) + (e.location ? ` · ${e.location}` : ''), key: 'agenda' });
}


// ---------------------------------------------------------------- 시스템 탭 / 전원 탭
// 시스템: 배터리(있을 때만) · 볼륨/음소거 · 밝기(바꿀 수 있는 화면이 있을 때만) · Wi-Fi · 블루투스 · 마이크. 값은 파이썬(sysctl.py)이 읽고 바꾼다.
// 전원: 잠금 · 화면 끄기 · 절전 · 로그아웃 · 다시 시작 · 전원 끄기. 뒤의 세 개는 3초 안에 한 번 더 눌러야 실행된다(서버도 confirmed 가 없으면 실행하지 않는다).
const sysS = { data: null, holdUntil: 0, loading: false, sendT: null };
const PWR_ICON = { lock: 'lock', screenoff: 'monitor', sleep: 'moon', signout: 'signout', restart: 'restart', shutdown: 'power' };
const SYS_REFRESH_MS = 2500;
const PWR_CONFIRM_MS = 3000;

function sysSetIc(svgEl, name) { if (svgEl) svgEl.innerHTML = (typeof UI_ICONS !== 'undefined' && UI_ICONS[name]) || ''; }
function sysFill(input) { input.style.setProperty('--fill', input.value + '%'); }


// 시스템 탭이 펼쳐져 있으면 볼륨·밝기가 바뀔 때 팝업 대신 이 탭의 슬라이더가 따라간다(true 를 돌려주면 팝업을 만들지 않는다)
function sysFollow(kind, e) {
  if (!(page === 'sys' && isExpanded && $('sysLayer'))) return false;
  if (sysS.data && Date.now() >= sysS.holdUntil) {
    if (kind === 'volume' && sysS.data.volume) { sysS.data.volume = { percent: Math.round(e.value * 100), muted: !!e.muted }; renderSys(); }
    if (kind === 'brightness' && sysS.data.brightness) { sysS.data.brightness = Object.assign({}, sysS.data.brightness, { percent: Math.round(e.value) }); renderSys(); }
  }
  return true;
}
// 배터리 모양: 충전량만큼 채우고, 충전 중이면 번개 표시
function batteryIconInner(p, ac) {
  const w = Math.max(0, Math.min(12, (p / 100) * 12));
  return '<rect x="2.5" y="8" width="16" height="9" rx="2.2" fill="none"/><path d="M21 11v3" fill="none"/>' +
         (w > 0.4 ? `<rect x="4.5" y="10" width="${w.toFixed(1)}" height="5" rx="1" fill="currentColor" stroke="none"/>` : '') +
         (ac ? '<path class="bolt" d="M11.6 8.8l-2.7 3.9h2.2l-1 3.1 3.1-4.2h-2.2z"/>' : '');
}
function renderSys() {
  const d = sysS.data || {};
  // 배터리: 배터리가 있는 PC 만
  const bat = $('sysBat');
  if (d.battery) {
    bat.hidden = false;
    const p = d.battery.percent;
    $('sysBatIcon').innerHTML = batteryIconInner(p, !!d.battery.ac);
    setText($('sysBatTxt'), `${p}%` + (d.battery.ac ? ' · ' + (p < 100 ? t('sysCharging') : t('sysPlugged')) : ''));
    bat.classList.toggle('low', !d.battery.ac && p <= 20);
    bat.classList.toggle('chg', !!d.battery.ac);
  } else bat.hidden = true;
  // 볼륨
  const vr = $('sysRowVol');
  vr.hidden = !d.volume;
  if (d.volume && Date.now() >= sysS.holdUntil) {
    const v = d.volume.muted ? 0 : d.volume.percent;
    $('sysVol').value = v; sysFill($('sysVol'));
    setText($('sysVolOut'), d.volume.muted ? t('sysMuted') : v + '%');
    sysSetIc($('sysMuteIcon'), d.volume.muted ? 'mute' : (v < 34 ? 'volume1' : v < 67 ? 'volume2' : 'volume'));
    $('sysMute').setAttribute('aria-label', t('sysMuteTitle'));          // 마우스를 올려도 말풍선은 뜨지 않는다(화면 읽기용 이름만)
  }
  // 밝기: 바꿀 수 있는 화면이 있을 때만
  const br = $('sysRowBri');
  br.hidden = !d.brightness;
  if (d.brightness) {
    sysSetIc($('sysBriIcon').querySelector('svg'), 'sun');
    if (Date.now() >= sysS.holdUntil) { $('sysBri').value = d.brightness.percent; sysFill($('sysBri')); setText($('sysBriOut'), d.brightness.percent + '%'); }
  }
  // 켜기/끄기 타일
  const tile = (id, key, icon, label, on, text) => {
    const el = $(id); const item = d[key];
    el.hidden = !item;
    if (!item) return;
    sysSetIc(el.querySelector('svg'), icon);
    el.classList.toggle('on', !!on);
    setText(el.querySelector('.nm'), text);
  };
  tile('sysWifi', 'wifi', 'wifi', t('sysWifi'), d.wifi && d.wifi.on, d.wifi && d.wifi.on ? (d.wifi.name || t('sysNotConnected')) : t('sysWifi'));
  tile('sysBt', 'bluetooth', 'bluetooth', t('sysBluetooth'), d.bluetooth && d.bluetooth.on, t('sysBluetooth'));
  tile('sysMic', 'mic', d.mic && d.mic.muted ? 'micoff' : 'mic', t('sysMic'), d.mic && !d.mic.muted, d.mic && d.mic.muted ? t('sysMuted') : t('sysMic'));
  $('sysTog').hidden = !(d.wifi || d.bluetooth || d.mic);
}

async function sysLoad() {
  const api = getApi();
  if (!api || !api.sys_get || sysS.loading) return;
  sysS.loading = true;
  try { const d = await api.sys_get(); if (d && typeof d === 'object') { sysS.data = d; renderSys(); } } catch (e) { /* 이전 값 유지 */ }
  sysS.loading = false;
}

async function sysDo(action, value, tileEl) {
  const api = getApi();
  if (!api || !api.sys_do) return;
  if (tileEl) tileEl.classList.add('busy');
  let r = null;
  try { r = await api.sys_do(action, value); } catch (e) { r = null; }
  if (tileEl) tileEl.classList.remove('busy');
  if (!r || r.status !== 'ok') { showToast(t('sysFail')); sysS.holdUntil = 0; sysLoad(false); return; }
  if (action === 'mute' || action === 'mic') sysS.holdUntil = 0;            // 버튼으로 바꾼 값은 바로 보여 준다(슬라이더 끄는 중의 보호는 슬라이더에만)
  if (r.state) {
    // 켜기/끄기 직후에는 무선 장치 값이 잠깐 이전 값일 수 있어 요청한 값을 먼저 보여 주고 곧 다시 읽는다
    // 값이 없는(null) 항목은 덮어쓰지 않는다: 마이크·음소거·밝기 같은 동작은 무선 장치(와이파이·블루투스)를 다시 읽지 않아 그 둘이 null 로 온다.
    // 그대로 합치면 와이파이·블루투스 타일이 사라져 마이크 타일이 줄 전체로 갑자기 커졌다(다음 갱신까지 약 2초)
    const known = {}; for (const k of Object.keys(r.state)) if (r.state[k] != null) known[k] = r.state[k];
    sysS.data = Object.assign({}, sysS.data || {}, known);
    if (action === 'wifi' && sysS.data.wifi) sysS.data.wifi = Object.assign({}, sysS.data.wifi, { on: !!value });
    if (action === 'bluetooth' && sysS.data.bluetooth) sysS.data.bluetooth = Object.assign({}, sysS.data.bluetooth, { on: !!value });
    renderSys();
    if (action === 'wifi' || action === 'bluetooth') setTimeout(() => sysLoad(false), 1500);
  }
}

function sysSlider(id, outId, action) {
  const el = $(id);
  el.addEventListener('input', () => {
    sysFill(el);
    setText($(outId), el.value + '%');
    sysS.holdUntil = Date.now() + 1500;                 // 끄는 동안 주기 갱신이 슬라이더를 되돌리지 않게
    clearTimeout(sysS.sendT);
    sysS.sendT = setTimeout(() => { const api = getApi(); if (api && api.sys_do) api.sys_do(action, Number(el.value)); }, 70);
  });
  el.addEventListener('change', () => { clearTimeout(sysS.sendT); sysDo(action, Number(el.value)); sysS.holdUntil = Date.now() + 600; });
  el.addEventListener('click', (e) => e.stopPropagation());
}

// 전원 타일: 위험한 것은 첫 번째 누름에서 "한 번 더 누르세요"로 바뀌고 3초 안에 다시 눌러야 실행된다
const pwrConfirm = { el: null, timer: null };
function pwrResetConfirm() {
  if (pwrConfirm.el) { pwrConfirm.el.classList.remove('confirm'); const nm = pwrConfirm.el.querySelector('.nm'); if (nm && nm.dataset.i18n) nm.textContent = t(nm.dataset.i18n); }
  clearTimeout(pwrConfirm.timer); pwrConfirm.el = null;
}
async function pwrPress(btn) {
  const kind = btn.dataset.k;
  const api = getApi();
  if (!api || !api.power_do) return;
  const fail = () => { btn.classList.add('fail'); setTimeout(() => btn.classList.remove('fail'), 900); showToast(t('sysFail')); };
  if (btn.classList.contains('danger')) {
    if (pwrConfirm.el !== btn) {
      pwrResetConfirm();
      pwrConfirm.el = btn; btn.classList.add('confirm');
      const nm = btn.querySelector('.nm'); if (nm) nm.textContent = t('pwrAgain');
      pwrConfirm.timer = setTimeout(pwrResetConfirm, PWR_CONFIRM_MS);
      return;
    }
    pwrResetConfirm();
    const r = await api.power_do(kind, true);
    if (!r || r.status !== 'ok') fail();
    return;
  }
  pwrResetConfirm();
  const r = await api.power_do(kind, false);
  if (!r || r.status !== 'ok') fail();
}


// ---------------------------------------------------------------- 시스템 탭: Wi-Fi / 블루투스 선택창 (타일을 0.5초 꾹 누르면 노치 안에 목록이 펼쳐진다)
const spk = { kind: null, items: [], busy: false, pwFor: null, poll: null };
const SPK_HOLD_MS = 520;
function spkSignal(pct) {
  const n = Math.max(1, Math.min(4, Math.ceil((pct || 0) / 25)));
  return '<span class="sig">' + [4, 6, 9, 12].map((h, i) => `<i${i < n ? ' class="f"' : ''} style="height:${h}px"></i>`).join('') + '</span>';
}
function spkIcon(name) { return typeof uiIconSvg === 'function' ? (uiIconSvg(name) || '') : ''; }
function spkClose() {
  clearInterval(spk.poll); spk.poll = null;
  spk.kind = null; spk.pwFor = null;
  const lay = $('sysLayer'); if (lay) lay.classList.remove('picking');
  for (const id of ['spkHead', 'spkList', 'spkPw']) { const e = $(id); if (e) e.hidden = true; }
  const pw = $('spkPwIn'); if (pw) pw.value = '';           // 비밀번호는 화면에 남기지 않는다
}
function spkShowList() {
  $('spkPw').hidden = true; $('spkPwIn').value = ''; spk.pwFor = null;
  $('spkList').hidden = false;
}
function spkRender() {
  const list = $('spkList');
  list.textContent = '';
  if (spk.busy && !spk.items.length) { const d = document.createElement('div'); d.className = 'spk-empty'; d.textContent = t('spkScanning'); list.appendChild(d); return; }
  if (!spk.items.length) { const d = document.createElement('div'); d.className = 'spk-empty'; d.textContent = t('spkNone'); list.appendChild(d); return; }
  for (const it of spk.items) {
    const b = document.createElement('button');
    b.className = 'spk-row' + (it.connected ? ' on' : '');
    const nm = document.createElement('span'); nm.className = 'nm'; nm.textContent = it.ssid || it.name;
    if (spk.kind === 'wifi') {
      b.innerHTML = spkSignal(it.signal);
      b.appendChild(nm);
      const st = document.createElement('span'); st.className = 'st';
      st.textContent = it.connected ? t('spkConnected') : (it.saved ? t('spkSaved') : '');
      if (it.kind === 'psk' && !it.saved) st.innerHTML = spkIcon('lock');
      b.appendChild(st);
      b.dataset.ssid = it.ssid;
    } else {
      b.innerHTML = spkIcon({ headphones: 'headphones', speaker: 'speaker', mic: 'mic', keyboard: 'keyboard', mouse: 'mouse', gamepad: 'gamepad', input: 'mouse', phone: 'phone', computer: 'laptop', watch: 'watch' }[it.kind] || 'bluetooth');
      b.appendChild(nm);
      const st = document.createElement('span'); st.className = 'st'; st.textContent = it.connected ? t('spkConnected') : t('spkPaired');
      b.appendChild(st);
      b.dataset.address = it.address;
    }
    b.addEventListener('click', (e) => { e.stopPropagation(); spkPick(it, b); });
    list.appendChild(b);
  }
  enterEach(list.querySelectorAll('.spk-row'), RISE, 0, 35, { duration: 380 });
  const more = $('spkMore');
  if (more) { setTimeout(() => { more.hidden = !(list.scrollHeight > list.clientHeight + 4); }, 60); }
}
async function spkLoad() {
  const api = getApi(); if (!api) return;
  spk.busy = true; spkRender();
  try {
    if (spk.kind === 'wifi') { const r = await api.wifi_scan(); spk.items = (r && r.items) || []; }
    else { const r = await api.bt_devices(); spk.items = (r && r.items) || []; }
  } catch (e) { spk.items = []; }
  spk.busy = false;
  if (spk.kind) spkRender();
}
function spkOpen(kind) {
  const lay = $('sysLayer'); if (!lay) return;
  spk.kind = kind; spk.items = [];
  lay.classList.add('picking');
  $('spkHead').hidden = false;
  setText($('spkTitle'), kind === 'wifi' ? t('sysWifi') : t('sysBluetooth'));
  setText($('spkHint'), kind === 'wifi' ? t('spkHintWifi') : t('spkHintBt'));
  sysSetIc($('spkBack').querySelector('svg'), 'back');
  spkShowList();
  spkLoad();
}
async function spkPick(it, row) {
  const api = getApi(); if (!api) return;
  if (spk.kind === 'wifi') {
    if (it.connected) return;
    if (it.kind === 'unsupported' && !it.saved) { showToast(t('spkUnsupported')); return; }
    if (it.kind === 'psk' && !it.saved) {                         // 처음 보는 보안 네트워크: 비밀번호를 받는다
      spk.pwFor = it.ssid;
      $('spkList').hidden = true; $('spkPw').hidden = false;
      setText($('spkPwName'), it.ssid); const pw = $('spkPwIn'); pw.value = ''; setTimeout(() => pw.focus(), 60);
      return;
    }
    spkConnectWifi(it.ssid, null, row);
  } else {
    row.classList.add('busy');
    setText(row.querySelector('.st'), t('spkConnecting'));
    let r = null; try { r = await api.bt_connect(it.address, !it.connected); } catch (e) { r = null; }
    if (!r || r.status !== 'ok') { showToast(t('spkFailed')); row.classList.remove('busy'); spkLoad(); return; }
    spkWaitFor(async () => { const d = await api.bt_devices(); const m = ((d && d.items) || []).find((x) => x.address === it.address); return m && m.connected === !it.connected ? d.items : null; }, 8000);
  }
}
async function spkConnectWifi(ssid, password, row) {
  const api = getApi(); if (!api) return;
  if (row) { row.classList.add('busy'); setText(row.querySelector('.st'), t('spkConnecting')); }
  let r = null; try { r = await api.wifi_connect(ssid, password); } catch (e) { r = null; }
  if (!r || r.status !== 'ok') {
    showToast(r && r.error === 'unsupported' ? t('spkUnsupported') : (r && r.error === 'profile' ? t('spkBadPw') : t('spkFailed')));
    if (row) row.classList.remove('busy');
    spkShowList(); spkLoad(); return;
  }
  spkShowList(); spkRender();
  spkWaitFor(async () => { const d = await api.wifi_scan(); const m = ((d && d.items) || []).find((x) => x.ssid === ssid); return m && m.connected ? d.items : null; }, 12000, () => showToast(t('spkBadPw')));
}
// 연결/해제가 실제로 끝날 때까지 1.5초마다 다시 읽는다(끝나면 목록을 새로 그리고, 시간이 지나도 안 되면 onTimeout)
function spkWaitFor(check, ms, onTimeout) {
  clearInterval(spk.poll);
  const t0 = Date.now(); const kind = spk.kind;
  spk.poll = setInterval(async () => {
    if (spk.kind !== kind) { clearInterval(spk.poll); return; }
    let items = null; try { items = await check(); } catch (e) { items = null; }
    if (items) { clearInterval(spk.poll); spk.poll = null; spk.items = items; spkRender(); sysLoad(); return; }
    if (Date.now() - t0 > ms) { clearInterval(spk.poll); spk.poll = null; if (onTimeout) onTimeout(); spkLoad(); }
  }, 1500);
}
// 타일: 짧게 누르면 켜기/끄기, 0.5초 꾹 누르면 선택창
function sysHoldable(el, onTap, onHold) {
  let timer = null, held = false, sx = 0, sy = 0;
  el.dataset.hold = '1';          // 길게 눌러 선택창을 여는 타일: reorder.js 는 이 타일에서 '길게 누른 뒤 움직일 때'만 끌기를 시작한다(가만히 있으면 선택창)
  const start = (e) => {
    held = false; clearTimeout(timer); sx = e.clientX; sy = e.clientY;
    timer = setTimeout(() => { if (typeof reorderActive !== 'undefined' && reorderActive) return; held = true; onHold(); }, SPK_HOLD_MS);
  };
  const stop = () => clearTimeout(timer);
  const move = (e) => { if (timer && Math.hypot(e.clientX - sx, e.clientY - sy) > 6) clearTimeout(timer); };          // 움직였다: 끌기이거나 손이 미끄러진 것이다
  el.addEventListener('pointerdown', start);
  el.addEventListener('pointermove', move);
  el.addEventListener('pointerup', stop); el.addEventListener('pointerleave', stop); el.addEventListener('pointercancel', stop);
  el.addEventListener('click', (e) => { e.stopPropagation(); if (held) { held = false; return; } onTap(); });
}
function initPickers() {
  $('spkBack').addEventListener('click', (e) => { e.stopPropagation(); if (spk.pwFor) spkShowList(); else spkClose(); });
  $('spkList').addEventListener('wheel', (e) => { const l = $('spkList'); if (l.scrollHeight > l.clientHeight + 1) e.stopPropagation(); }, { passive: true });
  $('spkPwGo').addEventListener('click', (e) => { e.stopPropagation(); const pw = $('spkPwIn').value; if (pw && spk.pwFor) { const ssid = spk.pwFor; $('spkPwIn').value = ''; spkConnectWifi(ssid, pw, null); } });
  $('spkPwIn').addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); $('spkPwGo').click(); } });
  $('spkPwIn').addEventListener('click', (e) => e.stopPropagation());
  sysHoldable($('sysWifi'), () => { const d = sysS.data && sysS.data.wifi; sysDo('wifi', !(d && d.on), $('sysWifi')); }, () => spkOpen('wifi'));
  sysHoldable($('sysBt'), () => { const d = sysS.data && sysS.data.bluetooth; sysDo('bluetooth', !(d && d.on), $('sysBt')); }, () => spkOpen('bt'));
  langHooks.push(() => { if (spk.kind) { setText($('spkTitle'), spk.kind === 'wifi' ? t('sysWifi') : t('sysBluetooth')); setText($('spkHint'), spk.kind === 'wifi' ? t('spkHintWifi') : t('spkHintBt')); spkRender(); } });
}


// ---------------------------------------------------------------- 성능 탭 (CPU · 메모리 · 네트워크) + 작은 노치에 띄울 값
const perfS = { data: null, busy: false, hCpu: [], hMem: [], hNet: [], hGpu: [] };
// 탭이 꺼져 있으면(설정 › 모양 › 탭 구성) 그 탭에 속한 기능도 멈춘다
function tabVisibleId(id) { return !parseTabHidden(store.settings.tabHidden).includes(id); }
function fmtRate(bps) {
  const v = Math.max(0, Number(bps) || 0);
  if (v >= 1048576) return (v / 1048576).toFixed(v >= 10485760 ? 0 : 1) + ' MB/s';
  if (v >= 1024) return Math.round(v / 1024) + ' KB/s';
  return Math.round(v) + ' B/s';
}
function fmtRateShort(bps) {
  const v = Math.max(0, Number(bps) || 0);
  if (v >= 1048576) return (v / 1048576).toFixed(v >= 10485760 ? 0 : 1) + 'M';
  if (v >= 1024) return Math.round(v / 1024) + 'K';
  return Math.round(v) + 'B';
}
function perfSatWanted() { const s = store.settings; return tabVisibleId('perf') && !!(s.satPerfCpu || s.satPerfMem || s.satPerfGpu || s.satPerfNet); }
async function perfLoad() {
  const api = getApi();
  if (!api || !api.perf_get || perfS.busy) return;
  perfS.busy = true;
  try { const d = await api.perf_get(); if (d && typeof d === 'object') { perfS.data = d; renderPerf(); } } catch (e) { /* 이전 값 유지 */ }
  perfS.busy = false;
}
const PERF_HIST = 60;
function perfPush(arr, v) { arr.push(v == null ? null : v); while (arr.length > PERF_HIST) arr.shift(); }
function sparkPath(vals, max) {
  const n = vals.length; if (n < 2) return ['', ''];
  const step = 100 / (PERF_HIST - 1), x0 = 100 - (n - 1) * step;
  let line = '', started = false, lastX = x0;
  vals.forEach((v, i) => { if (v == null) { started = false; return; } const x = x0 + i * step, y = 23 - Math.max(0, Math.min(1, v / max)) * 21; line += (started ? 'L' : 'M') + x.toFixed(1) + ' ' + y.toFixed(1); started = true; lastX = x; });
  const area = line ? line + `L${lastX.toFixed(1)} 24L${x0.toFixed(1)} 24Z` : '';
  return [line, area];
}
function drawSpark(id, vals, max, warn) {
  const svg = $(id); if (!svg) return;
  const [line, area] = sparkPath(vals, max);
  svg.querySelector('.l').setAttribute('d', line); svg.querySelector('.a').setAttribute('d', area);
  svg.classList.toggle('hot', !!warn && (vals.length ? (vals[vals.length - 1] || 0) : 0) >= 85);
}
function renderPerf() {
  const d = perfS.data; if (!d) return;
  setText($('pfCpu'), d.cpu == null ? '--' : d.cpu + '%');
  setText($('pfMem'), d.mem ? d.mem.percent + '%' : '--');
  setText($('pfMemSub'), d.mem ? `${d.mem.used_gb} / ${d.mem.total_gb} GB` : '');
  perfPush(perfS.hCpu, d.cpu); perfPush(perfS.hMem, d.mem ? d.mem.percent : null); perfPush(perfS.hNet, d.net ? d.net.down : null); perfPush(perfS.hGpu, d.gpu == null ? null : d.gpu);
  const hasGpu = perfS.hGpu.some((x) => x != null);          // 그래픽 카드(또는 윈도우 성능 카운터)가 없으면 GPU 칸은 아예 보이지 않는다
  if ($('pfGpuCol').hidden === hasGpu) $('pfGpuCol').hidden = !hasGpu;
  $('pfGrid').dataset.cols = hasGpu ? '4' : '3';
  setText($('pfGpu'), d.gpu == null ? '--' : d.gpu + '%');
  drawSpark('pfGpuGraph', perfS.hGpu, 100, true);
  drawSpark('pfCpuGraph', perfS.hCpu, 100, true);
  drawSpark('pfMemGraph', perfS.hMem, 100, true);
  const peak = Math.max(1e6, ...perfS.hNet.filter((x) => x != null));            // 네트워크 그래프는 최근 1분의 최고 속도 대비
  drawSpark('pfNetGraph', perfS.hNet, peak, false);
  if (d.net) { setText($('pfNet'), '↓ ' + fmtRate(d.net.down)); setText($('pfNetSub'), '↑ ' + fmtRate(d.net.up)); }
  else { setText($('pfNet'), '--'); setText($('pfNetSub'), ''); }
}
// 작은 노치용 항목: 켠 것만, 짧은 글자로
function perfSatItems() {
  const d = perfS.data, s = store.settings, out = [];
  if (!d || !tabVisibleId('perf')) return out;
  if (s.satPerfCpu && d.cpu != null) out.push({ id: 'perf-cpu', kind: 'perf', page: 'perf', running: false, text: `CPU ${d.cpu}%`, pct: 100 });
  if (s.satPerfGpu && d.gpu != null) out.push({ id: 'perf-gpu', kind: 'perf', page: 'perf', running: false, text: `GPU ${d.gpu}%`, pct: 100 });
  if (s.satPerfMem && d.mem) out.push({ id: 'perf-mem', kind: 'perf', page: 'perf', running: false, text: `RAM ${d.mem.percent}%`, pct: 100 });
  if (s.satPerfNet && d.net) out.push({ id: 'perf-net', kind: 'perf', page: 'perf', running: false, text: `↓${fmtRateShort(d.net.down)} ↑${fmtRateShort(d.net.up)}`, pct: 100 });
  return out;
}
function initPerf() {
  setInterval(() => { if (page === 'perf' && isExpanded && !document.hidden) perfLoad(); }, 1000);
  setInterval(() => { if (perfSatWanted() && typeof satOn === 'function' && satOn() && !isExpanded && !document.hidden) perfLoad().then(() => { if (typeof renderSat === 'function') renderSat(); }); }, 2000);
}


// ---------------------------------------------------------------- 날씨 탭 (+ 작은 노치). 내 위치(윈도우 위치 서비스) 또는 설정에서 고른 도시가 있을 때만 서버(Open-Meteo)에 요청한다
const wxS = { res: null, busy: false };
function wxUnit(u) { return u === 'f' ? '°F' : '°C'; }
function wxLabel(key) { return t('wx_' + key); }
async function wxLoad(force) {
  const api = getApi();
  if (!api || !api.weather_get || wxS.busy) return;
  wxS.busy = true;
  try { const r = await api.weather_get(!!force); if (r && typeof r === 'object') { wxS.res = r; renderWeather(); } } catch (e) { /* 이전 값 유지 */ }
  wxS.busy = false;
  if (typeof renderSat === 'function') renderSat();
}
function renderWeather() {
  const r = wxS.res || { status: 'loading' };
  const body = $('wxBody'), msg = $('wxMsg');
  sysSetIc($('wxRefreshIc'), 'restart');
  const showMsg = (text, btn) => { body.hidden = true; msg.hidden = false; setText($('wxMsgText'), text); const b = $('wxMsgBtn'); b.hidden = !btn; if (btn) setText(b, btn); };
  if (r.status === 'nocity') { setText($('wxCity'), t('tab_weather')); setText($('wxUpd'), ''); showMsg(t('wxNoCity'), t('wxOpenSettings')); return; }
  if (r.status === 'noloc') { setText($('wxCity'), t('tab_weather')); setText($('wxUpd'), ''); showMsg(t('wxNoLoc'), t('wxOpenSettings')); return; }
  if (r.status === 'loading') { showMsg(t('wxLoading'), ''); return; }
  if (r.status !== 'ok' || !r.weather) { setText($('wxCity'), r.city || t('tab_weather')); setText($('wxUpd'), ''); showMsg(t('wxErr'), t('wxRefresh')); return; }
  const w = r.weather;
  body.hidden = false; msg.hidden = true;
  setText($('wxCity'), r.city || t('tab_weather'));
  const upd = new Date((w.updated || 0) * 1000);
  setText($('wxUpd'), t('wxUpdatedAt', { t: upd.toLocaleTimeString(lang, { hour: '2-digit', minute: '2-digit' }) }) + (r.stale ? ' ' + t('wxStale') : '') + (r.where === 'city' && store.settings.weatherLocate && r.loc && r.loc !== 'ok' ? ' · ' + t('wxFallback') : ''));
  $('wxCity').title = r.city || ''; $('wxUpd').title = $('wxUpd').textContent;          // 길어서 줄임표가 되면 마우스를 올려 전체를 본다
  sysSetIc($('wxIc'), w.icon);
  setText($('wxTemp'), `${w.temp}°`);
  setText($('wxCond'), wxLabel(w.key));
  setText($('wxFeels'), t('wxFeels', { n: w.feels }));
  const d0 = w.days && w.days[0];
  setText($('wxHiLo'), d0 ? t('wxHiLo', { hi: d0.hi, lo: d0.lo }) : '');
  const air = $('wxAir');
  if (w.air && w.air.grade) {
    const colors = { 1: '#4cd98a', 2: '#ffd24d', 3: '#ff9a4d', 4: '#ff6b6b' };
    air.style.setProperty('--air', colors[w.air.grade]);
    const station = w.air.source === 'station';          // 에어코리아 측정소의 실제 값이면 측정소 이름을, 예측 모델 값이면 '추정'을 붙인다
    setText(air, t('wxAir', { g: t('wxAir' + w.air.grade) }) + ' · ' + (station ? w.air.station : t('wxAirEst')));
    air.title = t('wxAirTip', { a: w.air.pm25 == null ? '-' : w.air.pm25, b: w.air.pm10 == null ? '-' : w.air.pm10 }) + ' — ' + (station ? t('wxAirSrcStation', { s: w.air.station, t: String(w.air.time || '').slice(-5) }) + (w.air.provider ? ' · ' + t('wxAirProvider', { p: w.air.provider }) : '') : t('wxAirSrcModel')) + (w.airErr ? ' · ' + t('wxAirKeyBad') : '');
    air.hidden = false;
  } else { setText(air, ''); air.hidden = true; }
  const days = $('wxDays'); days.textContent = '';
  (w.days || []).forEach((d, i) => {
    const el = document.createElement('div'); el.className = 'wxday';
    const dt = new Date(d.date + 'T12:00:00');
    const name = i === 0 ? t('wxToday') : dt.toLocaleDateString(lang, { weekday: 'short' });
    el.innerHTML = '<span></span>' + (typeof uiIconSvg === 'function' ? (uiIconSvg(d.icon, 20) || '') : '') + '<b></b>';
    el.firstChild.textContent = name;
    el.lastChild.textContent = `${d.hi}° / ${d.lo}°`;
    days.appendChild(el);
  });
}
function wxHasCity() { const s = store.settings; return !!(Number(s.weatherLat) || Number(s.weatherLon)); }
// 날씨를 받아 올 수 있는 상태인가: 내 위치를 쓰는 설정이거나 고른 도시가 있을 때(탭이 꺼져 있으면 받지 않는다)
function wxWanted() { return tabVisibleId('weather') && (!!store.settings.weatherLocate || wxHasCity()); }
function weatherSatItems() {
  const s = store.settings, r = wxS.res;
  if (!s.satWeather || !tabVisibleId('weather') || !r || r.status !== 'ok' || !r.weather) return [];
  return [{ id: 'weather', kind: 'weather', page: 'weather', running: false, text: `${r.weather.temp}° ${wxLabel(r.weather.key)}`, icon: r.weather.icon, pct: 100 }];
}
function initWeather() {
  $('wxRefresh').addEventListener('click', (e) => { e.stopPropagation(); wxLoad(true); });
  $('wxMsgBtn').addEventListener('click', (e) => {
    e.stopPropagation();
    const r = wxS.res || {};
    if (r.status === 'nocity' || r.status === 'noloc') { const a = getApi(); if (a && a.open_settings) a.open_settings('tools'); }
    else wxLoad(true);
  });
  langHooks.push(renderWeather);
  setInterval(() => { const s = store.settings; if (wxWanted() && !document.hidden && ((page === 'weather' && isExpanded) || s.satWeather)) wxLoad(false); }, 5 * 60 * 1000);
  setTimeout(() => { const s = store.settings; if (wxWanted() && s.satWeather) wxLoad(false); }, 4000);
  renderWeather();
}


// ---------------------------------------------------------------- D-day: 일정(달력) 탭 안의 구역 + 작은 노치. 직접 만든 항목과 일정에서 별로 표시한 항목을 날짜 차이로 보여 준다
const ddS = { items: [] };
function ddayLocalMidnight(ms) { const d = new Date(ms); return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime(); }
function ddayDiff(targetMs, nowMs) { return Math.round((ddayLocalMidnight(targetMs) - ddayLocalMidnight(nowMs)) / 86400000); }
function ddayLabel(n) { return n === 0 ? t('ddayDay') : (n > 0 ? 'D-' + n : 'D+' + (-n)); }
function ddayDateStr(ms) { const d = new Date(ms); const p = (x) => String(x).padStart(2, '0'); return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`; }
function ddayParse(str) { const p = String(str).split('-').map(Number); return (p.length === 3 && p.every((x) => Number.isFinite(x))) ? new Date(p[0], p[1] - 1, p[2]).getTime() : NaN; }
// 보여 줄 목록: 완료하지 않은 것만, 오늘·앞으로 날짜 순, 그 뒤에 지난 것(가까운 순)
function ddayAll(nowMs) {
  const now = nowMs || Date.now();
  const rows = [];
  for (const m of ddS.items) {
    if (m.done) continue;
    const ms = ddayParse(m.date);
    if (!Number.isFinite(ms)) continue;
    rows.push({ id: m.id, name: m.name, ms, n: ddayDiff(ms, now), cal: !!m.cal });
  }
  const up = rows.filter((r) => r.n >= 0).sort((a, b) => a.n - b.n || a.name.localeCompare(b.name));
  const past = rows.filter((r) => r.n < 0).sort((a, b) => b.n - a.n);
  return up.concat(past);
}
let ddaySaveT = null;
function ddaySave() {
  clearTimeout(ddaySaveT);
  ddaySaveT = setTimeout(async () => { const api = getApi(); if (api && api.dday_set) { try { await api.dday_set(ddS.items); } catch (e) { /* 다음에 다시 저장 */ } } }, 300);
}
function ddayRefreshViews() {
  if (typeof refreshPageDots === 'function') refreshPageDots();
  if (typeof agendaRefresh === 'function') agendaRefresh(true);
  if (typeof renderSat === 'function') renderSat();
}
async function ddayLoad() {
  const api = getApi();
  if (!api || !api.dday_get) return;
  try { const d = await api.dday_get(); ddS.items = (d && d.items) || []; } catch (e) { /* 이전 값 유지 */ }
  ddayRefreshViews();
}
function ddayMark(id, patch) { const it = ddS.items.find((x) => x.id === id); if (it) { Object.assign(it, patch); ddaySave(); ddayRefreshViews(); } }
function ddayRemove(id) { ddS.items = ddS.items.filter((x) => x.id !== id); ddaySave(); ddayRefreshViews(); }
// 일정 옆 별: 그 일정을 D-day 로 표시하거나 뺀다(제목 + 날짜가 같으면 같은 일정)
function ddayName(title) { return String(title || t('agendaNoTitle')).split(/\s+/).filter(Boolean).join(' ').slice(0, 30); }          // 파이썬 clean_dday 와 같은 규칙(공백을 하나로, 30자까지)
function ddayEventKey(title, startSec) { return `${ddayName(title)}|${ddayDateStr(startSec * 1000)}`; }          // 저장 이름(30자)과 같은 길이로
function ddayFindEvent(title, startSec) { const k = ddayEventKey(title, startSec); return ddS.items.find((x) => x.cal && `${x.name}|${x.date}` === k); }
function ddayToggleEvent(title, startSec) {
  const hit = ddayFindEvent(title, startSec);
  if (hit) ddS.items = ddS.items.filter((x) => x !== hit);
  else {
    if (ddS.items.length >= 40) { showToast(t('ddayFull')); return; }
    ddS.items.push({ id: 'e' + Date.now().toString(36) + ddS.items.length, name: ddayName(title), date: ddayDateStr(startSec * 1000), done: false, cal: true });
  }
  ddaySave(); ddayRefreshViews();
}
function ddayStarButton(title, startSec) {
  const b = document.createElement('button');
  const on = !!ddayFindEvent(title, startSec);
  b.className = 'agstar' + (on ? ' on' : ''); b.type = 'button'; b.title = t(on ? 'ddayUnmark' : 'ddayMark');
  b.innerHTML = typeof uiIconSvg === 'function' ? (uiIconSvg('star', 13) || '') : '';
  b.addEventListener('click', (e) => { e.stopPropagation(); ddayToggleEvent(title, startSec); });
  return b;
}
// 일정 탭 맨 위의 D-day 줄들
function ddayRows() {
  const out = [];
  for (const r of ddayAll()) {
    const el = document.createElement('div');
    el.className = 'trow agenda dday' + (r.n === 0 ? ' today' : r.n > 0 && r.n <= 7 ? ' soon' : r.n < 0 ? ' past' : '');
    const dn = document.createElement('span'); dn.className = 'dn'; dn.textContent = ddayLabel(r.n);
    const tx = document.createElement('span'); tx.className = 'tx'; tx.textContent = r.name;
    const dd = document.createElement('span'); dd.className = 'due';
    dd.textContent = new Date(r.ms).toLocaleDateString(lang, { month: 'numeric', day: 'numeric', weekday: 'short' });
    const done = document.createElement('button'); done.className = 'ddb'; done.type = 'button'; done.title = t('ddayDone'); done.innerHTML = uiIconSvg('tick', 12) || '';
    done.addEventListener('click', (e) => { e.stopPropagation(); ddayMark(r.id, { done: true }); });
    const del = document.createElement('button'); del.className = 'ddb rm'; del.type = 'button'; del.title = t('ddayDelete'); del.innerHTML = uiIconSvg('close', 12) || '';
    del.addEventListener('click', (e) => { e.stopPropagation(); ddayRemove(r.id); });
    el.append(dn, tx, dd, done, del);
    out.push(el);
  }
  return out;
}
// 작은 노치: 가장 가까운(오늘 포함) D-day 하나
function ddaySatItems() {
  if (!store.settings.satDday || !tabVisibleId('agenda')) return [];
  const next = ddayAll().find((r) => r.n >= 0);
  if (!next) return [];
  const nm = Array.from(next.name);
  const short = nm.length > 6 ? nm.slice(0, 6).join('') + '…' : next.name;
  return [{ id: 'dday', kind: 'dday', page: 'agenda', running: false, text: `${ddayLabel(next.n)} | ${short}`, parts: [ddayLabel(next.n), short], pct: 100 }];
}
function initDday() {
  setTimeout(ddayLoad, 3000);
  setInterval(ddayLoad, 10 * 60 * 1000);
  setInterval(() => { if (store.settings.satDday && typeof renderSat === 'function') renderSat(); }, 60 * 1000);
}

function initSystemTabs() {
  sysSlider('sysVol', 'sysVolOut', 'volume');
  sysSlider('sysBri', 'sysBriOut', 'brightness');
  $('sysMute').addEventListener('click', (e) => { e.stopPropagation(); sysDo('mute'); });
  initPickers();
  $('sysMic').addEventListener('click', (e) => { e.stopPropagation(); sysDo('mic'); });
  for (const b of $$('#pwrGrid .ltile')) {
    sysSetIc(b.querySelector('svg'), PWR_ICON[b.dataset.k]);
    b.addEventListener('click', (e) => { e.stopPropagation(); pwrPress(b); });
  }
  langHooks.push(() => { renderSys(); pwrResetConfirm(); });
  setInterval(() => { if (page === 'sys' && isExpanded && !document.hidden && !spk.kind) sysLoad(false); }, SYS_REFRESH_MS);
}

function initFeatures2() {
  initDock();
  initTimer();
  initClip();
  initAgenda();
  initVolume();
  initSource();
  initLauncherPlugins();
  initSystemTabs();
  initPerf();
  if (typeof initPhone === 'function') initPhone();
  if (typeof initReorder === 'function') initReorder();          // 시스템·전원·휴대폰 탭의 버튼을 길게 눌러 끌어 옮기기(reorder.js)
  initWeather();
  initDday();
  launcherLoad();
  refreshPageDots();
}
