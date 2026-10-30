// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
// Copyright (c) 2026 Flirty_BananaMilk — 상업적 이용 금지, 자세한 내용은 LICENSE
// ========================================================
// 보조 노치 (아이폰 다이나믹 아일랜드처럼): 음악이 나오는 접힌 노치 옆에 작은 알약이 따로 붙는다.
//  - 큰 노치는 계속 음악(가사)을 보여 주고, 보조 노치는 지금 진행 중인 것을 보여 준다:
//    포모도로/타이머가 돌고 있으면 링 + 남은 시간, 스톱워치는 아이콘 + 지난 시간, 아니면 현재 시간 (설정 satellite: 끔 / 타이머만 / 타이머+시계).
//  - 보조 노치는 두 개(오른쪽이 먼저, 그 뒤에 왼쪽)이고, 하나에 정보를 최대 두 개까지 담는다(두 개를 담으면 폭이 넓어진다). 최대 네 개.
//    (포모도로 > 타이머 > 스톱워치 > 시계 순으로 앞선 것부터 오른쪽을 채우고 절반씩 나눈다: 3개면 오른쪽 둘 + 왼쪽 하나.)
//  - 누르면 노치가 펼쳐지며 그 페이지(타이머/스톱워치/포모도로)가 열린다.
//  - 큰 노치와 같은 스프링으로 따라다니도록, 큰 노치의 너비를 CSS 변수(--island-w)로 넘기고 left 를 그에 맞춰 전환한다.
//  - 왼쪽은 오른쪽 레이어를 좌우로 뒤집은 것이다(.goo-l, .sat-wrap-l: scaleX(-1)). 글자와 유리 화면은 다시 뒤집어 바르게 보인다.
// ========================================================
const SAT_GAP = 16;                 // 큰 노치와 물방울 사이 간격(px). 이보다 가까울 때만 물방울 필터의 '목'이 생긴다
const SAT_SETTLE_MS = 800;           // 큰 노치가 완전히 줄어든 뒤(스프링 0.62초 + 여유)에야 물방울이 나온다 (애니메이션 속도 설정에 따라 늘고 준다)
const SAT_SECOND_MS = 1500;          // 오른쪽이 나온 뒤 왼쪽이 나오기까지 (오른쪽이 나오고 큰 노치가 흔들리는 시간 1.5초)
const SAT_GOO_OFF_MS = 1500;         // 들어간 뒤 필터 레이어를 끄기까지 (들어가는 전환 0.95초 + 겉면이 사라지는 지연 1초 중 큰 쪽 + 여유)
const satScale = (ms) => (typeof PREF !== 'undefined' && PREF.animOff ? 30 : ms / ((typeof PREF !== 'undefined' && PREF.rate) || 1));
let satLastView = null;
let satReadyAt = 0;
let satReadyTimer = null;

const SAT_PRIORITY = { notif: 4, pomo: 3, timer: 2, stopwatch: 1, clock: 0 };
// 윈도우 알림: 알림이 오면 왼쪽 자리에 작은 '동그라미'(종 + 빨간 점)가 뜬다 (내용은 보여 주지 않고, 왔다는 것만).
// 사라지지 않고 유지되다가, 동그라미를 누르거나 윈도우 알림 센터를 열거나 윈도우에서 알림을 다 처리하면 사라진다. 여러 개면 숫자.
const satNotif = { count: 0 };
function satNotifActive() { return !!(store.settings.winNotify) && satNotif.count > 0; }
function satNotify(apps) {
  if (!store.settings.winNotify) return;
  satNotif.count += Math.max(1, (apps && apps.length) || 1);
  renderSat();
}
function satNotifDismiss() { satNotif.count = 0; renderSat(); }
// 눌렀을 때: 윈도우 알림 센터를 열고(파이썬이 Win+N/Win+A 를 보낸다) 동그라미를 지운다
function satNotifOpen() {
  const api = typeof getApi === 'function' ? getApi() : null;
  if (api && api.open_notification_center) api.open_notification_center();
  satNotifDismiss();
}
// 자리: r = 오른쪽(먼저), l = 왼쪽(나중). id = 지금 그 자리에 있는 항목 (우선순위 순으로 채운다)
const satSlots = [
  { side: 'r', ids: { sat: 'sat', layer: 'gooLayer', drop: 'gooDrop', neck: 'gooNeck', wrap: 'satWrap' }, delay: 0 },
  { side: 'l', ids: { sat: 'satL', layer: 'gooLayerL', drop: 'gooDropL', neck: 'gooNeckL', wrap: 'satWrapL' }, delay: SAT_SECOND_MS },
];
for (const s of satSlots) Object.assign(s, { id: '', items: [], key: '', shown: false, width: 0, gooOffTimer: null, keepUntil: 0, keepTimer: null, px: -34 });
function satEls(slot) {
  const e = {};
  for (const k of Object.keys(slot.ids)) e[k] = document.getElementById(slot.ids[k]);
  return e;
}

