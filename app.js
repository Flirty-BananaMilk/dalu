// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
// Copyright (c) 2026 Flirty_BananaMilk — 상업적 이용 금지, 자세한 내용은 LICENSE
// ========================================================
// Dalu — 코어: 상태 기계, 저장소, i18n, 가사 렌더링
// 기능(포모도로/물/할 일/선반/시스템 알림)은 features.js, 시작은 main.js
// ========================================================

// 노치 크기(CSS px). island.css 의 .island[data-s=...] 의 --w/--h/--e 와 같아야 한다.
// 전환 애니메이션 도중의 getBoundingClientRect() 는 중간값이라 창 클릭 영역 계산에 쓰면 안 된다.
const BG_EXTRA_H = 24;      // 백그라운드 보컬 줄이 나올 때 작은 노치가 늘어나는 높이 (CSS --h 56px 와 같아야 한다)
const STATES = {
  idle:       { w: 150, h: 30,  e: 10 },
  pet:        { w: 150, h: 30,  e: 10 },
  mini:       { w: 300, h: 32,  e: 10 },
  compact:    { w: 190, h: 30,  e: 10 },
  peek_track: { w: 340, h: 62,  e: 13 },
  peek_info:  { w: 310, h: 60,  e: 13 },
  peek_msg:   { w: 240, h: 40,  e: 12 },
  music:      { w: 420, h: 140, e: 22 },
  pomo:       { w: 420, h: 140, e: 22 },
  water:      { w: 420, h: 140, e: 22 },
  shelf:      { w: 560, h: 172, e: 24 },
  todo:       { w: 420, h: 140, e: 22 },
  timer:      { w: 420, h: 140, e: 22 },
  launcher:   { w: 420, h: 140, e: 22 },
  plugins:    { w: 420, h: 140, e: 22 },
  clip:       { w: 420, h: 140, e: 22 },
  agenda:     { w: 420, h: 140, e: 22 },
  buds:       { w: 420, h: 140, e: 22 },
  lyrics:     { w: 520, h: 140, e: 22 }
};
const CHIP_EXTRA_W = 60;        // 포모도로 칩이 보일 때 mini 노치가 넓어지는 폭
const PAGES = ['music', 'pomo', 'timer', 'water', 'shelf', 'todo', 'clip', 'agenda', 'launcher', 'plugins', 'buds'];   // 기본 순서(실제 순서는 설정 tabOrder)
// 이어버드는 연결됐을 때만, 클립보드는 켰을 때만, 일정은 캘린더 주소가 있을 때만 넘길 수 있다 (features2.js 의 pageAvailable)
function availablePages() {
  return visibleTabs(store.settings, (p) => (typeof pageAvailable === 'function' ? pageAvailable(p) : true));
}
const POLL_MS = 200;
const POLL_BOOST_MS = 60;          // 재생 컨트롤을 누른 직후에는 짧게 자주 물어본다 (반응이 느리게 느껴지지 않도록)
let pollBoostUntil = 0;
let playHoldUntil = 0;             // 방금 재생/일시정지를 눌렀다면 잠시 서버의 옛 재생 상태를 무시한다
const REDUCED_MOTION = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const IDLE_AFTER_MS = 120000;   // 일시정지/정지 후 이 시간이 지나면 시계(idle)로 돌아간다
const PEEK_MS = 3200;
const PET_AFTER_SEC = 45;       // 입력이 이만큼 없으면 시계 대신 눈 캐릭터가 나온다
const PET_DOZE_SEC = 150;       // 이만큼 없으면 눈을 감고 존다
const PET_WAVE_MS = 2600;       // 졸다가 돌아오면 이만큼 인사한다

// ========================================================
// 아이콘 (Material 아이콘 path, 신뢰된 상수만 innerHTML 로 넣는다)
// ========================================================
const ICONS = {
  monitor: 'M20 3H4c-1.1 0-2 .9-2 2v11c0 1.1.9 2 2 2h6v2H8v2h8v-2h-2v-2h6c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm0 13H4V5h16v11z',      // 캡처 모드 알림
  volume: 'M3 9v6h4l5 5V4L7 9H3zm13.5 3A4.5 4.5 0 0 0 14 7.97v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z',
  volumeOff: 'M16.5 12A4.5 4.5 0 0 0 14 7.97v2.21l2.45 2.45c.03-.2.05-.41.05-.63zm2.5 0c0 .94-.2 1.82-.54 2.64l1.51 1.51A8.796 8.796 0 0 0 21 12c0-4.28-2.99-7.86-7-8.77v2.06c2.89.86 5 3.54 5 6.71zM4.27 3L3 4.27 7.73 9H3v6h4l5 5v-6.73l4.25 4.25c-.67.52-1.42.93-2.25 1.18v2.06a8.99 8.99 0 0 0 3.69-1.81L19.73 21 21 19.73l-9-9L4.27 3zM12 4L9.91 6.09 12 8.18V4z',
  sun: 'M20 8.69V4h-4.69L12 .69 8.69 4H4v4.69L.69 12 4 15.31V20h4.69L12 23.31 15.31 20H20v-4.69L23.31 12 20 8.69zM12 18c-3.31 0-6-2.69-6-6s2.69-6 6-6 6 2.69 6 6-2.69 6-6 6zm0-10c-2.21 0-4 1.79-4 4s1.79 4 4 4 4-1.79 4-4-1.79-4-4-4z',
  caps: 'M12 8.41L16.59 13 18 11.59l-6-6-6 6L7.41 13 12 8.41zM6 18h12v-2H6v2z',
  globe: 'M11.99 2C6.47 2 2 6.48 2 12s4.47 10 9.99 10C17.52 22 22 17.52 22 12S17.52 2 11.99 2zm6.93 6h-2.95a15.65 15.65 0 0 0-1.38-3.56A8.03 8.03 0 0 1 18.92 8zM12 4.04c.83 1.2 1.48 2.53 1.91 3.96h-3.82c.43-1.43 1.08-2.76 1.91-3.96zM4.26 14C4.1 13.36 4 12.69 4 12s.1-1.36.26-2h3.38c-.08.66-.14 1.32-.14 2 0 .68.06 1.34.14 2H4.26zm.82 2h2.95c.32 1.25.78 2.45 1.38 3.56A7.987 7.987 0 0 1 5.08 16zm2.95-8H5.08a7.987 7.987 0 0 1 4.33-3.56A15.65 15.65 0 0 0 8.03 8zM12 19.96c-.83-1.2-1.48-2.53-1.91-3.96h3.82c-.43 1.43-1.08 2.76-1.91 3.96zM14.34 14H9.66c-.09-.66-.16-1.32-.16-2 0-.68.07-1.35.16-2h4.68c.09.65.16 1.32.16 2 0 .68-.07 1.34-.16 2zm.25 5.56c.6-1.11 1.06-2.31 1.38-3.56h2.95a8.03 8.03 0 0 1-4.33 3.56zM16.36 14c.08-.66.14-1.32.14-2 0-.68-.06-1.34-.14-2h3.38c.16.64.26 1.31.26 2s-.1 1.36-.26 2h-3.38z',
  charge: 'M15.67 4H14V2h-4v2H8.33C7.6 4 7 4.6 7 5.33v15.33C7 21.4 7.6 22 8.33 22h7.33c.74 0 1.34-.6 1.34-1.33V5.33C17 4.6 16.4 4 15.67 4zM11 20v-5.5H9L13 7v5.5h2L11 20z',
  batteryLow: 'M15.67 4H14V2h-4v2H8.33C7.6 4 7 4.6 7 5.33v15.34C7 21.4 7.6 22 8.33 22h7.34c.73 0 1.33-.6 1.33-1.33V5.33C17 4.6 16.4 4 15.67 4zM13 18h-2v-2h2v2zm0-4h-2V9h2v5z',
  wifi: 'M1 9l2 2c4.97-4.97 13.03-4.97 18 0l2-2C16.93 2.93 7.08 2.93 1 9zm8 8l3 3 3-3a4.237 4.237 0 0 0-6 0zm-4-4l2 2a7.074 7.074 0 0 1 10 0l2-2C15.14 9.14 8.87 9.14 5 13z',
  wifiOff: 'M23.64 7c-.45-.34-4.93-4-11.64-4-1.5 0-2.89.19-4.15.48L18.18 13.8 23.64 7zm-6.6 8.22L3.27 1.44 2 2.72l2.05 2.06C1.91 5.76.59 6.82.36 7l11.63 14.49.01.01.01-.01 3.9-4.86 3.32 3.32 1.27-1.27-3.46-3.46z',
  headphones: 'M12 1a9 9 0 0 0-9 9v7c0 1.66 1.34 3 3 3h3v-8H5v-2c0-3.87 3.13-7 7-7s7 3.13 7 7v2h-4v8h3c1.66 0 3-1.34 3-3v-7a9 9 0 0 0-9-9z',
  timer: 'M15 1H9v2h6V1zm-4 13h2V8h-2v6zm8.03-6.61l1.42-1.42c-.43-.51-.9-.99-1.41-1.41l-1.42 1.42A8.962 8.962 0 0 0 12 4c-4.97 0-9 4.03-9 9s4.02 9 9 9a8.994 8.994 0 0 0 7.03-14.61zM12 20c-3.87 0-7-3.13-7-7s3.13-7 7-7 7 3.13 7 7-3.13 7-7 7z',
  drop: 'M12 2c-5.33 4.55-8 8.48-8 11.8 0 4.98 3.8 8.2 8 8.2s8-3.22 8-8.2c0-3.32-2.67-7.25-8-11.8zm0 18c-3.35 0-6-2.57-6-6.2 0-2.34 1.95-5.44 6-9.14 4.05 3.7 6 6.79 6 9.14 0 3.63-2.65 6.2-6 6.2z',
  check: 'M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z',
  file: 'M14 2H6c-1.1 0-1.99.9-1.99 2L4 20c0 1.1.89 2 1.99 2H18c1.1 0 2-.9 2-2V8l-6-6zm2 16H8v-2h8v2zm0-4H8v-2h8v2zm-3-5V3.5L18.5 9H13z',
  chat: 'M21.99 4c0-1.1-.89-2-1.99-2H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h14l4 4-.01-18zM18 14H6v-2h12v2zm0-3H6V9h12v2zm0-3H6V6h12v2z',
  play: 'M8 5v14l11-7z',
  pause: 'M6 19h4V5H6v14zm8-14v14h4V5h-4z',
  close: 'M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z',
  check2: 'M5 12.5l4.2 4.2L19 7',
  shuffle: 'M10.59 9.17L5.41 4 4 5.41l5.17 5.17 1.42-1.41zM14.5 4l2.04 2.04L4 18.59 5.41 20 17.96 7.46 20 9.5V4h-5.5zm.33 9.41l-1.41 1.41 3.13 3.13L14.5 20H20v-5.5l-2.04 2.04-3.13-3.13z',
  modeOff: 'M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zm0 2c1.85 0 3.55.63 4.9 1.69L5.69 16.9A7.94 7.94 0 0 1 4 12c0-4.41 3.59-8 8-8zm0 16c-1.85 0-3.55-.63-4.9-1.69L18.31 7.1A7.94 7.94 0 0 1 20 12c0 4.41-3.59 8-8 8z',
  modeAmbient: 'M17 20c-.29 0-.56-.06-.76-.15-.71-.37-1.21-.88-1.71-2.38-.51-1.56-1.47-2.29-2.39-3-.79-.61-1.61-1.24-2.32-2.53C9.29 10.98 9 9.93 9 9c0-2.8 2.2-5 5-5s5 2.2 5 5h2c0-3.93-3.07-7-7-7S7 5.07 7 9c0 1.26.38 2.65 1.07 3.9.91 1.65 1.98 2.48 2.85 3.15.81.62 1.39 1.07 1.71 2.05.6 1.82 1.37 2.84 2.73 3.55.51.23 1.07.35 1.64.35 2.21 0 4-1.79 4-4h-2c0 1.1-.9 2-2 2zM7.64 2.64L6.22 1.22C4.23 3.21 3 5.96 3 9s1.23 5.79 3.22 7.78l1.41-1.41C6.01 13.74 5 11.49 5 9s1.01-4.74 2.64-6.36zM11.5 9a2.5 2.5 0 0 0 5 0 2.5 2.5 0 0 0-5 0z',
  modeAdaptive: 'M3 17v2h6v-2H3zM3 5v2h10V5H3zm10 16v-2h8v-2h-8v-2h-2v6h2zM7 9v2H3v2h4v2h2V9H7zm14 4v-2H11v2h10zm-6-4h2V7h4V5h-4V3h-2v6z',
  modeAnc: 'M12 1a9 9 0 0 0-9 9v7c0 1.66 1.34 3 3 3h3v-8H5v-2c0-3.87 3.13-7 7-7s7 3.13 7 7v2h-4v8h3c1.66 0 3-1.34 3-3v-7a9 9 0 0 0-9-9z',
  repeat: 'M7 7h10v3l4-4-4-4v3H5v6h2V7zm10 10H7v-3l-4 4 4 4v-3h12v-6h-2v4z',
  repeatOne: 'M7 7h10v3l4-4-4-4v3H5v6h2V7zm10 10H7v-3l-4 4 4 4v-3h12v-6h-2v4zm-4-2V9h-1l-2 1v1h1.5v4H13z'
};
function iconSvg(name) {
  return `<svg viewBox="0 0 24 24"><path d="${ICONS[name]}"/></svg>`;
}

