// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
// Copyright (c) 2026 Flirty_BananaMilk — 상업적 이용 금지, 자세한 내용은 LICENSE
// ========================================================
// 아이콘 세트: 24x24 선(stroke) 아이콘. 이모지 대신 이걸 쓴다 — 크기/색/두께가 글자 색(currentColor)을 따라서 화면과 어울린다.
// 노치(index.html)와 설정 창(settings.html)이 함께 쓴다. 플러그인 JSON / 바로가기의 icon 값은 여기 이름이다.
// ========================================================
const UI_ICONS = {
  // 재생 / 음악
  playpause: '<path d="M5.5 5.5l8 6.5-8 6.5z"/><path d="M17.5 6v12"/>',
  play: '<path d="M8 5.5l11 6.5-11 6.5z"/>',
  prev: '<path d="M18 6v12l-8-6z"/><path d="M6 6v12"/>',
  next: '<path d="M6 6v12l8-6z"/><path d="M18 6v12"/>',
  restart: '<path d="M5 12a7 7 0 1 0 2.2-5.1"/><path d="M4 4v4h4"/>',
  shuffle: '<path d="M4 7h4l8 10h4"/><path d="M4 17h4l2.3-3"/><path d="M13.7 10L16 7h4"/><path d="M18 5l2 2-2 2M18 15l2 2-2 2"/>',
  repeat: '<path d="M5 11V9a3 3 0 0 1 3-3h11"/><path d="M16 3l3 3-3 3"/><path d="M19 13v2a3 3 0 0 1-3 3H5"/><path d="M8 21l-3-3 3-3"/>',
  music: '<path d="M9 18V6l10-2v12"/><circle cx="7" cy="18" r="2.2"/><circle cx="17" cy="16" r="2.2"/>',
  disc: '<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="2.4"/>',
  waves: '<path d="M4 9c5-2 11-2 16 0"/><path d="M5.5 13c4-1.4 9-1.4 13 0"/><path d="M7 17c3-.9 7-.9 10 0"/>',
  lyrics: '<path d="M4 7h16M4 12h10M4 17h13"/>',
  // 소리
  volume: '<path d="M4 10v4h3.5L12 18V6L7.5 10z"/><path d="M15.5 9a4 4 0 0 1 0 6M18 6.5a8 8 0 0 1 0 11"/>',
  volume1: '<path d="M4 10v4h3.5L12 18V6L7.5 10z"/><path d="M15.5 10.2a2.6 2.6 0 0 1 0 3.6"/>',
  volume2: '<path d="M4 10v4h3.5L12 18V6L7.5 10z"/><path d="M15.5 9a4 4 0 0 1 0 6"/>',
  mute: '<path d="M4 10v4h3.5L12 18V6L7.5 10z"/><path d="M16 9.5l5 5M21 9.5l-5 5"/>',
  mic: '<rect x="9" y="3.5" width="6" height="11" rx="3"/><path d="M6 11.5a6 6 0 0 0 12 0M12 17.5V21M9 21h6"/>',
  micoff: '<path d="M9 8.5V6.5a3 3 0 0 1 5.6-1.5M15 10.5v1a3 3 0 0 1-4.7 2.5"/><path d="M6 11.5a6 6 0 0 0 9.4 4.9M18 11.5a6 6 0 0 1-.4 2.2M12 17.5V21M9 21h6"/><path d="M4 4l16 16"/>',
  headphones: '<path d="M4 15v-3a8 8 0 0 1 16 0v3"/><rect x="3" y="14" width="4" height="6" rx="1.5"/><rect x="17" y="14" width="4" height="6" rx="1.5"/>',
  plus: '<path d="M12 6v12M6 12h12"/>',
  minus: '<path d="M6 12h12"/>',
  // 시스템 / 도구
  lock: '<rect x="5" y="10.5" width="14" height="9.5" rx="2"/><path d="M8.5 10.5V8a3.5 3.5 0 0 1 7 0v2.5"/>',
  crop: '<path d="M7 3v14h14M3 7h14v14"/>',
  monitor: '<rect x="3" y="4.5" width="18" height="12" rx="2"/><path d="M9 20h6M12 16.5V20"/>',
  gauge: '<path d="M4 18a8.5 8.5 0 1 1 16 0"/><path d="M12 18l3.8-4.8"/><path d="M7 11.5l1 .6M12 8v1.2M17 11.5l-1 .6"/>',
  moon: '<path d="M19 14.5A7.5 7.5 0 0 1 9.5 5a7.5 7.5 0 1 0 9.5 9.5z"/>',
  gear: '<circle cx="12" cy="12" r="3"/><path d="M12 3.5v2.4M12 18.1v2.4M3.5 12h2.4M18.1 12h2.4M6 6l1.7 1.7M16.3 16.3L18 18M6 18l1.7-1.7M16.3 7.7L18 6"/>',
  tool: '<path d="M20 7.5a4.5 4.5 0 0 1-6 4.2L7 18.7 5.3 17l7-7A4.5 4.5 0 0 1 16.5 4l-2.6 2.6 2.5 2.5z"/>',
  plug: '<path d="M9 3v5M15 3v5"/><path d="M6.5 8h11v3a5.5 5.5 0 0 1-11 0z"/><path d="M12 16.5V21"/>',
  bell: '<path d="M6 16v-5a6 6 0 0 1 12 0v5l1.5 2h-15z"/><path d="M10 20.5a2 2 0 0 0 4 0"/>',
  // 파일 / 앱
  copy: '<rect x="8.5" y="8.5" width="11" height="11" rx="2"/><path d="M15.5 8.5V6.5a2 2 0 0 0-2-2h-7a2 2 0 0 0-2 2v7a2 2 0 0 0 2 2h2"/>',
  clipboard: '<rect x="6" y="4.5" width="12" height="16" rx="2"/><path d="M9.5 4.5v-1h5v1M9 11h6M9 15h4"/>',
  folder: '<path d="M3.5 7.5a2 2 0 0 1 2-2h4l2 2.5h7a2 2 0 0 1 2 2V17a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2z"/>',
  file: '<path d="M7.5 3.5h6.5l4.5 4.5V19a1.5 1.5 0 0 1-1.5 1.5h-9.5A1.5 1.5 0 0 1 6 19V5a1.5 1.5 0 0 1 1.5-1.5z"/><path d="M14 3.5V8h4.5"/>',
  note: '<path d="M7.5 3.5h9A1.5 1.5 0 0 1 18 5v14a1.5 1.5 0 0 1-1.5 1.5h-9A1.5 1.5 0 0 1 6 19V5a1.5 1.5 0 0 1 1.5-1.5z"/><path d="M9 8.5h6M9 12h6M9 15.5h3.5"/>',
  calc: '<rect x="5" y="3.5" width="14" height="17" rx="2"/><path d="M8.5 8h7"/><path d="M9 12h.01M12 12h.01M15 12h.01M9 16h.01M12 16h.01M15 16h.01"/>',
  terminal: '<rect x="3.5" y="5" width="17" height="14" rx="2"/><path d="M7.5 10l3 2.5-3 2.5M13 15h4"/>',
  code: '<path d="M9 8l-4 4 4 4M15 8l4 4-4 4"/>',
  brush: '<path d="M4 20c2.4 0 4-1 4-3a2 2 0 0 0-4 0c0 1-.4 2-1 3z"/><path d="M9 15.5L19.5 5 21 6.5 10.5 17z"/>',
  image: '<rect x="3.5" y="5" width="17" height="14" rx="2"/><circle cx="9" cy="10" r="1.6"/><path d="M4 17l5-4.5 4 3 3-2.5 4 3.5"/>',
  download: '<path d="M12 4v11M7 11l5 5 5-5M5 20h14"/>',
  launch: '<path d="M6 18L18 6M9.5 6H18v8.5"/>',
  link: '<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1"/><path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/>',
  star: '<path d="M12 4l2.4 5 5.4.7-4 3.7 1 5.4L12 16l-4.8 2.8 1-5.4-4-3.7 5.4-.7z"/>',
  home: '<path d="M4 11l8-6.5 8 6.5"/><path d="M6 10v9.5h4.5V14h3v5.5H18V10"/>',
  edit: '<path d="M4 20h4L19.5 8.5l-4-4L4 16z"/><path d="M13.5 6.5l4 4"/>',
  // 웹 / 소통
  globe: '<circle cx="12" cy="12" r="8.5"/><path d="M3.5 12h17M12 3.5c-3 3-3 14 0 17M12 3.5c3 3 3 14 0 17"/>',
  mail: '<rect x="3.5" y="5.5" width="17" height="13" rx="2"/><path d="M4 7l8 6 8-6"/>',
  chat: '<path d="M5.5 5.5h13a1.5 1.5 0 0 1 1.5 1.5v8a1.5 1.5 0 0 1-1.5 1.5H11l-4 3v-3H5.5A1.5 1.5 0 0 1 4 15V7a1.5 1.5 0 0 1 1.5-1.5z"/>',
  branch: '<circle cx="7" cy="6" r="2"/><circle cx="7" cy="18" r="2"/><circle cx="17" cy="9" r="2"/><path d="M7 8v8M17 11c0 3-4 3-8 5"/>',
  video: '<rect x="3" y="6" width="18" height="12" rx="3.5"/><path d="M10.5 9.5l4.5 2.5-4.5 2.5z"/>',
  search: '<circle cx="11" cy="11" r="6.5"/><path d="M16 16l4.5 4.5"/>',
  calendar: '<rect x="4" y="5.5" width="16" height="14.5" rx="2"/><path d="M4 10h16M8.5 3.5v4M15.5 3.5v4"/>',
  // 시간 / 생활
  timer: '<circle cx="12" cy="13.5" r="7.5"/><path d="M12 9.5v4l2.5 2M9.5 3h5"/>',
  stopwatch: '<circle cx="12" cy="13.5" r="7.5"/><path d="M12 13.5L15 10M10 3h4M12 3v3"/>',
  target: '<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="4"/><path d="M12 12h.01"/>',
  drop: '<path d="M12 3.5c3.5 4 6 7 6 10a6 6 0 0 1-12 0c0-3 2.5-6 6-10z"/>',
  checklist: '<path d="M5 7l1.5 1.5L9 6M5 14l1.5 1.5L9 13M12 7.5h7M12 14.5h7"/>',
  sun: '<circle cx="12" cy="12" r="3.8"/><path d="M12 3.5v2M12 18.5v2M3.5 12h2M18.5 12h2M6 6l1.4 1.4M16.6 16.6L18 18M6 18l1.4-1.4M16.6 7.4L18 6"/>',
  sliders: '<path d="M4 7h9M17 7h3M4 17h3M11 17h9"/><circle cx="15" cy="7" r="2"/><circle cx="9" cy="17" r="2"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7.6v.4"/>',
  hand: '<path d="M8 12V6.5a1.5 1.5 0 0 1 3 0V11M11 11V5a1.5 1.5 0 0 1 3 0v6M14 11V6.5a1.5 1.5 0 0 1 3 0V14a6 6 0 0 1-6 6h-.5A5.5 5.5 0 0 1 6 15v-2.5a1.5 1.5 0 0 1 2-1.4"/>',
  close: '<path d="M6 6l12 12M18 6L6 18"/>',
};

const UI_ICON_NAMES = Object.keys(UI_ICONS);

// 이름 -> <svg> 문자열. 모르는 이름이면 null (호출한 쪽이 글자 배지로 대신한다)
function uiIconSvg(name, size) {
  const inner = UI_ICONS[name];
  if (!inner) return null;
  const s = size ? ` width="${size}" height="${size}"` : '';
  return `<svg class="uic" viewBox="0 0 24 24"${s} fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${inner}</svg>`;
}

// 아이콘 이름 -> 요소 안에 넣을 HTML. 이름이 없거나 모르면(예: 사용자가 이모지/글자를 넣음) 이름의 첫 글자를 둥근 배지로 보여 준다.
function uiIconHtml(name, fallbackText, size) {
  const svg = uiIconSvg(String(name || '').trim(), size);
  if (svg) return svg;
  const raw = String(fallbackText || name || '').trim();
  const ch = Array.from(raw)[0] || '·';
  return `<span class="uic badge">${ch.replace(/[<&>]/g, '')}</span>`;
}

if (typeof module !== 'undefined') module.exports = { UI_ICONS, UI_ICON_NAMES, uiIconSvg, uiIconHtml };