function satMode() {
  const v = store.settings.satellite;
  return v === 'off' || v === 'timer' ? v : 'full';
}
function satOn() { return satMode() !== 'off'; }

// 진행 중인 타이머류 목록 (우선순위 순). 접힌 노치 칩과 보조 노치가 같이 쓴다
function timerItems() {
  const out = [];
  if (pomoActive()) {
    out.push({ id: 'pomo', kind: pomo.mode === 'break' ? 'pomo-break' : 'pomo', page: 'pomo', running: !!pomo.running,
               text: `${pad2(Math.floor(pomo.remaining / 60))}:${pad2(pomo.remaining % 60)}`, pct: pomo.total > 0 ? (pomo.remaining / pomo.total) * 100 : 100 });
  }
  if (tmrActiveOf('timer')) {
    const s = tmrS.timer;
    out.push({ id: 'timer', kind: 'timer', page: 'timer', running: s.running, text: fmtClock(s.remaining), pct: s.total > 0 ? (s.remaining / s.total) * 100 : 100 });
  }
  if (tmrActiveOf('stopwatch')) {      // 스톱워치는 끝이 없어서 줄어드는 링을 쓰지 않는다 (아이콘으로 보여 준다)
    const s = tmrS.stopwatch;
    out.push({ id: 'stopwatch', kind: 'stopwatch', page: 'timer', running: s.running, text: fmtClock(s.elapsed), pct: 100 });
  }
  return out;
}

// 접힌 노치 칩: 가장 앞선 하나
function chipInfo() {
  const it = timerItems()[0];
  return it ? Object.assign({ active: true }, it) : { active: false, id: '', kind: '', page: 'music', text: '', pct: 100, running: false };
}

const SAT_RING_COLOR = { pomo: 'var(--red)', 'pomo-break': 'var(--green)', timer: '#ffb340', stopwatch: '#4da3ff' };

// 지금 보여 줄 후보: 우선순위 순(포모도로 > 타이머 > 스톱워치 > 시계), 최대 네 개
function satCandidates(v, settled) {
  const list = [];
  if (satNotifActive() && (v === 'mini' || v === 'idle' || v === 'pet') && settled) {
    list.push({ id: 'notif', kind: 'notif', page: 'music', running: false, text: '', pct: 100, count: satNotif.count });
  }
  if (!satOn() || v !== 'mini' || !settled) return list;
  list.push(...timerItems());
  if (satMode() === 'full' && !(compactMode && store.settings.compactClock !== false) && typeof lastClockHtml === 'string' && lastClockHtml) {
    list.push({ id: 'clock', kind: 'clock', page: 'music', running: false, text: '', html: lastClockHtml, pct: 100 });
  }
  return list.sort((a, b) => SAT_PRIORITY[a.id] - SAT_PRIORITY[b.id] < 0 ? 1 : -1);
}

// 보조 노치는 두 개(오른쪽, 왼쪽)이고, 하나에 정보를 최대 두 개까지 담는다(두 개일 때는 폭이 넓어진다).
// 앞선 항목부터 오른쪽을 채우되 절반씩 나눈다: 1개 -> 오른쪽 / 2개 -> 오른쪽·왼쪽 한 개씩 / 3개 -> 오른쪽 둘 + 왼쪽 하나 / 4개 -> 둘씩
function satSplit(cands) {
  const notif = cands.find((c) => c.id === 'notif');
  if (notif) return [cands.filter((c) => c !== notif).slice(0, 2), [notif]];      // 알림 동그라미는 왼쪽 자리를 혼자 쓴다
  const n = Math.min(4, cands.length);
  const r = Math.ceil(n / 2);
  return [cands.slice(0, r), cands.slice(r, n)];
}