// ========================================================
// i18n (ko / en)
// ========================================================
const I18N = {
  ko: {
    noTrack: '재생 중인 곡 없음', lyricsLoading: '가사를 불러오는 중...', lyricsNone: '가사가 없어요',
    prev: '이전 곡', next: '다음 곡', shuffle: '셔플', repeat: '반복',
    budsLeft: '왼쪽', budsRight: '오른쪽', budsCase: '케이스', modeOff: '끄기', modeAmbient: '주변 소리 듣기', modeAdaptive: '소음 제어 최적화', modeAnc: '액티브 노이즈 캔슬링',
    budsConnected: '연결됨', budsNoControl: '소음 제어를 사용할 수 없어요', budsModeFailed: '모드를 바꾸지 못했어요', budsInUse: '다른 앱이 이어버드를 쓰고 있어요 (Galaxy Buds 앱을 닫아 주세요)', budsModeSet: '{mode}(으)로 변경', budsLowMsg: '{pos} 배터리 부족', budsGone: '이어버드 연결 끊김', captureOn: '캡처 모드', captureOnSub: '지금 {n}초 동안 스크린샷에 노치가 보여요', captureNone: '이미 캡처할 수 있어요', captureNoneSub: '리퀴드 글래스 “전체”일 때만 필요해요', captureOff: '캡처 모드 꺼짐', captureOffSub: '노치가 다시 캡처에서 빠져요', captureHoldSub: '끌 때까지 녹화·스크린샷에 노치가 보여요', budsAlertT: '충전이 중지되었습니다', budsAlertS: '땀이나 얼룩이 감지됐어요. 버즈와 케이스의 단자를 닦아 주세요', budsCharging: '충전 중',
    shuffleOnMsg: '셔플 켬', shuffleOffMsg: '셔플 끔', repeatNoneMsg: '반복 끔', repeatAllMsg: '전체 반복', repeatOneMsg: '한 곡 반복', playPause: '재생 / 일시정지', lyricsToggle: '가사 표시 켜기/끄기',
    lyricsOnMsg: '가사 표시 켬', lyricsOffMsg: '가사 표시 끔', menuLyricsOff: '가사 표시 끄기', menuLyricsOn: '가사 표시 켜기',
    pin: '노치 항상 펼쳐두기 (고정)', pinned: '노치 고정됨', autoHide: '자동 숨김 모드',
    menuUnpin: '고정 해제 (자동 숨김)', menuPin: '항상 펼쳐두기 (고정)',
    compact: '컴팩트 모드 전환',
    clickThrough: '클릭 투과 (해제: 창 위에서 Ctrl)', ctOn: '클릭 투과 켬 — 해제: 노치 위에서 Ctrl', ctOff: '클릭 투과 해제',
    menuSoundOff: '알림음 끄기', menuSoundOn: '알림음 켜기', soundOnMsg: '알림음 켬', soundOffMsg: '알림음 끔',
    menuLang: '언어', exit: '종료',
    settings: '설정', focusStarted: '집중 시작', dndOnSub: '방해 금지를 켰어요', launcherTitle: '바로가기', launcherEmpty: '설정에서 바로가기를 추가해 보세요', launcherFailed: '실행하지 못했어요', launcherEditTitle: '바로가기 편집',
    pluginsEmpty: '설정에서 플러그인을 켜 주세요', pluginFailed: '실행하지 못했어요', pluginDone: '완료',
    timerMode: '타이머', stopwatchMode: '스톱워치', timerDone: '타이머 종료', timerDoneSub: '{n}분이 지났어요',
    clipTitle: '클립보드', clipClear: '모두 지우기', clipEmpty: '복사한 글이 여기에 쌓여요', clipOff: '클립보드 기록이 꺼져 있어요', openSettings: '설정 열기', clipCopied: '다시 복사했어요',
    delete: '삭제', failed: '실패했어요', agoNow: '방금', agoMin: '{n}분 전', agoHour: '{n}시간 전',
    agendaTitle: '일정', agendaNoTitle: '(제목 없음)', agendaEmpty: '앞으로 7일 동안 일정이 없어요', agendaNoSource: '설정에서 캘린더 주소를 넣어 주세요', agendaError: '캘린더를 불러오지 못했어요',
    agendaAllDay: '종일', agendaNow: '진행 중', agendaInMin: '{n}분 후', agendaTomorrow: '내일', agendaRefreshing: '다시 불러오는 중…', agendaRefreshTitle: '새로고침', agendaStartsIn: '{n}분 후 시작', agendaViewList: '목록', agendaViewWeek: '주', agendaViewMonth: '월', agendaToday: '오늘', agendaDayEmpty: '이 날은 일정이 없어요', agendaCont: '이어짐', agendaPrev: '이전', agendaNext: '다음',
    sourceSwitch: '재생 소스 전환', sourceSwitched: '재생 소스를 바꿨어요', volumeTitle: '볼륨', muteTitle: '음소거', menuSettings: '설정…', testAlert: '테스트 알림', testAlertSub: '이렇게 표시돼요', done: '완료', cancel: '취소', add: '추가', reset: '초기화', undo: '되돌리기',
    // pomodoro
    pomoFocus: '집중 시간', pomoBreak: '짧은 휴식', start: '시작', pause: '일시정지', resume: '계속',
    toBreak: '휴식으로', toFocus: '집중으로', minutesN: '{n}분', pomoToday: '오늘 {n}회 완료',
    pomoFocusDone: '집중 완료!', pomoFocusDoneSub: '{n}분 쉬어 가세요', pomoBreakDone: '휴식 끝', pomoBreakDoneSub: '다시 집중할 시간이에요',
    // water
    waterToday: '오늘 마신 물', bottleSize: '병 크기', dailyGoal: '하루 목표', remindEvery: '알림 간격', remindFrom: '시작 시각', remindTo: '종료 시각', remindOn: '물 알림',
    waterGoalReached: '목표 달성!', waterLeft: '{l} 남았어요', waterNext: '다음 알림 {t}', waterRemindOff: '알림 꺼짐',
    waterTime: '물 마실 시간이에요', waterAdded: '+{ml} ml', minutesUnit: '분', hourUnit: '시',
    // shelf
    shHint: '파일을 여기로 끌어다 놓으세요', shHint2: '또는 + 버튼으로 추가', shAdd: '파일 추가', shClear: '모두 지우기',
    shAdded: '선반에 {n}개 추가됨', shMissing: '파일을 찾을 수 없어요', shDragOut: '끌어서 내보내기 · 클릭하면 열기',
    // todo
    todoTitle: '오늘 할 일', todoAdd: '할 일 추가', todoEmpty: '할 일이 없어요\n+ 버튼으로 추가해 보세요', todoPlaceholder: '할 일을 입력하세요', todoTimeHint: '알림 시각(선택)', todoDue: '할 일 알림', todoSoon: '{n}분 뒤 마감', todoTimeNone: '시간 없음', todoTimeClear: '시간 지우기', snoozeTitle: '{n}분 미루기', snoozed: '{n}분 뒤에 다시 알려요', snoozedUntil: '{t}에 다시 알려요',
    // system
    volume: '음량', muted: '음소거', brightness: '밝기', capsOn: 'Caps Lock 켜짐', capsOff: 'Caps Lock 꺼짐', numOn: 'Num Lock 켜짐', numOff: 'Num Lock 꺼짐', scrollOn: 'Scroll Lock 켜짐', scrollOff: 'Scroll Lock 꺼짐', upNext: '다음 곡',  inputLang: '입력 언어',
    charging: '충전기 연결됨', unplugged: '충전기 분리됨', batteryLow: '배터리 부족', netOn: '인터넷 연결됨', netOff: '인터넷 연결 끊김',
    audioOut: '오디오 출력', connected: '연결됨', percentN: '{n}%'
  },
  en: {
    noTrack: 'Nothing playing', lyricsLoading: 'Loading lyrics...', lyricsNone: 'No lyrics',
    prev: 'Previous', next: 'Next', shuffle: 'Shuffle', repeat: 'Repeat',
    budsLeft: 'Left', budsRight: 'Right', budsCase: 'Case', modeOff: 'Off', modeAmbient: 'Ambient sound', modeAdaptive: 'Adaptive', modeAnc: 'Active noise cancelling',
    budsConnected: 'Connected', budsNoControl: 'Noise control unavailable', budsModeFailed: 'Could not change mode', budsInUse: 'Another app is using the earbuds (close the Galaxy Buds app)', budsModeSet: 'Set to {mode}', budsLowMsg: '{pos} battery low', budsGone: 'Earbuds disconnected', captureOn: 'Capture mode', captureOnSub: 'The notch is visible to screenshots for {n}s', captureNone: 'Already capturable', captureNoneSub: 'Only needed with Liquid Glass “Full”', captureOff: 'Capture mode off', captureOffSub: 'The notch is hidden from capture again', captureHoldSub: 'Visible until turned off', budsAlertT: 'Charging stopped', budsAlertS: 'Sweat or a stain was detected. Wipe the earbuds and the case contacts', budsCharging: 'Charging',
    shuffleOnMsg: 'Shuffle on', shuffleOffMsg: 'Shuffle off', repeatNoneMsg: 'Repeat off', repeatAllMsg: 'Repeat all', repeatOneMsg: 'Repeat one', playPause: 'Play / Pause', lyricsToggle: 'Show / hide lyrics',
    lyricsOnMsg: 'Lyrics on', lyricsOffMsg: 'Lyrics off', menuLyricsOff: 'Hide lyrics', menuLyricsOn: 'Show lyrics',
    pin: 'Keep notch open (pin)', pinned: 'Notch pinned', autoHide: 'Auto-hide mode',
    menuUnpin: 'Unpin (auto-hide)', menuPin: 'Keep open (pin)',
    compact: 'Toggle compact mode',
    clickThrough: 'Click-through (release: Ctrl over it)', ctOn: 'Click-through on — release: Ctrl over the notch', ctOff: 'Click-through off',
    menuSoundOff: 'Mute notification sounds', menuSoundOn: 'Unmute notification sounds', soundOnMsg: 'Sounds on', soundOffMsg: 'Sounds off',
    menuLang: 'Language', exit: 'Quit',
    settings: 'Settings', focusStarted: 'Focus started', dndOnSub: 'Do Not Disturb is on', launcherTitle: 'Shortcuts', launcherEmpty: 'Add shortcuts in Settings', launcherFailed: 'Could not launch it', launcherEditTitle: 'Edit shortcuts',
    pluginsEmpty: 'Turn on plugins in Settings', pluginFailed: 'Could not run it', pluginDone: 'Done',
    timerMode: 'Timer', stopwatchMode: 'Stopwatch', timerDone: 'Timer finished', timerDoneSub: '{n} min have passed',
    clipTitle: 'Clipboard', clipClear: 'Clear all', clipEmpty: 'Things you copy will pile up here', clipOff: 'Clipboard history is off', openSettings: 'Open settings', clipCopied: 'Copied again',
    delete: 'Delete', failed: 'Failed', agoNow: 'just now', agoMin: '{n} min ago', agoHour: '{n} h ago',
    agendaTitle: 'Agenda', agendaNoTitle: '(No title)', agendaEmpty: 'Nothing on your calendar for the next 7 days', agendaNoSource: 'Add a calendar address in Settings', agendaError: 'Could not load the calendar',
    agendaAllDay: 'All day', agendaNow: 'Now', agendaInMin: 'in {n} min', agendaTomorrow: 'Tomorrow', agendaRefreshing: 'Refreshing…', agendaRefreshTitle: 'Refresh', agendaStartsIn: 'starts in {n} min', agendaViewList: 'List', agendaViewWeek: 'Week', agendaViewMonth: 'Month', agendaToday: 'Today', agendaDayEmpty: 'Nothing on this day', agendaCont: 'Continues', agendaPrev: 'Previous', agendaNext: 'Next',
    sourceSwitch: 'Switch playback source', sourceSwitched: 'Playback source changed', volumeTitle: 'Volume', muteTitle: 'Mute', menuSettings: 'Settings…', testAlert: 'Test alert', testAlertSub: 'This is how alerts look', done: 'Done', cancel: 'Cancel', add: 'Add', reset: 'Reset', undo: 'Undo',
    pomoFocus: 'Focus time', pomoBreak: 'Short break', start: 'Start', pause: 'Pause', resume: 'Resume',
    toBreak: 'Take a break', toFocus: 'Back to focus', minutesN: '{n} min', pomoToday: '{n} done today',
    pomoFocusDone: 'Focus complete!', pomoFocusDoneSub: 'Take a {n}-minute break', pomoBreakDone: 'Break over', pomoBreakDoneSub: 'Time to focus again',
    waterToday: 'Water today', bottleSize: 'Bottle', dailyGoal: 'Daily goal', remindEvery: 'Remind every', remindFrom: 'From', remindTo: 'Until', remindOn: 'Reminders',
    waterGoalReached: 'Goal reached!', waterLeft: '{l} to go', waterNext: 'Next reminder {t}', waterRemindOff: 'Reminders off',
    waterTime: 'Time to drink water', waterAdded: '+{ml} ml', minutesUnit: 'min', hourUnit: 'h',
    shHint: 'Drop files here', shHint2: 'or add with the + button', shAdd: 'Add files', shClear: 'Clear all',
    shAdded: '{n} added to shelf', shMissing: 'File not found', shDragOut: 'Drag out anytime · click to open',
    todoTitle: "Today's tasks", todoAdd: 'Add task', todoEmpty: 'No tasks yet\nTap + to add one', todoPlaceholder: 'What needs doing?', todoTimeHint: 'Reminder time (optional)', todoDue: 'Task due', todoSoon: 'Due in {n} min', todoTimeNone: 'No time', todoTimeClear: 'Clear time', snoozeTitle: 'Snooze {n} min', snoozed: 'I’ll remind you again in {n} min', snoozedUntil: 'Reminds again at {t}',
    volume: 'Volume', muted: 'Muted', brightness: 'Brightness', capsOn: 'Caps Lock on', capsOff: 'Caps Lock off', numOn: 'Num Lock on', numOff: 'Num Lock off', scrollOn: 'Scroll Lock on', scrollOff: 'Scroll Lock off', upNext: 'Up next',  inputLang: 'Input language',
    charging: 'Charger connected', unplugged: 'Charger unplugged', batteryLow: 'Battery low', netOn: 'Internet connected', netOff: 'Internet disconnected',
    audioOut: 'Audio output', connected: 'connected', percentN: '{n}%'
  }
};

