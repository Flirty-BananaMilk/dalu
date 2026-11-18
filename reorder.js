// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
// Copyright (c) 2026 Flirty_BananaMilk — 상업적 이용 금지, 자세한 내용은 LICENSE
// ========================================================
// 노치 안 버튼 위치 바꾸기 (시스템 · 전원 · 휴대폰 탭)
//   버튼을 길게 누르면(약 0.3초) 버튼이 떠오르고, 끌어서 다른 버튼 위에 가져가면 그 버튼이 자리를 비켜 준다. 놓으면 그 자리에 저장된다.
//   짧게 누르거나 조금 움직이기만 하면 평소처럼 버튼이 눌린다. 끌기가 끝난 직후의 클릭은 무시한다(놓은 버튼이 실행되지 않게).
//   Esc 를 누르면 원래대로 돌아간다. 설정 › 모양 › 탭 구성 의 ‘되돌리기’로 모든 탭의 순서를 기본값으로 되돌린다.
// 저장: 설정 phoneButtons / powerButtons / sysButtons (쉼표로 이은 버튼 이름 목록).
// ========================================================
const REORDER_HOLD_MS = 320;       // 이 시간 누르고 있으면 끌기가 시작된다
const REORDER_ARM_MS = 110;        // 누른 지 이만큼 지나면 '곧 떠오른다'는 표시를 시작한다
const REORDER_MOVE_PX = 7;         // 길게 누르기 전에 이만큼 움직이면 끌기가 아니라 평범한 누르기(또는 스크롤)로 본다
var reorderActive = false;         // 끄는 동안 true: 노치가 마우스를 벗어나도 접히지 않는다
var reorderSwallowUntil = 0;       // 끌기를 마친 직후의 click 을 삼키는 시각

const SYS_KEYS = { sysWifi: 'wifi', sysBt: 'bluetooth', sysMic: 'mic' };
const REORDER_TABS = {
  phone: { setting: 'phoneButtons', grid: () => $('phGrid'), def: ['call', 'sms', 'ringer', 'dnd', 'files', 'media', 'ring', 'mirror'] },
  power: { setting: 'powerButtons', grid: () => $('pwrGrid'), def: ['shutdown', 'restart', 'sleep', 'screenoff', 'lock', 'signout'] },
  sys: { setting: 'sysButtons', grid: () => $('sysTog'), def: ['wifi', 'bluetooth', 'mic'] },
};

function reorderKeyOf(tab, el) { return tab === 'sys' ? (SYS_KEYS[el.id] || '') : (el.dataset.k || ''); }
function reorderItems(grid) { return Array.from(grid.children).filter((e) => e.classList.contains('ltile')); }
function reorderParse(v) { return String(v || '').split(',').map((x) => x.trim()).filter(Boolean); }

// 저장된 순서대로 DOM 을 정렬한다(목록에 없는 버튼은 원래 순서로 뒤에 둔다). 바뀐 것이 없으면 건드리지 않는다.
function reorderApply(tab) {
  const def = REORDER_TABS[tab], grid = def && def.grid();
  if (!grid) return;
  const items = reorderItems(grid), want = reorderParse(store.settings && store.settings[def.setting]);
  // 저장된 순서가 있으면 그 순서대로, 목록에 없는 버튼은 기본 순서로 뒤에 둔다(저장된 값이 비어 있으면 기본 순서)
  const rank = (el) => { const k = reorderKeyOf(tab, el), i = want.indexOf(k), j = def.def.indexOf(k); return i >= 0 ? i : 1000 + (j >= 0 ? j : 100 + items.indexOf(el)); };
  const sorted = items.slice().sort((a, b) => rank(a) - rank(b));
  if (sorted.every((el, i) => el === items[i])) return;
  const frag = document.createDocumentFragment();
  for (const el of sorted) frag.appendChild(el);
  grid.appendChild(frag);
}
function reorderApplyAll() {
  reorderApply('power'); reorderApply('sys');
  if (typeof phoneS !== 'undefined' && typeof renderPhone === 'function' && document.getElementById('phGrid')) { renderPhone(); }          // 휴대폰 탭: 타일 키가 달라졌을 때만 다시 만든다(끌어다 놓은 직후에는 키가 이미 같아서 애니메이션을 끊지 않는다)
}

// 끝낸 순서를 저장한다(화면에는 바로 적용하고, 파이썬에 저장한다)
function reorderSave(tab, domKeys) {
  const def = REORDER_TABS[tab];
  let keys = domKeys.slice();
  if (tab === 'phone') {
    // 지금 화면에 없는 버튼(예: 설정에서 꺼 둔 '화면 보기')이 사용자 목록에 있으면 그대로 뒤에 보존한다: 나중에 켰을 때 사라지지 않게
    const base = reorderParse(store.settings.phoneButtons);
    for (const k of (base.length ? base : PHONE_DEFAULT_BUTTONS)) if (!keys.includes(k) && PHONE_ACTIONS[k]) keys.push(k);
  }
  const str = keys.join(',');
  if (str === String(store.settings[def.setting] || '')) return;
  store.settings[def.setting] = str;
  if (tab === 'phone') phoneS.sig = phoneButtons().join(',');          // 이미 그 순서로 놓였으니 타일을 다시 만들지 않는다
  const api = getApi();
  if (api && api.settings_patch) { try { api.settings_patch({ settings: { [def.setting]: str } }); } catch (e) { /* 다음에 바꿀 때 다시 저장된다 */ } }
}