const SAT_PAD_W = 24;        // 보조 노치 좌우 여백 합
const SAT_DIV_W = 15;        // 두 정보 사이(구분선 포함)
const SAT_CHAR_W = 7.4;      // 숫자 한 글자 폭
function satInnerWidth(item, textLen, ampm) {
  return (item.kind === 'clock' ? 6 : 20) + textLen * SAT_CHAR_W + (ampm ? 10 : 0);
}

// .sat-in 안에 정보 칸 두 개(+ 구분선)를 만든다. 첫 칸은 원래 있던 링/아이콘/글자를 그대로 쓴다.
function satEnsureCells(el) {
  const inn = el && el.querySelector('.sat-in');
  if (!inn || inn.dataset.cells === '2') return;
  const first = document.createElement('div');
  first.className = 'sat-item';
  while (inn.firstChild) first.appendChild(inn.firstChild);
  first.insertAdjacentHTML('beforeend', '<svg class="bell-ico" viewBox="0 0 24 24"><path d="M12 22c1.1 0 2-.9 2-2h-4c0 1.1.9 2 2 2zm6-6v-5c0-3.07-1.63-5.64-4.5-6.32V4c0-.83-.67-1.5-1.5-1.5s-1.5.67-1.5 1.5v.68C7.64 5.36 6 7.92 6 11v5l-2 2v1h16v-1l-2-2z"/></svg><b class="bell-n"></b>');
  const div = document.createElement('i');
  div.className = 'sat-div';
  const second = first.cloneNode(true);
  second.classList.add('second');
  inn.append(first, div, second);
  inn.dataset.cells = '2';
}

// 한 칸을 채운다. 글자 수와 AM/PM 여부를 돌려준다 (폭 계산용)
function satFillCell(cell, item) {
  const ring = cell.querySelector('.sat-ring');
  const sw = cell.querySelector('.sw-ico');
  const label = cell.querySelector('.sat-t');
  const isNotif = item.kind === 'notif';
  const bell = cell.querySelector('.bell-ico'), badge = cell.querySelector('.bell-n');
  if (bell) bell.style.display = isNotif ? 'block' : 'none';
  if (badge) {          // 빨간 점은 항상, 둘 이상이면 점 안에 숫자
    badge.style.display = isNotif ? 'grid' : 'none';
    badge.textContent = isNotif && item.count > 1 ? (item.count > 9 ? '9+' : String(item.count)) : '';
    badge.classList.toggle('dot', isNotif && !(item.count > 1));
  }
  label.style.display = isNotif ? 'none' : '';          // 비어 있는 글자 칸도 간격(gap)을 차지해서 종이 가운데에서 밀렸다
  const isTimer = item.kind !== 'clock' && !isNotif;
  const isSw = item.kind === 'stopwatch';
  ring.style.display = isTimer && !isSw ? 'block' : 'none';
  sw.style.display = isSw ? 'block' : 'none';
  if (isTimer && !isSw) { ring.style.setProperty('--c', SAT_RING_COLOR[item.kind] || 'var(--red)'); ring.style.setProperty('--p', item.pct.toFixed(2)); }
  if (isNotif) label.textContent = '';
  else if (isTimer) label.textContent = item.text; else label.innerHTML = item.html;
  cell.dataset.kind = item.kind;
  cell.dataset.run = item.running ? '1' : '0';
  const txt = label.textContent || '';
  return { len: txt.length, ampm: /AM|PM/.test(txt) };
}

// 접힌 상태의 뷰: 음악이 있으면 mini, 없으면 idle(시계)/pet. 어느 쪽이든 큰 노치가 다 줄어든 뒤에야 보조 노치가 나온다
const satCollapsedView = (v) => v === 'mini' || v === 'idle' || v === 'pet';