// 중국어(간체)·일본어는 i18n_cjk.js 에 있다. 문구가 빠져 있으면 영어, 영어도 없으면 한국어로 보인다.
I18N.zh = I18N_CJK.zh;
I18N.ja = I18N_CJK.ja;

let lang = 'ko';
function t(key, params) {
  let s = (I18N[lang] && I18N[lang][key]) || I18N.en[key] || I18N.ko[key] || key;
  if (params) for (const k in params) s = s.replace(`{${k}}`, params[k]);
  return s;
}

// ========================================================
// 저장소 (Python 의 data.json) — 이 PC 에만 저장된다
// ========================================================
const DEFAULT_STORE = {
  settings: {
    lang: 'ko', lyricsOn: true, sound: true, compact: false,
    clock24: true, clockSeconds: false, compactClock: true, satellite: 'full', glassNotch: 'controls', glassStrength: 100, glassRim: true, winNotify: false, winNotifyIgnore: '', uiScale: 100, setAnim: true, setAnimSpeed: 100, budsWatch: true,
    wordSync: true, lyricSize: 100, lyricGlow: true,
    smtcOn: true, mediaPriority: 'auto', extLyrics: true, extApple: true, extNetease: true, extLrclib: true,
    visualizer: true, vizGain: 100, artGlow: true, glowStrength: 100,
    notify: { volume: true, brightness: true, caps: true, num: true, scroll: true, lang: true, power: true, battery_low: true, net: true, audio_device: true, buds: true, buds_low: true, buds_alert: true, track: true, capture_mode: true },
    peekTime: 100, budsLowPct: 20,
    theme: 'black', monitor: 0, hoverDelay: 0, collapseDelay: 850, idleMin: 2, pet: true, petAfter: 45, fullscreenMode: 'yield',
    animOff: false, animSpeed: 100, bounce: 100, entrance: true, pageAnim: 'slide',
    tabOrder: DEFAULT_TAB_ORDER, tabHidden: '', pluginsEnabled: '',
    focusDnd: true,
    clipboardOn: false, calendarUrl: '', calendarRemindMin: 10, hotkeysOn: true, hkToggle: 'Ctrl+Alt+N', hkSettings: 'Ctrl+Alt+S', hkMixer: 'Ctrl+Alt+V', hkLyrics: 'Ctrl+Alt+L', hkCapture: 'Ctrl+Alt+P', captureSeconds: 15, captureNotch: 'auto',
    todoRemind: true, todoLeadMin: 0, snoozeMin: 10, weekStart: 'sun', agendaView: 'list', mediaKeys: true, upNext: true, upNextSec: 12, appFilterMode: 'off', appFilterList: ''
  },
  pomo: { focusMin: 25, breakMin: 5, doneToday: 0, doneDate: '' },
  water: { enabled: true, bottleMl: 250, goalMl: 2000, startHour: 9, endHour: 21, intervalMin: 60, lastRemindAt: 0, snoozeUntil: 0, log: { date: '', entries: [] } },
  todos: [],
  shelf: [],
  buds: { mode: null },
  launcher: { items: [] },
  timer: { minutes: 5, mode: 'timer' }
};
let store = JSON.parse(JSON.stringify(DEFAULT_STORE));

function mergeDeep(base, extra) {
  const out = Array.isArray(base) ? base.slice() : Object.assign({}, base);
  if (!extra || typeof extra !== 'object') return out;
  for (const k of Object.keys(extra)) {
    if (base && typeof base[k] === 'object' && !Array.isArray(base[k]) && base[k] !== null
        && typeof extra[k] === 'object' && !Array.isArray(extra[k]) && extra[k] !== null) {
      out[k] = mergeDeep(base[k], extra[k]);
    } else if (k in base || Array.isArray(base)) {
      out[k] = extra[k];
    }
  }
  return out;
}

let saveTimer = null;
let storeLoaded = false;      // 저장된 값을 읽기 전에는 저장하지 않는다(기본값이 저장된 설정을 덮어쓰지 않도록)
function saveStoreSoon() {
  clearTimeout(saveTimer);
  saveTimer = setTimeout(() => {
    const api = getApi();
    if (storeLoaded && api && api.save_data) api.save_data(store);
  }, 400);
}

async function loadStore() {
  const api = getApi();
  if (!api || !api.load_data) return;
  try {
    const data = await api.load_data();
    store = mergeDeep(DEFAULT_STORE, data || {});
    storeLoaded = true;
  } catch (e) { console.error(e); }
}

// ========================================================
// 상태
// ========================================================
let state = {
  isPlaying: false, duration: 0, title: "", artist: "", album: "", artworkUrl: "", trackId: "",
  lyrics: null,
  repeat: 'none',     // 'none' | 'one' | 'all'
  shuffle: false,
  lyricsVersion: -1   // Python 쪽 가사 버전. 이 값이 다를 때만 서버가 가사를 내려준다.
};

let playheadAnchorTime = 0;
let playheadAnchorPerf = performance.now();
let lastPlayingAt = 0;

let view = null;             // 'idle' | 'pet' | 'mini' | 'peek' | 'music' | 'lyrics' | 'pomo' | 'water' | 'shelf' | 'todo'
let page = 'music';          // 펼쳤을 때 보이는 페이지
let isExpanded = false;
let isPinned = false;
let contextMenuOpen = false;
let compactMode = false;
let collapseTimer = null;

const peek = { active: false, kind: 'track', key: '', timer: null };
const pet = { idleSec: 0, mode: 'awake', waveUntil: 0, dozed: false };

const $ = (id) => document.getElementById(id);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));
const island = $('island');
const miniLyricBox = $('miniLyricBox');
const miniLyricLine = $('miniLyricLine');
const miniBg = $('miniBg');
const miniBgLine = $('miniBgLine');
const miniDots = $('miniDots');
const mDots = [$('mDot1'), $('mDot2'), $('mDot3')];
const mFills = [$('mDotFill1'), $('mDotFill2'), $('mDotFill3')];
const lyBox = $('lyBox');
const lyList = $('lyList');
const btnPin = $('btnPin');
const toastEl = $('toast');
const peekMsg = $('peekMsg');
const pkIco = $('pkIco');
const pkTitle = $('pkTitle');
const pkSub = $('pkSub');
const pkMeter = $('pkMeter');
const contextMenu = $('contextMenu');
const clockEl = $('clock');
const miniClockEl = $('miniClock');
const petLayer = $('petLayer');
const playerEl = document.querySelector('.l-player');
const eyesEl = $('eyes');

const artBoxes = $$('.art-box');
const artMain = $('artMain');
const artImgs = $$('.js-art');
const titleEls = $$('.js-title');
const artistEls = $$('.js-artist');
const elapsedEls = $$('.js-elapsed');
const remainEls = $$('.js-remain');
const fillEls = $$('.js-fill');
const playIcons = $$('.js-play-icon');

const PATH_PLAY = ICONS.play;
const PATH_PAUSE = ICONS.pause;

function getApi() {
  return (window.pywebview && window.pywebview.api) || null;
}

// ========================================================
// 모션 도우미 (Web Animations API). `translate` / `scale` / `rotate` 개별 속성으로 애니메이션해서
// CSS 의 transform·transition 과 충돌하지 않는다. 모션 최소화 설정에서는 아무것도 하지 않는다.
// ========================================================
let SPRING = 'cubic-bezier(0.34, 1.56, 0.64, 1)';   // applyPrefs 가 탄성 설정에 맞춰 바꾼다
// 설정에서 온 애니메이션 값 (prefs.js 의 applyPrefs 가 채운다)
const PREF = { rate: 1, animOff: false, entrance: true, pageAnim: 'slide' };
const EASE_OUT = 'cubic-bezier(0.22, 1, 0.36, 1)';
function anim(el, keyframes, opts) {
  if (!el || REDUCED_MOTION || PREF.animOff || !el.animate) return null;
  try {
    const o = Object.assign({ easing: EASE_OUT, fill: 'backwards' }, opts);
    if (PREF.rate !== 1) {            // 속도 설정: 길이와 지연을 같은 비율로 줄이거나 늘린다
      if (o.duration) o.duration /= PREF.rate;
      if (o.delay) o.delay /= PREF.rate;
    }
    return el.animate(keyframes, o);
  } catch (e) { return null; }
}
// 여러 요소를 시차를 두고 차례로 등장시킨다
function enterEach(els, keyframes, delay, step, opts) {
  if (!PREF.entrance) return;
  Array.from(els).forEach((el, i) => anim(el, keyframes, Object.assign({ delay: delay + i * step }, opts)));
}
const RISE = [{ opacity: 0, translate: '0 10px' }, { opacity: 1, translate: '0 0' }];
const POP = [{ opacity: 0, scale: 0.55 }, { opacity: 1, scale: 1 }];
const FADE = [{ opacity: 0 }, { opacity: 1 }];

// textContent 읽기는 레이아웃을 강제하지 않지만 innerText 읽기는 강제한다. 같은 값이면 쓰지 않는다.
function setText(el, text) {
  if (el.textContent !== text) el.textContent = text;
}
function setTextAll(list, text) {
  for (const el of list) setText(el, text);
}

function formatTime(sec) {
  if (isNaN(sec) || sec < 0) sec = 0;
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m}:${s < 10 ? '0' : ''}${s}`;
}

function pad2(n) { return String(n).padStart(2, '0'); }
function todayKey() {
  const d = new Date();
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`;
}

// Precision continuous audio playhead
function getCurrentPlayhead() {
  if (!state.isPlaying || state.duration <= 0) {
    return playheadAnchorTime;
  }
  const elapsed = (performance.now() - playheadAnchorPerf) / 1000.0;
  return Math.min(state.duration, Math.max(0, playheadAnchorTime + elapsed));
}

function seekTo(sec) {
  const api = getApi();
  if (!api || !(state.duration > 0)) return;
  const tt = Math.max(0, Math.min(state.duration, sec));
  api.media_action('seek', tt);
  playheadAnchorTime = tt;
  playheadAnchorPerf = performance.now();
}

// ========================================================
// i18n 적용
// ========================================================
const langHooks = [];   // features.js 가 다시 그릴 함수를 등록한다

