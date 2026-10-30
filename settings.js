// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
// Copyright (c) 2026 Flirty_BananaMilk — 상업적 이용 금지, 자세한 내용은 LICENSE
'use strict';
// ========================================================
// 설정 창 엔진: settings_schema.js 의 정의로 화면을 만들고, 바꾼 값을 파이썬(settings_patch)에 저장한다.
// 저장된 값은 파이썬이 노치 화면에 이벤트로 알려 즉시 반영된다. 반대로 노치 쪽에서 바뀐 값은 onExternalData 로 들어온다.
// ========================================================
const $ = (id) => document.getElementById(id);
const getApi = () => (window.pywebview && window.pywebview.api) || null;

const ICONS = {
  sliders: '<path d="M4 7h9M17 7h3M4 17h3M11 17h9"/><circle cx="15" cy="7" r="2"/><circle cx="9" cy="17" r="2"/>',
  music: '<path d="M9 18V6l10-2v12"/><circle cx="7" cy="18" r="2.5"/><circle cx="17" cy="16" r="2.5"/>',
  bell: '<path d="M6 16v-5a6 6 0 0 1 12 0v5l1.5 2h-15z"/><path d="M10 20.5a2 2 0 0 0 4 0"/>',
  palette: '<circle cx="12" cy="12" r="8.5"/><path d="M12 3.5a8.5 8.5 0 0 1 0 17z" fill="currentColor" stroke="none" opacity=".45"/>',
  sparkle: '<path d="M11 3l1.8 5.2L18 10l-5.2 1.8L11 17l-1.8-5.2L4 10l5.2-1.8z"/><path d="M18.5 15.5l.8 2.2 2.2.8-2.2.8-.8 2.2-.8-2.2-2.2-.8 2.2-.8z"/>',
  timer: '<circle cx="12" cy="13.5" r="7.5"/><path d="M12 9.5v4l2.5 2M9.5 3h5"/>',
  headphones: '<path d="M4 15v-3a8 8 0 0 1 16 0v3"/><rect x="3" y="14" width="4" height="7" rx="1.6"/><rect x="17" y="14" width="4" height="7" rx="1.6"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7.6v.4"/>',
  volume: '<path d="M4 9.5v5h3.5L12 18.5v-13L7.5 9.5z"/><path d="M15.5 9a4 4 0 0 1 0 6M18 6.5a8 8 0 0 1 0 11"/>',
  puzzle: '<path d="M10 4h4v3a2 2 0 1 1 3 1.7V12h-3.3a2 2 0 1 0-3.4 0H7V8.7A2 2 0 1 1 10 7z"/><path d="M7 12v4h10v-4"/>',
  clip: '<rect x="6" y="4" width="12" height="17" rx="2.5"/><path d="M9 4V3h6v1M9 11h6M9 15h4"/>',
  reset: '<path d="M4 12a8 8 0 1 0 2.6-5.9M4 4v4.2h4.2"/>',
};
const icon = (name) => `<svg viewBox="0 0 24 24">${ICONS[name] || ''}</svg>`;

const STR = {
  ko: { search: '설정 검색', searchTitle: '검색 결과', noResults: '일치하는 설정이 없어요', ver: '버전', reset: '기본값으로', copied: '완료',
        removed: (n) => `가사 캐시 ${n}개를 지웠어요`, sent: '테스트 알림을 보냈어요', armed: '정말 초기화할까요?', resetDone: '모든 설정을 초기화했어요',
        restarting: '다시 시작합니다…', centered: '가운데로 옮겼어요', failed: '실패했어요', on: '사용 가능', off: '사용 불가',
        eqTitle: '이퀄라이저', eqDesc: '이어버드의 소리 성향을 골라요. 이어버드에 직접 적용되는 설정이라 삼성 Galaxy Buds 앱과 같아요.', eqNormal: '일반', eqBass: '베이스 부스트', eqSoft: '소프트', eqDynamic: '다이내믹', eqClear: '클리어', eqTreble: '트레블 부스트', eqApplied: '적용했어요', eqFailed: '적용하지 못했어요', eqInUse: '다른 앱이 이어버드를 쓰고 있어요 (Galaxy Buds 앱을 닫아 주세요)', eqNoDevice: '이어버드가 연결돼 있지 않거나 제어를 쓸 수 없어요',
        eqCustom: '사용자 설정', eqCustomHint: '9개 대역의 소리를 직접 조절해요. 슬라이더를 놓으면 이어버드에 바로 적용돼요.', eqReset: '모두 0으로', eqLow: '저음', eqHigh: '고음', eqBand: '대역', advTitle: '고급', advGame: '게이밍 모드', advGameDesc: '소리가 늦게 들리는 지연을 줄여요. 켜고 끌 때 연결이 잠깐 바뀌어 소리가 순간 끊길 수 있어요.', advOne: '한쪽만 끼고도 소음 제어', advOneDesc: '한쪽 이어버드만 착용해도 노이즈 캔슬링이 자동으로 꺼지지 않게 해요.', advUnknown: '(이 모델에서는 아직 확인하지 못해 바꿀 수 없어요)',
        btNone: '연결된 이어버드가 없어요', btConnected: '연결됨', btControl: '소음 제어', btLeft: '왼쪽', btRight: '오른쪽', btCase: '케이스',
        btTip: '삼성 <b>Galaxy Buds 앱</b>이 켜져 있으면 이어버드 제어 연결을 먼저 잡고 있어서 노이즈 컨트롤 모드 변경이 막힐 수 있어요. 모드가 안 바뀌면 그 앱을 닫아 보세요.',
        pvTitle: '지금 설정으로 움직여 보기', pvPlay: '다시 재생', pvNote: '클릭하면 <b>접힘 → 미니 → 펼침</b> 순서로 노치가 움직여요. 아래 값을 바꾸면 바로 다시 재생돼요.',
        aVersion: '버전', aPython: 'Python', aWebview: 'pywebview', aData: '데이터 폴더', aMedia: '다른 앱 미디어(SMTC)', aViz: '비주얼라이저', aBuds: '이어버드',
        yes: '사용 가능', no: '사용 불가',
        tabsHint: '위/아래 버튼으로 순서를 바꾸고, 스위치로 탭을 넣거나 뺍니다. 노치에서 휠이나 점을 눌러 넘기는 순서가 이대로 바뀌어요.', tabsReset: '탭 구성 초기화',
        tabNote_clip: '“클립보드·일정” 설정에서 기록을 켜야 보여요', tabNote_agenda: '캘린더 주소를 넣어야 보여요', tabNote_buds: '이어버드가 연결됐을 때만 보여요', tabNote_plugins: '켜 둔 플러그인이 있어야 보여요',
        tabLast: '탭이 하나는 보여야 해요', pluginFolder: '플러그인 폴더 열기', pluginAdd: '추가', pluginRemove: '제거', pluginsAdded: '추가한 플러그인', pluginsAvailable: '추가할 수 있는 플러그인', pluginsNone: '아직 추가한 플러그인이 없어요. 아래에서 필요한 것을 추가하면 노치에 “플러그인” 탭이 나타나요.', pluginsAllAdded: '모든 플러그인을 추가했어요', pluginReload: '다시 읽기', pluginUser: '내가 만든 플러그인', pluginActions: (n) => `동작 ${n}개`,
        capOn: '캡처 모드 켜짐 (다시 누르면 꺼요)', capOff: '캡처 모드 꺼짐', capNone: '이미 캡처할 수 있어요',
        pluginHeroT: '플러그인', pluginHeroD: '노치에 나만의 도구 모음을 붙여요. 필요한 것만 추가하면 “플러그인” 탭에 나란히 나타나고, 추가하지 않은 플러그인은 아무 일도 하지 않아요.', pluginsCount: (n) => `${n}개 사용 중`,
        pluginInUse: '사용 중', pluginMoveL: '앞으로', pluginMoveR: '뒤로', pluginMore: (n) => `+${n}`, pluginCreateT: '나만의 플러그인 만들기', pluginCreateD: '프로그램 실행, 주소 열기, 글 복사, 키 보내기를 JSON 파일 하나로 묶을 수 있어요. 예제를 설치해서 고쳐 쓰는 게 가장 빨라요.',
        pluginInstallEx: '예제 설치', pluginExDone: '예제를 plugins 폴더에 만들었어요 (my-tools.json)', pluginExHave: '예제가 이미 있어요 — 그대로 두었어요', pluginLive: '연결됨',
        pluginHelp: '직접 만들려면 플러그인 폴더에 .json 파일을 넣으세요(예: 프로그램 실행, 주소 열기, 글 복사, 키 보내기). 설명은 README의 “플러그인 만들기”에 있어요.',
        lnAdd: '바로가기 추가', lnBrowse: '찾아보기', lnPresets: '자주 쓰는 것', lnName: '이름', lnTarget: '프로그램·파일·폴더·주소', lnArgs: '인수(선택)', lnIcon: '아이콘', lnEmpty: '아직 바로가기가 없어요. 아래 “자주 쓰는 것”에서 골라 보세요.', lnSaved: '저장했어요', lnFull: '바로가기는 24개까지 만들 수 있어요',
        exported: '설정을 저장했어요', imported: (n) => `설정 ${n}개를 가져왔어요`, importFail: '가져오지 못했어요: 올바른 설정 파일이 아니에요', cleared: '기록을 지웠어요',
        calOk: (n) => `일정 ${n}개를 불러왔어요 (앞으로 7일)`, calFail: '캘린더를 읽지 못했어요. 주소를 확인해 주세요',
        hkOk: '사용 중', hkInvalid: '조합 형식이 올바르지 않아요 (예: Ctrl+Alt+N)', hkConflict: '다른 프로그램이 이미 쓰는 조합이에요', hkOff: '꺼짐' },
  en: { search: 'Search settings', searchTitle: 'Search results', noResults: 'No matching settings', ver: 'Version', reset: 'Reset to default', copied: 'Done',
        removed: (n) => `Cleared ${n} cached lyric file(s)`, sent: 'Sent a test alert', armed: 'Really reset?', resetDone: 'All settings were reset',
        restarting: 'Restarting…', centered: 'Moved to the center', failed: 'Failed', on: 'Available', off: 'Unavailable',
        eqTitle: 'Equalizer', eqDesc: 'Pick the sound profile. It is applied to the earbuds themselves, same as in the Samsung Galaxy Buds app.', eqNormal: 'Normal', eqBass: 'Bass boost', eqSoft: 'Soft', eqDynamic: 'Dynamic', eqClear: 'Clear', eqTreble: 'Treble boost', eqApplied: 'Applied', eqFailed: 'Could not apply', eqInUse: 'Another app is using the earbuds (close the Galaxy Buds app)', eqNoDevice: 'Earbuds are not connected or control is unavailable',
        eqCustom: 'Custom', eqCustomHint: 'Shape the sound in nine bands. Letting go of a slider applies it to the earbuds right away.', eqReset: 'Reset to 0', eqLow: 'Low', eqHigh: 'High', eqBand: 'Band', advTitle: 'Advanced', advGame: 'Gaming mode', advGameDesc: 'Reduces the audio delay. Switching it can briefly change the connection, so the sound may cut out for a moment.', advOne: 'Noise controls with one earbud', advOneDesc: 'Keeps noise canceling on when only one earbud is worn.', advUnknown: '(Not verified on this model yet, so it cannot be changed.)',
        btNone: 'No earbuds connected', btConnected: 'Connected', btControl: 'Noise control', btLeft: 'Left', btRight: 'Right', btCase: 'Case',
        btTip: 'If the Samsung <b>Galaxy Buds app</b> is running it can hold the earbuds’ control connection, which blocks noise-control changes. Close it if modes will not change.',
        pvTitle: 'Try your current settings', pvPlay: 'Replay', pvNote: 'Click to move the notch through <b>collapsed → mini → expanded</b>. It replays when you change a value below.',
        aVersion: 'Version', aPython: 'Python', aWebview: 'pywebview', aData: 'Data folder', aMedia: 'Other-app media (SMTC)', aViz: 'Visualizer', aBuds: 'Earbuds',
        yes: 'Available', no: 'Unavailable',
        tabsHint: 'Use the arrows to reorder and the switches to add or remove tabs. The notch pages follow this order.', tabsReset: 'Reset tabs',
        tabNote_clip: 'Turn on clipboard history in “Clipboard & Agenda” to show it', tabNote_agenda: 'Add a calendar address to show it', tabNote_buds: 'Shown only while earbuds are connected', tabNote_plugins: 'Needs at least one enabled plugin',
        tabLast: 'At least one tab must stay visible', pluginFolder: 'Open plugin folder', pluginAdd: 'Add', pluginRemove: 'Remove', pluginsAdded: 'Added plugins', pluginsAvailable: 'Available plugins', pluginsNone: 'No plugins added yet. Add one below and a “Plugins” tab appears on the notch.', pluginsAllAdded: 'All plugins are added', pluginReload: 'Reload', pluginUser: 'My plugin', pluginActions: (n) => `${n} actions`,
        capOn: 'Capture mode on (press again to turn it off)', capOff: 'Capture mode off', capNone: 'Already capturable',
        pluginHeroT: 'Plugins', pluginHeroD: 'Attach your own tool sets to the notch. Add only what you need and they line up in the “Plugins” tab; plugins you have not added do nothing.', pluginsCount: (n) => `${n} in use`,
        pluginInUse: 'In use', pluginMoveL: 'Move earlier', pluginMoveR: 'Move later', pluginMore: (n) => `+${n}`, pluginCreateT: 'Make your own plugin', pluginCreateD: 'Bundle running a program, opening an address, copying text and sending keys into one JSON file. Installing the example and editing it is the quickest way.',
        pluginInstallEx: 'Install example', pluginExDone: 'Example created in the plugins folder (my-tools.json)', pluginExHave: 'The example already exists — left untouched', pluginLive: 'Live',
        pluginHelp: 'To make your own, drop a .json file into the plugin folder (run a program, open an address, copy text, send keys). See “Writing plugins” in the README.',
        lnAdd: 'Add shortcut', lnBrowse: 'Browse', lnPresets: 'Common ones', lnName: 'Name', lnTarget: 'Program, file, folder or address', lnArgs: 'Arguments (optional)', lnIcon: 'Icon', lnEmpty: 'No shortcuts yet. Pick some from “Common ones” below.', lnSaved: 'Saved', lnFull: 'You can have up to 24 shortcuts',
        exported: 'Settings saved', imported: (n) => `Imported ${n} settings`, importFail: 'Could not import: not a valid settings file', cleared: 'History cleared',
        calOk: (n) => `Loaded ${n} events (next 7 days)`, calFail: 'Could not read the calendar. Check the address',
        hkOk: 'Active', hkInvalid: 'Invalid combination (e.g. Ctrl+Alt+N)', hkConflict: 'Already used by another program', hkOff: 'Off' },
};

