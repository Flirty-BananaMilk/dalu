// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
// Copyright (c) 2026 Flirty_BananaMilk — 상업적 이용 금지, 자세한 내용은 LICENSE
// ========================================================
// 기능 모듈: 포모도로 / 물 마시기 / 할 일 / 파일 선반 / 시스템 알림
// app.js 의 코어(상태 기계, 저장소, notify, i18n) 위에서 동작한다.
// ========================================================

// 테스트에서 시간을 줄여 돌리기 위한 훅(보통은 60초 = 1분)
const SEC_PER_MIN = (typeof window.__SEC_PER_MIN === 'number') ? window.__SEC_PER_MIN : 60;

// ---------------------------------------------------------------- POMODORO
const pomo = { mode: 'focus', total: 0, remaining: 0, running: false, endsAt: 0 };

function pomoModeSeconds(mode) {
  const min = mode === 'focus' ? store.pomo.focusMin : store.pomo.breakMin;
  return Math.max(1, Math.round(min * SEC_PER_MIN));
}

function pomoActive() {
  return pomo.running || pomo.remaining < pomo.total;
}

function pomoSetMode(mode) {
  pomo.mode = mode;
  pomo.total = pomoModeSeconds(mode);
  pomo.remaining = pomo.total;
  pomo.running = false;
  renderPomo();
}

function pomoStartPause() {
  if (pomo.running) {
    pomo.remaining = Math.max(0, Math.ceil((pomo.endsAt - Date.now()) / 1000));
    pomo.running = false;
  } else {
    if (pomo.remaining <= 0) pomo.remaining = pomo.total;
    pomo.endsAt = Date.now() + pomo.remaining * 1000;
    pomo.running = true;
  }
  renderPomo();
}

function pomoTick() {
  if (!pomo.running) return;
  const left = Math.max(0, Math.ceil((pomo.endsAt - Date.now()) / 1000));
  if (left !== pomo.remaining) {
    pomo.remaining = left;
    renderPomo();
  }
  if (left <= 0) pomoComplete();
}

function pomoComplete() {
  const wasFocus = pomo.mode === 'focus';
  if (wasFocus) {
    if (store.pomo.doneDate !== todayKey()) { store.pomo.doneDate = todayKey(); store.pomo.doneToday = 0; }
    store.pomo.doneToday += 1;
    saveStoreSoon();
  }
  pomoSetMode(wasFocus ? 'break' : 'focus');
  playChime('pomo');
  notify({
    icon: 'timer', tone: wasFocus ? 'green' : 'red', ms: 6000,
    title: t(wasFocus ? 'pomoFocusDone' : 'pomoBreakDone'),
    sub: wasFocus ? t('pomoFocusDoneSub', { n: store.pomo.breakMin }) : t('pomoBreakDoneSub')
  });
}

// 집중 시간(포모도로의 '집중'이 진행 중)에는 윈도우 방해 금지를 켜 둔다. 멈추거나 끝나거나 휴식이 되면 되돌린다.
let dndWanted = false;
function syncFocusDnd() {
  const want = store.settings.focusDnd !== false && pomo.mode === 'focus' && pomo.running;
  if (want === dndWanted) return;
  dndWanted = want;
  const api = getApi();
  if (api && api.dnd_set) api.dnd_set(want);
  if (want) notify({ icon: 'timer', tone: 'blue', ms: 2800, title: t('focusStarted'), sub: t('dndOnSub') });
}

function renderPomo() {
  const mm = pad2(Math.floor(pomo.remaining / 60));
  const ss = pad2(pomo.remaining % 60);
  setTextAll($$('.js-ptime'), `${mm}:${ss}`);

  const pct = pomo.total > 0 ? (pomo.remaining / pomo.total) * 100 : 100;
  $('pomoRing').style.setProperty('--p', pct.toFixed(2));

  const active = pomoActive();
  if (island.dataset.pm !== pomo.mode) island.dataset.pm = pomo.mode;
  if (typeof renderChip === 'function') renderChip();     // 접힌 노치의 칩(포모도로/타이머)
  syncFocusDnd();

  setText($('pomoMode'), t(pomo.mode === 'focus' ? 'pomoFocus' : 'pomoBreak'));
  if (store.pomo.doneDate !== todayKey()) { store.pomo.doneDate = todayKey(); store.pomo.doneToday = 0; }
  setText($('pomoSub'), t('pomoToday', { n: store.pomo.doneToday }));
  setText($('pomoStartText'), t(pomo.running ? 'pause' : (active ? 'resume' : 'start')));
  $('pomoStartIcon').setAttribute('d', pomo.running ? ICONS.pause : ICONS.play);
  setText($('pomoSwitch'), t(pomo.mode === 'focus' ? 'toBreak' : 'toFocus'));
  setText($('pomoMin'), t('minutesN', { n: pomo.mode === 'focus' ? store.pomo.focusMin : store.pomo.breakMin }));
  $('pomoStep').style.visibility = active ? 'hidden' : 'visible';   // 진행 중에는 시간을 바꾸지 못한다
}

// 설정 창에서 집중/휴식 시간을 바꿨을 때: 진행 중이 아니면 지금 모드의 남은 시간을 새 값으로 맞춘다
function pomoSettingsChanged() {
  if (!pomoActive()) pomoSetMode(pomo.mode);
}

function pomoAdjust(dir) {
  if (pomoActive()) return;
  if (pomo.mode === 'focus') store.pomo.focusMin = Math.max(5, Math.min(90, store.pomo.focusMin + 5 * dir));
  else store.pomo.breakMin = Math.max(1, Math.min(30, store.pomo.breakMin + dir));
  saveStoreSoon();
  pomoSetMode(pomo.mode);
}

// ---------------------------------------------------------------- WATER
function ensureWaterDay() {
  const w = store.water;
  if (w.log.date !== todayKey()) {
    w.log = { date: todayKey(), entries: [] };
    w.lastRemindAt = Date.now();
    saveStoreSoon();
  }
}

function waterTotal() {
  ensureWaterDay();
  return store.water.log.entries.reduce((s, e) => s + e.ml, 0);
}

function fmtL(ml) {
  return String(Number((ml / 1000).toFixed(2)));
}

function waterAdd(ml) {
  ensureWaterDay();
  store.water.log.entries.push({ t: Date.now(), ml });
  store.water.lastRemindAt = Date.now();   // 방금 마셨으니 다음 알림은 간격 뒤로
  store.water.snoozeUntil = 0;
  saveStoreSoon();
  renderWater();
  showToast(t('waterAdded', { ml }));
}

// 물 알림 미루기: 설정한 시간(기본 10분) 뒤에 다시 알린다. 그 사이에 물을 마시면 미루기는 풀리고 간격이 새로 센다
function waterSnooze() {
  const n = clampN(store.settings.snoozeMin, 1, 120, 10);
  store.water.snoozeUntil = Date.now() + n * 60000;
  saveStoreSoon();
  showToast(t('snoozed', { n }));
}