function applyLang() {
  document.documentElement.lang = HTML_LANG[lang];      // 'zh-Hans' / 'ja' 등: 언어별 글꼴과 맞춤법에 쓰인다
  for (const el of $$('[data-i18n]')) setText(el, t(el.dataset.i18n));
  for (const el of $$('[data-i18n-title]')) el.title = t(el.dataset.i18nTitle);
  for (const el of $$('[data-i18n-ph]')) el.placeholder = t(el.dataset.i18nPh);
  setText($('menuLangText'), `${t('menuLang')}: ${LANG_NAMES[lang]} → ${LANG_NAMES[LANGS[(LANGS.indexOf(lang) + 1) % LANGS.length]]}`);      // 지금 언어 → 누르면 넘어갈 언어 (한국어 → English → 简体中文 → 日本語 → 한국어 …)
  updateLyricsButtons();
  updateSoundMenu();
  setText($('menuPinText'), t(isPinned ? 'menuUnpin' : 'menuPin'));
  setTextAll(titleEls, state.title || t('noTrack'));
  buildList(hasLyricLines() ? state.lyrics.lines : null);   // 리스트의 안내 문구 갱신
  miniIdx = -1;
  for (const fn of langHooks) fn();
}

function toggleLang() {
  lang = LANGS[(LANGS.indexOf(lang) + 1) % LANGS.length];
  store.settings.lang = lang;
  saveStoreSoon();
  applyLang();
}

// ========================================================
// 뷰 상태 기계: idle / pet / mini / peek / music / lyrics / pomo / water / shelf / todo
// ========================================================
function hasLyricLines() {
  return !!(state.lyrics && state.lyrics.lines && state.lyrics.lines.length);
}

function lyricsOn() {
  return !!store.settings.lyricsOn;
}

function wordSyncOn() {
  return store.settings.wordSync !== false;
}

function hasTrack() {
  if (!state.title) return false;
  return state.isPlaying || (Date.now() - lastPlayingAt) < idleAfterMs();
}

// 음악 페이지는 가사 표시가 켜져 있고(가사를 불러오는 중이거나 있을 때) 곡이 있으면 가사 레이아웃(520px)이 된다
function expandedView() {
  if (page === 'music') {
    const lyricsLayout = lyricsOn() && !!state.title && (state.lyrics === null || hasLyricLines());
    return lyricsLayout ? 'lyrics' : 'music';
  }
  return page;
}

function petVisible(now) {
  if (!store.settings.pet) return false;
  return pet.idleSec >= petAfterSec() || now < pet.waveUntil;
}

function computeView() {
  if (isExpanded) return expandedView();
  if (peek.active) return 'peek';
  if (hasTrack()) return 'mini';
  if (island.dataset.timer === '1') return 'idle';
  return petVisible(Date.now()) ? 'pet' : 'idle';
}

function chipVisible() {
  return island.dataset.chip === '1' && !(typeof satOn === 'function' && satOn());   // 보조 노치가 켜져 있으면 큰 노치 안의 칩은 쓰지 않는다
}

// 어떤 뷰의 노치 크기. (updateView 가 view 를 바꾸기 전에 '곧 바뀔 뷰'의 크기가 필요한 곳에서 쓴다 — 보조 노치 위치)
function geometry() { return geometryFor(view); }

function geometryFor(v) {
  let g;
  if (v === 'mini') {
    g = compactMode ? STATES.compact : STATES.mini;
    if (chipVisible()) g = { w: g.w + CHIP_EXTRA_W, h: g.h, e: g.e };
    if (!compactMode && island.dataset.bg === '1') g = { w: g.w, h: g.h + BG_EXTRA_H, e: g.e };
    return g;
  }
  if (v === 'peek') return STATES['peek_' + peek.kind] || STATES.peek_track;
  return STATES[v] || STATES.mini;
}

const PAGE_VIEWS = ['music', 'lyrics', 'pomo', 'timer', 'water', 'shelf', 'todo', 'clip', 'agenda', 'launcher', 'plugins', 'buds'];
const isPageView = (v) => PAGE_VIEWS.includes(v);
const layerOf = (v) => ((v === 'music' || v === 'lyrics') ? 'player' : v);
let pageDir = 1;   // 페이지를 넘기는 방향 (+1: 오른쪽 페이지로, -1: 왼쪽으로)

// 플레이어 레이어의 배치(music <-> lyrics). snap=true 면 이동 애니메이션 없이 제자리에 놓는다(다른 페이지에서 막 들어올 때)
function setPlayerMode(mode, snap) {
  if (playerEl.dataset.mode === mode) return;
  if (snap) playerEl.classList.add('snap');
  playerEl.dataset.mode = mode;
  if (snap) { void playerEl.offsetWidth; playerEl.classList.remove('snap'); }
}

// 이전 전환에서 걸어 둔 스크립트(WAAPI) 애니메이션을 정리한다. CSS transition/animation 은 건드리지 않는다
// (취소하면 끝값으로 튀어 깜빡이므로). 빠르게 연달아 전환해도 애니메이션이 쌓이지 않게 한다.
function cancelScriptAnimations(root) {
  if (!root || !root.getAnimations) return;
  for (const a of root.getAnimations({ subtree: true })) {
    const n = a.constructor && a.constructor.name;
    if (n !== 'CSSTransition' && n !== 'CSSAnimation') a.cancel();
  }
}

// 페이지 레이어끼리 방향 있는 슬라이드: 나가는 쪽은 빠르게 밀려나고, 들어오는 쪽은 탄성 있게 자리 잡는다
function slideLayers(fromName, toName, dir) {
  cancelScriptAnimations(document.querySelector('.l-' + fromName));
  cancelScriptAnimations(document.querySelector('.l-' + toName));
  anim(document.querySelector('.l-' + fromName), [{ translate: '0 0' }, { translate: `${-dir * 26}px 0` }],
       { duration: 240, easing: 'cubic-bezier(0.4, 0, 1, 1)', fill: 'none' });
  anim(document.querySelector('.l-' + toName), [{ translate: `${dir * 36}px 0` }, { translate: '0 0' }],
       { duration: 680, delay: 90, easing: SPRING });
}

// 가사를 켤 때 보이는 줄들이 위에서부터 차례로 들어온다 (리스트 위치가 잡힌 뒤의 보이는 줄만)
function staggerLyrics() {
  requestAnimationFrame(() => requestAnimationFrame(() => {
    const box = lyBox.getBoundingClientRect();
    const vis = Array.from(lyList.children).filter((li) => {
      const r = li.getBoundingClientRect();
      return r.bottom > box.top && r.top < box.bottom;
    });
    enterEach(vis, [{ opacity: 0, translate: '22px 0' }, { opacity: 1, translate: '0 0' }], 260, 55, { duration: 620, easing: EASE_OUT });
  }));
}

// 나간 레이어는 페이드가 끝난 뒤(0.3s) .off(display:none)로 치우고, 다시 들어오면 즉시 뗀다.
// visibility 로 숨기면 빠른 연속 전환에서 자손 요소가 hidden 으로 남는 크롬 문제가 있다(island.css .ly 설명 참고).
const layerEls = Array.from(document.querySelectorAll('.ly'));
const layerOffTimers = new Map();
function syncLayerVisibility(activeName) {
  for (const el of layerEls) {
    const active = el.classList.contains('l-' + activeName);
    clearTimeout(layerOffTimers.get(el));
    if (active) {
      // 레이어를 먼저 표시해 레이아웃을 확정한 뒤 자식 요소에 연출을 건다 (이어서 enterAnim 이 위치를 재고 애니메이션을 건다)
      if (el.classList.contains('off')) { el.classList.remove('off'); void el.offsetWidth; }
    } else if (!el.classList.contains('off')) {
      layerOffTimers.set(el, setTimeout(() => el.classList.add('off'), PREF.animOff ? 0 : 300 / PREF.rate));
    }
  }
}

function updateView() {
  const next = computeView();
  if (typeof renderSat === 'function') renderSat(next);
  if (island.dataset.pk !== peek.kind) island.dataset.pk = peek.kind;
  if (next === view) return;
  const prev = view;
  view = next;
  if (next === 'music' || next === 'lyrics') setPlayerMode(next, !(prev === 'music' || prev === 'lyrics'));
  island.dataset.s = next;
  syncLayerVisibility(layerOf(next));
  // 뷰가 바뀌면 mini 는 줄을 다시 그리고, 세로 리스트는 다음 배치를 애니메이션 없이 즉시 맞춘다.
  // (리스트의 활성 줄 상태는 DOM 과 함께 유지해야 하므로 listIdx 는 건드리지 않는다)
  miniIdx = -1;
  listFresh = true;
  scheduleRegion();

  if (prev !== null && isPageView(next) && layerOf(next) !== layerOf(prev)) {
    if (isPageView(prev) && PREF.pageAnim === 'slide') slideLayers(layerOf(prev), layerOf(next), pageDir);
    if (PREF.entrance && typeof enterAnim === 'function') enterAnim(layerOf(next));
  }
  if (next === 'lyrics' && prev !== 'lyrics') staggerLyrics();
  pageDir = 1;
}

function setPage(p, dir) {
  if (p !== page) {
    const order = parseTabOrder(store.settings.tabOrder);
    const a = order.indexOf(page), b = order.indexOf(p);   // 방향은 전체 순서 기준
    pageDir = dir || (b >= a ? 1 : -1);
  }
  page = p;
  island.dataset.p = p;
  for (const dot of $$('#pageDots i')) dot.classList.toggle('on', dot.dataset.p === p);
  // 데이터 갱신을 먼저: 레이어가 들어오며 항목에 등장 연출을 걸기 때문에, 그 뒤에 목록을 다시 그리면 연출이 사라진다
  if (typeof onPageShown === 'function') onPageShown(p);
  updateView();
}

function stepPage(dir) {
  const list = availablePages();
  const i = Math.max(0, list.indexOf(page));
  setPage(list[(i + dir + list.length) % list.length], dir);
}

// ========================================================
// 알림: 접힌 상태에서는 노치가 잠깐 나타나는 peek, 펼친 상태에서는 노치 안쪽 토스트
// ========================================================
function setIcon(el, name, tone) {
  el.innerHTML = iconSvg(name);
  el.dataset.tone = tone || '';
}

function startPeekTimer(ms) {
  peek.active = true;
  clearTimeout(peek.timer);
  peek.timer = setTimeout(() => { peek.active = false; peek.key = ''; updateView(); }, ms);
  updateView();
}

// 설정 '알림 표시 시간'(100% = 기본)을 모든 접힌 상태 알림(곡이 바뀔 때, 문구, 시스템 알림)에 같게 적용한다
const peekMs = (ms) => ms * (clampN(store.settings.peekTime, 30, 400, 100) / 100);

function showTrackPeek() {
  if (store.settings.notify && store.settings.notify.track === false) return;
  peek.kind = 'track';
  startPeekTimer(peekMs(PEEK_MS));
  // 앨범 아트는 공유 요소가 이동해 오고, 텍스트는 옆에서 스며든다
  enterEach(document.querySelectorAll('.pk-track .pk-title, .pk-track .pk-artist'),
            [{ opacity: 0, translate: '16px 0' }, { opacity: 1, translate: '0 0' }], 230, 60, { duration: 520 });
}

let toastTimer = null;
function showToast(msg) {
  if (isExpanded) {
    toastEl.textContent = msg;
    toastEl.classList.add('show');
    island.classList.add('toasting');   // 토스트가 있는 동안 페이지 도트는 숨긴다
    clearTimeout(toastTimer); // 연속 호출 시 이전 타이머가 새 토스트를 일찍 닫지 않도록
    toastTimer = setTimeout(() => { toastEl.classList.remove('show'); island.classList.remove('toasting'); }, 1500);
  } else {
    peek.kind = 'msg';
    setText(peekMsg, msg);
    startPeekTimer(peekMs(1700));
  }
}

// opts: { icon, tone, title, sub, meter(0~1), ms, key }
// key(예: 'volume')가 같은 알림이 이미 떠 있으면 등장 연출을 다시 하지 않고 값만 갱신한다 (볼륨을 계속 조절할 때 연출이 반복되지 않게).
function notify(opts) {
  opts = Object.assign({}, opts, { ms: (opts.ms || 2600) * (clampN(store.settings.peekTime, 30, 400, 100) / 100) });   // 표시 시간 설정
  if (isExpanded) {
    showToast(opts.sub ? `${opts.title} · ${opts.sub}` : opts.title);
    return;
  }
  const live = !!opts.key && peek.active && peek.kind === 'info' && peek.key === opts.key;
  peek.kind = 'info';
  peek.key = opts.key || '';
  setIcon(pkIco, opts.icon, opts.tone);
  setText(pkTitle, opts.title);
  setText(pkSub, opts.sub || '');
  const hasMeter = typeof opts.meter === 'number';
  pkMeter.classList.toggle('on', hasMeter);
  if (hasMeter) pkMeter.firstElementChild.style.width = `${Math.round(Math.max(0, Math.min(1, opts.meter)) * 100)}%`;
  if (live) {   // 이미 보이는 중: 막대/숫자만 바뀌고, 표시 시간만 연장한다
    clearTimeout(peek.timer);
    peek.timer = setTimeout(() => { peek.active = false; peek.key = ''; updateView(); }, opts.ms || 2600);
    return;
  }
  startPeekTimer(opts.ms || 2600);
  anim(pkIco, [{ opacity: 0, scale: 0.35, rotate: '-28deg' }, { opacity: 1, scale: 1, rotate: '0deg' }], { duration: 560, delay: 150, easing: SPRING });
  enterEach([pkTitle, pkSub], [{ opacity: 0, translate: '14px 0' }, { opacity: 1, translate: '0 0' }], 220, 55, { duration: 460 });
  if (hasMeter) anim(pkMeter, [{ opacity: 0, scale: '0.6 1' }, { opacity: 1, scale: '1 1' }], { duration: 420, delay: 300 });
}