// ---------------------------------------------------------------- 상태
const DEFAULTS = schemaDefaults();
const clone = (o) => JSON.parse(JSON.stringify(o));
let D = clone(DEFAULTS);                 // 지금 값 (기본값 위에 저장된 값을 덮은 것)
let LANG = 'ko';      // 'ko' | 'en' | 'zh' | 'ja' (LANGS: i18n_cjk.js)
let ABOUT = {};
let AUTOSTART = false;
let currentPage = null;
let renderedRows = [];                   // 지금 화면의 행들: { item, el, update() }
let CATALOG = [], LAUNCHER = [], PRESETS = [];
let MONITORS = { monitors: [], current: null };   // 파이썬이 알려 주는 연결된 모니터 (식별 번호는 윈도우 설정의 '식별'과 같다)
let pageToken = 0;

const lx = (ko, en, zh, ja) => locOf({ ko, en, zh, ja }, LANG);      // 값이 끼는 짧은 문구를 4개 언어로 직접 주고 싶을 때
const tr = (o) => locOf(o, LANG);      // 설정 항목의 {ko, en} 문구: 그 언어 -> (중·일) 영어 원문 번역표 -> 영어 -> 한국어
Object.assign(STR, STR_CJK);      // 중국어(간체)·일본어 문구
const S = (k) => (STR[LANG] && STR[LANG][k] !== undefined ? STR[LANG][k] : (STR.en[k] !== undefined ? STR.en[k] : STR.ko[k]));
const fmtOf = (item) => (FMT_CJK[LANG] && (FMT_CJK[LANG][item.id] || (item.fmt === ms && FMT_CJK[LANG].ms))) || (LANG !== 'ko' && item.fmtEn) || item.fmt || String;

function mergeInto(base, extra) {
  for (const k of Object.keys(extra || {})) {
    const v = extra[k];
    if (v && typeof v === 'object' && !Array.isArray(v) && base[k] && typeof base[k] === 'object') mergeInto(base[k], v);
    else if (k in base) base[k] = v;
  }
  return base;
}

function valueOf(item) {
  if (item.special === 'autostart') return AUTOSTART;
  if (item.special === 'animPreset') return matchAnimPreset(D.settings);
  return getPath(D[item.path], item.key, item.def);
}
const isChanged = (item) => item.def !== undefined && valueOf(item) !== item.def;
const isEnabled = (item) => (item.enabledIf ? !!item.enabledIf(D) : true);

// ---------------------------------------------------------------- 저장 (슬라이더를 끌 때 쏟아지지 않게 모아서 보낸다)
let pending = null, flushTimer = null;
function queuePatch(path, key, value) {
  pending = pending || { settings: {}, pomo: {}, water: {} };
  setPath(pending[path], key, value);
  clearTimeout(flushTimer);
  flushTimer = setTimeout(flushPatch, 140);
}
function flushPatch() {
  clearTimeout(flushTimer);
  flushTimer = null;
  if (!pending) return;
  const patch = pending;
  pending = null;
  for (const sec of Object.keys(patch)) if (!Object.keys(patch[sec]).length) delete patch[sec];
  const api = getApi();
  if (api && api.settings_patch && Object.keys(patch).length) api.settings_patch(patch);
}

function commit(item, value) {
  if (item.special === 'autostart') {
    AUTOSTART = !!value;
    updateAll();
    const api = getApi();
    if (api && api.set_autostart) {
      api.set_autostart(!!value).then((r) => { AUTOSTART = !!(r && r.enabled); updateAll(); if (r && r.status !== 'ok') toast(S('failed')); });
    }
    return;
  }
  if (item.special === 'animPreset') {
    const p = ANIM_PRESETS[value];
    if (!p) return;
    for (const k of Object.keys(p)) { D.settings[k] = p[k]; queuePatch('settings', k, p[k]); }
  } else {
    setPath(D[item.path], item.key, value);
    queuePatch(item.path, item.key, value);
  }
  applyLocal();
  updateAll();
  if (item.group === 'anim' || ['animSpeed', 'bounce', 'animOff', 'animPreset'].includes(item.id)) schedulePreview();
  if (item.key === 'lang') rebuild();
  if (/^hk|^hotkeysOn$/.test(item.key || '')) refreshHotkeys();
}

// ---------------------------------------------------------------- 설정 창 자신에게 적용 (언어, 애니메이션 변수)
function applyLocal() {
  const s = D.settings;
  LANG = normLang(s.lang);
  document.documentElement.lang = HTML_LANG[LANG];
  const cw = springCurves(100), cn = springCurves(s.bounce);        // 설정 창 자신은 기본 탄성, 미리보기(.demo)만 노치 설정을 따른다
  const root = document.documentElement;
  root.style.setProperty('--spring', cw.soft);
  root.style.setProperty('--spring-hard', cw.hard);
  root.style.setProperty('--nspring', cn.soft);
  root.style.setProperty('--nspring-hard', cn.hard);
  root.style.setProperty('--rate', String(rate()));
  root.style.setProperty('--nrate', String(nRate()));
  root.dataset.anim = animOff() ? 'off' : 'on';
  root.dataset.nanim = nAnimOff() ? 'off' : 'on';
}
// 설정 창 자신의 애니메이션(setAnim / setAnimSpeed)과 노치의 애니메이션(animOff / animSpeed)은 별개다.
const clampRate = (v) => Math.max(0.3, Math.min(3, (Number(v) || 100) / 100));
const rate = () => clampRate(D.settings.setAnimSpeed);
const animOff = () => D.settings.setAnim === false;
const nRate = () => clampRate(D.settings.animSpeed);            // 미리보기용: 노치 속도
const nAnimOff = () => !!D.settings.animOff;