function waterUndo() {
  ensureWaterDay();
  if (store.water.log.entries.pop()) { saveStoreSoon(); renderWater(); }
}

let chartKey = '';
function renderWater(grow) {
  const w = store.water;
  ensureWaterDay();
  const total = waterTotal();
  const pct = Math.min(100, Math.round((total / w.goalMl) * 100));

  $('wAmount').innerHTML = `${fmtL(total)}<small>/ ${fmtL(w.goalMl)} L</small>`;
  $('wBarFill').style.width = `${pct}%`;
  setText($('wStatus'), total >= w.goalMl ? t('waterGoalReached') : `${pct}% · ${t('waterLeft', { l: fmtL(w.goalMl - total) + ' L' })}`);
  setText($('wAddText'), `${w.bottleMl} ml`);

  // 시간대별 막대 차트
  const hours = [];
  for (let h = w.startHour; h <= w.endHour; h++) hours.push(h);
  const key = hours.join(',');
  const chart = $('wChart');
  if (key !== chartKey) {
    chartKey = key;
    chart.textContent = '';
    const bw = 8;
    const gap = hours.length > 1 ? Math.max(2, (176 - hours.length * bw) / (hours.length - 1)) : 0;
    hours.forEach((h, i) => {
      const bar = document.createElement('i');
      bar.className = 'cbar';
      bar.dataset.h = h;
      bar.style.left = `${i * (bw + gap)}px`;
      chart.appendChild(bar);
    });
    const axis = $('wAxis');
    axis.textContent = '';
    const labels = [hours[0], hours[Math.floor(hours.length / 2)], hours[hours.length - 1]];
    const xs = [0, 88, 176];
    labels.forEach((h, i) => {
      const s = document.createElement('span');
      s.style.left = `${xs[i] + (i === 0 ? 4 : i === 2 ? -4 : 0)}px`;
      s.textContent = pad2(h);
      axis.appendChild(s);
    });
  }
  const perHour = {};
  for (const e of w.log.entries) {
    const h = new Date(e.t).getHours();
    perHour[h] = (perHour[h] || 0) + e.ml;
  }
  const max = Math.max(300, ...Object.values(perHour));
  const nowH = new Date().getHours();
  const bars = Array.from(chart.children);
  if (grow) {   // 페이지가 열릴 때 막대가 0 에서 스프링으로 자란다
    for (const b of bars) { b.style.transition = 'none'; b.style.height = '2px'; }
    void chart.offsetHeight;
    for (const b of bars) b.style.transition = '';
  }
  for (const b of bars) {
    const ml = perHour[b.dataset.h] || 0;
    b.style.height = ml > 0 ? `${Math.max(6, Math.round((ml / max) * 70))}px` : '2px';
    b.classList.toggle('empty', ml === 0);
    b.classList.toggle('now', Number(b.dataset.h) === nowH);
  }

  // 설정 화면 값
  setText($('wsBottle'), String(w.bottleMl));
  setText($('wsGoal'), `${fmtL(w.goalMl)} L`);
  setText($('wsInterval'), `${w.intervalMin} ${t('minutesUnit')}`);
  setText($('wsStart'), `${w.startHour}${t('hourUnit')}`);
  setText($('wsEnd'), `${w.endHour}${t('hourUnit')}`);
  $('wsEnabled').classList.toggle('on', !!w.enabled);
}

function waterAdjust(what, dir) {
  const w = store.water;
  if (what === 'bottle') w.bottleMl = Math.max(100, Math.min(1000, w.bottleMl + 50 * dir));
  else if (what === 'goal') w.goalMl = Math.max(500, Math.min(5000, w.goalMl + 250 * dir));
  else if (what === 'interval') w.intervalMin = Math.max(15, Math.min(180, w.intervalMin + 15 * dir));
  else if (what === 'start') w.startHour = Math.max(0, Math.min(w.endHour - 1, w.startHour + dir));
  else if (what === 'end') w.endHour = Math.max(w.startHour + 1, Math.min(23, w.endHour + dir));
  saveStoreSoon();
  renderWater();
}

function waterRemindCheck() {
  const w = store.water;
  if (!w.enabled) return;
  const now = new Date();
  const h = now.getHours();
  if (h < w.startHour || h >= w.endHour) return;
  const total = waterTotal();
  if (total >= w.goalMl) return;
  if (w.snoozeUntil) {
    if (Date.now() < w.snoozeUntil) return;
    w.snoozeUntil = 0;
    w.lastRemindAt = Date.now() - w.intervalMin * 60000;       // 미루기가 끝났으니 바로 알린다
  }
  if (!w.lastRemindAt || w.lastRemindAt > Date.now()) { w.lastRemindAt = Date.now(); saveStoreSoon(); return; }
  if (Date.now() - w.lastRemindAt >= w.intervalMin * 60 * 1000) {
    w.lastRemindAt = Date.now();
    saveStoreSoon();
    playChime('water');
    notify({ icon: 'drop', tone: 'blue', ms: 5000, title: t('waterTime'), sub: `${fmtL(total)} / ${fmtL(w.goalMl)} L` });
  }
}

// ---------------------------------------------------------------- TODO
let todoDay = '';
const todoNew = new Set();   // 방금 추가된 할 일 id (이것만 등장 연출)

function todoRollover() {
  if (todoDay === todayKey()) return;
  if (todoDay !== '') {   // 날이 바뀜: 끝낸 일은 치우고, 남은 일은 오늘 알림이 다시 울리도록 초기화
    store.todos = store.todos.filter((x) => !x.done);
    for (const x of store.todos) { x.notified = false; x.leadDone = false; x.snoozeUntil = 0; }
    saveStoreSoon();
    if (typeof renderTodos === 'function') renderTodos();
  }
  todoDay = todayKey();
}

// 시각 표기: 설정 '24시간제'를 따른다 (끄면 오전/오후 12시간제). 시계뿐 아니라 할 일·일정의 시각에도 같게 쓴다
function fmtHM(h, m) {
  if (store.settings.clock24 !== false) return `${pad2(h)}:${pad2(m)}`;
  return `${h % 12 || 12}:${pad2(m)} ${h < 12 ? 'AM' : 'PM'}`;
}

function todoDueTs(todo) {
  if (!todo.due) return 0;
  const [h, m] = todo.due.split(':').map(Number);
  const d = new Date();
  d.setHours(h, m, 0, 0);
  return d.getTime();
}