function playChime(kind) {
  const api = getApi();
  if (store.settings.sound && api && api.chime) api.chime(kind);
}

// ========================================================
// 창 클릭 영역(SetWindowRgn): 노치(귀 + 스프링 오버슈트 여유 포함)만 클릭되고 나머지는 통과
// ========================================================
let regionTimer = null;
let appliedSize = { w: 0, h: 0 };

function targetPillRect() {
  const g = geometry();
  const pad = g.e + 8;
  const left = (window.innerWidth - g.w) / 2 - pad;
  const satRight = typeof satRegionRight === 'function' ? satRegionRight(g, pad) : 0;
  const satLeft = typeof satRegionLeft === 'function' ? satRegionLeft(g, pad) : Infinity;
  return {
    left: Math.min(left, satLeft), right: Math.max(left + g.w + pad * 2, satRight), top: 0, bottom: g.h + 4,
    width: g.w, height: g.h,
    dpr: window.devicePixelRatio || 1
  };
}

// UI 크기(확대 배율)가 바뀌면 창 크기/devicePixelRatio 가 바뀐다: 클릭 영역을 다시 맞춘다
let lastDpr = window.devicePixelRatio;
window.addEventListener('resize', () => {
  if (window.devicePixelRatio !== lastDpr) { lastDpr = window.devicePixelRatio; scheduleRegion(true); }
});

function applyRegion() {
  const api = getApi();
  if (!api || contextMenuOpen) return;
  const g = geometry();
  const r = targetPillRect();
  if (isExpanded) {
    if (api.expand_window) api.expand_window(r);
  } else if (api.collapse_window) {
    api.collapse_window(r);
  }
  appliedSize = { w: g.w, h: g.h };
}

// 커질 때는 즉시(애니메이션보다 먼저 영역을 넓혀야 안 잘림), 작아질 때는 애니메이션이 끝난 뒤.
function scheduleRegion(force) {
  clearTimeout(regionTimer);
  if (contextMenuOpen) return;
  const g = geometry();
  const grow = g.w > appliedSize.w || g.h > appliedSize.h;
  if (force || grow) applyRegion();
  else regionTimer = setTimeout(applyRegion, PREF.animOff ? 60 : Math.round(700 / (PREF.rate || 1)));      // 줄어드는 전환이 끝난 뒤에 영역을 줄인다: 애니메이션 속도(느리게)에 맞춰야 도중에 잘리지 않는다
}

// ========================================================
// 앨범 아트 / 앰비언트 색
// ========================================================
const artColorCache = new Map();

function applyAmbient(c) {
  const s = Math.round(Math.max(45, Math.min(85, c.s * 100)));
  island.style.setProperty('--art-a', `hsl(${c.h} ${s}% 38%)`);
  island.style.setProperty('--art-b', `hsl(${(c.h + 28) % 360} ${s}% 26%)`);
  document.documentElement.style.setProperty('--art-a', `hsl(${c.h} ${s}% 38%)`);       // 섬 바깥의 보조 노치(물방울)도 앨범 색 테마를 쓴다
  document.documentElement.style.setProperty('--art-b', `hsl(${(c.h + 28) % 360} ${s}% 26%)`);
}

function updateArtColor(url) {
  if (!url) { applyAmbient({ h: 215, s: 0.6 }); return; }
  if (artColorCache.has(url)) { applyAmbient(artColorCache.get(url)); return; }
  const img = new Image();
  img.crossOrigin = 'anonymous';   // 아트워크 CDN 이 CORS 를 허용해야 픽셀을 읽을 수 있다. 실패하면 기본색.
  img.onload = () => {
    try {
      const N = 24;
      const cv = document.createElement('canvas');
      cv.width = cv.height = N;
      const ctx = cv.getContext('2d', { willReadFrequently: true });
      ctx.drawImage(img, 0, 0, N, N);
      const d = ctx.getImageData(0, 0, N, N).data;
      // 색상(hue) 12구간에 채도*명도로 가중해 쌓고, 가장 무거운 구간의 평균을 대표색으로 쓴다.
      const bins = Array.from({ length: 12 }, () => ({ w: 0, hx: 0, hy: 0, s: 0 }));
      for (let i = 0; i < d.length; i += 4) {
        const r = d[i] / 255, g = d[i + 1] / 255, b = d[i + 2] / 255;
        const mx = Math.max(r, g, b), mn = Math.min(r, g, b), df = mx - mn;
        if (mx < 0.15) continue;
        const sat = mx === 0 ? 0 : df / mx;
        if (sat < 0.12) continue;
        let h;
        if (df === 0) h = 0;
        else if (mx === r) h = ((g - b) / df) % 6;
        else if (mx === g) h = (b - r) / df + 2;
        else h = (r - g) / df + 4;
        h = ((h * 60) + 360) % 360;
        const wgt = sat * mx;
        const bin = bins[Math.floor(h / 30) % 12];
        bin.w += wgt; bin.s += sat * wgt;
        bin.hx += Math.cos(h * Math.PI / 180) * wgt;
        bin.hy += Math.sin(h * Math.PI / 180) * wgt;
      }
      let best = bins[0];
      for (const b of bins) if (b.w > best.w) best = b;
      const c = best.w > 0
        ? { h: Math.round(((Math.atan2(best.hy, best.hx) * 180 / Math.PI) + 360) % 360), s: best.s / best.w }
        : { h: 215, s: 0.35 };   // 흑백 아트는 차분한 푸른 회색
      artColorCache.set(url, c);
      if (url === state.artworkUrl) applyAmbient(c);
    } catch (e) {
      if (url === state.artworkUrl) applyAmbient({ h: 215, s: 0.6 });
    }
  };
  img.onerror = () => { if (url === state.artworkUrl) applyAmbient({ h: 215, s: 0.6 }); };
  img.src = url;
}

// ========================================================
// Python 브리지 폴링
// ========================================================
// setInterval 은 응답이 늦어지면 호출이 겹쳐 쌓이므로, 응답을 받은 뒤에 다음 호출을 예약한다.
let pollInFlight = false;
let pollTimer = null;
async function pollState() {
  if (pollInFlight) return;   // 겹쳐 호출돼도 한 번에 하나만
  pollInFlight = true;
  try {
    const api = getApi();
    if (api && api.get_state) {
      const res = await api.get_state(state.lyricsVersion);
      if (res) {
        handleStateUpdate(res);
      }
    }
  } catch (e) {
    console.error(e);
  } finally {
    pollInFlight = false;
    clearTimeout(pollTimer);
    pollTimer = setTimeout(pollState, performance.now() < pollBoostUntil ? POLL_BOOST_MS : POLL_MS);
  }
}
// 파이썬이 중요한 이벤트(파일 드롭 등)를 큐에 넣은 직후 호출해, 다음 폴링 주기를 기다리지 않고 바로 가져온다
// 재생 컨트롤: 누르는 순간 화면부터 바꾸고(낙관적 갱신) 실제 값이 오면 맞춘다. 누른 직후 잠시 상태를 자주 읽는다.
function mediaAct(action, arg) {
  const api = getApi();
  if (!api || !api.media_action) return;
  if (action === 'toggle' && state.title) {
    const want = !state.isPlaying;
    const nowPos = getCurrentPlayhead();
    state.isPlaying = want;
    playheadAnchorTime = nowPos;
    playheadAnchorPerf = performance.now();
    island.classList.toggle('playing', want);
    for (const p of playIcons) p.setAttribute('d', want ? PATH_PAUSE : PATH_PLAY);
    if (isExpanded) anim(document.querySelector('.l-player .js-toggle svg'), [{ transform: 'scale(0.65)' }, { transform: 'scale(1)' }], { duration: 380, easing: SPRING });
    playHoldUntil = performance.now() + 900;
  }
  pollBoostUntil = performance.now() + 1800;
  Promise.resolve(api.media_action(action, arg)).then(() => pollNow(), () => pollNow());
}

function pollNow() {
  clearTimeout(pollTimer);
  pollState();
}

function handleStateUpdate(res) {
  const prevTrackId = state.trackId;
  const isTrackChange = state.trackId !== res.trackId;
  if (performance.now() < playHoldUntil) {
    if (res.isPlaying !== state.isPlaying) res = Object.assign({}, res, { isPlaying: state.isPlaying });   // 방금 누른 결과를 옛 서버 값이 되돌리지 않게
  } else playHoldUntil = 0;
  const playStateChange = state.isPlaying !== res.isPlaying;
  const prevArt = state.artworkUrl;

  state.isPlaying = res.isPlaying;
  state.duration = res.duration || 0;
  state.title = res.title || "";
  state.artist = res.artist || "";
  state.album = res.album || "";
  state.artworkUrl = res.artworkUrl || "";
  state.trackId = res.trackId || "";

  // 'lyrics' 키는 서버가 보유한 가사 버전이 바뀐 경우에만 온다. null 도 유효한 값이다
  // (곡이 바뀌어 이전 곡 가사를 비운 것). null 을 무시하면 이전 곡 가사가 새 곡에 남는다.
  if ('lyrics' in res) {
    state.lyrics = res.lyrics || null;
    miniIdx = -1;   // 세로 리스트는 renderList 가 lyrics 객체가 바뀐 걸 보고 알아서 다시 만든다
  }
  state.lyricsVersion = res.lyricsVersion;

  // 일시정지 상태로 앱을 켰어도 곡이 처음 잡히면 바로 시계로 돌아가지 않도록 기준 시각을 갱신
  if (state.isPlaying || (isTrackChange && state.title)) lastPlayingAt = Date.now();

  if (!state.isPlaying) {
    playheadAnchorTime = res.currentTime || 0;
    playheadAnchorPerf = performance.now();
  } else {
    const local = getCurrentPlayhead();
    const drift = Math.abs((res.currentTime || 0) - local);
    if (isTrackChange || playStateChange || drift > 0.25) {
      playheadAnchorTime = res.currentTime || 0;
      playheadAnchorPerf = performance.now();
    }
  }
  island.classList.toggle('playing', state.isPlaying);

  // 반복/셔플: 방금 사용자가 눌렀다면 잠시 서버 값을 무시한다 (적용되기 전의 옛 값이 깜빡이며 되돌리는 것 방지)
  if (performance.now() >= modeHoldUntil) {
    state.repeat = res.repeat || 'none';
    state.shuffle = !!res.shuffle;
  }
  // 반복/셔플을 지원하지 않는 앱(윈도우 미디어 세션으로 읽는 일부 앱)에서는 두 버튼을 흐리게 하고 누를 수 없게 한다
  island.dataset.nomode = res.canMode === false ? '1' : '';
  renderModes();

  // 아트 (같은 값이면 건드리지 않는다)
  if (state.artworkUrl) {
    for (const img of artImgs) {
      if (img.getAttribute('src') !== state.artworkUrl) img.src = state.artworkUrl;
    }
  }
  for (const box of artBoxes) box.classList.toggle('has', !!state.artworkUrl);
  if (state.artworkUrl !== prevArt) updateArtColor(state.artworkUrl);

  // 텍스트
  setTextAll(titleEls, state.title || t('noTrack'));
  setTextAll(artistEls, state.artist);

  // 재생 상태가 바뀔 때만 아이콘 교체
  if (playStateChange || isTrackChange || !playIcons[0].getAttribute('data-ok')) {
    for (const p of playIcons) {
      p.setAttribute('d', state.isPlaying ? PATH_PAUSE : PATH_PLAY);
      p.setAttribute('data-ok', '1');
    }
  }

  if (isTrackChange && prevTrackId && state.title && isExpanded && (view === 'music' || view === 'lyrics')) {
    // 곡이 바뀌면 앨범 아트가 톡 튀어 오르고 제목/아티스트가 위로 스며든다
    anim($('artIn'), [{ transform: 'scale(0.8) rotate(-5deg)' }, { transform: 'none' }], { duration: 640, easing: SPRING });
    enterEach($$('.l-player .js-title, .l-player .js-artist'), RISE, 60, 60, { duration: 480 });
  }
  if (playStateChange && isExpanded) {
    anim(document.querySelector('.l-player .js-toggle svg'), [{ transform: 'scale(0.65)' }, { transform: 'scale(1)' }], { duration: 380, easing: SPRING });
  }

  if (isTrackChange) {
    miniIdx = -1;
    currentMiniScrollX = 0;
    targetMiniScrollX = 0;
    lastMiniX = null;
    // 접힌 상태에서 곡이 바뀌면 노치가 잠깐 곡 정보를 보여준다 (앱 시작 직후 첫 곡은 제외)
    if (prevTrackId && state.trackId && state.title && !isExpanded) showTrackPeek();
  }

  if (typeof checkUpNext === 'function') checkUpNext(res);
  if (typeof updateSourceBtn === 'function') updateSourceBtn(res);
  if (res.buds && typeof updateBuds === 'function') updateBuds(res.buds);

  // 사용자 입력이 없었던 시간 -> 캐릭터(눈) 상태
  if (typeof res.idleSec === 'number') updatePet(res.idleSec);

  // 시스템 이벤트(볼륨/Caps Lock/충전기/네트워크/오디오 장치/파일 드롭 ...)
  if (res.events && res.events.length && typeof handleSysEvent === 'function') {
    for (const e of res.events) handleSysEvent(e);
  }

  updateView();
}