// ---------------------------------------------------------------- 행 만들기
function makeRow(item, opts) {
  const row = document.createElement('div');
  row.className = 'row' + (item.indent ? ' indent' : '');
  row.dataset.id = item.id;
  const text = document.createElement('div');
  text.className = 'row-text';
  const title = document.createElement('div');
  title.className = 'row-title';
  text.appendChild(title);
  const desc = document.createElement('div');
  desc.className = 'row-desc';
  text.appendChild(desc);
  let pageTag = null;
  if (opts && opts.pageTitle) { pageTag = document.createElement('span'); pageTag.className = 'row-page'; text.appendChild(pageTag); }
  const ctl = document.createElement('div');
  ctl.className = 'row-ctl';
  row.append(text, ctl);

  let updateCtl = () => {};
  if (item.type === 'toggle') {
    const sw = document.createElement('button');
    sw.className = 'sw'; sw.setAttribute('role', 'switch');
    sw.addEventListener('click', () => commit(item, !valueOf(item)));
    ctl.appendChild(sw);
    updateCtl = () => sw.setAttribute('aria-checked', String(!!valueOf(item)));
    row.addEventListener('click', (e) => { if (e.target === row || e.target.closest('.row-text')) sw.click(); });
  } else if (item.type === 'slider') {
    const wrap = document.createElement('div');
    wrap.className = 'slider';
    const input = document.createElement('input');
    input.type = 'range'; input.min = item.min; input.max = item.max; input.step = item.step || 1;
    const out = document.createElement('output');
    wrap.append(input, out);
    ctl.appendChild(wrap);
    const paint = (v) => {
      input.style.setProperty('--fill', `${((v - item.min) / (item.max - item.min)) * 100}%`);
      out.textContent = fmtOf(item)(v);
    };
    input.addEventListener('input', () => { const v = Number(input.value); paint(v); commit(item, v); });
    updateCtl = () => { const v = Number(valueOf(item)); if (document.activeElement !== input || Number(input.value) !== v) input.value = v; paint(v); };
  } else if (item.type === 'seg') {
    const seg = document.createElement('div');
    seg.className = 'seg';
    const hl = document.createElement('i');
    hl.className = 'seg-hl';
    seg.appendChild(hl);
    const optionList = () => (item.optionsFrom === 'monitors' ? monitorOptions() : (item.options || []));
    const btns = optionList().map((o) => {
      const b = document.createElement('button');
      b.dataset.v = o.v;
      if (o.disabled) b.disabled = true;
      b.addEventListener('click', () => { if (!o.disabled) commit(item, o.v); });
      seg.appendChild(b);
      return { o, b };
    });
    ctl.appendChild(seg);
    updateCtl = () => {
      const cur = valueOf(item);
      btns.forEach(({ o, b }) => { b.textContent = tr(o.label); b.classList.toggle('on', o.v === cur); });
      placeSeg(seg);
    };
    row._seg = seg;
  } else if (item.type === 'text') {
    const inp = document.createElement('input');
    inp.type = 'text'; inp.className = 'txt' + (item.wide ? ' wide' : ''); inp.maxLength = 160; inp.spellcheck = false; inp.autocomplete = 'off';
    inp.addEventListener('input', () => commit(item, inp.value));
    ctl.appendChild(inp);
    updateCtl = () => { inp.placeholder = tr(item.placeholder); if (document.activeElement !== inp) inp.value = String(valueOf(item) || ''); };
  } else if (item.type === 'button') {
    const b = document.createElement('button');
    b.className = 'btn' + (item.danger ? ' danger' : '');
    b.addEventListener('click', () => runAction(item, b));
    ctl.appendChild(b);
    updateCtl = () => { if (!b._armed) b.textContent = tr(item.btn); };
    b._item = item;
  }

  const reset = document.createElement('button');
  reset.className = 'reset-dot'; reset.innerHTML = icon('reset'); reset.type = 'button';
  reset.addEventListener('click', (e) => { e.stopPropagation(); if (item.special === 'animPreset') commit(item, 'normal'); else commit(item, item.def); });
  ctl.appendChild(reset);

  const update = () => {
    title.textContent = tr(item.label);
    const d = item.descFn === 'monitors' ? monitorDesc() : (item.descFn === 'hotkey' ? hotkeyDesc(item) : tr(item.desc));
    desc.textContent = d;
    desc.style.display = d ? '' : 'none';
    if (pageTag) pageTag.textContent = opts.pageTitle;
    reset.title = S('reset');
    row.classList.toggle('disabled', !isEnabled(item));
    row.classList.toggle('changed', isChanged(item) || (item.special === 'animPreset' && valueOf(item) !== 'normal'));
    updateCtl();
  };
  return { item, el: row, update };
}

// 단축키 상태: 파이썬이 알려 주는 등록 결과를 풀어서 보여 준다
let HOTKEYS = { status: {}, combos: {} };
function hotkeyDesc(item) {
  const st = (HOTKEYS.status || {})[item.key];
  if (!st) return '';
  return S({ ok: 'hkOk', invalid: 'hkInvalid', conflict: 'hkConflict', off: 'hkOff' }[st] || 'hkOk');
}
let hkTimer = null;
function refreshHotkeys() {
  clearTimeout(hkTimer);
  hkTimer = setTimeout(async () => {
    const api = getApi();
    if (!api || !api.hotkeys_status) return;
    try { HOTKEYS = await api.hotkeys_status(); updateAll(); } catch (e) { /* 다음에 */ }
  }, 700);
}

// 모니터 선택지: '주 모니터' + 연결된 모니터들(식별 번호). 저장된 번호의 모니터가 지금 없으면 아무것도 강조되지 않는다.
function monitorOptions() {
  const opts = [{ v: 0, label: L('주 모니터', 'Primary') }];
  for (const m of MONITORS.monitors || []) opts.push({ v: m.number, label: { ko: `${m.number}번`, en: `#${m.number}`, zh: `${m.number} 号`, ja: `${m.number} 番` } });
  return opts;
}
function monitorDesc() {
  const ms = MONITORS.monitors || [];
  if (!ms.length) return tr(L('모니터 목록을 읽지 못했어요.', 'Could not read the monitor list.'));
  const list = ms.map((m) => `${m.number}: ${m.width}×${m.height}${m.primary ? tr(L(' (주)', ' (primary)')) : ''}`).join('   ');
  const wanted = Number(getPath(D.settings, 'monitor', 0));
  const missing = wanted > 0 && !ms.some((m) => m.number === wanted);
  const note = missing ? ` — ${lx(`${wanted}번 모니터가 연결돼 있지 않아 주 모니터에 띄웁니다.`, `monitor ${wanted} is not connected, using the primary one.`, `显示器 ${wanted} 未连接，将显示在主显示器上。`, `モニター ${wanted} が接続されていないため、メインモニターに表示します。`)}` : '';
  return tr(L('번호는 윈도우 설정 › 디스플레이 › 식별의 번호와 같아요. ', 'Numbers match Windows Settings › Display › Identify. ')) + (LANG === 'zh' || LANG === 'ja' ? ' ' : '') + list + note;
}

// 세그먼트 하이라이트를 선택된 버튼 위치로 (스프링으로 이동)
function placeSeg(seg) {
  const hl = seg.querySelector('.seg-hl');
  const on = seg.querySelector('button.on');
  if (!on || !on.offsetWidth) { seg.classList.add('none'); return; }
  seg.classList.remove('none');
  const moved = hl.style.transform && hl.style.transform !== `translateX(${on.offsetLeft}px)`;
  hl.style.width = `${on.offsetWidth}px`;
  hl.style.transform = `translateX(${on.offsetLeft}px)`;
  if (moved && typeof LG !== 'undefined') LG.stretch(hl, 'x', 520);
}

function updateAll() {
  for (const r of renderedRows) r.update();
}

// ---------------------------------------------------------------- 동작 버튼
function runAction(item, btn) {
  const api = getApi();
  const done = (msg) => { btn.classList.add('done'); setTimeout(() => btn.classList.remove('done'), 1200); if (msg) toast(msg); };
  switch (item.action) {
    case 'restart': toast(S('restarting')); setTimeout(() => api && api.restart_app && api.restart_app(), 250); break;
    case 'captureMode': if (api) api.capture_toggle().then((r) => done(r && r.off ? S('capOff') : (r && r.active ? S('capOn') : S('capNone')))); break;
    case 'recenter': if (api) api.recenter_window().then(() => done(S('centered'))); break;
    case 'clearCache': if (api) api.clear_lyrics_cache().then((r) => done(S('removed')(r ? r.removed : 0))); break;
    case 'testNotify': if (api) api.test_notify().then(() => done(S('sent'))); break;
    case 'clipClear': if (api) api.clip_clear().then(() => done(S('cleared'))); break;
    case 'calendarTest':
      if (api) { flushPatch(); setTimeout(() => api.calendar_test().then((r) => (r && r.status === 'ok' ? done(S('calOk')(r.count)) : toast(S('calFail')))), 250); }
      break;
    case 'exportSettings': if (api) { flushPatch(); setTimeout(() => api.export_settings().then((r) => { if (r && r.status === 'ok') done(S('exported')); else if (r && r.status !== 'cancelled') toast(S('failed')); }), 250); } break;
    case 'importSettings':
      if (api) api.import_settings().then((r) => {
        if (r && r.status === 'ok') { api.settings_get().then((res) => { loadData(res); rebuild(); toast(S('imported')(r.count)); }); }
        else if (r && r.status === 'error') toast(S('importFail'));
      });
      break;
    case 'openData': if (api) api.open_folder('data'); break;
    case 'openLog': if (api) api.open_folder('log'); break;
    case 'resetAll':
      if (!btn._armed) {                       // 두 번 눌러야 초기화 (실수 방지)
        btn._armed = true; btn.classList.add('armed'); btn.textContent = S('armed');
        setTimeout(() => { btn._armed = false; btn.classList.remove('armed'); btn.textContent = tr(item.btn); }, 3000);
        return;
      }
      btn._armed = false; btn.classList.remove('armed');
      if (api) {
        flushPatch();
        api.settings_reset().then(() => api.settings_get()).then((res) => { loadData(res); rebuild(); toast(S('resetDone')); });
      }
      break;
  }
}

