// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
// Copyright (c) 2026 Flirty_BananaMilk — 상업적 이용 금지, 자세한 내용은 LICENSE
// ========================================================
// 설정 창(settings.html)과 노치 화면(index.html)이 함께 쓰는 순수 함수/상수.
// DOM 에 의존하지 않아 node 로도 테스트한다.
// ========================================================

// 스프링 곡선: bounce(0~200, 기본 100)가 클수록 목표를 지나쳤다 돌아오는 정도가 커진다.
// 100 일 때 soft=1.32, hard=1.56 으로 예전에 고정해 두던 값과 같다. 0 이면 오버슈트가 없다(1.0).
function springCurves(bounce) {
  const n = Number(bounce);
  const k = Math.max(0, Math.min(200, Number.isFinite(n) ? n : 100)) / 100;
  return {
    soft: `cubic-bezier(0.34, ${(1 + 0.32 * k).toFixed(3)}, 0.5, 1)`,
    hard: `cubic-bezier(0.34, ${(1 + 0.56 * k).toFixed(3)}, 0.64, 1)`,
  };
}

// 애니메이션 프리셋: 한 번에 바꾸는 설정 묶음. 'normal' 은 기본값과 같아야 한다.
const ANIM_PRESETS = {
  off:     { animOff: true,  animSpeed: 100, bounce: 100, entrance: false, pageAnim: 'fade' },
  minimal: { animOff: false, animSpeed: 130, bounce: 40,  entrance: false, pageAnim: 'fade' },
  normal:  { animOff: false, animSpeed: 100, bounce: 100, entrance: true,  pageAnim: 'slide' },
  lively:  { animOff: false, animSpeed: 90,  bounce: 160, entrance: true,  pageAnim: 'slide' },
};

// 현재 설정이 어느 프리셋과 같은가 ('custom' = 어느 것과도 다름)
function matchAnimPreset(s) {
  for (const name of Object.keys(ANIM_PRESETS)) {
    const p = ANIM_PRESETS[name];
    if (Object.keys(p).every((k) => s[k] === p[k])) return name;
  }
  return 'custom';
}

// 시스템 이벤트 종류 -> 알림 설정 키 (notify.<키>)
const NOTIFY_KEY_OF_EVENT = {
  volume: 'volume', brightness: 'brightness', caps: 'caps', num: 'num', scroll: 'scroll', lang: 'lang', power: 'power', battery_low: 'battery_low',
  net: 'net', buds: 'buds', buds_gone: 'buds', buds_low: 'buds_low', buds_alert: 'buds_alert', audio_device: 'audio_device', capture_mode: 'capture_mode',
};

// 알림을 보여 줄지. 모르는 종류는 보여 준다(새 알림이 생겨도 설정 때문에 조용히 사라지지 않게).
function notifyAllowed(settings, eventType) {
  const key = NOTIFY_KEY_OF_EVENT[eventType];
  if (!key) return true;
  const n = (settings && settings.notify) || {};
  return n[key] !== false;
}

// 'a.b' 형태의 키로 중첩 객체에서 읽고 쓰기
function getPath(obj, dotted, fallback) {
  let cur = obj;
  for (const part of String(dotted).split('.')) {
    if (cur == null || typeof cur !== 'object' || !(part in cur)) return fallback;
    cur = cur[part];
  }
  return cur === undefined ? fallback : cur;
}

function setPath(obj, dotted, value) {
  const parts = String(dotted).split('.');
  let cur = obj;
  for (let i = 0; i < parts.length - 1; i++) {
    if (cur[parts[i]] == null || typeof cur[parts[i]] !== 'object') cur[parts[i]] = {};
    cur = cur[parts[i]];
  }
  cur[parts[parts.length - 1]] = value;
  return obj;
}

// 'notify.volume' = false -> { notify: { volume: false } }
function nestedPatch(dotted, value) {
  return setPath({}, dotted, value);
}

// ---------------------------------------------------------------- 탭(페이지) 구성
// 노치 페이지의 기본 순서. 설정 tabOrder(쉼표 문자열)로 순서를, tabHidden 으로 숨길 탭을 정한다.
const TAB_IDS = ['music', 'pomo', 'timer', 'water', 'shelf', 'todo', 'clip', 'agenda', 'launcher', 'plugins', 'buds'];
const DEFAULT_TAB_ORDER = TAB_IDS.join(',');

function parseTabOrder(str) {
  const seen = [];
  for (const raw of String(str || '').split(',')) {
    const id = raw.trim();
    if (TAB_IDS.includes(id) && !seen.includes(id)) seen.push(id);
  }
  for (const id of TAB_IDS) if (!seen.includes(id)) seen.push(id);        // 목록에 없는(새로 생긴) 탭은 기본 순서대로 뒤에 붙인다
  return seen;
}

function parseTabHidden(str) {
  const out = [];
  for (const raw of String(str || '').split(',')) {
    const id = raw.trim();
    if (TAB_IDS.includes(id) && !out.includes(id)) out.push(id);
  }
  return out;
}

// i 번째 탭을 dir(-1/+1) 만큼 옮긴 순서(문자열). 끝이면 그대로.
function moveTab(orderStr, id, dir) {
  const list = parseTabOrder(orderStr);
  const i = list.indexOf(id), j = i + dir;
  if (i < 0 || j < 0 || j >= list.length) return list.join(',');
  [list[i], list[j]] = [list[j], list[i]];
  return list.join(',');
}

function toggleTabHidden(hiddenStr, id) {
  const list = parseTabHidden(hiddenStr);
  const i = list.indexOf(id);
  if (i >= 0) list.splice(i, 1); else list.push(id);
  return list.join(',');
}

// 페이지 전환에 쓸 목록: 순서대로, 사용자가 숨기지 않았고 지금 쓸 수 있는 것만. 하나도 없으면 음악만.
function visibleTabs(settings, isAvailable) {
  const hidden = parseTabHidden(settings && settings.tabHidden);
  const list = parseTabOrder(settings && settings.tabOrder).filter((id) => !hidden.includes(id) && (!isAvailable || isAvailable(id)));
  return list.length ? list : ['music'];
}

if (typeof module !== 'undefined') {
  module.exports = { TAB_IDS, DEFAULT_TAB_ORDER, parseTabOrder, parseTabHidden, moveTab, toggleTabHidden, visibleTabs, springCurves, ANIM_PRESETS, matchAnimPreset, notifyAllowed, NOTIFY_KEY_OF_EVENT, getPath, setPath, nestedPatch };
}