// ========================================================
// 캐릭터(눈): 한동안 입력이 없으면 시계 대신 나타나고, 더 지나면 졸고, 돌아오면 인사한다
// ========================================================
function updatePet(idleSec) {
  const now = Date.now();
  if (pet.idleSec >= petDozeSec()) pet.dozed = true;
  if (idleSec < 2 && pet.dozed) {          // 졸던 중에 입력이 돌아왔다 -> 인사
    pet.dozed = false;
    pet.waveUntil = now + PET_WAVE_MS;
  }
  pet.idleSec = idleSec;
  let mode = 'awake';
  if (now < pet.waveUntil) mode = 'wave';
  else if (idleSec >= petDozeSec()) mode = 'doze';
  if (mode !== pet.mode) {
    pet.mode = mode;
    petLayer.dataset.mode = mode;
  }
  if (mode === 'wave') setTimeout(updateView, PET_WAVE_MS + 50);   // 인사가 끝나면 시계로
}

// 눈동자가 가끔 두리번거린다
function lookAround() {
  if (pet.mode === 'awake' && view === 'pet') {
    const lx = (Math.random() * 3 - 1.5).toFixed(1);
    const ly = (Math.random() * 3 - 1.5).toFixed(1);
    eyesEl.style.setProperty('--lx', `${lx}px`);
    eyesEl.style.setProperty('--ly', `${ly}px`);
  }
}

// ========================================================
// 가사 위치 계산 (순수 함수)
// ========================================================
function locate(nowSec, lines) {
  let idx = -1;
  let interlude = false;
  let iStart = 0;
  let iEnd = 0;
  let nextIdx = -1;

  if (nowSec < lines[0].start) {
    // 1. 첫 줄 전 인트로
    if (lines[0].start - nowSec >= 1.5) {
      interlude = true;
      iStart = 0;
      iEnd = lines[0].start;
      nextIdx = 0;
    } else {
      idx = 0;
    }
  } else {
    // 2. 줄 / 간주 판정
    for (let i = 0; i < lines.length; i++) {
      const l = lines[i];
      const nextL = (i + 1 < lines.length) ? lines[i + 1] : null;

      if (nowSec >= l.start && nowSec <= l.end) {
        idx = i;
        break;
      } else if (nextL && nowSec > l.end && nowSec < nextL.start) {
        const gap = nextL.start - l.end;
        if (gap >= 3.2) {
          if (nowSec <= l.end + 0.6) {
            idx = i;
          } else {
            interlude = true;
            iStart = l.end + 0.6;
            iEnd = nextL.start;
            nextIdx = i + 1;
          }
        } else {
          idx = (nowSec >= nextL.start - 0.4) ? i + 1 : i;
        }
        break;
      } else if (i === lines.length - 1 && nowSec > l.end) {
        if (nowSec <= l.end + 2.0) {
          idx = i;
        } else {
          interlude = true;
          iStart = l.end + 2.0;
          iEnd = state.duration || (l.end + 15.0);
          nextIdx = -1;   // 마지막 줄 뒤(아웃트로)
        }
      }
    }
  }
  return { idx, interlude, iStart, iEnd, nextIdx };
}

function dotProgress(pos, nowSec) {
  const total = Math.max(0.1, pos.iEnd - pos.iStart);
  const progress = Math.min(1, Math.max(0, (nowSec - pos.iStart) / total));
  // Dot 1, 2, 3 를 순서대로 채운다
  return [
    Math.min(1, Math.max(0, progress * 3)),
    Math.min(1, Math.max(0, progress * 3 - 1)),
    Math.min(1, Math.max(0, progress * 3 - 2))
  ];
}

function paintDots(dotEls, fillEls2, ps) {
  for (let k = 0; k < 3; k++) {
    fillEls2[k].style.width = `${(ps[k] * 100).toFixed(1)}%`;
    dotEls[k].classList.toggle('filled', ps[k] >= 0.99);
  }
}

// 단어 하이라이트: 진행 중인 단어만 매 프레임 --wp 를 갱신하고, 상태가 바뀔 때만 클래스를 바꾼다.
function syncWords(words, els, states, nowSec, base) {
  for (let w = 0; w < words.length; w++) {
    const word = words[w];
    const el = els[w];
    let st;   // 0: 대기, 1: 진행 중, 2: 완료
    if (nowSec >= word.end) st = 2;
    else if (nowSec >= word.start) st = 1;
    else st = 0;

    if (st === 1) {
      const p = Math.min(1, Math.max(0, (nowSec - word.start) / Math.max(0.01, word.end - word.start)));
      el.style.setProperty('--wp', `${(p * 100).toFixed(1)}%`);
    }
    if (states[w] !== st) {
      const prev = states[w];
      states[w] = st;
      // 진행 중이던 단어가 끝날 때만 글로우가 서서히 꺼진다. 건너뛰어 완료된 단어는 바로 완료 모양(instant)
      el.className = st === 2 ? `${base} completed${prev === 1 ? '' : ' instant'}` : (st === 1 ? `${base} active` : base);
    }
  }
}

// 현재 시각이 단어 배열 안 어디쯤인지 px 위치로 환산 (텔레프롬프터 스크롤 기준점)
function wordCursorX(words, els, nowSec) {
  const first = words[0];
  const last = words[words.length - 1];

  if (nowSec <= first.start) {
    return els[0].offsetLeft;
  }
  if (nowSec >= last.end) {
    const lastEl = els[els.length - 1];
    return lastEl.offsetLeft + lastEl.offsetWidth;
  }
  for (let w = 0; w < words.length; w++) {
    const word = words[w];
    const el = els[w];
    if (nowSec >= word.start && nowSec <= word.end) {
      const p = (nowSec - word.start) / Math.max(0.001, word.end - word.start);
      return el.offsetLeft + p * el.offsetWidth;
    }
    if (w + 1 < words.length && nowSec > word.end && nowSec < words[w + 1].start) {
      const nextEl = els[w + 1];
      const p = (nowSec - word.end) / Math.max(0.001, words[w + 1].start - word.end);
      const endX = el.offsetLeft + el.offsetWidth;
      return endX + p * (nextEl.offsetLeft - endX);
    }
  }
  return 0;
}

// 단어 span 들을 부모에 채운다. 원문에서 단어 뒤에 공백이 있었던 경우에만 띄운다
// (음절 단위 가사가 "Hel lo" 로 갈라지지 않도록).
function fillWords(parent, words, cls) {
  const els = [];
  words.forEach((w, i) => {
    const span = document.createElement('span');
    span.className = cls;
    span.textContent = w.text;
    span.dataset.t = w.text;          // CSS ::after 가 같은 글자를 흰색으로 얹는다 (단어 하이라이트)
    parent.appendChild(span);
    els.push(span);
    if (w.space !== false && i < words.length - 1) parent.appendChild(document.createTextNode(' '));
  });
  return els;
}

// ========================================================
// 렌더: 가사 (mini 한 줄 / lyrics 세로 리스트)
// ========================================================
function renderLyrics(nowSec) {
  // 가사 표시가 꺼져 있거나 시간 정보가 없는 가사는 한 줄 실시간 표시를 할 수 없으니 곡 정보를 보인다
  const lines = (lyricsOn() && hasLyricLines() && !state.lyrics.unsynced) ? state.lyrics.lines : null;

  if (view === 'lyrics') {
    renderList(hasLyricLines() ? state.lyrics.lines : null, nowSec);
  } else if (view === 'mini' && !compactMode) {
    renderMini(lines, nowSec);
  }
}

// ---------- MINI ----------
let miniIdx = -1;
let miniWordEls = [];
let miniWordStates = [];
let miniInterlude = false;
let currentMiniScrollX = 0;
let targetMiniScrollX = 0;
let lastMiniX = null;
const miniMetrics = { box: 0, line: 0 };

function setMiniInterlude(on) {
  if (miniInterlude === on) return;
  miniInterlude = on;
  miniDots.classList.toggle('active', on);
  miniLyricLine.style.display = on ? 'none' : 'inline-block';
}

function buildMiniLine(line) {
  miniLyricLine.textContent = '';
  miniWordEls = [];
  miniWordStates = [];

  if (wordSyncOn() && line.words && line.words.length > 0) {
    miniLyricLine.className = 'mini-lyric-line';
    miniWordEls = fillWords(miniLyricLine, line.words, 'mini-word');
    miniWordStates = new Array(line.words.length).fill(0);
  } else {
    miniLyricLine.className = 'mini-lyric-line line-sync';
    miniLyricLine.textContent = line.text || "♪";
  }

  // 줄이 바뀔 때 아래에서 살짝 떠오르며 나타난다.
  // Web Animations API + 개별 `translate` 속성은 스크롤용 transform 과 충돌하지 않는다.
  anim(miniLyricLine, [{ opacity: 0.3, translate: '0 3px' }, { opacity: 1, translate: '0 0' }], { duration: 240, easing: 'ease', fill: 'none' });
}

// ---------- 백그라운드 보컬 (작은 노치) ----------
// 본 줄과 따로, 지금 시각에 걸쳐 있는 bg 줄을 찾는다. 너무 짧은 것(<0.8초)은 작은 노치를 흔들 만큼의 가치가 없어서 건너뛴다(전체 가사 목록에는 나온다).
const BG_MIN_SEC = 0.8, BG_LEAD = 0.35, BG_HOLD = 0.45;
let miniBgIdx = -1, miniBgWordEls = [], miniBgWordStates = [], miniBgHideAt = 0, miniBgScrollX = 0;
let miniBgFor = null;

function findMiniBg(nowSec) {
  const bg = state.lyrics && state.lyrics.bg;
  if (!bg || !bg.length) return -1;
  for (let i = 0; i < bg.length; i++) {
    const b = bg[i];
    if (b.end - b.start < BG_MIN_SEC) continue;
    if (nowSec >= b.start - BG_LEAD && nowSec <= b.end + BG_HOLD) return i;
    if (b.start - BG_LEAD > nowSec) break;
  }
  return -1;
}

function setMiniBgOpen(on) {
  const cur = island.dataset.bg === '1';
  if (cur === on) return;
  if (on) island.dataset.bg = '1'; else delete island.dataset.bg;
  scheduleRegion(on);
}

function renderMiniBg(nowSec, enabled) {
  if (miniBgFor !== state.lyrics) { miniBgFor = state.lyrics; miniBgIdx = -1; }      // 곡/가사가 바뀌면 처음부터
  const idx = enabled ? findMiniBg(nowSec) : -1;
  const now = performance.now();
  if (idx >= 0) {
    miniBgHideAt = now + 700;                       // 바로 다음 bg 줄이 이어질 때 노치가 접혔다 펴지지 않게 잠깐 유지
    setMiniBgOpen(true);
    const b = state.lyrics.bg[idx];
    if (idx !== miniBgIdx) {
      miniBgIdx = idx;
      miniBgLine.textContent = '';
      miniBgWordEls = []; miniBgWordStates = [];
      if (wordSyncOn() && b.words && b.words.length) {
        miniBgWordEls = fillWords(miniBgLine, b.words, 'mini-word');
        miniBgWordStates = new Array(b.words.length).fill(0);
      } else {
        miniBgLine.textContent = b.text;
        miniBgLine.style.color = 'rgba(255,255,255,0.85)';
      }
      if (miniBgWordEls.length) miniBgLine.style.color = '';
      miniBgScrollX = 0;
    }
    const boxW = miniBg.clientWidth, lineW = miniBgLine.scrollWidth;
    if (miniBgWordEls.length === (b.words || []).length && miniBgWordEls.length) {
      syncWords(b.words, miniBgWordEls, miniBgWordStates, nowSec, 'mini-word');
      if (lineW > boxW) {
        miniBg.classList.add('scrolling');
        const cur = wordCursorX(b.words, miniBgWordEls, nowSec);
        miniBgScrollX = Math.max(boxW - lineW - 6, Math.min(0, boxW / 2 - cur));
      } else { miniBg.classList.remove('scrolling'); miniBgScrollX = (boxW - lineW) / 2; }
    } else {
      miniBg.classList.toggle('scrolling', lineW > boxW);
      miniBgScrollX = lineW > boxW ? Math.max(boxW - lineW - 6, Math.min(0, -((nowSec - b.start) / Math.max(0.5, b.end - b.start)) * (lineW - boxW))) : (boxW - lineW) / 2;
    }
    miniBgLine.style.transform = `translateX(${miniBgScrollX.toFixed(1)}px)`;
  } else if (island.dataset.bg === '1' && now > miniBgHideAt) {
    setMiniBgOpen(false);
    miniBgIdx = -1;
  }
}