// ---------------------------------------------------------------- 사용자 정의 컴포넌트
const COMPONENTS = {
  animPreview() {
    const wrap = document.createElement('div');
    wrap.className = 'preview';
    wrap.innerHTML = `<div class="stage"><div class="demo" data-s="0"><div class="d-mini"><i></i><span>Midnight City</span></div>
      <div class="d-full"><div class="art"></div><div class="meta"><b>Midnight City</b><span>M83</span><div class="ctrls"><i></i><i></i><i></i></div></div></div></div></div>
      <div class="side-note"><b></b><p></p><button class="btn" style="margin-top:12px"></button></div>`;
    const demo = wrap.querySelector('.demo');
    const note = wrap.querySelector('.side-note');
    const text = () => { note.querySelector('b').textContent = S('pvTitle'); note.querySelector('p').innerHTML = S('pvNote'); note.querySelector('.btn').textContent = S('pvPlay'); };
    text();
    let step = 0, timers = [];
    const set = (s) => { demo.dataset.s = s; demo.classList.remove('pop'); if (s === 2) { void demo.offsetWidth; demo.classList.add('pop'); } };
    const play = () => {
      timers.forEach(clearTimeout); timers = [];
      const k = nAnimOff() ? 0.001 : 1 / nRate();
      [[0, 1], [900, 2], [2500, 1], [3500, 0]].forEach(([t, s]) => timers.push(setTimeout(() => set(s), t * k + (nAnimOff() ? t * 0.35 : 0))));
    };
    wrap.querySelector('.btn').addEventListener('click', play);
    wrap.querySelector('.stage').addEventListener('click', () => { step = (Number(demo.dataset.s) + 1) % 3; set(step); });
    wrap._play = play; wrap._text = text;
    previewHandle = wrap;
    setTimeout(play, 350);
    return { el: wrap, update: text };
  },

  budsStatus() {
    const box = document.createElement('div');
    box.className = 'card';
    const stat = document.createElement('div');
    stat.className = 'bstat';
    stat.innerHTML = `<span class="bdot"></span><div><div class="bname"></div><div class="bsub"></div></div><div class="brings"></div>`;
    box.appendChild(stat);
    const tip = document.createElement('div');
    tip.className = 'tip';
    const render = (b) => {
      const dot = stat.querySelector('.bdot'), name = stat.querySelector('.bname'), sub = stat.querySelector('.bsub'), rings = stat.querySelector('.brings');
      tip.innerHTML = S('btTip');
      if (!b || !b.connected) {
        dot.classList.remove('on'); name.textContent = S('btNone'); sub.textContent = ''; rings.innerHTML = ''; return;
      }
      dot.classList.add('on');
      name.textContent = b.name || 'Earbuds';
      sub.textContent = `${S('btConnected')} · ${S('btControl')}: ${b.control ? S('on') : S('off')}`;
      const lab = { left: S('btLeft'), right: S('btRight'), case: S('btCase') };
      rings.innerHTML = ['left', 'right', 'case'].filter((k) => b.battery && b.battery[k] != null).map((k) => {
        const v = b.battery[k];
        const c = v < 20 ? 'var(--danger)' : v < 50 ? '#ffc25a' : 'var(--ok)';
        return `<div class="bring"><div class="wrap"><div class="ring" style="--v:${v};--c:${c}"></div><span class="val">${v}</span></div><span>${lab[k]}</span></div>`;
      }).join('');
    };
    let timer = null;
    const poll = async () => {
      const api = getApi();
      if (!api || !api.get_state) return;
      try { const s = await api.get_state(null); BUDS_CACHE.snap = s && s.buds; render(s && s.buds); } catch (e) { /* 다음 주기에 다시 */ }
    };
    render(BUDS_CACHE.snap);
    poll();
    timer = setInterval(() => { if (!document.body.contains(box)) { clearInterval(timer); return; } poll(); }, 2500);
    const frag = document.createDocumentFragment();
    frag.append(box, tip);
    return { el: frag, update: () => render(BUDS_CACHE.snap) || poll() };
  },

  about() {
    const box = document.createElement('div');
    box.className = 'card kv';
    const render = () => {
      const a = ABOUT || {};
      const yn = (v) => (v ? S('yes') : S('no'));
      const rows = [[S('aVersion'), a.version || '-'], [S('aPython'), a.python || '-'], [S('aWebview'), a.webview || '-'],
        [S('aMedia'), yn(a.smtc)], [S('aViz'), yn(a.viz)], [S('aBuds'), yn(a.buds)], [S('aData'), a.dataDir || '-']];
      box.innerHTML = rows.map(([k, v]) => `<div class="r"><span>${k}</span><span>${String(v).replace(/</g, '&lt;')}</span></div>`).join('');
    };
    render();
    return { el: box, update: render };
  },
};
// 이어버드 쪽 값은 몇 초마다 읽어 오므로, 화면이 다시 만들어질 때(탭 이동, 언어 바꿈) 마지막으로 알던 값을 바로 보여 주려고 기억해 둔다
const BUDS_CACHE = { snap: null, bands: null };
COMPONENTS.budsEq = function () {
  const box = document.createElement('div');
  box.className = 'card beq';
  box.innerHTML = '<div class="beq-head"><div class="row-title"></div><div class="row-desc"></div></div><div class="beq-grid"></div>'
    + '<div class="beq-custom"><div class="beq-chint"></div><div class="beq-bands"></div><div class="beq-axis"><span class="lo"></span><button type="button" class="beq-reset"></button><span class="hi"></span></div></div>'
    + '<div class="beq-msg"></div>';
  const title = box.querySelector('.row-title'), desc = box.querySelector('.row-desc'), grid = box.querySelector('.beq-grid'), msg = box.querySelector('.beq-msg');
  const chint = box.querySelector('.beq-chint'), bandsEl = box.querySelector('.beq-bands'), lo = box.querySelector('.lo'), hi = box.querySelector('.hi'), reset = box.querySelector('.beq-reset');
  const OPTS = [[0, 'eqNormal'], [1, 'eqBass'], [2, 'eqSoft'], [3, 'eqDynamic'], [4, 'eqClear'], [5, 'eqTreble'], [7, 'eqCustom']];       // [이어버드의 프리셋 번호, 문구]. 7 = 사용자 설정(9밴드)
  const N = 9;
  const FREQ = ['63', '125', '250', '500', '1k', '2k', '4k', '8k', '16k'];       // 밴드 중심 주파수(Hz). 삼성 Galaxy Buds 앱의 이퀄라이저 화면과 같다
  let snap = BUDS_CACHE.snap, cur = (snap && snap.eq != null) ? snap.eq : null, busy = false, pickedAt = 0, msgTimer = null, sendTimer = null, tableLoaded = !!BUDS_CACHE.bands, loading = false, editedAt = 0;
  let bands = BUDS_CACHE.bands ? BUDS_CACHE.bands.slice() : new Array(N).fill(0);
  const say = (text, bad) => { msg.textContent = text; msg.classList.toggle('bad', !!bad); clearTimeout(msgTimer); if (text) msgTimer = setTimeout(() => { msg.textContent = ''; }, 4000); };
  const usable = () => !!(snap && snap.connected && snap.control);
  const fmt = (v) => (v > 0 ? '+' + v : String(v));
  const renderBands = () => {
    const sliders = bandsEl.querySelectorAll('input');
    if (sliders.length !== N) {
      bandsEl.textContent = '';
      for (let i = 0; i < N; i++) {
        const w = document.createElement('label'); w.className = 'bnd';
        w.innerHTML = '<span class="bv"></span><input type="range" min="-10" max="10" step="1"><span class="bn"></span>';
        const inp = w.querySelector('input');
        inp.addEventListener('input', () => { editedAt = Date.now(); bands[i] = Number(inp.value); w.querySelector('.bv').textContent = fmt(bands[i]); scheduleSend(); });
        w.querySelector('.bn').textContent = FREQ[i];
        bandsEl.appendChild(w);
      }
    }
    bandsEl.querySelectorAll('.bnd').forEach((w, i) => {
      const inp = w.querySelector('input');
      if (document.activeElement !== inp) inp.value = String(bands[i]);
      inp.disabled = !usable();
      inp.title = FREQ[i] + ' Hz';
      w.querySelector('.bv').textContent = fmt(bands[i]);
    });
  };
  const render = () => {
    title.textContent = S('eqTitle'); desc.textContent = S('eqDesc');
    grid.textContent = '';
    for (const [v, k] of OPTS) {
      const b = document.createElement('button');
      b.type = 'button'; b.textContent = S(k);
      b.className = cur === v ? 'on' : '';
      b.disabled = !usable() || busy;
      b.addEventListener('click', () => pick(v));
      grid.appendChild(b);
    }
    box.classList.toggle('custom', cur === 7);
    chint.textContent = S('eqCustomHint'); lo.textContent = S('eqLow'); hi.textContent = S('eqHigh'); reset.textContent = S('eqReset');
    reset.disabled = !usable();
    renderBands();
    if (!usable()) { msg.textContent = S('eqNoDevice'); msg.classList.remove('bad'); }
    else if (msg.textContent === S('eqNoDevice')) msg.textContent = '';
  };
  const loadTable = async () => {
    const api = getApi();
    if (!api || !api.buds_eq_table || loading || !usable()) return;
    loading = true;
    let r; try { r = await api.buds_eq_table(); } catch (e) { r = null; }
    loading = false;
    if (r && r.status === 'ok' && Array.isArray(r.custom) && r.custom.length === N) { bands = r.custom.slice(); BUDS_CACHE.bands = bands.slice(); tableLoaded = true; render(); }
  };
  const fail = (res) => say(res && res.code === 'in_use' ? S('eqInUse') : S('eqFailed'), true);
  const pick = async (v) => {
    const api = getApi();
    if (!api || !api.buds_set_eq || busy || v === cur) return;
    const prev = cur;
    busy = true; cur = v; pickedAt = Date.now(); render();
    let res; try { res = await api.buds_set_eq(v); } catch (e) { res = { status: 'error' }; }
    busy = false;
    if (res && res.status === 'ok') { say(S('eqApplied'), false); if (v === 7 && !tableLoaded) loadTable(); }
    else { cur = prev; fail(res); }
    render();
  };
  const sendBands = async () => {
    const api = getApi();
    if (!api || !api.buds_set_custom_eq || !usable()) return;
    if (busy) { scheduleSend(); return; }
    busy = true; pickedAt = Date.now(); cur = 7; render();
    let res; try { res = await api.buds_set_custom_eq(bands.slice()); } catch (e) { res = { status: 'error' }; }
    busy = false;
    if (res && res.status === 'ok') { BUDS_CACHE.bands = bands.slice(); say(S('eqApplied'), false); } else fail(res);
    render();
  };
  const scheduleSend = () => { clearTimeout(sendTimer); sendTimer = setTimeout(sendBands, 350); };       // 슬라이더를 움직이는 동안에는 보내지 않고, 멈추면 한 번에 보낸다
  reset.addEventListener('click', () => { bands = new Array(N).fill(0); renderBands(); sendBands(); });
  const poll = async () => {
    const api = getApi();
    if (!api || !api.get_state) return;
    try {
      const s = await api.get_state(null);
      snap = s && s.buds; BUDS_CACHE.snap = snap;
      if (snap && Array.isArray(snap.eq_custom) && snap.eq_custom.length === N && !busy && Date.now() - editedAt > 3000) { bands = snap.eq_custom.slice(); BUDS_CACHE.bands = bands.slice(); tableLoaded = true; }       // 파이썬이 기억해 둔 사용자 곡선
      if (snap && snap.eq != null && !busy && Date.now() - pickedAt > 4000) cur = snap.eq;      // 이어버드가 알려 주는 현재 값 (삼성 앱에서 바꾼 것도 따라간다)
      if (usable() && !tableLoaded) loadTable();
      render();
    } catch (e) { /* 다음 주기에 다시 */ }
  };
  render();
  poll();
  const timer = setInterval(() => { if (!document.body.contains(box)) { clearInterval(timer); return; } poll(); }, 2500);
  return { el: box, update: render };
};