// ---------------------------------------------------------------- 끌기
let reorderDrag = null;      // { tab, grid, el, pid, g:{x,y}, s, tx, ty, orig:[el...], timer, arm, begun, sx, sy, last }

function reorderPointerDown(e, tab) {
  if (e.button !== 0 || reorderDrag) return;
  const def = REORDER_TABS[tab], grid = def.grid();
  const el = e.target.closest && e.target.closest('.ltile');
  if (!grid || !el || !grid.contains(el) || el.hidden) return;
  if (reorderItems(grid).filter((x) => !x.hidden).length < 2) return;
  const d = { tab, grid, el, pid: e.pointerId, sx: e.clientX, sy: e.clientY, begun: false, g: { x: 0, y: 0 }, s: 1, tx: 0, ty: 0, orig: reorderItems(grid), last: null };
  d.hold = !!(el.dataset && el.dataset.hold);          // 길게 누르면 다른 동작(선택창)이 있는 타일
  if (!d.hold) d.arm = setTimeout(() => { if (reorderDrag === d && !d.begun) el.classList.add('reorder-arm'); }, REORDER_ARM_MS);
  d.timer = setTimeout(() => { if (d.hold) d.ready = true; else reorderBegin(d); }, REORDER_HOLD_MS);          // 그런 타일은 길게 누른 뒤 움직이면 끌기가 되고, 가만히 있으면 선택창이 열린다
  reorderDrag = d;
  window.addEventListener('pointermove', reorderMove, true);
  window.addEventListener('pointerup', reorderUp, true);
  window.addEventListener('pointercancel', reorderUp, true);
  window.addEventListener('keydown', reorderKey, true);
}

function reorderBegin(d) {
  if (reorderDrag !== d) return;
  const r = d.el.getBoundingClientRect();
  d.s = d.el.offsetWidth ? r.width / d.el.offsetWidth : 1;          // 노치 크기 설정(확대)이 있어도 화면 거리와 CSS 거리를 맞춘다
  d.g = { x: d.sx - r.left, y: d.sy - r.top };
  d.begun = true;
  reorderActive = true;
  d.el.classList.remove('reorder-arm'); d.el.classList.add('reorder-lift'); d.grid.classList.add('reorder-on');
  try { d.el.setPointerCapture(d.pid); } catch (e) { /* 캡처가 안 돼도 window 에서 받는다 */ }
}

function reorderPlace(d, cx, cy) {
  // 끄는 버튼이 포인터를 따라가게 한다(자리는 그리드가 정하고, 그 자리에서 얼마나 떨어져 있는지만 translate 로 준다)
  const r = d.el.getBoundingClientRect();
  const slotL = r.left - d.tx * d.s, slotT = r.top - d.ty * d.s;
  d.tx = (cx - d.g.x - slotL) / d.s; d.ty = (cy - d.g.y - slotT) / d.s;
  d.el.style.translate = `${d.tx.toFixed(1)}px ${d.ty.toFixed(1)}px`;
}

function reorderMove(e) {
  const d = reorderDrag; if (!d || e.pointerId !== d.pid) return;
  if (!d.begun) {
    if (Math.hypot(e.clientX - d.sx, e.clientY - d.sy) > REORDER_MOVE_PX) { if (d.ready) reorderBegin(d); else reorderCancelPending(d); }          // 길게 누르기 전에 움직였다: 평범한 누르기
    return;
  }
  e.preventDefault();
  d.last = { x: e.clientX, y: e.clientY };
  reorderPlace(d, e.clientX, e.clientY);
  // 포인터가 다른 버튼 위에 있으면 그 자리로 들어가고, 그 버튼은 비켜 준다
  const sib = reorderItems(d.grid).filter((x) => x !== d.el && !x.hidden);
  const hit = sib.find((x) => { const b = x.getBoundingClientRect(); return e.clientX >= b.left && e.clientX <= b.right && e.clientY >= b.top && e.clientY <= b.bottom; });
  if (!hit || Date.now() - (d.swapAt || 0) < 110) return;          // 방금 자리를 바꿨다: 비켜 가는 중인 버튼에 다시 걸려 떨리지 않게 잠깐 기다린다
  d.swapAt = Date.now();
  const all = reorderItems(d.grid), from = all.indexOf(d.el), to = all.indexOf(hit);
  const before = new Map(sib.map((x) => [x, x.getBoundingClientRect()]));
  d.grid.insertBefore(d.el, from < to ? hit.nextSibling : hit);
  // 비켜 주는 버튼들은 원래 있던 자리에서 새 자리로 부드럽게 옮겨 간다(FLIP)
  const animate = !(typeof PREF !== 'undefined' && PREF.animOff);
  for (const x of sib) {
    const a = before.get(x), b = x.getBoundingClientRect(), dx = (a.left - b.left) / d.s, dy = (a.top - b.top) / d.s;
    if (!animate || (Math.abs(dx) < 0.5 && Math.abs(dy) < 0.5)) continue;
    x.style.transition = 'none'; x.style.translate = `${dx.toFixed(1)}px ${dy.toFixed(1)}px`;
    void x.offsetWidth;
    x.style.transition = 'translate 0.2s cubic-bezier(0.2, 0.9, 0.3, 1.05)'; x.style.translate = '0px 0px';
    setTimeout(() => { x.style.transition = ''; x.style.translate = ''; }, 260);
  }
  reorderPlace(d, e.clientX, e.clientY);          // 자리가 바뀌었으니 포인터 아래에 다시 맞춘다
}