function renderTodos() {
  const list = $('todoList');
  const todos = store.todos.slice().sort((a, b) => (a.done - b.done) || ((a.due || '99:99') < (b.due || '99:99') ? -1 : 1));
  list.textContent = '';
  const now = Date.now();
  for (const todo of todos) {
    const row = document.createElement('div');
    row.className = 'trow' + (todo.done ? ' done' : '');
    row.dataset.id = todo.id;
    const chk = document.createElement('button');
    chk.className = 'chk';
    chk.innerHTML = `<svg viewBox="0 0 24 24"><path d="${ICONS.check2}"/></svg>`;
    chk.addEventListener('click', () => { todo.done = !todo.done; saveStoreSoon(); renderTodos(); });
    const tx = document.createElement('span');
    tx.className = 'tx';
    tx.textContent = todo.text;
    row.append(chk, tx);
    if (todo.due) {
      const due = document.createElement('span');
      due.className = 'due' + (!todo.done && todoDueTs(todo) < now ? ' late' : '');
      due.textContent = fmtHM(...todo.due.split(':').map(Number));
      if (todo.snoozeUntil && todo.snoozeUntil > now) {
        const d = new Date(todo.snoozeUntil);
        due.classList.add('snoozed');
        due.title = t('snoozedUntil', { t: fmtHM(d.getHours(), d.getMinutes()) });
      }
      row.append(due);
    }
    if (todo.due && !todo.done) {
      const snz = document.createElement('button');
      snz.className = 'snz';
      snz.title = t('snoozeTitle', { n: clampN(store.settings.snoozeMin, 1, 120, 10) });
      snz.innerHTML = '<svg viewBox="0 0 24 24"><path d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zm4.2 13.4-.8 1.3L11 13.9V7h1.5v6.1l3.7 2.3z"/></svg>';
      snz.addEventListener('click', (e) => { e.stopPropagation(); todoSnooze(todo); });
      row.append(snz);
    }
    const del = document.createElement('button');
    del.className = 'del';
    del.innerHTML = `<svg viewBox="0 0 24 24"><path d="${ICONS.close}"/></svg>`;
    del.addEventListener('click', () => { store.todos = store.todos.filter((x) => x !== todo); saveStoreSoon(); renderTodos(); });
    row.append(del);
    list.append(row);
  }
  for (const row of list.children) {
    if (todoNew.has(Number(row.dataset.id))) anim(row, [{ opacity: 0, translate: '0 12px', scale: 0.92 }, { opacity: 1, translate: '0 0', scale: 1 }], { duration: 520, easing: SPRING });
  }
  todoNew.clear();
  const done = store.todos.filter((x) => x.done).length;
  setText($('todoCount'), `${done}/${store.todos.length}`);
  todoTimeRefresh();      // 언어가 바뀐 뒤에도 "시간 없음" 문구가 맞게
  $('todoEmpty').classList.toggle('hidden', store.todos.length > 0);
  $('todoLayer').classList.toggle('empty', store.todos.length === 0);
}

// 시간 고르기: 브라우저 기본 시간 입력창은 노치 밖으로 삐져나오는 OS 팝업이라, 노치 안에서 쓰는 작은 선택기를 따로 만든다
const tp = { h: 18, m: 0 };
function todoTimeRefresh() {
  const v = $('todoTime').value;
  setText($('todoTimeTxt'), v ? fmtHM(...v.split(':').map(Number)) : t('todoTimeNone'));
  $('todoTimeBtn').classList.toggle('set', !!v);
}
function todoPickRender() { setText($('tpH'), pad2(tp.h)); setText($('tpM'), pad2(tp.m)); }
function todoPickOpen() {
  const v = $('todoTime').value;
  if (v) { const [h, m] = v.split(':').map(Number); tp.h = h; tp.m = m; }
  else {      // 정해 둔 시간이 없으면 다음 30분 단위
    const n = new Date(), mins = Math.min(1435, Math.ceil((n.getHours() * 60 + n.getMinutes() + 1) / 30) * 30);
    tp.h = Math.floor(mins / 60) % 24; tp.m = mins % 60;
  }
  todoPickRender();
  $('todoLayer').classList.add('picking');
}
function todoPickClose() { $('todoLayer').classList.remove('picking'); }
function todoPickStep(which, dir) {
  if (which === 'h') tp.h = (tp.h + dir + 24) % 24;
  else tp.m = ((dir > 0 ? Math.floor(tp.m / 5) + 1 : Math.ceil(tp.m / 5) - 1) * 5 + 60) % 60;      // 분은 5분 단위
  todoPickRender();
}

function todoOpenAdd() {
  $('todoLayer').classList.add('adding');
  $('todoLayer').classList.remove('picking');
  $('todoText').value = '';
  $('todoTime').value = '';
  todoTimeRefresh();
  setTimeout(() => $('todoText').focus(), 30);
}

function todoCloseAdd() {
  $('todoLayer').classList.remove('adding', 'picking');
  if (document.activeElement) document.activeElement.blur();
}

function todoSave() {
  const text = $('todoText').value.trim();
  if (!text) { $('todoText').focus(); return; }
  const newTodo = { id: Date.now() + Math.floor(Math.random() * 1000), text, due: $('todoTime').value || '', done: false, notified: false, leadDone: false, snoozeUntil: 0 };
  if (newTodo.due && todoDueTs(newTodo) - Date.now() < todoLeadMs()) newTodo.leadDone = true;      // 이미 마감이 코앞이면 "곧 마감" 알림은 건너뛴다
  store.todos.push(newTodo);
  todoNew.add(newTodo.id);
  saveStoreSoon();
  todoCloseAdd();
  renderTodos();
}

const todoLeadMs = () => clampN(store.settings.todoLeadMin, 0, 60, 0) * 60000;      // 마감 몇 분 전에 미리 알릴지 (0 = 미리 알리지 않음)

// 미루기: 알림을 설정한 시간(기본 10분) 늦춘다. 마감 전이면 마감 시각부터 센다
function todoSnooze(todo) {
  const n = clampN(store.settings.snoozeMin, 1, 120, 10);
  todo.snoozeUntil = Math.max(Date.now(), todoDueTs(todo)) + n * 60000;
  todo.notified = true; todo.leadDone = true;
  saveStoreSoon();
  renderTodos();
  showToast(t('snoozed', { n }));
}

function todoDueCheck() {
  todoRollover();
  if (store.settings.todoRemind === false) return;
  const now = Date.now();
  const lead = todoLeadMs();
  for (const todo of store.todos) {
    if (todo.done || !todo.due) continue;
    const ts = todoDueTs(todo);
    if (todo.snoozeUntil) {      // 미루는 중: 그 시각이 되면 한 번 더 알린다
      if (now < todo.snoozeUntil) continue;
      todo.snoozeUntil = 0;
      saveStoreSoon();
      playChime('todo');
      notify({ icon: 'check', tone: 'green', ms: 6000, title: t('todoDue'), sub: todo.text });
      renderTodos();
      break;
    }
    if (lead && !todo.leadDone && !todo.notified && now >= ts - lead && now < ts) {      // 마감 N분 전 미리 알림
      todo.leadDone = true;
      saveStoreSoon();
      playChime('todo');
      notify({ icon: 'check', tone: 'blue', ms: 6000, title: t('todoSoon', { n: Math.max(1, Math.ceil((ts - now) / 60000)) }), sub: todo.text });
      break;   // 한 번에 하나씩
    }
    if (todo.notified) continue;
    if (now >= ts && now - ts < 12 * 3600 * 1000) {
      todo.notified = true;
      saveStoreSoon();
      playChime('todo');
      notify({ icon: 'check', tone: 'green', ms: 6000, title: t('todoDue'), sub: todo.text });
      renderTodos();
      break;   // 한 번에 하나씩
    }
  }
}