COMPONENTS.budsAdvanced = function () {
  const box = document.createElement('div');
  box.className = 'card badv';
  box.innerHTML = '<div class="badv-row" data-k="game"><div class="badv-t"><div class="row-title"></div><div class="row-desc"></div></div><div class="sw" role="switch"></div></div>'
    + '<div class="badv-row" data-k="nc_one"><div class="badv-t"><div class="row-title"></div><div class="row-desc"></div></div><div class="sw" role="switch"></div></div>'
    + '<div class="beq-msg"></div>';
  const msg = box.querySelector('.beq-msg');
  const ROWS = { game: ['advGame', 'advGameDesc', 'buds_set_game_mode'], nc_one: ['advOne', 'advOneDesc', 'buds_set_nc_one'] };
  let snap = BUDS_CACHE.snap ? Object.assign({}, BUDS_CACHE.snap) : null, busy = false, msgTimer = null;
  const say = (text, bad) => { msg.textContent = text; msg.classList.toggle('bad', !!bad); clearTimeout(msgTimer); if (text) msgTimer = setTimeout(() => { msg.textContent = ''; }, 4000); };
  const render = () => {
    const ok = !!(snap && snap.connected && snap.control);
    for (const row of box.querySelectorAll('.badv-row')) {
      const k = row.dataset.k, [tk, dk] = ROWS[k];
      const known = ok && typeof snap[k] === 'boolean';
      row.querySelector('.row-title').textContent = S(tk);
      row.querySelector('.row-desc').textContent = ok && !known ? S(dk) + ' ' + S('advUnknown') : S(dk);
      const sw = row.querySelector('.sw');
      sw.setAttribute('aria-checked', String(known && snap[k]));
      sw.classList.toggle('disabled', !known || busy);
    }
    if (!ok) { msg.textContent = S('eqNoDevice'); msg.classList.remove('bad'); }
    else if (msg.textContent === S('eqNoDevice')) msg.textContent = '';
  };
  const toggle = async (k) => {
    const api = getApi();
    const fn = ROWS[k][2];
    if (!api || !api[fn] || busy || !snap || typeof snap[k] !== 'boolean') return;
    const prev = snap[k];
    busy = true; snap[k] = !prev; render();
    let res; try { res = await api[fn](!prev); } catch (e) { res = { status: 'error' }; }
    busy = false;
    if (res && res.status === 'ok') say(S('eqApplied'), false);
    else { snap[k] = prev; say(res && res.code === 'in_use' ? S('eqInUse') : S('eqFailed'), true); }
    render();
  };
  for (const row of box.querySelectorAll('.badv-row')) row.querySelector('.sw').addEventListener('click', () => toggle(row.dataset.k));
  const poll = async () => {
    const api = getApi();
    if (!api || !api.get_state || busy) return;
    try { const s = await api.get_state(null); snap = s && s.buds; BUDS_CACHE.snap = snap; render(); } catch (e) { /* 다음 주기에 다시 */ }
  };
  render();
  poll();
  const timer = setInterval(() => { if (!document.body.contains(box)) { clearInterval(timer); return; } poll(); }, 2500);
  return { el: box, update: render };
};

const MIXER_CACHE = { list: null };       // 화면이 다시 만들어져도(언어 바꿈, 탭 이동) 마지막으로 읽은 믹서 값을 바로 보여 준다
COMPONENTS.mixer = function () {
  const box = document.createElement('div');
  box.className = 'card mixer';
  const note = document.createElement('div');
  note.className = 'row-desc mixnote';
  const rows = new Map();                       // id -> { row, slider, out, mute }
  let busy = 0;                                 // 사용자가 슬라이더를 만지는 동안은 읽어 온 값으로 덮어쓰지 않는다
  const label = (a) => (a.id === 'master' ? tr(L('마스터 볼륨', 'Master volume')) : (a.system ? tr(L('시스템 소리', 'System sounds')) : a.name));
  const make = (a) => {
    const row = document.createElement('div');
    row.className = 'mrow' + (a.id === 'master' ? ' master' : '');
    row.innerHTML = '<span class="mname"></span><div class="slider"><input type="range" min="0" max="100" step="1"><output></output></div><button class="mmute" type="button"></button>';
    const slider = row.querySelector('input'), out = row.querySelector('output'), mute = row.querySelector('.mmute');
    const paint = (v) => { slider.style.setProperty('--fill', v + '%'); out.textContent = v + '%'; };
    let t = null;
    slider.addEventListener('input', () => {
      const v = Number(slider.value); paint(v); busy = Date.now() + 1200;
      clearTimeout(t); t = setTimeout(() => { const api = getApi(); if (api) api.mixer_set(a.id, v / 100, null); }, 40);
    });
    mute.addEventListener('click', () => {
      const m = !mute.classList.contains('on'); mute.classList.toggle('on', m);
      const api = getApi(); if (api) api.mixer_set(a.id, null, m);
    });
    box.appendChild(row);
    const r = { row, slider, out, mute, paint };
    rows.set(a.id, r);
    return r;
  };
  const apply = (a) => {
    const r = rows.get(a.id) || make(a);
    r.row.querySelector('.mname').textContent = label(a);
    r.row.classList.toggle('idle', a.id !== 'master' && !a.active);
    r.mute.classList.toggle('on', !!a.muted);
    r.mute.innerHTML = `<svg viewBox="0 0 24 24">${a.muted ? '<path d="M4 9.5v5h3.5L12 18.5v-13L7.5 9.5z"/><path d="M16 9.5l5 5M21 9.5l-5 5"/>' : ICONS.volume}</svg>`;
    if (Date.now() > busy) { const v = Math.round((a.volume ?? 1) * 100); r.slider.value = v; r.paint(v); }
  };
  const refresh = async () => {
    const api = getApi();
    if (!api || !api.mixer_get) return;
    let d; try { d = await api.mixer_get(); } catch (e) { return; }
    if (!d) return;
    const list = [];
    if (d.master) list.push({ id: 'master', volume: d.master.volume, muted: d.master.muted, active: true });
    for (const a of d.apps || []) list.push(a);
    MIXER_CACHE.list = list;
    show(list);
  };
  const show = (list) => {
    const keep = new Set(list.map((a) => a.id));
    for (const [id, r] of rows) if (!keep.has(id)) { r.row.remove(); rows.delete(id); }
    list.forEach((a, i) => { apply(a); const r = rows.get(a.id); if (box.children[i + 1] !== r.row) box.insertBefore(r.row, box.children[i + 1] || null); });
    note.textContent = list.length > 1 ? '' : tr(L('지금 소리를 내는 앱이 없어요.', 'No app is playing sound right now.'));
  };
  box.appendChild(note);
  if (MIXER_CACHE.list) show(MIXER_CACHE.list);
  refresh();
  const timer = setInterval(() => { if (!document.body.contains(box)) { clearInterval(timer); return; } refresh(); }, 1500);
  return { el: box, update: () => { rows.forEach((r, id) => { /* 언어가 바뀌면 이름을 다시 그린다 */ }); refresh(); } };
};
const TAB_META = {
  music: ['music', { ko: '음악', en: 'Music' }], pomo: ['target', { ko: '집중 (포모도로)', en: 'Focus (Pomodoro)' }], timer: ['timer', { ko: '타이머·스톱워치', en: 'Timer & stopwatch' }],
  water: ['drop', { ko: '물 마시기', en: 'Water' }], shelf: ['folder', { ko: '파일 선반', en: 'File shelf' }], todo: ['checklist', { ko: '할 일', en: 'To-do' }],
  clip: ['clipboard', { ko: '클립보드', en: 'Clipboard' }], agenda: ['calendar', { ko: '일정', en: 'Agenda' }], launcher: ['launch', { ko: '바로가기', en: 'Shortcuts' }],
  plugins: ['plug', { ko: '플러그인', en: 'Plugins' }], buds: ['headphones', { ko: '이어버드', en: 'Earbuds' }],
};
const TAB_NOTE = { clip: 'tabNote_clip', agenda: 'tabNote_agenda', buds: 'tabNote_buds', plugins: 'tabNote_plugins' };