function renderSat(nextView) {
  const els0 = satEls(satSlots[0]);
  if (!els0.sat) return;
  const v = nextView || view;
  document.documentElement.dataset.sat = satOn() ? '1' : '0';
  const now = performance.now();
  if (v !== satLastView) { satLastView = v; satReadyAt = satCollapsedView(v) ? now + satScale(SAT_SETTLE_MS) : 0; }      // 접히는 도중에는 아직 나오지 않는다 (음악이 없는 idle/pet 도 마찬가지: 예전에는 mini 만 기다려서, 알림 동그라미가 큰 노치가 다 줄어들기 전에 떠 물줄기가 끊겨 보였다)
  const settled = now >= satReadyAt;
  const g = geometryFor(v);          // 곧 바뀔 뷰의 크기로 (바뀌기 전의 옛 너비로 위치를 잡으면 물방울이 엉뚱한 쪽에서 나온다)
  const h = g.h > 40 ? 28 : Math.max(22, g.h - 4);          // 큰 노치가 에코 줄 때문에 늘어나도 물방울은 한 줄 높이
  const rs = document.documentElement.style;
  if (v === 'mini' || v === 'idle' || v === 'pet') {          // 물방울은 접힌 노치 기준이다: 펼쳐지는 동안 숨는 자리가 늘어나는 노치의 끝을 따라 밀려가지 않게 마지막 접힌 크기를 유지한다
    rs.setProperty('--island-w', `${g.w}px`);
    rs.setProperty('--island-h', `${g.h}px`);
    rs.setProperty('--island-r', `${v === 'mini' ? (g.h > 40 ? 20 : (compactMode ? 14 : 15)) : 14}px`);      // 큰 노치의 아래 모서리 반지름 (가림 영역과 몸통 실루엣이 같은 곡선을 따른다)
  }
  rs.setProperty('--sat-h', `${h}px`);
  rs.setProperty('--sat-gap', `${SAT_GAP}px`);

  const cands = satCandidates(v, settled);
  const split = satSplit(cands);
  satSlots.forEach((s, i) => { s.items = split[i].map((c) => c.id); s.id = s.items[0] || ''; });
  let nextWake = 0;
  let anyChanged = false;
  satSlots.forEach((slot, i) => {
    const slotReady = satReadyAt + satScale(i === 1 && split[0].length === 0 ? 0 : slot.delay);      // 왼쪽은 오른쪽이 나오고 큰 노치가 흔들리는 시간을 기다린다 — 오른쪽이 없으면 기다릴 이유가 없다
    const slotSettled = now >= slotReady;
    if (split[i].length && !slotSettled) nextWake = Math.max(nextWake, slotReady - now + 30);
    if (satRenderSlot(slot, slotSettled ? split[i] : [], v, g, h)) anyChanged = true;
  });
  if (satCollapsedView(v) && !settled && !satReadyTimer) nextWake = Math.max(nextWake, satReadyAt - now + 30);
  if (nextWake > 0 && !satReadyTimer) satReadyTimer = setTimeout(() => { satReadyTimer = null; renderSat(); }, nextWake);
  if (anyChanged) scheduleRegion(true);
}