function renderMini(lines, nowSec) {
  renderMiniBg(nowSec, !!lines && !chipVisible());
  if (!lines) {
    // 가사 없음/로딩 중/표시 꺼짐: 간주 표시를 해제하고 곡 정보를 가운데에 보여준다
    setMiniInterlude(false);
    const fallbackText = state.artist ? `${state.artist} - ${state.title}` : (state.title || "♪");
    if (miniLyricLine.textContent !== fallbackText || !miniLyricLine.classList.contains('static')) {
      miniLyricLine.className = 'mini-lyric-line static';
      miniLyricLine.textContent = fallbackText;
      miniWordEls = [];
      miniIdx = -1;
      targetMiniScrollX = 0;
      currentMiniScrollX = 0;
      lastMiniX = null;
      miniLyricBox.classList.remove('scrolling');
    }
    return;
  }

  const pos = locate(nowSec, lines);

  if (pos.interlude) {
    miniIdx = -999;
    setMiniInterlude(true);
    paintDots(mDots, mFills, dotProgress(pos, nowSec));
    return;
  }
  setMiniInterlude(false);

  if (pos.idx !== -1 && pos.idx !== miniIdx && pos.idx < lines.length) {
    miniIdx = pos.idx;
    buildMiniLine(lines[miniIdx]);
  }
  if (miniIdx < 0 || miniIdx >= lines.length) return;

  const line = lines[miniIdx];
  const boxW = miniLyricBox.clientWidth;
  const lineW = miniLyricLine.scrollWidth;
  miniMetrics.box = boxW;
  miniMetrics.line = lineW;

  if (wordSyncOn() && line.words && line.words.length > 0 && miniWordEls.length === line.words.length) {
    syncWords(line.words, miniWordEls, miniWordStates, nowSec, 'mini-word');

    if (lineW > boxW) {
      miniLyricBox.classList.add('scrolling');
      const cursorX = wordCursorX(line.words, miniWordEls, nowSec);
      const idealTargetX = (boxW / 2) - cursorX;
      const minX = boxW - lineW - 8;
      targetMiniScrollX = Math.max(minX, Math.min(0, idealTargetX));
    } else {
      miniLyricBox.classList.remove('scrolling');
      targetMiniScrollX = (boxW - lineW) / 2;   // 들어맞으면 가운데 정렬
    }
  } else {
    // Line-level sync: 첫 20% 는 읽을 시간, 이후 부드럽게 패닝, 끝에서 정지
    const span = Math.max(0.5, line.end - line.start);
    const rawProg = Math.max(0, Math.min(1, (nowSec - line.start) / span));
    let scrollProg;
    if (rawProg < 0.20) scrollProg = 0;
    else if (rawProg > 0.85) scrollProg = 1;
    else {
      const tt = (rawProg - 0.20) / 0.65;
      scrollProg = tt * tt * (3 - 2 * tt);   // smoothstep
    }
    if (lineW > boxW) {
      miniLyricBox.classList.add('scrolling');
      targetMiniScrollX = -scrollProg * (lineW - boxW + 6);
    } else {
      miniLyricBox.classList.remove('scrolling');
      targetMiniScrollX = (boxW - lineW) / 2;
    }
  }
}

// ---------- LYRICS 세로 리스트 ----------
let listBuiltFor;            // 리스트를 만든 시점의 state.lyrics (undefined = 아직 안 만듦)
let listBuiltLang = '';
let listFresh = true;        // true 면 다음 스크롤 배치는 애니메이션 없이 즉시 (막 만들었거나 뷰에 막 들어옴)
let listLis = [];
let listIdx = -1;
let listWordEls = [];
let listWordStates = [];
let gapActive = false;
let gapNext = -2;
let gapDots = null;
let listBgLis = [];          // 본 줄 사이에 끼워 넣은 백그라운드 보컬 줄(작은 글씨) [{li, i, els, states, on}]

function makeGapLi() {
  const li = document.createElement('li');
  li.className = 'gap';
  const dots = [];
  const fills = [];
  for (let k = 0; k < 3; k++) {
    const d = document.createElement('div');
    d.className = 'dot-item';
    const f = document.createElement('div');
    f.className = 'dot-fill';
    d.appendChild(f);
    li.appendChild(d);
    dots.push(d);
    fills.push(f);
  }
  return { li, dots, fills };
}

function buildList(lines) {
  lyList.textContent = '';
  listLis = [];
  listIdx = -1;
  listWordEls = [];
  gapActive = false;
  gapNext = -2;
  listFresh = true;
  listBuiltFor = state.lyrics;
  listBuiltLang = lang;
  const isStatic = !!(lines && state.lyrics && state.lyrics.unsynced);
  lyBox.classList.toggle('static', isStatic);
  lyBox.scrollTop = 0;
  lyList.style.transform = 'translateY(0px)';

  if (!lines) {
    const li = document.createElement('li');
    li.className = 'ph';
    li.textContent = state.lyrics ? t('lyricsNone') : t('lyricsLoading');
    lyList.appendChild(li);
    lyList.style.transform = 'translateY(0px)';
    return;
  }
  listBgLis = [];
  const bg = (state.lyrics && state.lyrics.bg) || [];
  let bi = 0;
  const addBg = (upTo) => {
    while (bi < bg.length && bg[bi].start < upTo) {
      const b = bg[bi++];
      const bl = document.createElement('li');
      bl.className = 'bgl';
      bl.textContent = b.text;
      lyList.appendChild(bl);
      listBgLis.push({ li: bl, b, els: [], states: [], on: false });
    }
  };
  lines.forEach((line, i) => {
    const li = document.createElement('li');
    li.textContent = line.text || '♪';
    li._i = i;
    lyList.appendChild(li);
    listLis.push(li);
    addBg(i + 1 < lines.length ? lines[i + 1].start - 0.3 : Infinity);     // 다음 본 줄이 시작하기 전까지의 bg 는 이 줄 아래에
  });
}

// 목록의 bg 줄: 지금 부르는 중이면 밝게 + 단어 진행
function renderListBg(nowSec) {
  for (const e of listBgLis) {
    const active = nowSec >= e.b.start - 0.15 && nowSec <= e.b.end + 0.4;
    if (active && !e.on) {
      e.on = true; e.li.classList.add('on');
      if (wordSyncOn() && e.b.words && e.b.words.length) { e.li.textContent = ''; e.els = fillWords(e.li, e.b.words, 'w'); e.states = new Array(e.b.words.length).fill(0); }
    } else if (!active && e.on) {
      e.on = false; e.li.classList.remove('on'); e.li.textContent = e.b.text; e.els = []; e.states = [];
    }
    if (e.on && e.els.length) syncWords(e.b.words, e.els, e.states, nowSec, 'w');
  }
}

// 활성 줄(또는 간주 점)이 리스트 한가운데 오도록 스크롤한다. 줄이 바뀔 때만 한 번 호출된다.
function scrollListTo(li, instant) {
  const y = li.offsetTop + li.offsetHeight / 2 - lyBox.clientHeight / 2;
  if (instant || REDUCED_MOTION) {
    lyList.style.transition = 'none';
    lyList.style.transform = `translateY(${-y}px)`;
    void lyList.offsetHeight;
    lyList.style.transition = '';
  } else {
    lyList.style.transform = `translateY(${-y}px)`;
  }
}

function deactivateList(lines) {
  if (listIdx >= 0 && listLis[listIdx]) {
    const li = listLis[listIdx];
    li.classList.remove('on');
    li.textContent = lines[listIdx].text || '♪';
  }
  listIdx = -1;
  listWordEls = [];
  listWordStates = [];
}

function activateLine(i, lines, instant) {
  deactivateList(lines);
  listIdx = i;
  const li = listLis[i];
  const line = lines[i];
  li.classList.add('on');
  if (wordSyncOn() && line.words && line.words.length > 0) {
    li.textContent = '';
    listWordEls = fillWords(li, line.words, 'w');
    listWordStates = new Array(line.words.length).fill(0);
  }
  scrollListTo(li, instant);
}

function hideGap() {
  if (!gapActive) return;
  gapActive = false;
  gapNext = -2;
  if (gapDots) gapDots.li.remove();
}

function renderList(lines, nowSec) {
  if (listBuiltFor !== state.lyrics || (lines && listLis.length !== lines.length)) buildList(lines);
  if (!lines) return;
  if (state.lyrics && state.lyrics.unsynced) return;   // 시간 정보가 없으면 하이라이트/자동 스크롤 없이 정적 목록
  renderListBg(nowSec);

  const pos = locate(nowSec, lines);

  if (pos.interlude) {
    if (!gapDots) gapDots = makeGapLi();
    if (!gapActive || gapNext !== pos.nextIdx) {
      deactivateList(lines);
      const before = pos.nextIdx >= 0 ? listLis[pos.nextIdx] : null;
      lyList.insertBefore(gapDots.li, before || null);
      gapActive = true;
      gapNext = pos.nextIdx;
      scrollListTo(gapDots.li, listFresh);
      listFresh = false;
    }
    paintDots(gapDots.dots, gapDots.fills, dotProgress(pos, nowSec));
    return;
  }
  hideGap();

  if (pos.idx !== -1 && pos.idx !== listIdx && pos.idx < lines.length) {
    activateLine(pos.idx, lines, listFresh);
    listFresh = false;
  }
  if (listIdx >= 0) {
    const line = lines[listIdx];
    if (wordSyncOn() && line.words && line.words.length > 0 && listWordEls.length === line.words.length) {
      syncWords(line.words, listWordEls, listWordStates, nowSec, 'w');
    }
  }
}

// 줄 클릭 → 그 줄로 이동
lyList.addEventListener('click', (e) => {
  const li = e.target.closest('li');
  if (!li || li._i === undefined || !hasLyricLines() || state.lyrics.unsynced) return;
  e.stopPropagation();
  seekTo(state.lyrics.lines[li._i].start);
});

// ========================================================
// 프레임 루프
// ========================================================
let lastFrameTs = 0;
let lastProgressW = '';

function isPlayerView() {
  return view === 'music' || view === 'lyrics';
}

// 재생바를 끄는 중: 바와 시간이 손가락(커서)을 따라가고, 그동안 실제 재생 위치는 프레임 루프가 덮어쓰지 않는다
const scrub = { active: false, ratio: 0 };
function paintScrub() {
  const w = `${(scrub.ratio * 100).toFixed(2)}%`;
  lastProgressW = w;
  for (const f of fillEls) f.style.width = w;
  const at = scrub.ratio * state.duration;
  setTextAll(elapsedEls, formatTime(at));
  setTextAll(remainEls, `-${formatTime(state.duration - at)}`);
}

function animationFrame(ts) {
  const nowSec = getCurrentPlayhead();

  // 진행 바 / 시간 (music, lyrics 에서만 보인다. 값이 바뀔 때만 DOM 에 쓴다)
  if (isPlayerView() && state.duration > 0 && !scrub.active) {
    const pct = Math.min(100, Math.max(0, (nowSec / state.duration) * 100));
    const w = `${pct.toFixed(2)}%`;
    if (w !== lastProgressW) {
      lastProgressW = w;
      for (const f of fillEls) f.style.width = w;
    }
    setTextAll(elapsedEls, formatTime(nowSec));
    setTextAll(remainEls, `-${formatTime(state.duration - nowSec)}`);
  }

  renderLyrics(nowSec);

  // mini 가사 스크롤: 프레임 간격(dt)에 맞춰 감쇠 계수를 환산해 60Hz 든 144Hz 든 같은 속도로 따라가게 한다
  if (view === 'mini') {
    const dt = lastFrameTs ? Math.min(0.1, (ts - lastFrameTs) / 1000) : 1 / 60;
    const smoothing = 1 - Math.pow(1 - 0.12, dt * 60);
    currentMiniScrollX += (targetMiniScrollX - currentMiniScrollX) * smoothing;
    const miniX = currentMiniScrollX.toFixed(2);
    if (miniX !== lastMiniX) {   // 수렴한 뒤에는 style 을 다시 쓰지 않는다
      lastMiniX = miniX;
      miniLyricLine.style.transform = `translateX(${miniX}px)`;
    }
    applyEdgeFade(miniLyricBox, miniMetrics, currentMiniScrollX, 14);
  }
  if (view === 'mini') {
    const vdt = lastFrameTs ? Math.min(0.1, (ts - lastFrameTs) / 1000) : 1 / 60;
    updateViz(ts, vdt, performance.now());
  }
  lastFrameTs = ts;

  requestAnimationFrame(animationFrame);
}