// 윈도우 알림을 보낸 적 있는 앱 목록: 앱마다 켜고 끈다(끄면 그 앱의 알림은 동그라미로 알리지 않는다). 설정 'winNotifyIgnore'(쉼표 목록)를 같이 쓴다.
const _wnList = (s) => String(s || '').split(',').map((x) => x.trim()).filter(Boolean);
const _wnIgnored = (list, name) => _wnList(list).some((p) => name.toLowerCase().includes(p.toLowerCase()));
const _wnRemove = (list, name) => _wnList(list).filter((p) => !name.toLowerCase().includes(p.toLowerCase())).join(', ');      // 이 앱을 무시하게 만들던 항목을 지운다
const _wnAdd = (list, name) => _wnList(list).concat(name).join(', ');
const WINAPPS_CACHE = { apps: [] };       // 화면이 다시 만들어져도(언어 바꿈 등) 목록이 비어 보이지 않게
COMPONENTS.winApps = function () {
  const box = document.createElement('div');
  box.className = 'winapps';
  box.innerHTML = '<div class="wa-head"><div class="row-title"></div><div class="row-desc"></div></div><div class="wa-list"></div>';
  const title = box.querySelector('.row-title'), desc = box.querySelector('.row-desc'), list = box.querySelector('.wa-list');
  let apps = WINAPPS_CACHE.apps;
  const render = () => {
    title.textContent = tr(L('알림을 보낸 앱', 'Apps that sent notifications'));
    desc.textContent = tr(L('켜 둔 앱의 알림만 동그라미로 알려요. 끄면 그 앱의 알림은 알리지 않아요. 알림을 한 번이라도 보낸 앱이 여기에 나타나요.', 'Only apps that are on show the circle. Turn an app off to stop its notifications from showing. An app appears here once it has sent a notification.'));
    list.textContent = '';
    if (!apps.length) {
      const e = document.createElement('div'); e.className = 'row-desc wa-empty'; e.textContent = tr(L('아직 알림을 보낸 앱이 없어요.', 'No app has sent a notification yet.')); list.appendChild(e);
    }
    for (const a of apps) {
      const ign = _wnIgnored(D.settings.winNotifyIgnore, a.name);
      const row = document.createElement('div');
      row.className = 'wa-row' + (ign ? ' off' : '');
      row.innerHTML = '<span class="wa-name"></span><span class="wa-n"></span><div class="sw" role="switch"></div>';
      row.querySelector('.wa-name').textContent = a.name;
      row.querySelector('.wa-n').textContent = a.count > 0 ? lx(`${a.count}건`, `${a.count}×`, `${a.count} 条`, `${a.count} 件`) : '';
      const sw = row.querySelector('.sw'); sw.setAttribute('aria-checked', String(!ign));
      sw.addEventListener('click', () => {
        const cur = D.settings.winNotifyIgnore || '';
        const next = _wnIgnored(cur, a.name) ? _wnRemove(cur, a.name) : _wnAdd(cur, a.name);
        D.settings.winNotifyIgnore = next; queuePatch('settings', 'winNotifyIgnore', next);
        updateAll();
      });
      list.appendChild(row);
    }
  };
  const refresh = async () => {
    const api = getApi();
    if (!api || !api.winnotif_apps) return;
    let d; try { d = await api.winnotif_apps(); } catch (e) { return; }
    if (!d) return;
    apps = d.apps || []; WINAPPS_CACHE.apps = apps;
    render();
  };
  refresh();
  const timer = setInterval(() => { if (!document.body.contains(box)) { clearInterval(timer); return; } refresh(); }, 3000);
  return { el: box, update: () => { box.classList.toggle('disabled', !D.settings.winNotify); render(); } };
};

COMPONENTS.tabs = function () {
  const box = document.createElement('div');
  box.className = 'card tabs';
  const list = document.createElement('div');
  const foot = document.createElement('div');
  foot.className = 'tabfoot';
  box.append(list, foot);
  const render = () => {
    const order = parseTabOrder(D.settings.tabOrder), hidden = parseTabHidden(D.settings.tabHidden);
    const visibleCount = order.filter((id) => !hidden.includes(id)).length;
    list.textContent = '';
    order.forEach((id, i) => {
      const [iconName, name] = TAB_META[id] || ['star', { ko: id, en: id }];
      const row = document.createElement('div');
      row.className = 'tabrow' + (hidden.includes(id) ? ' off' : '');
      row.dataset.id = id;
      row.innerHTML = '<span class="te"></span><div class="tn"><b></b><small></small></div><div class="tmv"><button class="up" type="button">▲</button><button class="dn" type="button">▼</button></div><button class="sw" role="switch" type="button"></button>';
      row.querySelector('.te').innerHTML = uiIconHtml(iconName, tr(name));
      row.querySelector('b').textContent = tr(name);
      row.querySelector('small').textContent = TAB_NOTE[id] ? S(TAB_NOTE[id]) : '';
      const up = row.querySelector('.up'), dn = row.querySelector('.dn'), sw = row.querySelector('.sw');
      up.disabled = i === 0; dn.disabled = i === order.length - 1;
      sw.setAttribute('aria-checked', String(!hidden.includes(id)));
      up.addEventListener('click', () => setTabs(moveTab(D.settings.tabOrder, id, -1), D.settings.tabHidden, id));
      dn.addEventListener('click', () => setTabs(moveTab(D.settings.tabOrder, id, 1), D.settings.tabHidden, id));
      sw.addEventListener('click', () => {
        if (!hidden.includes(id) && visibleCount <= 1) { toast(S('tabLast')); return; }
        setTabs(D.settings.tabOrder, toggleTabHidden(D.settings.tabHidden, id), id);
      });
      list.appendChild(row);
    });
    foot.innerHTML = '';
    const hint = document.createElement('div'); hint.className = 'row-desc'; hint.textContent = S('tabsHint');
    const reset = document.createElement('button'); reset.className = 'btn'; reset.textContent = S('tabsReset');
    reset.addEventListener('click', () => setTabs(DEFAULT_TAB_ORDER, '', null));
    foot.append(hint, reset);
  };
  const setTabs = (order, hidden, flashId) => {
    D.settings.tabOrder = order; D.settings.tabHidden = hidden;
    queuePatch('settings', 'tabOrder', order); queuePatch('settings', 'tabHidden', hidden);
    render();
    if (flashId) { const r = list.querySelector(`.tabrow[data-id="${flashId}"]`); if (r && r.animate && !animOff()) r.animate([{ background: 'rgba(91,140,255,.35)' }, { background: 'transparent' }], { duration: 700 }); }
  };
  render();
  return { el: box, update: render };
};

COMPONENTS.plugins = function () {
  const box = document.createElement('div');
  box.className = 'plugwrap';
  let timer = null;
  const live = {};                                   // 플러그인 id -> 상태 문구
  const enabledIds = () => String(D.settings.pluginsEnabled || '').split(',').map((x) => x.trim()).filter(Boolean);
  const setEnabled = (ids, flashId) => { D.settings.pluginsEnabled = ids.join(','); queuePatch('settings', 'pluginsEnabled', D.settings.pluginsEnabled); render(flashId); };
  const mk = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };
  const chevron = (dir) => `<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="${dir < 0 ? 'M15 5l-7 7 7 7' : 'M9 5l7 7-7 7'}"/></svg>`;

  const cardFor = (p, added, idx, total) => {
    const c = mk('div', 'pcard' + (added ? ' added' : ''));
    c.dataset.id = p.id;
    const top = mk('div', 'ptop');
    const orb = mk('span', 'porb'); orb.innerHTML = uiIconHtml(p.icon, tr(p.name));
    const nm = mk('div', 'pname'); nm.appendChild(mk('span', null, tr(p.name)));
    if (!p.builtin) nm.appendChild(mk('span', 'pbadge', S('pluginUser')));
    if (added) nm.appendChild(mk('span', 'pbadge', S('pluginInUse')));
    top.append(orb, nm);
    c.append(top, mk('div', 'pdesc', tr(p.desc) || ''));
    const acts = mk('div', 'pacts');
    const shown = p.actions.slice(0, 7);
    for (const a of shown) { const i = mk('span', 'ai'); i.title = tr(a.label); i.innerHTML = uiIconHtml(a.icon, tr(a.label), 15); acts.appendChild(i); }
    if (p.actions.length > shown.length) acts.appendChild(mk('span', 'more', S('pluginMore')(p.actions.length - shown.length)));
    c.appendChild(acts);
    if (added) {
      const st = mk('div', 'pstat'); st.appendChild(mk('i', 'dot')); st.appendChild(mk('span', null, ''));
      const cur = live[p.id];
      if (cur) { st.classList.add('live'); st.lastChild.textContent = cur; } else st.lastChild.textContent = S('pluginActions')(p.actions.length);
      c.appendChild(st);
    }
    const ctl = mk('div', 'pctl');
    if (added) {
      const l = mk('button', 'pmv'); l.type = 'button'; l.innerHTML = chevron(-1); l.title = S('pluginMoveL'); l.disabled = idx === 0;
      const r = mk('button', 'pmv'); r.type = 'button'; r.innerHTML = chevron(1); r.title = S('pluginMoveR'); r.disabled = idx === total - 1;
      const swap = (d) => { const cur = enabledIds(); const i = cur.indexOf(p.id); const j = i + d; if (i < 0 || j < 0 || j >= cur.length) return; [cur[i], cur[j]] = [cur[j], cur[i]]; setEnabled(cur, p.id); };
      l.addEventListener('click', () => swap(-1)); r.addEventListener('click', () => swap(1));
      ctl.append(l, r, mk('span', 'grow'));
    } else ctl.appendChild(mk('span', 'grow'));
    const b = mk('button', 'btn' + (added ? '' : ' primary'), added ? S('pluginRemove') : S('pluginAdd'));
    b.type = 'button';
    b.addEventListener('click', () => { const cur = enabledIds(); setEnabled(added ? cur.filter((x) => x !== p.id) : cur.concat(p.id), added ? null : p.id); });
    ctl.appendChild(b);
    c.appendChild(ctl);
    return c;
  };

  const refreshLive = async () => {
    const api = getApi();
    if (!box.isConnected || !api || !api.plugin_status) return;
    for (const id of enabledIds()) {
      let r = null;
      try { r = await api.plugin_status(id); } catch (e) { r = null; }
      const txt = r ? tr(r) : '';
      live[id] = txt;
      const card = box.querySelector(`.pcard[data-id="${id}"] .pstat`);
      if (card) { card.classList.toggle('live', !!txt); if (txt) card.lastChild.textContent = txt; }
    }
  };

  const render = (flashId) => {
    clearInterval(timer);
    box.textContent = '';
    const ids = enabledIds();
    const byId = (id) => CATALOG.find((p) => p.id === id);
    const added = ids.map(byId).filter(Boolean), avail = CATALOG.filter((p) => !ids.includes(p.id));

    const hero = mk('div', 'phero lg-host');
    hero.innerHTML = '<i class="hero-orb"></i><span class="hero-glyph"></span><div class="hero-text"><h2></h2><p></p></div><span class="hero-count"></span>';
    hero.querySelector('.hero-glyph').innerHTML = uiIconSvg('plug', 30);
    hero.querySelector('h2').textContent = S('pluginHeroT');
    hero.querySelector('p').textContent = S('pluginHeroD');
    hero.querySelector('.hero-count').textContent = S('pluginsCount')(added.length);
    box.appendChild(hero);

    const sec1 = mk('div');
    const t1 = mk('div', 'psec-title', S('pluginsAdded'));
    sec1.appendChild(t1);
    if (added.length) {
      const g = mk('div', 'pgrid2');
      added.forEach((p, i) => g.appendChild(cardFor(p, true, i, added.length)));
      sec1.appendChild(g);
    } else {
      const e = mk('div', 'pempty'); const o = mk('span', 'porb'); o.innerHTML = uiIconSvg('plug', 24);
      e.append(o, mk('span', null, S('pluginsNone')));
      sec1.appendChild(e);
    }
    box.appendChild(sec1);

    const sec2 = mk('div');
    sec2.appendChild(mk('div', 'psec-title', S('pluginsAvailable')));
    const g2 = mk('div', 'pgrid2');
    avail.forEach((p) => g2.appendChild(cardFor(p, false)));
    const create = mk('div', 'pcreate');
    const co = mk('span', 'porb'); co.innerHTML = uiIconSvg('tool', 24);
    const ct = mk('div', 'ct'); ct.append(mk('b', null, S('pluginCreateT')), mk('p', null, S('pluginCreateD')));
    const cb = mk('div', 'cb');
    const ex = mk('button', 'btn primary', S('pluginInstallEx')); ex.type = 'button';
    ex.addEventListener('click', async () => {
      const api = getApi(); if (!api || !api.plugin_install_example) return;
      const r = await api.plugin_install_example();
      if (!r || r.status !== 'ok') return;
      toast(r.installed ? S('pluginExDone') : S('pluginExHave'));
      const res = await api.settings_get(); CATALOG = res.plugins || CATALOG; render(r.installed ? 'mytools' : null);
    });
    const open = mk('button', 'btn', S('pluginFolder')); open.type = 'button';
    open.addEventListener('click', () => { const api = getApi(); if (api) api.open_plugin_folder(); });
    const reload = mk('button', 'btn', S('pluginReload')); reload.type = 'button';
    reload.addEventListener('click', async () => { const api = getApi(); if (!api) return; await api.plugins_reload(); const res = await api.settings_get(); CATALOG = res.plugins || []; render(); });
    cb.append(ex, open, reload);
    create.append(co, ct, cb);
    g2.appendChild(create);
    sec2.appendChild(g2);
    box.appendChild(sec2);

    applyGlass(box);
    if (flashId && !animOff()) { const c = box.querySelector(`.pcard[data-id="${flashId}"]`); if (c) c.classList.add('flash'); }
    if (added.length) { setTimeout(refreshLive, 60); timer = setInterval(refreshLive, 4000); }
  };
  render();
  return { el: box, update: () => render() };
};