// 한 자리(보조 노치 하나)를 그린다. items: 담을 정보 0~2개. 모양이 바뀌었으면 true
function satRenderSlot(slot, items, v, g, h) {
  const e = satEls(slot);
  if (!e.sat) return false;
  satEnsureCells(e.sat);
  const show = items.length > 0;
  const key = [h, (v === 'mini' || v === 'idle' || v === 'pet') ? g.w : 0].concat(items.map((it) => [it.kind, it.text, it.html || '', it.running, it.count || 0].join(':'))).join('|');
  if (key === slot.key) return false;
  slot.key = key;
  if (show) {
    const cells = e.sat.querySelectorAll('.sat-item');
    const div = e.sat.querySelector('.sat-div');
    let w = SAT_PAD_W;
    items.forEach((it, i) => { const m = satFillCell(cells[i], it); cells[i].style.display = 'flex'; w += satInnerWidth(it, m.len, m.ampm); });
    if (items[0].kind === 'notif') w = h;          // 알림은 옆으로 긴 알약이 아니라 동그라미
    for (let i = items.length; i < cells.length; i++) cells[i].style.display = 'none';
    div.style.display = items.length > 1 ? 'block' : 'none';
    if (items.length > 1) w += SAT_DIV_W;
    slot.width = Math.round(w);
    e.sat.dataset.kind = items[0].kind;
    e.sat.dataset.run = items[0].running ? '1' : '0';
    e.sat.dataset.n = String(items.length);
    // 폭은 이 자리의 레이어마다 따로 둔다 (두 자리가 서로 다른 폭을 가질 수 있다)
    e.layer.style.setProperty('--sat-w', `${slot.width}px`);
    e.wrap.style.setProperty('--sat-w', `${slot.width}px`);
  }
  const changed = slot.shown !== show;
  slot.shown = show;
  if (show) {
    clearTimeout(slot.gooOffTimer);
    if (!e.layer.classList.contains('on')) { e.layer.classList.add('on'); void e.layer.offsetWidth; }      // 숨어 있던 자리(큰 노치 안쪽)에서 출발하도록 한 프레임 먼저 그린다
  } else if (changed) {
    clearTimeout(slot.gooOffTimer);
    slot.gooOffTimer = setTimeout(() => e.layer.classList.remove('on'), satScale(SAT_GOO_OFF_MS));                           // 흡수되는 전환이 끝난 뒤 레이어를 끈다(필터 비용)
    slot.keepUntil = performance.now() + satScale(SAT_GOO_OFF_MS);                                                           // 그때까지는 클릭/그리기 영역을 줄이지 않는다
    clearTimeout(slot.keepTimer);
    slot.keepTimer = setTimeout(() => scheduleRegion(true), satScale(SAT_GOO_OFF_MS) + 40);
  }
  e.sat.classList.toggle('show', show);
  e.drop.classList.toggle('show', show);
  if (changed) satDroplet(show ? 'out' : 'in', slot, v === 'mini' || v === 'idle' || v === 'pet');      // 노치가 펼쳐지는 중에 들어갈 때는 큰 노치를 끌거나 흔들지 않는다(보조 노치만 들어간다)
  return changed || show;
}

// ========================================================
// 큰 노치 + 물줄기 + 보조 노치는 '하나의 물방울'이다
// 셋을 따로 움직이지 않고, 하나의 진행(u: 0~1)에서 한꺼번에 계산해 매 프레임 그린다:
//   p     보조 노치의 안쪽 끝이 큰 노치 옆면에서 얼마나 떨어졌나(px, 음수 = 노치 안쪽)
//   pull  큰 노치가 보조 노치 쪽으로 끌려간 거리(px)
//   thick 물줄기의 굵기(0~1)
// 나올 때(out):  보조 노치가 노치 안쪽에서 옆면으로 빠져나온다 -> 더 나가면서 물줄기가 늘어나고 큰 노치가 그쪽으로 끌려간다(당겨진 만큼)
//                -> 물줄기가 끊어지는 순간 큰 노치가 놓여 좌우로 흔들리며 잦아들고, 보조 노치도 제자리로 출렁이며 자리를 잡는다.
// 들어갈 때(in): 보조 노치가 끌리듯 다가오며 물줄기가 생기고 큰 노치가 그쪽으로 살짝 당겨진다 -> 안으로 빨려 들어가면 큰 노치가 좌우로 흔들린다.
// 왼쪽 보조 노치는 거울상이다: 왼쪽으로 당기고, 오른쪽으로 흔들린다(레이어가 뒤집혀 있어 레이어 안의 값은 같다).
// ========================================================
const SAT_PX_HIDDEN = -34;       // 숨어 있을 때 보조 노치의 안쪽 끝 (큰 노치 안쪽)
const SAT_PX_SHOWN = SAT_GAP;    // 자리 잡았을 때
const SAT_SNAP = 26;             // 물줄기가 끊어지는 거리
const SAT_PULL_OUT = 4.2;        // 나올 때 큰 노치가 끌려가는 최대 거리(px)
const SAT_PULL_IN = 2.8;         // 들어갈 때
const SAT_DROP_MS = { out: 1500, in: 1300 };
const SAT_NECK_BACK = 14;        // 물줄기가 큰 노치 안쪽으로 파고드는 길이(노치 뒤에 가려져 있다)
const SAT_NECK_OVERLAP = 8;      // 물방울 안쪽으로 겹치는 길이(필터가 둘을 이어 붙이도록)

