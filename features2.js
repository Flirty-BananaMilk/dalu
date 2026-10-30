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
  if (p === 'agenda') return !!String(store.settings.calendarUrl || '').trim();
  return true;
}

// 설정(tabOrder/tabHidden)에 맞춰 도트를 순서대로 놓고, 숨기거나 쓸 수 없는 탭의 도트는 감춘다
let tabSig = '';
// 탭 아이콘 독: 점마다 아이콘을 넣어 두고(평소엔 점이라 보이지 않는다), 점 위에 마우스를 올리면 점들이 큰 아이콘으로 바뀐다
const DOCK_ICON = { music: 'music', pomo: 'target', timer: 'timer', water: 'drop', shelf: 'folder', todo: 'checklist', clip: 'clipboard', agenda: 'calendar', launcher: 'launch', plugins: 'plug', buds: 'headphones' };
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
    if (hit && !dockOn) dockTimer = setTimeout(() => setDock(true), 130);          // 스치기만 해서는 열리지 않는다
    else if (!hit && dockOn) dockTimer = setTimeout(() => setDock(false), 260);
  });
  island.addEventListener('mouseleave', () => { clearTimeout(dockTimer); setDock(false); });
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
  stopwatch: { elapsed: 0, running: false, startedAt: 0, baseElapsed: 0 },
};
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
  if (store.timer) store.timer.mode = tmrMode;
  renderTimer();
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
    s.running = false; s.elapsed = 0; s.baseElapsed = 0;
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
  for (const b of $$('#tmModes button')) {
    b.classList.toggle('on', b.dataset.m === tmrMode);
    b.classList.toggle('run', b.dataset.m !== tmrMode && tmrRunning(b.dataset.m));      // 다른 탭에서 돌고 있다는 작은 점
  }
  tmrPlaceHl();
  const running = tmrRunning(tmrMode);
  setText($('tmStartText'), t(running ? 'pause' : (tmrActiveOf(tmrMode) ? 'resume' : 'start')));
  $('tmStartIcon').setAttribute('d', running ? ICONS.pause : ICONS.play);
  $('tmAdj').style.visibility = timerMode ? 'visible' : 'hidden';
  $('timerLayer').dataset.run = running ? '1' : '0';
  renderChip();
}

function initTimer() {
  store.timer = store.timer || { minutes: 5, mode: 'timer' };
  tmrMode = store.timer.mode === 'stopwatch' ? 'stopwatch' : 'timer';
  tmrReset('timer'); tmrReset('stopwatch');
  $('tmStart').addEventListener('click', () => tmrStartPause());
  $('tmReset').addEventListener('click', () => tmrReset());
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
    row.append(when, tx);
    list.append(row);
  }
}

// 설정 창에서 보기/주 시작 요일을 바꿨을 때
function agendaPrefsChanged() {
  const v = store.settings.agendaView || 'list';
  if (v !== ag.view) agSetView(v, { quiet: true });
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
  const sig = JSON.stringify([d.configured, d.error, d.events.map((e) => [e.title, e.start]), Math.floor(nowSec / 60)]);
  if (sig === agendaSig && !force) return;
  agendaSig = sig;
  const list = $('agendaList'), empty = $('agendaEmpty');
  list.textContent = '';
  const evs = d.events.filter((e) => e.end >= nowSec);
  setText($('agendaCount'), evs.length ? String(evs.length) : '');
  empty.style.display = evs.length ? 'none' : '';
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
    row.append(when, tx, rel);
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
  btn.dataset.next = (sources.find((s) => s.id !== res.source) || {}).id || '';
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

function initFeatures2() {
  initDock();
  initTimer();
  initClip();
  initAgenda();
  initVolume();
  initSource();
  initLauncherPlugins();
  launcherLoad();
  refreshPageDots();
}