// 아이콘 선택 팝업: 버튼 아래에 아이콘 격자를 띄우고, 고르면 닫는다 (바깥을 누르거나 Esc 로도 닫힘)
function openIconPicker(anchor, current, onPick) {
  document.querySelectorAll('.icopick').forEach((e) => e.remove());
  const pop = document.createElement('div');
  pop.className = 'icopick';
  for (const name of UI_ICON_NAMES) {
    const b = document.createElement('button');
    b.type = 'button'; b.title = name; b.innerHTML = uiIconSvg(name, 18);
    if (name === current) b.classList.add('on');
    b.addEventListener('click', (e) => { e.stopPropagation(); onPick(name); close(); });
    pop.appendChild(b);
  }
  const close = () => { pop.remove(); document.removeEventListener('mousedown', away, true); document.removeEventListener('keydown', esc, true); };
  const away = (e) => { if (!pop.contains(e.target) && e.target !== anchor) close(); };
  const esc = (e) => { if (e.key === 'Escape') { e.stopPropagation(); close(); } };
  document.body.appendChild(pop);
  const r = anchor.getBoundingClientRect();
  pop.style.left = `${Math.max(8, Math.min(window.innerWidth - 300, r.left))}px`;
  pop.style.top = `${Math.min(window.innerHeight - pop.offsetHeight - 8, r.bottom + 6)}px`;
  setTimeout(() => { document.addEventListener('mousedown', away, true); document.addEventListener('keydown', esc, true); }, 0);
}

COMPONENTS.launcher = function () {
  const box = document.createElement('div');
  box.className = 'card lnedit';
  let items = LAUNCHER.map((x) => Object.assign({}, x));
  let saveTimer = null;
  const save = () => {
    clearTimeout(saveTimer);
    saveTimer = setTimeout(async () => {
      const api = getApi(); if (!api) return;
      const r = await api.launcher_set(items);
      if (r && r.status === 'ok') { LAUNCHER = r.items; }
    }, 500);
  };
  const render = () => {
    box.textContent = '';
    const rows = document.createElement('div');
    if (!items.length) { const e = document.createElement('div'); e.className = 'row-desc lnempty'; e.textContent = S('lnEmpty'); rows.appendChild(e); }
    items.forEach((it, idx) => {
      const row = document.createElement('div');
      row.className = 'lnrow';
      row.innerHTML = '<button class="icb" type="button"></button><input class="nm" maxlength="30"><input class="tg" maxlength="500"><input class="ag" maxlength="300"><button class="br" type="button"></button><button class="rm" type="button"></button>';
      const f = { nm: row.querySelector('.nm'), tg: row.querySelector('.tg'), ag: row.querySelector('.ag') };
      f.nm.value = it.name || ''; f.tg.value = it.target || ''; f.ag.value = it.args || '';
      f.nm.placeholder = S('lnName'); f.tg.placeholder = S('lnTarget'); f.ag.placeholder = S('lnArgs');
      for (const [k, el] of [['name', f.nm], ['target', f.tg], ['args', f.ag]]) el.addEventListener('input', () => { it[k] = el.value; save(); });
      const icb = row.querySelector('.icb');
      icb.title = S('lnIcon');
      icb.innerHTML = uiIconHtml(it.icon, it.name);
      icb.addEventListener('click', (e) => { e.stopPropagation(); openIconPicker(icb, it.icon, (name) => { it.icon = name; icb.innerHTML = uiIconHtml(it.icon, it.name); save(); }); });
      row.querySelector('.br').innerHTML = uiIconSvg('folder', 16);
      row.querySelector('.rm').innerHTML = uiIconSvg('close', 14);
      row.querySelector('.br').title = S('lnBrowse');
      row.querySelector('.br').addEventListener('click', async () => { const api = getApi(); if (!api) return; const r = await api.pick_launcher_target(); if (r && r.status === 'ok') { it.target = r.path; if (!it.name) it.name = r.path.split(/[\\/]/).pop().replace(/\.[^.]+$/, ''); save(); render(); } });
      row.querySelector('.rm').addEventListener('click', () => { items.splice(idx, 1); save(); render(); });
      rows.appendChild(row);
    });
    const add = document.createElement('button'); add.className = 'btn'; add.textContent = '+ ' + S('lnAdd');
    add.addEventListener('click', () => { if (items.length >= 24) { toast(S('lnFull')); return; } items.push({ id: 's' + Date.now().toString(36), icon: '', name: '', target: '', args: '' }); render(); const last = box.querySelectorAll('.lnrow .nm'); if (last.length) last[last.length - 1].focus(); });
    const pres = document.createElement('div'); pres.className = 'lnpresets';
    const lab = document.createElement('span'); lab.className = 'row-desc'; lab.textContent = S('lnPresets'); pres.appendChild(lab);
    for (const p of PRESETS) {
      const b = document.createElement('button'); b.className = 'pchipS'; b.innerHTML = `<span class="pi">${uiIconHtml(p.icon, p.name, 15)}</span><span></span>`; b.lastChild.textContent = p.name;
      b.addEventListener('click', () => { if (items.length >= 24) { toast(S('lnFull')); return; } items.push({ id: 's' + Date.now().toString(36) + items.length, icon: p.icon, name: p.name, target: p.target, args: '' }); save(); render(); });
      pres.appendChild(b);
    }
    const foot = document.createElement('div'); foot.className = 'tabfoot'; foot.append(add);
    box.append(rows, foot, pres);
  };
  render();
  return { el: box, update: () => { items = LAUNCHER.map((x) => Object.assign({}, x)); render(); } };
};
let previewHandle = null;
let previewTimer = null;
function schedulePreview() {
  clearTimeout(previewTimer);
  previewTimer = setTimeout(() => { if (previewHandle && document.body.contains(previewHandle)) previewHandle._play(); }, 380);
}

// ---------------------------------------------------------------- 페이지 그리기
function buildSections(sections, token) {
  const frag = document.createDocumentFragment();
  for (const sec of sections) {
    const block = document.createElement('div');
    if (sec.title) { const h = document.createElement('div'); h.className = 'sec-title'; h.textContent = tr(sec.title); block.appendChild(h); }
    const compOnly = sec.items.filter((it) => it.type !== 'hidden').every((it) => it.type === 'custom');   // 컴포넌트만 있는 구역은 바깥 카드 없이 컴포넌트가 자기 모양을 정한다
    const card = compOnly ? null : document.createElement('div');
    if (card) card.className = 'card';
    for (const it of sec.items) {
      if (it.type === 'hidden') continue;
      if (it.type === 'custom') {
        const c = COMPONENTS[it.component]();
        const holder = compOnly ? block : card;
        const el = c.el;
        if (it.component === 'animPreview') { const cd = document.createElement('div'); cd.className = 'card'; cd.appendChild(el); holder.appendChild(cd); }
        else holder.appendChild(el);
        renderedRows.push({ item: it, el, update: c.update });
      } else {
        const r = makeRow(it);
        card.appendChild(r.el);
        renderedRows.push(r);
      }
    }
    if (card) block.appendChild(card);
    frag.appendChild(block);
  }
  return frag;
}