function reorderCancelPending(d) {
  clearTimeout(d.timer); clearTimeout(d.arm);
  d.el.classList.remove('reorder-arm');
  reorderDrag = null;
  reorderUnlisten();
}

function reorderUnlisten() {
  window.removeEventListener('pointermove', reorderMove, true);
  window.removeEventListener('pointerup', reorderUp, true);
  window.removeEventListener('pointercancel', reorderUp, true);
  window.removeEventListener('keydown', reorderKey, true);
}

function reorderFinish(d, save) {
  const el = d.el, grid = d.grid;
  if (!save) {          // 취소: 처음 순서로 되돌린다
    const frag = document.createDocumentFragment();
    for (const x of d.orig) frag.appendChild(x);
    grid.appendChild(frag);
  }
  // 놓은 버튼은 포인터 위치에서 자기 자리로 미끄러져 들어간다
  const animate = !(typeof PREF !== 'undefined' && PREF.animOff);
  if (animate) {
    el.style.transition = 'translate 0.18s cubic-bezier(0.2, 0.9, 0.3, 1.05)'; el.style.translate = '0px 0px';
    setTimeout(() => { el.style.transition = ''; el.style.translate = ''; el.classList.remove('reorder-lift'); }, 200);
  } else { el.style.translate = ''; el.classList.remove('reorder-lift'); }
  grid.classList.remove('reorder-on');
  reorderSwallowUntil = Date.now() + 450;
  if (save) {
    const keys = reorderItems(grid).map((x) => reorderKeyOf(d.tab, x)).filter(Boolean);
    const before = d.orig.map((x) => reorderKeyOf(d.tab, x)).filter(Boolean);
    if (keys.length === d.orig.length && keys.join() !== before.join()) reorderSave(d.tab, keys);          // 순서가 바뀌었을 때만 저장한다
  }
  setTimeout(() => { reorderActive = false; if (typeof island !== 'undefined' && !island.matches(':hover') && typeof triggerCollapse === 'function') triggerCollapse(); }, 220);
}

function reorderUp(e) {
  const d = reorderDrag; if (!d || e.pointerId !== d.pid) return;
  clearTimeout(d.timer); clearTimeout(d.arm);
  d.el.classList.remove('reorder-arm');
  reorderDrag = null;
  reorderUnlisten();
  if (!d.begun) return;                      // 길게 누르지 않았다: 평범한 클릭
  try { d.el.releasePointerCapture(d.pid); } catch (err) { /* 이미 풀렸다 */ }
  reorderFinish(d, e.type === 'pointerup');
}

function reorderKey(e) {
  const d = reorderDrag; if (!d) return;
  if (e.key === 'Escape') {
    e.preventDefault(); e.stopPropagation();
    clearTimeout(d.timer); clearTimeout(d.arm);
    d.el.classList.remove('reorder-arm');
    reorderDrag = null;
    reorderUnlisten();
    if (d.begun) { try { d.el.releasePointerCapture(d.pid); } catch (err) { /* 이미 풀렸다 */ } reorderFinish(d, false); }
  }
}

function initReorder() {
  for (const tab of Object.keys(REORDER_TABS)) {
    const grid = REORDER_TABS[tab].grid();
    if (!grid || grid._reorder) continue;
    grid._reorder = true;
    grid.addEventListener('pointerdown', (e) => reorderPointerDown(e, tab));
    grid.addEventListener('click', (e) => { if (Date.now() < reorderSwallowUntil) { e.stopPropagation(); e.preventDefault(); } }, true);          // 끌기를 마친 직후의 클릭은 버튼을 실행하지 않는다
    grid.addEventListener('contextmenu', (e) => { if (reorderDrag && reorderDrag.begun) e.preventDefault(); });
  }
  reorderApplyAll();
}