const _c01 = (x) => Math.max(0, Math.min(1, x));
const _lerp = (a, b, t) => a + (b - a) * t;
const _smooth = (t) => { t = _c01(t); return t * t * (3 - 2 * t); };
const _inQ = (t) => t * t;
const _outQ = (t) => 1 - (1 - t) * (1 - t);

// u(0~1) -> { p, pull, thick }
function satPlanOut(p0) {
  const A = 0.15, B = 0.4;                        // A: 노치 안쪽에서 나옴 / B: 물줄기가 끊어지는 순간
  const pA = Math.max(p0, -6);
  return (u) => {
    let p;
    if (u < A) p = _lerp(p0, pA, _inQ(u / A));
    else if (u < B) p = _lerp(pA, SAT_SNAP, _outQ((u - A) / (B - A)));
    else { const t = (u - B) / (1 - B); p = SAT_PX_SHOWN + (SAT_SNAP - SAT_PX_SHOWN) * Math.exp(-3.4 * t) * Math.cos(2 * Math.PI * 1.15 * t); }
    let pull, thick;
    if (u < B) {
      pull = SAT_PULL_OUT * _smooth((p + 2) / (SAT_SNAP + 2));                       // 늘어난 만큼 큰 노치가 끌려온다
      thick = _c01((p + 14) / 10) * (1 - 0.88 * _smooth(p / SAT_SNAP));              // 나오면서 굵게 이어지고, 늘어날수록 가늘어진다
    } else {
      const t = (u - B) / (1 - B);
      pull = SAT_PULL_OUT * Math.exp(-1.8 * t) * Math.cos(2 * Math.PI * 2.5 * t);    // 끊어지면 놓여서 좌우로 여러 번 흔들리며 잦아든다
      thick = 0.12 * (1 - _smooth((u - B) / 0.06));                                  // 가늘어진 물줄기가 툭 끊어진다
    }
    return { p, pull, thick };
  };
}
function satPlanIn(p0) {
  const A = 0.25, B = 0.5;                        // A: 끌리듯 다가옴 / B: 안으로 다 들어간 순간
  const pA = Math.min(p0, 6);
  return (u) => {
    let p;
    if (u < A) p = _lerp(p0, pA, _inQ(u / A));
    else if (u < B) p = _lerp(pA, SAT_PX_HIDDEN, _inQ((u - A) / (B - A)));
    else p = SAT_PX_HIDDEN;
    let pull, thick;
    if (u < B) {
      pull = SAT_PULL_IN * _smooth((16 - p) / 14);                                   // 다가올수록 큰 노치가 그쪽으로 당겨진다
      thick = _smooth((16 - p) / 12) * (1 - _smooth((-6 - p) / 14));                 // 가까워지면 물줄기가 생기고, 안으로 들어가면 사라진다
    } else {
      const t = (u - B) / (1 - B);
      pull = SAT_PULL_IN * Math.exp(-1.8 * t) * Math.cos(2 * Math.PI * 2.0 * t);      // 흡수된 뒤 큰 노치가 출렁인다
      thick = 0;
    }
    return { p, pull, thick };
  };
}

const satAnims = new Map();       // slot -> { plan, t0, total, kind, sway }
let satRaf = 0;

function satSetPx(slot, px) {
  slot.px = px;
  const e = satEls(slot);
  if (e.layer) e.layer.style.setProperty('--px', `${px.toFixed(2)}px`);
  if (e.wrap) e.wrap.style.setProperty('--px', `${px.toFixed(2)}px`);
}
function satNeckReset(slot) {
  const e = satEls(slot);
  if (e.neck) { e.neck.style.width = ''; e.neck.style.scale = ''; e.neck.style.translate = ''; }
}