function showPage(id, opts) {
  const token = ++pageToken;
  const pageEl = $('page');
  const old = Array.from(pageEl.children);
  const dir = opts && opts.dir || 1;
  const build = () => {
    if (token !== pageToken) return;
    pageEl.innerHTML = '';
    renderedRows = [];
    let frag;
    if (id === '__search') frag = buildSearch(opts.query);
    else frag = buildSections(SETTINGS_PAGES.find((p) => p.id === id).sections, token);
    pageEl.appendChild(frag);
    updateAll();
    requestAnimationFrame(() => { document.querySelectorAll('.seg').forEach(placeSeg); });
    $('scroll').scrollTop = 0;
    if (!animOff() && pageEl.animate) {
      Array.from(pageEl.children).forEach((c, i) => c.animate(
        [{ opacity: 0, transform: `translateY(${14 * dir}px) scale(0.985)` }, { opacity: 1, transform: 'none' }],
        { duration: 520 / rate(), delay: (40 + i * 55) / rate(), easing: getComputedStyle(document.documentElement).getPropertyValue('--spring-hard') || 'ease-out', fill: 'backwards' }));
    }
  };
  if (!animOff() && old.length && pageEl.animate) {
    old.forEach((c) => c.animate([{ opacity: 1 }, { opacity: 0, transform: `translateY(${-8 * dir}px)` }], { duration: 140 / rate(), easing: 'ease-in', fill: 'forwards' }));
    setTimeout(build, 130 / rate());
  } else build();
}

function matches(item, q) {
  const hay = [tr(item.label), item.label && item.label.ko, item.label && item.label.en, tr(item.desc), item.desc && item.desc.ko, item.desc && item.desc.en]
    .filter(Boolean).join(' ').toLowerCase();
  return q.split(/\s+/).every((w) => hay.includes(w));
}

function buildSearch(query) {
  const q = query.trim().toLowerCase();
  const frag = document.createDocumentFragment();
  let any = false;
  for (const page of SETTINGS_PAGES) {
    const hits = [];
    for (const sec of page.sections) for (const it of sec.items) if (it.type !== 'custom' && it.type !== 'hidden' && matches(it, q)) hits.push(it);
    if (!hits.length) continue;
    any = true;
    const block = document.createElement('div');
    const h = document.createElement('div'); h.className = 'sec-title'; h.textContent = tr(page.title);
    const card = document.createElement('div'); card.className = 'card';
    for (const it of hits) { const r = makeRow(it); card.appendChild(r.el); renderedRows.push(r); }
    block.append(h, card);
    frag.appendChild(block);
  }
  if (!any) { const e = document.createElement('div'); e.className = 'empty'; e.textContent = S('noResults'); frag.appendChild(e); }
  return frag;
}

// ---------------------------------------------------------------- 사이드바
let searchQuery = '';
function buildNav() {
  const nav = $('nav');
  Array.from(nav.querySelectorAll('button')).forEach((b) => b.remove());
  for (const p of SETTINGS_PAGES) {
    const b = document.createElement('button');
    b.dataset.page = p.id;
    b.innerHTML = `${icon(p.icon)}<span>${tr(p.title)}</span>`;
    b.addEventListener('click', () => { $('search').value = ''; searchQuery = ''; gotoPage(p.id); });
    nav.appendChild(b);
  }
  placeNav();
}
function placeNav() {
  const nav = $('nav');
  const hl = $('navHl');
  nav.querySelectorAll('button').forEach((b) => b.classList.toggle('on', b.dataset.page === currentPage));
  const on = nav.querySelector('button.on');
  if (!on) { hl.style.opacity = '0'; return; }
  hl.style.opacity = '1';
  const moved = hl.style.transform && hl.style.transform !== `translateY(${on.offsetTop}px)`;
  hl.style.height = `${on.offsetHeight}px`;
  hl.style.transform = `translateY(${on.offsetTop}px)`;
  if (moved && typeof LG !== 'undefined') LG.stretch(hl, 'y', 520);
}

function gotoPage(id) {
  if (!SETTINGS_PAGES.some((p) => p.id === id)) id = SETTINGS_PAGES[0].id;
  const prevIdx = SETTINGS_PAGES.findIndex((p) => p.id === currentPage);
  const idx = SETTINGS_PAGES.findIndex((p) => p.id === id);
  if (id === currentPage && !searchQuery) return;
  currentPage = id;
  const page = SETTINGS_PAGES[idx];
  $('pageTitle').textContent = tr(page.title);
  placeNav();
  showPage(id, { dir: idx >= prevIdx ? 1 : -1 });
}

function onSearch(q) {
  searchQuery = q.trim();
  if (!searchQuery) { const id = currentPage; currentPage = null; gotoPage(id || SETTINGS_PAGES[0].id); return; }
  currentPage = null;
  $('pageTitle').textContent = S('searchTitle');
  placeNav();
  showPage('__search', { query: searchQuery });
}

// ---------------------------------------------------------------- 전체 다시 그리기 (언어가 바뀌었을 때 등)
function rebuild() {
  $('search').placeholder = S('search');
  $('verLine').textContent = ABOUT && ABOUT.version ? `${S('ver')} ${ABOUT.version}` : '';
  buildNav();
  const id = currentPage || SETTINGS_PAGES[0].id;
  if (searchQuery) { onSearch(searchQuery); return; }
  $('pageTitle').textContent = tr(SETTINGS_PAGES.find((p) => p.id === id).title);
  currentPage = id;
  placeNav();
  showPage(id, { dir: 1 });
}

// ---------------------------------------------------------------- Liquid Glass
// 작은 컨트롤(버튼/강조 막대/아이콘 구슬)에만 굴절 렌즈를 건다. 큰 카드는 렌즈 비용이 커서 반사광(CSS)만 쓴다.
const GLASS_TARGETS = ['.btn', '.winbtns button', '.seg-hl', '.nav-hl', '.porb', '.hero-glyph', '.pmv', '.pchipS', '.mmute', '.icopick', '.toast'];
function applyGlass(root) {
  if (typeof LG === 'undefined' || !LG.supported) return;
  const scope = root || document;
  for (const sel of GLASS_TARGETS) {
    scope.querySelectorAll(sel).forEach((el) => {
      if (el.classList.contains('lg')) return;
      const big = el.matches('.hero-glyph, .nav-hl');
      LG.lens(el, { bezel: big ? 16 : 10, scale: big ? 14 : 10, blur: 1.2, saturate: 1.5, brightness: 1.08 });
    });
  }
}
function initGlass() {
  if (typeof LG === 'undefined') return;
  LG.bindPointerGlow();
  if (LG.supported) {
    LG.defineStatic('thumb', 38, 26, { bezel: 11, scale: 12, dispersion: 0.08 });
    LG.defineStatic('knob', 28, 28, { bezel: 11, scale: 11, dispersion: 0.08 });
  }
  applyGlass(document);
  // 페이지가 다시 그려지거나 팝업이 생기면 새로 생긴 컨트롤에도 건다 (한 프레임에 한 번만)
  let raf = 0;
  new MutationObserver(() => { if (!raf) raf = requestAnimationFrame(() => { raf = 0; applyGlass(document); }); }).observe(document.body, { childList: true, subtree: true });
}

// ---------------------------------------------------------------- 외부와의 연결
function loadData(res) {
  const data = (res && res.data) || {};
  D = clone(DEFAULTS);
  for (const sec of ['settings', 'pomo', 'water']) if (data[sec]) mergeInto(D[sec], data[sec]);
  AUTOSTART = !!(res && res.autostart);
  ABOUT = (res && res.about) || {};
  if (res && res.monitors) MONITORS = res.monitors;
  if (res && res.hotkeys) HOTKEYS = res.hotkeys;
  if (res && res.plugins) CATALOG = res.plugins;
  if (res && res.launcher) LAUNCHER = res.launcher;
  if (res && res.presets) PRESETS = res.presets;
  applyLocal();
}

// 노치 화면에서 값이 바뀌었을 때(우클릭 메뉴, 포모도로 시간 조절 등) 파이썬이 호출한다
window.onExternalData = function (slim) {
  const before = D.settings.lang;
  for (const sec of ['settings', 'pomo', 'water']) if (slim && slim[sec]) mergeInto(D[sec], slim[sec]);
  applyLocal();
  if (D.settings.lang !== before) rebuild(); else updateAll();
};
window.openPage = (id) => { $('search').value = ''; searchQuery = ''; gotoPage(id); };      // 파이썬이 부른다
window.focusSettings = () => { const p = $('panel'); if (p.animate && !animOff()) p.animate([{ transform: 'scale(0.985)' }, { transform: 'none' }], { duration: 360 / rate(), easing: 'cubic-bezier(0.34,1.56,0.64,1)' }); };

let toastTimer = null;
function toast(msg) {
  const t = $('toast');
  t.textContent = msg;
  t.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove('show'), 2000);
}

function bindChrome() {
  $('btnClose').addEventListener('click', () => { flushPatch(); const api = getApi(); if (api) api.settings_close(); });
  $('btnMin').addEventListener('click', () => { const api = getApi(); if (api) api.settings_minimize(); });
  $('search').addEventListener('input', (e) => onSearch(e.target.value));
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      if ($('search').value) { $('search').value = ''; onSearch(''); } else $('btnClose').click();
    } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'f') { e.preventDefault(); $('search').focus(); }
  });
  window.addEventListener('resize', () => { document.querySelectorAll('.seg').forEach(placeSeg); placeNav(); });
  window.addEventListener('beforeunload', flushPatch);
}

async function start() {
  bindChrome();
  initGlass();
  const api = getApi();
  if (api && api.settings_get) {
    try { loadData(await api.settings_get()); } catch (e) { console.error(e); applyLocal(); }
  } else applyLocal();
  const hash = (location.hash || '').replace('#', '');
  currentPage = null;
  $('search').placeholder = S('search');
  $('verLine').textContent = ABOUT && ABOUT.version ? `${S('ver')} ${ABOUT.version}` : '';
  buildNav();
  gotoPage(hash || SETTINGS_PAGES[0].id);
}

// pywebview 브리지가 준비된 뒤에 시작한다 (브라우저에서 단독으로 열어도 동작하도록 시간 제한을 둔다)
(function boot() {
  let started = false;
  const go = () => { if (!started) { started = true; start(); } };
  window.addEventListener('pywebviewready', go);
  const t0 = performance.now();
  (function wait() { if (getApi()) go(); else if (performance.now() - t0 > 2500) go(); else setTimeout(wait, 40); })();
})();