// ---------------------------------------------------------------- SHELF
const IMAGE_EXT = /\.(png|jpe?g|gif|webp|bmp|svg)$/i;
const shelfInfoCache = new Map();
const shelfNew = new Set();   // 방금 추가된 파일 경로 (이것만 등장 연출)
const shelfThumbs = new Map();   // 경로 -> 썸네일 data URI (파이썬이 축소해 준 것)
const shelfThumbAsked = new Set();

function fmtSize(n) {
  if (n >= 1073741824) return (n / 1073741824).toFixed(1) + ' GB';
  if (n >= 1048576) return (n / 1048576).toFixed(1) + ' MB';
  if (n >= 1024) return Math.round(n / 1024) + ' KB';
  return n + ' B';
}

function fileUrl(path) {
  return encodeURI('file:///' + path.replace(/\\/g, '/')).replace(/#/g, '%23').replace(/\?/g, '%3F');
}

// 파일 종류 -> 아이콘 이름 (icons.js). 이모지 대신 선 아이콘을 쓴다.
function fileIconName(info) {
  if (info.isDir) return 'folder';
  const n = info.name.toLowerCase();
  if (/\.(mp3|flac|wav|m4a|aac|ogg)$/.test(n)) return 'music';
  if (/\.(mp4|mkv|mov|avi|webm)$/.test(n)) return 'video';
  if (/\.(png|jpe?g|gif|webp|bmp|svg)$/.test(n)) return 'image';
  if (/\.(zip|7z|rar|tar|gz)$/.test(n)) return 'download';
  if (/\.(exe|msi|bat|cmd|ps1|py|js|ts|json)$/.test(n)) return 'code';
  if (/\.(docx?|txt|md|hwp|rtf|pdf)$/.test(n)) return 'note';
  return 'file';
}

async function shelfRefresh() {
  const api = getApi();
  let changed = false;
  if (api && api.file_info && store.shelf.length) {
    try {
      const infos = await api.file_info(store.shelf);
      for (const i of infos || []) {
        const old = shelfInfoCache.get(i.path);
        if (!old || old.size !== i.size || old.exists !== i.exists) changed = true;
        shelfInfoCache.set(i.path, i);
      }
    } catch (e) { console.error(e); }
  }
  // 카드 구성이 달라졌거나(처음/추가/삭제) 파일 정보가 바뀐 경우에만 다시 그린다
  const built = Array.from($('shCards').children).map((c) => c.dataset.path).join('|');
  if (changed || built !== store.shelf.join('|')) renderShelf();
}

function shelfAdd(paths) {
  const fresh = (paths || []).filter((p) => p && !store.shelf.includes(p));
  if (!fresh.length) return;
  store.shelf.push(...fresh);
  for (const p of fresh) shelfNew.add(p);
  saveStoreSoon();
  shelfRefresh();
  setPage('shelf');
  triggerExpand();
  showToast(t('shAdded', { n: fresh.length }));
}

function shelfRemove(path) {
  store.shelf = store.shelf.filter((p) => p !== path);
  saveStoreSoon();
  renderShelf();
}

// 큰 원본을 화면에서 직접 디코딩하지 않는다: 파이썬이 만든 작은 썸네일만 쓴다
async function fetchThumbs(paths) {
  const api = getApi();
  const ask = paths.filter((p) => !shelfThumbAsked.has(p));
  if (!ask.length) return;
  for (const p of ask) shelfThumbAsked.add(p);
  for (const p of ask) {   // 하나씩 요청해, 만들어지는 대로 카드에 채운다 (6장을 한꺼번에 기다리지 않는다)
    let got = {};
    try { if (api && api.get_thumbs) got = (await api.get_thumbs([p])) || {}; } catch (e) { console.error(e); }
    let uri = got[p];
    const info = shelfInfoCache.get(p);
    // 파이썬이 못 만든 작은 SVG 만 원본을 그대로 쓴다
    if (!uri && /\.svg$/i.test(p) && info && info.size > 0 && info.size < 300 * 1024) uri = fileUrl(p);
    if (!uri) continue;
    shelfThumbs.set(p, uri);
    for (const card of $('shCards').children) {
      if (card.dataset.path !== p) continue;
      const thumb = card.querySelector('.thumb');
      const img = document.createElement('img');
      img.draggable = false;
      img.src = uri;
      thumb.textContent = '';
      thumb.append(img);
      anim(img, FADE, { duration: 260 });
    }
  }
}

function renderShelf() {
  const cards = $('shCards');
  const wantThumbs = [];
  cards.textContent = '';
  for (const path of store.shelf) {
    const info = shelfInfoCache.get(path) || { path, name: path.split(/[\\/]/).pop(), size: 0, isDir: false, exists: true };
    const card = document.createElement('div');
    card.className = 'shcard' + (info.exists === false ? ' missing' : '');
    card.dataset.path = path;
    card.title = path;
    const thumb = document.createElement('div');
    thumb.className = 'thumb';
    if (IMAGE_EXT.test(info.name) && info.exists !== false) {
      const uri = shelfThumbs.get(path);
      if (uri) {
        const img = document.createElement('img');
        img.src = uri;
        img.draggable = false;
        thumb.append(img);
      } else {
        thumb.innerHTML = uiIconSvg('image');   // 썸네일이 준비될 때까지 아이콘
        wantThumbs.push(path);
      }
    } else {
      thumb.innerHTML = uiIconSvg(fileIconName(info));
    }
    const nm = document.createElement('div');
    nm.className = 'nm';
    nm.textContent = info.name;
    const sz = document.createElement('div');
    sz.className = 'sz';
    sz.textContent = info.isDir ? '' : fmtSize(info.size);
    const rm = document.createElement('button');
    rm.className = 'rm';
    rm.innerHTML = `<svg viewBox="0 0 24 24"><path d="${ICONS.close}"/></svg>`;
    rm.addEventListener('click', (e) => { e.stopPropagation(); shelfRemove(path); });
    card.append(thumb, nm, sz, rm);
    cards.append(card);
    if (shelfNew.has(path)) anim(card, [{ opacity: 0, translate: '0 14px', scale: 0.7 }, { opacity: 1, translate: '0 0', scale: 1 }], { duration: 560, easing: SPRING });
  }
  shelfNew.clear();
  if (wantThumbs.length) fetchThumbs(wantThumbs);
  const has = store.shelf.length > 0;
  $('shZone').classList.toggle('has', has);
  $('shClear').classList.toggle('hidden', !has);
  setText($('shHint'), `${t('shHint')}\n${t('shHint2')}`);
  $('shHint').style.whiteSpace = 'pre-line';
}

// 선반 카드: 클릭하면 열고, 누른 채 움직이면 다른 앱으로 끌어낸다(네이티브 드래그)
let cardDrag = null;
function initShelfCards() {
  const cards = $('shCards');
  cards.addEventListener('mousedown', (e) => {
    const card = e.target.closest('.shcard');
    if (!card || e.target.closest('.rm') || e.button !== 0) return;
    cardDrag = { path: card.dataset.path, x: e.screenX, y: e.screenY, moved: false };
  });
  window.addEventListener('mousemove', (e) => {
    if (!cardDrag || cardDrag.moved) return;
    if (Math.abs(e.screenX - cardDrag.x) > 6 || Math.abs(e.screenY - cardDrag.y) > 6) {
      cardDrag.moved = true;
      const api = getApi();
      const path = cardDrag.path;
      if (api && api.start_file_drag) api.start_file_drag([path]);   // 놓을 때까지 반환되지 않는다
      cardDrag = null;
    }
  });
  window.addEventListener('mouseup', () => { setTimeout(() => { cardDrag = null; }, 0); });
  cards.addEventListener('click', (e) => {
    const card = e.target.closest('.shcard');
    if (!card || e.target.closest('.rm')) return;
    const api = getApi();
    const info = shelfInfoCache.get(card.dataset.path);
    if (info && info.exists === false) { showToast(t('shMissing')); return; }
    if (api && api.open_path) api.open_path(card.dataset.path);
  });
  // 가로 스크롤: 휠을 가로 스크롤로 바꿔 준다
  cards.addEventListener('wheel', (e) => {
    if (cards.scrollWidth > cards.clientWidth) { cards.scrollLeft += e.deltaY; e.preventDefault(); }
  }, { passive: false });

  $('shAdd').addEventListener('click', async (e) => {
    e.stopPropagation();
    const api = getApi();
    if (!api || !api.pick_files) return;
    const picked = await api.pick_files();
    if (picked && picked.length) shelfAdd(picked);
  });
  $('shClear').addEventListener('click', (e) => { e.stopPropagation(); store.shelf = []; saveStoreSoon(); renderShelf(); });
}

// 탐색기에서 파일을 끌어 노치 위로 가져오면 선반이 저절로 펼쳐진다 (실제 경로는 Python 이 drop 이벤트로 전달)
let dragDepth = 0;
function hasFiles(e) {
  return !!(e.dataTransfer && Array.from(e.dataTransfer.types || []).includes('Files'));
}
function initFileDrag() {
  window.addEventListener('dragenter', (e) => {
    if (!hasFiles(e)) return;
    dragDepth++;
    document.body.classList.add('dragging-files');
    if (page !== 'shelf' || !isExpanded) { setPage('shelf'); triggerExpand(); }
  });
  window.addEventListener('dragleave', () => {
    dragDepth = Math.max(0, dragDepth - 1);
    if (dragDepth === 0) { document.body.classList.remove('dragging-files'); triggerCollapse(); }
  });
  window.addEventListener('dragover', (e) => e.preventDefault());
  window.addEventListener('drop', (e) => {
    e.preventDefault();
    dragDepth = 0;
    document.body.classList.remove('dragging-files');
  });
}


// ---------------------------------------------------------------- BUDS (이어버드 배터리 / 소음 제어)
// 모드 번호 -> 버튼 정의. 번호와 실제 소리의 대응은 buds.py 의 MODE_* 와 같아야 한다.
const BUDS_MODES = [
  { value: 0, key: 'modeOff', icon: 'modeOff' },
  { value: 2, key: 'modeAmbient', icon: 'modeAmbient' },
  { value: 3, key: 'modeAdaptive', icon: 'modeAdaptive' },
  { value: 1, key: 'modeAnc', icon: 'modeAnc' }
];
let budsSnap = { available: false, connected: false, name: '', battery: {}, control: false };
let budsModeBusy = false;
let budsMode = null;            // 마지막으로 이 앱에서 설정한 모드 (버즈가 현재 모드를 알려 주지 않는다)

function budsConnected() { return !!(budsSnap && budsSnap.connected); }

function batteryLevel(lv) { return lv >= 50 ? 'high' : (lv >= 20 ? 'mid' : 'low'); }

function budsSummary(b) {
  const parts = [];
  if (b.left != null) parts.push(`L ${b.left}%`);
  if (b.right != null) parts.push(`R ${b.right}%`);
  if (b.case != null) parts.push(`${t('budsCase')} ${b.case}%`);
  if (!parts.length && b.main != null) parts.push(`${b.main}%`);
  return parts.join(' · ');
}

function renderBuds(grow) {
  const s = budsSnap;
  setText($('budsName'), s.name || '-');
  setText($('budsSub'), s.connected ? (s.control ? t('budsConnected') : `${t('budsConnected')} · ${t('budsNoControl')}`) : '');
  for (const el of $$('#budsBats .bat')) {
    const lv = s.battery ? s.battery[el.dataset.pos] : undefined;
    const ring = el.querySelector('.bring');
    const val = el.querySelector('.bval');
    const na = lv == null;
    ring.classList.toggle('na', na);
    val.classList.toggle('na', na);
    ring.dataset.lv = na ? '' : batteryLevel(lv);
    el.classList.toggle('charging', !!(s.charging && s.charging[el.dataset.pos]));
    setText(val, na ? '--' : String(lv));
    if (!grow) ring.style.setProperty('--p', na ? '0' : String(lv));
  }
  const modes = $('budsModes');
  modes.classList.toggle('disabled', !s.control);
  modes.classList.toggle('has-mode', budsMode !== null);
  const buttons = $$('#budsModes .mbtn');
  buttons.forEach((b) => {
    const on = budsMode !== null && Number(b.dataset.mode) === budsMode;
    b.classList.toggle('on', on);
    if (on) {
      const hl = $('modeHl');
      hl.style.setProperty('--hx', `${b.offsetLeft}px`);
      hl.style.setProperty('--hy', `${b.offsetTop}px`);
    }
  });
}

let budsKey = '';
function updateBuds(snap) {
  const was = budsConnected();
  budsSnap = snap || budsSnap;
  // 폴링마다 오지만 값이 바뀔 때만 화면을 갱신한다
  const key = JSON.stringify([budsSnap.available, budsSnap.connected, budsSnap.name, budsSnap.battery, budsSnap.control, budsSnap.charging]);
  if (key === budsKey) return;
  budsKey = key;
  const now = budsConnected();
  if (typeof refreshPageDots === 'function') refreshPageDots();
  if (was && !now && page === 'buds') setPage('music', -1);   // 연결이 끊기면 페이지에서 나간다
  renderBuds();
}

async function setBudsMode(value) {
  if (budsModeBusy || !budsSnap.control) return;
  const api = getApi();
  if (!api || !api.buds_set_mode) return;
  const prev = budsMode;
  const btn = document.querySelector(`#budsModes .mbtn[data-mode="${value}"]`);
  budsModeBusy = true;
  budsMode = value;                      // 낙관적으로 먼저 표시 (하이라이트가 스프링으로 이동)
  store.buds.mode = value;
  btn.classList.add('busy');
  renderBuds();
  let res = null;
  try { res = await api.buds_set_mode(value); } catch (e) { res = { status: 'error' }; }
  btn.classList.remove('busy');
  budsModeBusy = false;
  const label = t((BUDS_MODES.find((m) => m.value === value) || {}).key || 'modeOff');
  if (res && res.status === 'ok') {
    saveStoreSoon();
    showToast(t('budsModeSet', { mode: label }));
  } else {
    budsMode = prev;                     // 실패하면 원래 표시로 되돌린다
    store.buds.mode = prev;
    renderBuds();
    showToast(t(res && res.code === 'in_use' ? 'budsInUse' : 'budsModeFailed'));
  }
}

function initBuds() {
  budsMode = store.buds && store.buds.mode != null ? store.buds.mode : null;
  for (const b of $$('#budsModes .mbtn')) {
    const def = BUDS_MODES.find((m) => m.value === Number(b.dataset.mode));
    b.querySelector('.mic').innerHTML = `<path d="${ICONS[def.icon]}"/>`;
    b.title = '';
    b.addEventListener('click', (e) => { e.stopPropagation(); setBudsMode(Number(b.dataset.mode)); });
  }
  // 하이라이트 위치는 레이아웃이 잡힌 뒤에 정확하다
  langHooks.push(() => { for (const b of $$('#budsModes .mbtn')) b.title = t(BUDS_MODES.find((m) => m.value === Number(b.dataset.mode)).key); renderBuds(); });
  renderBuds();
}

// ---------------------------------------------------------------- 시스템 알림 (볼륨/밝기/Caps Lock/입력 언어/전원/네트워크/오디오 장치)
function handleSysEvent(e) {
  if (!notifyAllowed(store.settings, e.type)) return;       // 설정에서 끈 알림 종류
  switch (e.type) {
    case 'agenda':
      agendaAlert(e);
      break;
    case 'launcher':
      store.launcher = { items: e.items || [] };
      renderLauncher();
      break;
    case 'prefs':
      applyPrefPatch(e.patch);
      break;
    case 'prefs_reset':
      reloadPrefs();
      break;
    case 'test_notify':
      notify({ icon: 'volume', tone: 'blue', title: t('testAlert'), sub: t('testAlertSub'), ms: 3000 });
      break;
    case 'volume': {
      if (typeof volFromSystem === 'function' && volFromSystem(e)) break;     // 볼륨 팝오버가 열려 있으면 알림 대신 슬라이더가 따라간다
      const off = e.muted || e.value === 0;
      notify({ icon: off ? 'volumeOff' : 'volume', title: e.muted ? t('muted') : t('volume'),
               sub: e.muted ? '' : t('percentN', { n: Math.round(e.value * 100) }), meter: e.muted ? 0 : e.value, ms: 1600, key: 'volume' });
      break;
    }
    case 'brightness':
      notify({ icon: 'sun', title: t('brightness'), sub: t('percentN', { n: e.value }), meter: e.value / 100, ms: 1600, key: 'brightness' });
      break;
    case 'caps':
      notify({ icon: 'caps', tone: e.on ? 'blue' : '', title: t(e.on ? 'capsOn' : 'capsOff'), ms: 1800 });
      break;
    case 'num':
      notify({ icon: 'caps', tone: e.on ? 'blue' : '', title: t(e.on ? 'numOn' : 'numOff'), ms: 1800 });
      break;
    case 'scroll':
      notify({ icon: 'caps', tone: e.on ? 'blue' : '', title: t(e.on ? 'scrollOn' : 'scrollOff'), ms: 1800 });
      break;
    case 'media_key':
      // 키보드의 미디어 키(재생/일시정지/다음/이전)를 누르면 지금 곡을 잠깐 보여 준다. 곡이 바뀌는 순간은 새 곡이 뜨도록 잠시 뒤에 보여 준다.
      if (store.settings.mediaKeys !== false && !isExpanded && state.title) {
        setTimeout(() => { if (!isExpanded && state.title) { peek.kind = 'track'; startPeekTimer(peekMs(PEEK_MS)); } }, e.key === 'next' || e.key === 'prev' ? 450 : 120);
      }
      break;
    case 'lang':
      notify({ icon: 'globe', title: t('inputLang'), sub: e.name, ms: 1800 });
      break;
    case 'power':
      notify({ icon: 'charge', tone: e.plugged ? 'green' : '', title: t(e.plugged ? 'charging' : 'unplugged'),
               sub: e.percent != null ? t('percentN', { n: e.percent }) : '', ms: 3000 });
      break;
    case 'battery_low':
      notify({ icon: 'batteryLow', tone: 'red', title: t('batteryLow'), sub: t('percentN', { n: e.percent }), ms: 5000 });
      break;
    case 'net':
      notify({ icon: e.online ? 'wifi' : 'wifiOff', tone: e.online ? 'green' : 'red', title: t(e.online ? 'netOn' : 'netOff'), ms: 3000 });
      break;
    case 'buds':
      notify({ icon: 'headphones', tone: 'blue', title: e.name || 'Earbuds', sub: budsSummary(e.battery || {}), ms: 4600 });
      break;
    case 'buds_low':
      notify({ icon: 'batteryLow', tone: 'red', title: `${e.name || 'Earbuds'}`, sub: t('budsLowMsg', { pos: t(e.position === 'left' ? 'budsLeft' : (e.position === 'right' ? 'budsRight' : 'budsCase')) }) + ` · ${e.percent}%`, ms: 5000 });
      break;
    case 'buds_alert':
      notify({ icon: 'charge', tone: 'red', title: t('budsAlertT'), sub: t('budsAlertS'), ms: 9000, key: 'buds_alert' });
      break;
    case 'win_notify_clear':
      if (typeof satNotifDismiss === 'function') satNotifDismiss();      // 윈도우에서 알림을 처리했거나 알림 센터가 열렸다: 동그라미를 지운다
      break;
    case 'win_notify':
      if (typeof satNotify === 'function') satNotify(e.apps);      // 윈도우 알림이 왔다: 보조 노치(동그라미)로 알린다
      break;
    case 'capture_mode':
      if (e.off) notify({ icon: 'monitor', tone: 'blue', title: t('captureOff'), sub: t('captureOffSub'), ms: 2600 });
      else notify({ icon: 'monitor', tone: 'blue', title: t(e.on ? 'captureOn' : 'captureNone'), sub: e.on ? (e.hold ? t('captureHoldSub') : t('captureOnSub', { n: e.seconds })) : t('captureNoneSub'), ms: 3000 });
      break;
    case 'buds_gone':
      notify({ icon: 'headphones', title: t('budsGone'), ms: 2600 });
      break;
    case 'audio_device':
      if (e.headphones && budsConnected()) break;   // 버즈 연결 알림이 이미 보여 준다
      if (e.headphones) notify({ icon: 'headphones', tone: 'blue', title: e.name, sub: t('connected'), ms: 3600 });
      else notify({ icon: 'volume', title: t('audioOut'), sub: e.name, ms: 2600 });
      break;
    case 'shelf_drop':
      shelfAdd(e.paths);
      break;
  }
}


// ---------------------------------------------------------------- 다음 곡 (Up Next)
// 곡이 끝나기 upNextSec 초 전에 대기열의 다음 곡을 잠깐 보여 준다. 곡마다 한 번만.
let upNextShownFor = '';
function checkUpNext(res) {
  const s = store.settings;
  if (!s.upNext || !res.next || !res.isPlaying || isExpanded || !state.trackId) return;
  const left = (res.duration || 0) - (res.currentTime || 0);
  if (!(res.duration > 30) || left > clampN(s.upNextSec, 5, 60, 12) || left < 1.5) return;
  if (upNextShownFor === state.trackId) return;
  upNextShownFor = state.trackId;
  notify({ icon: 'play', tone: 'blue', title: t('upNext'), sub: res.next.artist ? `${res.next.title} · ${res.next.artist}` : res.next.title, ms: 4200, key: 'upnext' });
}

// ---------------------------------------------------------------- 페이지 등장 연출
// 레이어가 들어올 때(호버로 펼침 / 페이지 전환) 항목들이 시차를 두고 나타난다. 레이어 자체의 페이드(0.16s 지연)에 맞춰 시작한다.
let waterTween = 0;
function countUpWater() {
  const target = waterTotal();
  const token = ++waterTween;
  if (!target || REDUCED_MOTION) return;
  const t0 = performance.now();
  (function step(now) {
    if (token !== waterTween) return;
    const p = Math.min(1, (now - t0) / 800);
    const v = target * (1 - Math.pow(1 - p, 3));
    $('wAmount').innerHTML = `${fmtL(Math.round(v / 10) * 10)}<small>/ ${fmtL(store.water.goalMl)} L</small>`;
    if (p < 1) requestAnimationFrame(step);
  })(t0);
}

// 페이지가 열린 직후(데이터가 늦게 도착해 목록이 다시 그려져도) 새로 만든 항목에 같은 등장 연출을 걸어 주기 위한 기록
let lastEnter = { layer: '', at: 0 };
function enterLate(layer, sel, kf, delay, step, opts) {
  const dt = performance.now() - lastEnter.at;
  if (lastEnter.layer !== layer || dt > 900) return;
  enterEach(document.querySelectorAll(sel), kf, Math.max(0, delay - dt), step, opts);
}

function enterAnim(layer) {
  const root = document.querySelector('.l-' + layer);
  if (!root) return;
  lastEnter = { layer, at: performance.now() };
  const q = (sel) => root.querySelectorAll(sel);
  switch (layer) {
    case 'player':
      enterEach(q('.ttl, .sub'), RISE, 190, 55, { duration: 500 });
      enterEach(q('.controls .btn-ctrl'), POP, 230, 40, { duration: 560, easing: SPRING });
      enterEach(q('.prog-hit, .times'), FADE, 380, 40, { duration: 420 });
      enterEach(q('.volbtn, .srcbtn.on'), FADE, 260, 40, { duration: 420 });      // 볼륨·소스 버튼도 노치가 커지는 동안 먼저 보이지 않게 함께 나타난다. 소스 버튼은 켜져 있을 때(.on)만: 꺼진(투명) 버튼에 이 연출을 걸면 연출이 투명을 덮어써서 잠깐 보였다 사라졌다
      break;
    case 'pomo': {
      // 링이 0 에서 현재 값까지 차오른다
      const ring = $('pomoRing');
      ring.style.transition = 'none';
      ring.style.setProperty('--p', '0');
      void ring.offsetWidth;
      ring.style.transition = '--p 0.9s cubic-bezier(0.22, 1, 0.36, 1) 0.25s';
      renderPomo();
      setTimeout(() => { ring.style.transition = ''; }, 1500);
      anim(root.querySelector('.ptime'), [{ opacity: 0, scale: 0.7 }, { opacity: 1, scale: 1 }], { duration: 600, delay: 260, easing: SPRING });
      enterEach(q('.ttl, .sub, .pstep'), RISE, 230, 55, { duration: 480 });
      enterEach(q('.pbtns .pill'), POP, 330, 50, { duration: 540, easing: SPRING });
      break;
    }
    case 'water': {
      const fill = $('wBarFill');
      fill.style.transition = 'none';
      fill.style.width = '0%';
      void fill.offsetWidth;
      fill.style.transition = '';
      renderWater(true);        // 차트 막대가 0 에서 스프링으로 자란다
      countUpWater();
      enterEach(q('.wlabel, .wamount, .wbar, .wstatus'), RISE, 190, 50, { duration: 480 });
      enterEach(q('.caxis span'), FADE, 340, 40, { duration: 400 });
      enterEach(q('.wbtns .pill'), POP, 340, 50, { duration: 540, easing: SPRING });
      break;
    }
    case 'shelf':
      anim(root.querySelector('.szone'), [{ opacity: 0, scale: 0.94 }, { opacity: 1, scale: 1 }], { duration: 620, delay: 170, easing: SPRING });
      enterEach(q('.shcard'), [{ opacity: 0, translate: '0 14px', scale: 0.78 }, { opacity: 1, translate: '0 0', scale: 1 }], 280, 55, { duration: 560, easing: SPRING });
      enterEach(q('.shtools .pill'), POP, 330, 50, { duration: 480, easing: SPRING });
      break;
    case 'buds': {
      // 페이지를 여는 순간 제어 연결을 미리 맺어 둔다 (첫 모드 변경의 연결 대기 2~6초를 없앤다)
      const budsApi = getApi();
      if (budsApi && budsApi.buds_prepare && budsConnected() && budsSnap.control) budsApi.buds_prepare();
      // 배터리 링이 0 에서 차오르고, 모드 버튼들이 차례로 튀어 오른다
      renderBuds(true);
      const rings = Array.from(q('.bring'));
      rings.forEach((r, i) => {
        r.style.transition = 'none';
        r.style.setProperty('--p', '0');
        void r.offsetWidth;
        r.style.transition = `--p 0.9s cubic-bezier(0.22, 1, 0.36, 1) ${0.25 + i * 0.08}s`;
        const pos = r.closest('.bat').dataset.pos;
        const lv = budsSnap.battery ? budsSnap.battery[pos] : undefined;
        r.style.setProperty('--p', lv == null ? '0' : String(lv));
        setTimeout(() => { r.style.transition = ''; }, 1600);
      });
      enterEach(q('.ttl, .sub'), RISE, 190, 55, { duration: 480 });
      enterEach(q('.bat'), [{ opacity: 0, translate: '0 12px', scale: 0.8 }, { opacity: 1, translate: '0 0', scale: 1 }], 230, 70, { duration: 560, easing: SPRING });
      enterEach(q('.mbtn'), POP, 300, 55, { duration: 560, easing: SPRING });
      setTimeout(renderBuds, 350);   // 하이라이트 위치 재계산 (레이아웃 확정 후)
      break;
    }
    case 'timer':
      enterEach(q('.tmmodes, .tmtime'), RISE, 190, 55, { duration: 480 });
      enterEach(q('.tmadj .pill, .tmbtns .pill'), POP, 300, 45, { duration: 520, easing: SPRING });
      break;
    case 'launcher':
      enterEach(q('.thead > *'), RISE, 190, 45, { duration: 460 });
      enterEach(q('.ltile'), POP, 260, 28, { duration: 500, easing: SPRING });
      break;
    case 'plugins':
      enterEach(q('.porb'), POP, 170, 0, { duration: 520, easing: SPRING });      // 선택한 플러그인의 큰 아이콘·이름도 나머지와 함께 나타난다
      enterEach(q('.pnm, .pst'), RISE, 230, 40, { duration: 460 });
      enterEach(q('.pchip'), RISE, 190, 35, { duration: 440 });
      enterEach(q('.pbtn'), POP, 280, 30, { duration: 500, easing: SPRING });
      break;
    case 'clip':
    case 'agenda':
      enterEach(q('.thead > *'), RISE, 190, 45, { duration: 460 });
      enterEach(q('.trow'), RISE, 260, 45, { duration: 480 });
      enterEach(q('.tempty'), FADE, 280, 0, { duration: 500 });
      break;
    case 'todo':
      enterEach(q('.thead > *'), RISE, 190, 45, { duration: 460 });
      enterEach(q('.trow'), RISE, 260, 55, { duration: 500 });
      enterEach(q('.tempty'), FADE, 280, 0, { duration: 500 });
      break;
  }
}

// ---------------------------------------------------------------- 페이지가 열릴 때 / 언어 변경 / 주기 작업
function onPageShown(p) {
  if (p === 'music' || p === 'lyrics') volSync();      // 볼륨 버튼 아이콘(음소거 여부)을 지금 값으로
  if (p === 'launcher') launcherLoad();
  else if (p === 'plugins') { pluginsLoad(); pluginStatusRefresh(); }
  else if (p === 'timer') renderTimer();
  else if (p === 'clip') clipRefresh(true);
  else if (p === 'agenda') agendaRefresh(true);
  else if (p === 'water') renderWater();
  else if (p === 'shelf') shelfRefresh();
  else if (p === 'pomo') renderPomo();
  else if (p === 'buds') renderBuds();
}

function renderAllFeatures() {
  renderPomo();
  renderWater();
  renderTodos();
  renderShelf();
}

let slowTick = 0;
function featureTick() {
  pomoTick();
  if (typeof tmrTick === 'function') tmrTick();
  slowTick++;
  if (slowTick % 20 === 0) {   // 약 5초마다
    waterRemindCheck();
    todoDueCheck();
    ensureWaterDay();
  }
}

function initFeatures() {
  pomoSetMode('focus');
  todoRollover();
  ensureWaterDay();
  renderAllFeatures();
  shelfRefresh();
  langHooks.push(renderAllFeatures);

  // 포모도로
  $('pomoStart').addEventListener('click', pomoStartPause);
  $('pomoReset').addEventListener('click', () => pomoSetMode(pomo.mode));
  $('pomoSwitch').addEventListener('click', () => pomoSetMode(pomo.mode === 'focus' ? 'break' : 'focus'));
  $('pomoMinus').addEventListener('click', () => pomoAdjust(-1));
  $('pomoPlus').addEventListener('click', () => pomoAdjust(1));

  // 물
  $('wAdd').addEventListener('click', () => waterAdd(store.water.bottleMl));
  $('wSnooze').addEventListener('click', waterSnooze);
  $('wUndo').addEventListener('click', waterUndo);
  $('wSettings').addEventListener('click', () => $('waterLayer').classList.add('settings'));
  $('wsDone').addEventListener('click', () => $('waterLayer').classList.remove('settings'));
  $('wsEnabled').addEventListener('click', () => { store.water.enabled = !store.water.enabled; saveStoreSoon(); renderWater(); });
  for (const b of $$('.wsettings [data-w]')) b.addEventListener('click', () => waterAdjust(b.dataset.w, Number(b.dataset.d)));

  // 할 일
  $('todoAddBtn').addEventListener('click', () => ($('todoLayer').classList.contains('adding') ? todoCloseAdd() : todoOpenAdd()));
  $('todoSave').addEventListener('click', todoSave);
  $('todoCancel').addEventListener('click', todoCloseAdd);
  $('todoTimeBtn').addEventListener('click', todoPickOpen);
  for (const st of $$('#todoPick .stepper')) {
    for (const b of st.querySelectorAll('button')) b.addEventListener('click', () => todoPickStep(st.dataset.t, Number(b.dataset.d)));
    st.addEventListener('wheel', (e) => { e.preventDefault(); e.stopPropagation(); todoPickStep(st.dataset.t, e.deltaY < 0 ? 1 : -1); }, { passive: false });      // 휠: 위로 올리면 커진다
  }
  $('tpOk').addEventListener('click', () => { $('todoTime').value = `${pad2(tp.h)}:${pad2(tp.m)}`; todoTimeRefresh(); todoPickClose(); });
  $('tpClear').addEventListener('click', () => { $('todoTime').value = ''; todoTimeRefresh(); todoPickClose(); });
  $('todoPick').addEventListener('keydown', (e) => {
    if (e.key === 'Escape') { e.stopPropagation(); todoPickClose(); }
    else if (e.key === 'Enter') { e.preventDefault(); $('tpOk').click(); }
  });
  $('todoText').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') todoSave();
    else if (e.key === 'Escape') { e.stopPropagation(); todoCloseAdd(); }
  });

  // 선반
  initShelfCards();
  initFileDrag();
  initBuds();

  setInterval(featureTick, 250);
  setInterval(lookAround, 2200);
}