// 시작: kind 'out' | 'in'. sway=false 면 큰 노치는 끌려가거나 흔들리지 않는다(노치가 펼쳐지는 중에 들어갈 때).
function satDroplet(kind, slot, sway) {
  const e = satEls(slot);
  if (!e.layer) return;
  const final = kind === 'out' ? SAT_PX_SHOWN : SAT_PX_HIDDEN;
  if (typeof PREF !== 'undefined' && PREF.animOff) { satAnims.delete(slot); satSetPx(slot, final); satNeckReset(slot); return; }
  const p0 = Number.isFinite(slot.px) ? slot.px : (kind === 'out' ? SAT_PX_HIDDEN : SAT_PX_SHOWN);
  const plan = kind === 'out' ? satPlanOut(p0) : satPlanIn(p0);
  satAnims.set(slot, { plan, t0: performance.now(), total: SAT_DROP_MS[kind] / ((typeof PREF !== 'undefined' && PREF.rate) || 1), kind, sway: sway !== false });
  if (!satRaf) satRaf = requestAnimationFrame(satStep);
}

function satStep(now) {
  const res = new Map();
  let dx = 0;                                           // 큰 노치의 화면 기준 가로 이동량(오른쪽 +)
  for (const [slot, a] of satAnims) {
    const u = Math.min(1, (now - a.t0) / a.total);
    const r = a.plan(u);
    // 큰 노치가 당겨지는 쪽 옆면의 물줄기 뿌리가 부푼다(둥근 덩어리): 당겨진 만큼 + 물줄기가 굵을수록
    const pullHere = a.sway ? Math.max(0, r.pull) : 0;
    const br = pullHere > 0.15 || r.thick > 0.03 ? Math.min(13, pullHere * 2.3 + r.thick * 3.5) : 0;
    res.set(slot, { u, r, a, br });
    if (a.sway) dx += (slot.side === 'l' ? -1 : 1) * r.pull;
  }
  // 큰 노치는 한 번에 한 값으로 움직이고, 몸통·가림 영역·물줄기도 같은 값을 쓴다 (한 덩어리)
  island.style.translate = dx ? `${dx.toFixed(2)}px 0` : '';
  // 큰 노치의 테두리 띠: 물줄기/보조 노치가 닿은 자리를 비우고(한 덩어리), 움직이는 동안 옆 띠를 흐리게 한다
  // 선을 비우는 구멍은 '지금 실제로 물줄기가 이어져 있는 동안, 그 폭'에만 낸다. 접힌 노치의 옆면 직선은 y=10~17px 로 짧아서, 구멍이 크거나 물줄기가 끊어진 뒤에도 남아 있으면
  // 옆면 선이 통째로 사라진 것처럼 보였다. 큰 노치가 펼쳐지는 중(sway=false)에는 물줄기가 없으므로 열지 않는다.
  let holeR = -6, holeL = -6;
  for (const [slot, st] of res) {
    if (!st.a.sway) continue;
    let r = st.r.thick > 0.03 ? st.r.thick * 8 + 2 : -6;
    // (부푼 덩어리 때문에는 열지 않는다: 큰 노치가 출렁이는 동안 양쪽에서 번갈아 생겼다 사라져 옆면 선이 깜빡이며 잘려 보였다)
    if (slot.side === 'l') holeL = Math.max(holeL, r); else holeR = Math.max(holeR, r);
  }
  island.style.setProperty('--rim-hr', `${holeR.toFixed(1)}px`);
  island.style.setProperty('--rim-hl', `${holeL.toFixed(1)}px`);
  island.style.setProperty('--rim-side', satAnims.size ? '0.3' : '1');
  for (const slot of satSlots) {
    const e = satEls(slot);
    if (!e.layer) continue;
    const layerDx = (slot.side === 'l' ? -1 : 1) * dx;       // 왼쪽 레이어는 뒤집혀 있어서 레이어 안의 값은 화면과 부호가 반대다
    const px = `${layerDx.toFixed(2)}px`;
    const body = e.layer.querySelector('.goo-body');
    if (body) body.style.translate = layerDx ? `${px} 0` : '';
    if (layerDx) { e.layer.style.setProperty('--hole-dx', px); if (e.wrap) e.wrap.style.setProperty('--hole-dx', px); }
    else { e.layer.style.removeProperty('--hole-dx'); if (e.wrap) e.wrap.style.removeProperty('--hole-dx'); }
    const st = res.get(slot);
    if (!st) { if (e.neck) { e.neck.style.translate = ''; } e.layer.style.removeProperty('--br'); continue; }
    satSetPx(slot, st.r.p);
    e.layer.style.setProperty('--br', `${st.br.toFixed(2)}px`);
    e.layer.style.setProperty('--bdx', px);
    // 물줄기: 큰 노치 옆면(노치와 같이 움직임)에서 보조 노치의 안쪽 끝까지 이어 붙인다
    const len = Math.max(0, st.r.p + SAT_NECK_OVERLAP + SAT_NECK_BACK - layerDx);
    if (e.neck) {
      e.neck.style.translate = layerDx ? `${px} 0` : '';
      e.neck.style.width = `${len.toFixed(1)}px`;
      e.neck.style.scale = `1 ${(Math.max(0, st.r.thick) * 1.1).toFixed(3)}`;
    }
  }
  for (const [slot, st] of res) {
    if (st.u >= 1) { satAnims.delete(slot); satSetPx(slot, st.a.kind === 'out' ? SAT_PX_SHOWN : SAT_PX_HIDDEN); satNeckReset(slot); }
  }
  if (satAnims.size) { satRaf = requestAnimationFrame(satStep); return; }
  satRaf = 0;
  island.style.translate = '';
  island.style.removeProperty('--rim-hr'); island.style.removeProperty('--rim-hl'); island.style.removeProperty('--rim-side');
  for (const slot of satSlots) {
    const e = satEls(slot);
    const body = e.layer && e.layer.querySelector('.goo-body');
    if (body) body.style.translate = '';
    if (e.layer) { e.layer.style.removeProperty('--hole-dx'); e.layer.style.removeProperty('--br'); e.layer.style.removeProperty('--bdx'); }
    if (e.wrap) e.wrap.style.removeProperty('--hole-dx');
  }
}