// 비네트: 가려진 글자가 있는 쪽의 가장자리만, 가려진 양에 비례해(최대 max px) 흐리게 한다.
function applyEdgeFade(el, m, x, max) {
  const fl = Math.max(0, Math.min(max, -x));                    // 왼쪽으로 밀려 가려진 폭
  const fr = Math.max(0, Math.min(max, m.line + x - m.box));    // 오른쪽에 아직 가려진 폭
  const key = `${Math.round(fl)}|${Math.round(fr)}`;
  if (el._fadeKey === key) return;                              // 값이 같으면 스타일을 건드리지 않는다
  el._fadeKey = key;
  el.style.setProperty('--fl', `${Math.round(fl)}px`);
  el.style.setProperty('--fr', `${Math.round(fr)}px`);
}

// ========================================================
// 비주얼라이저: 실제 출력 오디오의 대역별 레벨(Python 루프백)로 막대를 구동한다.
// 레벨을 못 받으면(루프백 실패 등) 불규칙한 자체 움직임으로 대체한다.
// 빠르게 오르고 천천히 내려가야 음악처럼 보인다.
// ========================================================
const vizBars = $$('.bars i');
const VIZ_MIN = 0.16;            // 막대가 가장 작을 때의 scaleY (작은 점)
const viz = {
  cur: vizBars.map(() => VIZ_MIN), last: vizBars.map(() => -1),
  target: vizBars.map(() => 0), real: false, lastRealAt: 0,
  pending: false, lastPoll: 0, synth: vizBars.map(() => ({ v: 0.3, next: 0 })), beatAt: 0, noApi: false
};

const vizGain = () => clampN(store.settings.vizGain, 20, 300, 100) / 100;

function pollLevels(now) {
  const api = getApi();
  if (!api || !api.get_levels || viz.pending || viz.noApi) return;
  viz.pending = true;
  Promise.resolve(api.get_levels()).then((r) => {
    viz.pending = false;
    if (r && r.available && Array.isArray(r.levels)) {
      viz.real = true;
      viz.lastRealAt = performance.now();
      viz.target = r.levels;
    } else {
      viz.real = false;
    }
  }).catch(() => { viz.pending = false; viz.noApi = true; viz.real = false; });
}

// 대체 움직임: 막대마다 100~260ms 간격으로 새 목표를 무작위로 잡고, 일정 간격으로 저음 막대에 박자 펄스를 준다
function synthLevels(now) {
  if (now - viz.beatAt > 460 + Math.random() * 120) {
    viz.beatAt = now;
    viz.synth[0].v = 0.95; viz.synth[0].next = now + 160;
    viz.synth[1].v = 0.75; viz.synth[1].next = now + 160;
  }
  return viz.synth.map((s, i) => {
    if (now >= s.next) {
      s.next = now + 100 + Math.random() * 160;
      const ceil = 1 - i * 0.09;                       // 고음 쪽 막대는 낮게 움직인다
      s.v = 0.18 + Math.random() * (ceil - 0.18);
    }
    return s.v;
  });
}

function updateViz(ts, dt, now) {
  const playing = state.isPlaying;
  let tgt;
  if (!playing || store.settings.visualizer === false) {
    tgt = viz.cur.map(() => 0);
  } else if (REDUCED_MOTION) {
    tgt = viz.cur.map(() => 0.45);
  } else {
    if (now - viz.lastPoll >= 50) { viz.lastPoll = now; pollLevels(now); }
    // 실제 레벨이 한동안 안 오면(루프백 끊김) 대체 움직임
    tgt = (viz.real && now - viz.lastRealAt < 800) ? viz.target : synthLevels(now);
  }
  for (let i = 0; i < vizBars.length; i++) {
    const lv = Math.max(0, Math.min(1, (tgt[i] || 0) * vizGain()));
    const goal = VIZ_MIN + (1 - VIZ_MIN) * Math.pow(lv, 0.85);
    const k = goal > viz.cur[i] ? 0.6 : 0.16;                       // 빠른 어택, 느린 릴리스
    viz.cur[i] += (goal - viz.cur[i]) * (1 - Math.pow(1 - k, dt * 60));
    if (Math.abs(viz.cur[i] - viz.last[i]) > 0.008) {
      viz.last[i] = viz.cur[i];
      vizBars[i].style.transform = `scaleY(${viz.cur[i].toFixed(3)})`;
    }
  }
}

// 시계 (idle)
let lastClockHtml = '';
function updateClock() {
  const d = new Date();
  const s = store.settings;
  const secs = !!s.clockSeconds;
  island.classList.toggle('cclock', s.compactClock !== false);
  const key = pad2(d.getHours()) + pad2(d.getMinutes()) + (secs ? pad2(d.getSeconds()) : '') + (s.clock24 === false ? 'a' : '');
  if (clockEl._k === key) return;
  clockEl._k = key;
  const h24 = s.clock24 !== false;
  const hh = h24 ? pad2(d.getHours()) : String(d.getHours() % 12 || 12);
  const html = `${hh}<i>:</i>${pad2(d.getMinutes())}` + (secs ? `<i>:</i>${pad2(d.getSeconds())}` : '')
    + (h24 ? '' : `<small>${d.getHours() < 12 ? 'AM' : 'PM'}</small>`);
  clockEl.innerHTML = html;
  miniClockEl.innerHTML = html;
  lastClockHtml = html;
  if (typeof renderSat === 'function') renderSat();
}

// ========================================================
// 펼침 / 접힘 / 페이지
// ========================================================
function isEditing() {
  const a = document.activeElement;
  return !!(a && a.tagName === 'INPUT');
}

function triggerExpand() {
  if (collapseTimer) {
    clearTimeout(collapseTimer);
    collapseTimer = null;
  }
  editWaitSince = 0;
  if (isExpanded) return;
  isExpanded = true;
  updateView();
}

function triggerCollapse() {
  if (isPinned || contextMenuOpen) return;
  if (!isExpanded) return;

  if (collapseTimer) clearTimeout(collapseTimer);
  collapseTimer = setTimeout(() => {
    // 대기 중에 메뉴가 열리거나 고정됐다면 접지 않는다 (mouseleave 직후 우클릭한 경우)
    if (isPinned || contextMenuOpen) return;
    // 입력창에 글을 쓰는 중이면 접지 않고 잠시 뒤 다시 확인한다. 다만 창이 포커스를 잃었거나(다른 창으로 옮겨 감) 15초가 지나도록
    // 입력이 이어지지 않으면 포기하고 접는다: 입력창이 열린 채 떠난 노치가 화면을 계속 가리는(소프트락) 일이 없게 한다
    const waited = editWaitSince ? Date.now() - editWaitSince : 0;
    if (isEditing() && document.hasFocus() && waited < 15000) {
      if (!editWaitSince) editWaitSince = Date.now();
      triggerCollapse(); return;
    }
    editWaitSince = 0;
    if (isEditing() && typeof todoCloseAdd === 'function') todoCloseAdd();      // 열려 있던 입력 창은 닫는다(다시 펼쳤을 때 입력 창이 그대로 남지 않게)
    isExpanded = false;
    updateView();
  }, isEditing() ? 1500 : collapseDelayMs());   // 기본 850ms: 차분하고 자연스러운 유예
}
let editWaitSince = 0;
window.addEventListener('keydown', () => { editWaitSince = 0; });      // 글을 쓰고 있으면 15초 기다림을 처음부터 다시 센다

// Pin Toggle
function togglePin() {
  isPinned = !isPinned;
  if (isPinned) {
    btnPin.classList.add('active');
    setText($('menuPinText'), t('menuUnpin'));
    triggerExpand();
    showToast(t('pinned'));
  } else {
    btnPin.classList.remove('active');
    setText($('menuPinText'), t('menuPin'));
    showToast(t('autoHide'));
    triggerCollapse();
  }
}

// 가사 표시 토글: 켜면 미니 노치와 음악 페이지에 가사가 나오고, 끄면 곡 정보만 나온다
function updateLyricsButtons() {
  const on = lyricsOn();
  for (const b of $$('.js-lyr-toggle')) b.classList.toggle('on', on);
  setText($('menuLyricsText'), t(on ? 'menuLyricsOff' : 'menuLyricsOn'));
}

function toggleLyrics() {
  store.settings.lyricsOn = !store.settings.lyricsOn;
  saveStoreSoon();
  updateLyricsButtons();
  miniIdx = -1;
  updateView();
  showToast(t(lyricsOn() ? 'lyricsOnMsg' : 'lyricsOffMsg'));
  if (lyricsOn() && state.title && state.lyrics && !hasLyricLines()) setTimeout(() => showToast(t('lyricsNone')), 1300);
}

// 반복/셔플 버튼 (music / lyrics 두 페이지에 같은 버튼이 있다)
let modeHoldUntil = 0;
let modeKey = '';
function renderModes() {
  const key = `${state.repeat}|${state.shuffle}`;
  if (key === modeKey) return;
  modeKey = key;
  for (const b of $$('.js-shuffle')) b.classList.toggle('on', state.shuffle);
  for (const p of $$('.js-shuffle-icon')) p.setAttribute('d', ICONS.shuffle);
  for (const b of $$('.js-repeat')) b.classList.toggle('on', state.repeat !== 'none');
  for (const p of $$('.js-repeat-icon')) p.setAttribute('d', state.repeat === 'one' ? ICONS.repeatOne : ICONS.repeat);
}

function toggleShuffle() {
  state.shuffle = !state.shuffle;
  modeHoldUntil = performance.now() + 2500;
  renderModes();
  const api = getApi();
  if (api) api.media_action('shuffle', state.shuffle);
  showToast(t(state.shuffle ? 'shuffleOnMsg' : 'shuffleOffMsg'));
}

// Apple Music 과 같은 순서: 끔 -> 전체 반복 -> 한 곡 반복 -> 끔
function cycleRepeat() {
  const next = { none: 'all', all: 'one', one: 'none' }[state.repeat] || 'all';
  state.repeat = next;
  modeHoldUntil = performance.now() + 2500;
  renderModes();
  const api = getApi();
  if (api) api.media_action('repeat', next);
  showToast(t({ none: 'repeatNoneMsg', all: 'repeatAllMsg', one: 'repeatOneMsg' }[next]));
}

function updateSoundMenu() {
  setText($('menuSoundText'), t(store.settings.sound ? 'menuSoundOff' : 'menuSoundOn'));
}

function toggleSound() {
  store.settings.sound = !store.settings.sound;
  saveStoreSoon();
  updateSoundMenu();
  showToast(t(store.settings.sound ? 'soundOnMsg' : 'soundOffMsg'));
}

// ========================================================
// 컨텍스트 메뉴
// ========================================================
// 메뉴는 기본 창 높이보다 클 수 있으므로, 열 때 창 높이를 키우고 닫을 때 되돌린다.
function openContextMenu(e) {
  e.preventDefault();
  contextMenuOpen = true;
  clearTimeout(regionTimer);

  // 크기를 재기 위해 보이지 않게 먼저 렌더
  contextMenu.style.visibility = 'hidden';
  contextMenu.style.display = 'block';
  const menuW = contextMenu.offsetWidth;
  const menuH = contextMenu.offsetHeight;

  const top = island.getBoundingClientRect().bottom + 8;   // 노치 바로 아래에 띄운다
  const left = Math.min(window.innerWidth - menuW - 10, Math.max(10, e.clientX));
  contextMenu.style.left = `${left}px`;
  contextMenu.style.top = `${top}px`;
  contextMenu.style.visibility = 'visible';

  const api = getApi();
  if (api) {
    if (api.expand_window) api.expand_window();   // rect 없이 호출: 창 전체를 상호작용 가능하게
    if (api.resize_window) api.resize_window(top + menuH + 22, window.devicePixelRatio || 1);
  }
}

function closeContextMenu() {
  if (!contextMenuOpen) return;
  contextMenuOpen = false;
  contextMenu.style.display = 'none';

  const api = getApi();
  if (api && api.resize_window) api.resize_window();   // 기본 높이로 복원
  scheduleRegion(true);

  // 메뉴 때문에 막아 두었던 자동 접힘을 재개 (커서가 노치 위에 있으면 유지)
  if (isExpanded && !island.matches(':hover')) triggerCollapse();
}