// 클릭 가능 영역(SetWindowRgn)에 보조 노치를 포함시킨다 (큰 노치 가운데 기준 좌우로 얼마나 나가는지)
// 들어가는 중(slot.keepUntil 전까지)에도 영역을 유지한다: 큰 노치가 펼쳐지며 영역이 먼저 줄어들면, 아직 노치 쪽으로 움직이는 물방울이 영역 경계에 잘린다.
const satHolds = (s) => s.shown || performance.now() < (s.keepUntil || 0);
function satRegionRight(g, pad) {
  const s = satSlots[0];
  if (!satHolds(s)) return 0;
  return (window.innerWidth + g.w) / 2 + SAT_GAP + s.width + pad;
}
function satRegionLeft(g, pad) {
  const s = satSlots[1];
  if (!satHolds(s)) return Infinity;
  return (window.innerWidth - g.w) / 2 - SAT_GAP - s.width - pad;
}

function initSatellite() {
  for (const slot of satSlots) {
    const el = document.getElementById(slot.ids.sat);
    if (!el) continue;
    satEnsureCells(el);
    el.addEventListener('click', (e) => {
      e.stopPropagation();
      const cell = e.target.closest && e.target.closest('.sat-item');
      const id = slot.items[cell && cell.classList.contains('second') ? 1 : 0] || slot.id;      // 정보가 둘이면 누른 쪽의 페이지
      if (id === 'notif') { satNotifOpen(); return; }      // 알림 동그라미: 누르면 윈도우 알림 센터가 열리고 동그라미는 사라진다
      if (typeof triggerExpand === 'function') triggerExpand();
      if (id === 'timer' || id === 'stopwatch') { tmrSetMode(id); setPage('timer'); }
      else setPage(id === 'pomo' ? 'pomo' : 'music');
    });
  }
  setInterval(() => renderSat(), 1000);      // 시계/타이머 글자 갱신 (값이 같으면 DOM 을 건드리지 않는다)
}
