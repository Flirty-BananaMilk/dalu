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
  phone: '<rect x="7" y="2.5" width="10" height="19" rx="2.4"/><path d="M11 18.5h2"/>',
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
  gauge: '<path d="M4.5 16a8 8 0 1 1 15 0"/><path d="M12 15.5l3.6-4.6"/><circle cx="12" cy="15.5" r="1.4"/>',
};
const icon = (name) => `<svg viewBox="0 0 24 24">${ICONS[name] || ''}</svg>`;

const STR = {
  ko: { lkTitle: '폰 앱 (Dalu Link)', lkNone: '연결된 폰이 없어요', lkConnected: '연결됨: {n}', lkBatt: '배터리 {p}%', lkCharging: '충전 중', lkOff: '먼저 위의 “폰 앱으로 연결” 스위치를 켜 주세요', lkStep1: '1. 폰에 앱 설치', lkStep1d: '폰이 이 PC와 같은 와이파이에 있어야 해요. 버튼을 누르고 폰 카메라로 QR을 찍으면 앱을 받을 수 있어요. 설치할 때 “출처를 알 수 없는 앱” 허용이 필요할 수 있어요.', lkStep2: '2. 폰과 연결', lkStep2d: '폰에서 Dalu Link를 열고 “QR로 PC와 연결”을 눌러 이 QR을 비춰 주세요. 알림 접근 허용과 배터리 최적화 제외도 앱 안에서 안내해요.', lkShowInstall: '설치 QR 보기', lkShowPair: '연결 QR 보기', lkOpenFor: '{m}분 동안만 열려 있어요', lkExpires: '{s}초 뒤 만료돼요', lkExpired: '만료됐어요. 다시 눌러 주세요', lkNoApk: '이 Dalu에는 폰 앱 파일이 들어 있지 않아요', lkNoNet: '같은 네트워크 주소를 찾지 못했어요', lkErr: '열지 못했어요', lkForget: '연결 해제', lkFirewall: '처음 켤 때 Windows 방화벽이 물으면 “개인 네트워크”를 허용해 주세요. 폰과 PC가 같은 와이파이일 때만 연결돼요. 알림 내용은 폰과 이 PC 사이에서만 오가고 저장하지 않아요. 연결이 안 되면: 학교·학원·회사 와이파이는 같은 와이파이여도 기기끼리의 접속을 막는 경우가 있어요. 그럴 땐 폰의 핫스팟을 켜고 PC를 그 핫스팟에 연결한 뒤 다시 해 보세요. 모바일 데이터에서도 쓰려면 위의 “모바일 데이터에서도 연결(중계 서버)”을 켜세요(앱 설치용 QR 은 그래도 같은 와이파이에서만 받을 수 있어요).', lkJustConnected: '폰이 연결됐어요', lkServerErr: '연결을 받을 수 없어요(포트가 막혀 있을 수 있어요)', lkRelay_off: '중계 서버: 꺼짐', lkRelay_connecting: '중계 서버에 연결하는 중…', lkRelay_online: '중계 서버에 연결됨 · 모바일 데이터의 폰도 연결할 수 있어요', lkRelay_offline: '중계 서버에 닿지 않아요(인터넷과 주소를 확인하세요). 계속 다시 시도해요', lkRelay_error: '중계 서버를 쓸 수 없어요(필요한 구성 요소가 없어요)', lkRelayNeedUrl: '중계 서버 주소를 입력해 주세요(wss:// 로 쓸 수 있는 주소만 돼요)', lkRelayQr: '이 QR에는 중계 서버 정보가 들어 있어요(모바일 데이터에서도 연결돼요)', wxTitle: '날씨', wxPrivacy: 'Open-Meteo(무료 날씨 서비스)에서 받아요. 도시를 고르기 전에는 아무것도 보내지 않고, 고른 뒤에는 그 도시의 위도·경도(약 1km 로 뭉뚱그림)만 보내요. 계정이 필요 없고 내 위치를 자동으로 알아내지 않아요. 미세먼지는 관측소 값이 아니라 모델 추정값이에요.', wxCityTitle: '도시', wxPick: '선택', ddTitle: '내 D-day', ddDone2: '완료', ddHint: '일정 탭에서 일정 옆 별 버튼을 눌러도 D-day 로 추가돼요.', ddDoneTag: '완료함', ddRestore: '되돌리기', ddDel: '삭제', swWarnMany: '켠 항목이 많아요. 작은 노치는 최대 네 칸이라 시계·타이머 같은 다른 보조 노치가 밀려서 안 보일 수 있어요.', swWarnOff: '보조 노치가 꺼져 있어요. “모양·동작 > 보조 노치”를 켜야 여기서 고른 항목이 보여요.', wxSearchPh: '도시 이름 (예: 서울, Tokyo)', wxSearchBtn: '검색', wxSearching: '찾는 중…', wxNoResult: '찾지 못했어요', wxClearCity: '지우기', wxCityNone: '고른 도시가 없어요', wxCityNow: '지금: {c}', wxSearchFail: '검색하지 못했어요', ddName: '이름', ddAdd: '추가', ddFull: 'D-day 는 40개까지예요', ddEmpty: '직접 만든 D-day 가 없어요', ddSaved: '저장했어요', search: '설정 검색', searchTitle: '검색 결과', noResults: '일치하는 설정이 없어요', ver: '버전', reset: '기본값으로', copied: '완료',
        aUpdate: '업데이트', updAvail: (v) => `${v} 받을 수 있어요`, updNew: (v) => `새 버전 ${v}이 있어요. 다운로드 페이지를 열었어요`, updLatest: '최신 버전이에요', updFail: '확인하지 못했어요 (인터넷 연결을 확인해 주세요)',
        updReady: (v) => `새 버전 ${v}이 있어요. 아래 "지금 업데이트"를 눌러 주세요`, updProgress: (p) => `받는 중 ${p}%`, updInstalling: '설치 중…', updNoDirect: '앱 안에서 받을 수 없는 버전이라 다운로드 페이지를 열었어요',
        updErrVerify: '받은 파일이 올바르지 않아 멈췄어요. 다운로드 페이지에서 직접 받아 주세요', updErrNet: '받지 못했어요 (인터넷 연결을 확인해 주세요)', updErrRun: '설치 프로그램을 실행하지 못했어요. 백신이 막았을 수 있어요', updErrStuck: '설치가 시작되지 않았어요. 다운로드 페이지에서 직접 받아 주세요',
        removed: (n) => `가사 캐시 ${n}개를 지웠어요`, sent: '테스트 알림을 보냈어요', soundBad: '이 파일은 쓸 수 없어요 (.wav, 10MB·30초 이내)', armed: '정말 초기화할까요?', resetDone: '모든 설정을 초기화했어요',
        restarting: '다시 시작합니다…', failed: '실패했어요', on: '사용 가능', off: '사용 불가',
        eqTitle: '이퀄라이저', eqDesc: '이어버드의 소리 성향을 골라요. 이어버드에 직접 적용되는 설정이라 삼성 Galaxy Buds 앱과 같아요.', eqNormal: '일반', eqBass: '베이스 부스트', eqSoft: '소프트', eqDynamic: '다이내믹', eqClear: '클리어', eqTreble: '트레블 부스트', eqFailed: '적용하지 못했어요', eqInUse: '다른 앱이 이어버드를 쓰고 있어요 (Galaxy Buds 앱을 닫아 주세요)', eqNoDevice: '이어버드가 연결돼 있지 않거나 제어를 쓸 수 없어요',
        eqCustom: '사용자 설정', eqCustomHint: '9개 대역의 소리를 직접 조절해요. 슬라이더를 놓으면 이어버드에 바로 적용돼요.', eqReset: '모두 0으로', eqLow: '저음', eqHigh: '고음', eqBand: '대역', advTitle: '고급', advOne: '한쪽만 끼고도 소음 제어', advOneDesc: '한쪽 이어버드만 착용해도 노이즈 캔슬링이 자동으로 꺼지지 않게 해요.', advUnknown: '(이 모델에서는 아직 확인하지 못해 바꿀 수 없어요)',
        btNone: '연결된 이어버드가 없어요', btConnected: '연결됨', btControl: '소음 제어', btLeft: '왼쪽', btRight: '오른쪽', btCase: '케이스',
        btTip: '삼성 <b>Galaxy Buds 앱</b>이 켜져 있으면 이어버드 제어 연결을 먼저 잡고 있어서 노이즈 컨트롤 모드 변경이 막힐 수 있어요. 모드가 안 바뀌면 그 앱을 닫아 보세요.',
        pvTitle: '지금 설정으로 움직여 보기', pvPlay: '다시 재생', pvNote: '클릭하면 <b>접힘 → 미니 → 펼침</b> 순서로 노치가 움직여요. 아래 값을 바꾸면 바로 다시 재생돼요.',
        aVersion: '버전', aPython: 'Python', aWebview: 'pywebview', aData: '데이터 폴더', aMedia: '다른 앱 미디어(SMTC)', aViz: '비주얼라이저', aBuds: '이어버드',
        yes: '사용 가능', no: '사용 불가',
        tabsHint: '위/아래 버튼으로 순서를 바꾸고, 스위치로 탭을 넣거나 뺍니다.', tabsReset: '탭 구성 초기화',
        tabNote_clip: '“클립보드·일정” 설정에서 기록을 켜야 보여요', tabNote_agenda: '캘린더 주소를 넣어야 보여요', tabNote_buds: '이어버드가 연결됐을 때만 보여요', tabNote_plugins: '켜 둔 플러그인이 있어야 보여요',
        tabLast: '탭이 하나는 보여야 해요', pluginFolder: '플러그인 폴더 열기', pluginAdd: '추가', pluginRemove: '제거', pluginsAdded: '추가한 플러그인', pluginsAvailable: '추가할 수 있는 플러그인', pluginsNone: '아직 추가한 플러그인이 없어요. 아래에서 필요한 것을 추가하면 노치에 “플러그인” 탭이 나타나요.', pluginsAllAdded: '모든 플러그인을 추가했어요', pluginReload: '다시 읽기', pluginUser: '내가 만든 플러그인', pluginActions: (n) => `동작 ${n}개`,
        
        pluginHeroT: '플러그인', pluginHeroD: '노치에 나만의 도구 모음을 붙여요. 필요한 것만 추가하면 “플러그인” 탭에 나란히 나타나고, 추가하지 않은 플러그인은 아무 일도 하지 않아요.', pluginsCount: (n) => `${n}개 사용 중`,
        pluginInUse: '사용 중', pluginMoveL: '앞으로', pluginMoveR: '뒤로', pluginMore: (n) => `+${n}`, pluginCreateT: '나만의 플러그인 만들기', pluginCreateD: '프로그램 실행, 주소 열기, 글 복사, 키 보내기를 JSON 파일 하나로 묶을 수 있어요(버튼은 플러그인마다 최대 6개). 예제를 설치해서 고쳐 쓰는 게 가장 빨라요.',
        pluginInstallEx: '예제 설치', pluginExDone: '예제를 plugins 폴더에 만들었어요 (my-tools.json)', pluginExHave: '예제가 이미 있어요 — 그대로 두었어요', pluginLive: '연결됨',
        pluginHelp: '직접 만들려면 플러그인 폴더에 .json 파일을 넣으세요(예: 프로그램 실행, 주소 열기, 글 복사, 키 보내기). 설명은 README의 “플러그인 만들기”에 있어요.',
        lnAdd: '바로가기 추가', lnBrowse: '찾아보기', lnPresets: '자주 쓰는 것', lnName: '이름', lnTarget: '프로그램·파일·폴더·주소', lnArgs: '인수(선택)', lnIcon: '아이콘', lnEmpty: '아직 바로가기가 없어요. 아래 “자주 쓰는 것”에서 골라 보세요.', lnSaved: '저장했어요', lnFull: '바로가기는 24개까지 만들 수 있어요',
        exported: '설정을 저장했어요', imported: (n) => `설정 ${n}개를 가져왔어요`, importFail: '가져오지 못했어요: 올바른 설정 파일이 아니에요', cleared: '기록을 지웠어요',
        calOk: (n) => `일정 ${n}개를 불러왔어요 (앞으로 7일)`, calFail: '캘린더를 읽지 못했어요. 주소를 확인해 주세요',
        hkOk: '사용 중', hkInvalid: '조합 형식이 올바르지 않아요 (예: Ctrl+Alt+N)', hkConflict: '다른 프로그램이 이미 쓰는 조합이에요', hkOff: '꺼짐' },
  en: { lkTitle: 'Phone app (Dalu Link)', lkNone: 'No phone connected', lkConnected: 'Connected: {n}', lkBatt: 'Battery {p}%', lkCharging: 'charging', lkOff: 'Turn on “Connect with the phone app” above first', lkStep1: '1. Install the app on the phone', lkStep1d: 'The phone must be on the same Wi-Fi as this PC. Press the button and scan the QR with the phone camera to get the app. You may need to allow “unknown sources” to install it.', lkStep2: '2. Connect the phone', lkStep2d: 'Open Dalu Link on the phone, tap “Connect to PC with QR” and scan this QR. The app also guides you through the notification access and battery settings.', lkShowInstall: 'Show install QR', lkShowPair: 'Show connect QR', lkOpenFor: 'Open for {m} minutes only', lkExpires: 'Expires in {s} s', lkExpired: 'Expired. Press again', lkNoApk: 'This Dalu does not contain the phone app file', lkNoNet: 'Could not find a network address', lkErr: 'Could not open it', lkForget: 'Disconnect', lkFirewall: 'If Windows Firewall asks the first time, allow “Private networks”. It only connects when the phone and PC are on the same Wi-Fi. Notification content only travels between the phone and this PC and is never stored. If it does not connect: school, academy or office Wi-Fi may block devices from reaching each other even on the same network. Turn on the phone\'s hotspot, connect the PC to it and try again. To use it on mobile data, turn on “Also connect over mobile data (relay server)” above (the install QR still needs the same Wi-Fi).', lkJustConnected: 'Phone connected', lkServerErr: 'Cannot accept connections (a port may be blocked)', lkRelay_off: 'Relay server: off', lkRelay_connecting: 'Connecting to the relay server…', lkRelay_online: 'Connected to the relay server · phones on mobile data can connect too', lkRelay_offline: 'Cannot reach the relay server (check the internet and the address). Retrying', lkRelay_error: 'The relay server cannot be used (a required component is missing)', lkRelayNeedUrl: 'Enter the relay server address (only addresses that work over wss:// are accepted)', lkRelayQr: 'This QR includes the relay server (it also connects over mobile data)', wxTitle: 'Weather', wxPrivacy: 'Comes from Open-Meteo, a free weather service. Nothing is sent until you pick a city; after that only that city\'s latitude and longitude (rounded to about 1 km) are sent. No account, and your location is never detected automatically. Air quality is a modelled estimate, not a station reading.', wxCityTitle: 'City', wxPick: 'Choose', ddTitle: 'My D-days', ddDone2: 'Done', ddHint: 'You can also star an event in the Agenda tab to add it here.', ddDoneTag: 'Done', ddRestore: 'Restore', ddDel: 'Delete', swWarnMany: 'You turned on a lot. The small notch has four slots at most, so other pills such as the clock or timers may be pushed out.', swWarnOff: 'The small notch is off. Turn it on under “Look & Behavior > Satellite pill” to see these.', wxSearchPh: 'City name (e.g. Seoul, Tokyo)', wxSearchBtn: 'Search', wxSearching: 'Searching…', wxNoResult: 'Nothing found', wxClearCity: 'Clear', wxCityNone: 'No city chosen', wxCityNow: 'Now: {c}', wxSearchFail: 'Search failed', ddName: 'Name', ddAdd: 'Add', ddFull: 'Up to 40 D-days', ddEmpty: 'No D-days of your own yet', ddSaved: 'Saved', search: 'Search settings', searchTitle: 'Search results', noResults: 'No matching settings', ver: 'Version', reset: 'Reset to default', copied: 'Done',
        aUpdate: 'Update', updAvail: (v) => `${v} is available`, updNew: (v) => `Version ${v} is out. Opened the download page`, updLatest: 'You are up to date', updFail: 'Could not check (please check your internet connection)',
        updReady: (v) => `Version ${v} is out. Press "Update now" below`, updProgress: (p) => `Downloading ${p}%`, updInstalling: 'Installing…', updNoDirect: 'This version cannot be downloaded inside the app, so the download page was opened',
        updErrVerify: 'The downloaded file did not match, so it was stopped. Please download it from the page', updErrNet: 'Download failed (please check your internet connection)', updErrRun: 'Could not start the installer. Antivirus may have blocked it', updErrStuck: 'The installer did not start. Please download it from the page',
        removed: (n) => `Cleared ${n} cached lyric file(s)`, sent: 'Sent a test alert', soundBad: 'This file cannot be used (.wav, up to 10 MB and 30 s)', armed: 'Really reset?', resetDone: 'All settings were reset',
        restarting: 'Restarting…', failed: 'Failed', on: 'Available', off: 'Unavailable',
        eqTitle: 'Equalizer', eqDesc: 'Pick the sound profile. It is applied to the earbuds themselves, same as in the Samsung Galaxy Buds app.', eqNormal: 'Normal', eqBass: 'Bass boost', eqSoft: 'Soft', eqDynamic: 'Dynamic', eqClear: 'Clear', eqTreble: 'Treble boost', eqFailed: 'Could not apply', eqInUse: 'Another app is using the earbuds (close the Galaxy Buds app)', eqNoDevice: 'Earbuds are not connected or control is unavailable',
        eqCustom: 'Custom', eqCustomHint: 'Shape the sound in nine bands. Letting go of a slider applies it to the earbuds right away.', eqReset: 'Reset to 0', eqLow: 'Low', eqHigh: 'High', eqBand: 'Band', advTitle: 'Advanced', advOne: 'Noise controls with one earbud', advOneDesc: 'Keeps noise canceling on when only one earbud is worn.', advUnknown: '(Not verified on this model yet, so it cannot be changed.)',
        btNone: 'No earbuds connected', btConnected: 'Connected', btControl: 'Noise control', btLeft: 'Left', btRight: 'Right', btCase: 'Case',
        btTip: 'If the Samsung <b>Galaxy Buds app</b> is running it can hold the earbuds’ control connection, which blocks noise-control changes. Close it if modes will not change.',
        pvTitle: 'Try your current settings', pvPlay: 'Replay', pvNote: 'Click to move the notch through <b>collapsed → mini → expanded</b>. It replays when you change a value below.',
        aVersion: 'Version', aPython: 'Python', aWebview: 'pywebview', aData: 'Data folder', aMedia: 'Other-app media (SMTC)', aViz: 'Visualizer', aBuds: 'Earbuds',
        yes: 'Available', no: 'Unavailable',
        tabsHint: 'Use the arrows to reorder and the switches to add or remove tabs.', tabsReset: 'Reset tabs',
        tabNote_clip: 'Turn on clipboard history in “Clipboard & Agenda” to show it', tabNote_agenda: 'Add a calendar address to show it', tabNote_buds: 'Shown only while earbuds are connected', tabNote_plugins: 'Needs at least one enabled plugin',
        tabLast: 'At least one tab must stay visible', pluginFolder: 'Open plugin folder', pluginAdd: 'Add', pluginRemove: 'Remove', pluginsAdded: 'Added plugins', pluginsAvailable: 'Available plugins', pluginsNone: 'No plugins added yet. Add one below and a “Plugins” tab appears on the notch.', pluginsAllAdded: 'All plugins are added', pluginReload: 'Reload', pluginUser: 'My plugin', pluginActions: (n) => `${n} actions`,
        
        pluginHeroT: 'Plugins', pluginHeroD: 'Attach your own tool sets to the notch. Add only what you need and they line up in the “Plugins” tab; plugins you have not added do nothing.', pluginsCount: (n) => `${n} in use`,
        pluginInUse: 'In use', pluginMoveL: 'Move earlier', pluginMoveR: 'Move later', pluginMore: (n) => `+${n}`, pluginCreateT: 'Make your own plugin', pluginCreateD: 'Bundle running a program, opening an address, copying text and sending keys into one JSON file (up to 6 buttons per plugin). Installing the example and editing it is the quickest way.',
        pluginInstallEx: 'Install example', pluginExDone: 'Example created in the plugins folder (my-tools.json)', pluginExHave: 'The example already exists — left untouched', pluginLive: 'Live',
        pluginHelp: 'To make your own, drop a .json file into the plugin folder (run a program, open an address, copy text, send keys). See “Writing plugins” in the README.',
        lnAdd: 'Add shortcut', lnBrowse: 'Browse', lnPresets: 'Common ones', lnName: 'Name', lnTarget: 'Program, file, folder or address', lnArgs: 'Arguments (optional)', lnIcon: 'Icon', lnEmpty: 'No shortcuts yet. Pick some from “Common ones” below.', lnSaved: 'Saved', lnFull: 'You can have up to 24 shortcuts',
        exported: 'Settings saved', imported: (n) => `Imported ${n} settings`, importFail: 'Could not import: not a valid settings file', cleared: 'History cleared',
        calOk: (n) => `Loaded ${n} events (next 7 days)`, calFail: 'Could not read the calendar. Check the address',
        hkOk: 'Active', hkInvalid: 'Invalid combination (e.g. Ctrl+Alt+N)', hkConflict: 'Already used by another program', hkOff: 'Off' },
};

// ---------------------------------------------------------------- 상태
Object.assign(STR.ko, {
  wxPrivacy: 'Open-Meteo(무료 날씨 서비스)에서 받아요. 위치도 도시도 없으면 아무것도 보내지 않고, 보내는 것은 약 1km 로 뭉뚱그린 좌표뿐이에요. 계정은 필요 없어요.',
  wxTitle: '데이터 출처와 개인정보', wxCityTitle: '도시 고르기', wxLocTitle: '위치 서비스 상태', wxLocCheck: '다시 확인', wxLocChecking: '확인하는 중…',
  wxLoc_ok: '이 PC의 위치를 읽을 수 있어요.', wxLoc_denied: '윈도우 위치 서비스가 꺼져 있거나 이 앱이 막혀 있어요. 윈도우 설정 › 개인 정보 및 보안 › 위치에서 켜 주세요.',
  wxLoc_unavailable: '이 PC에서는 위치 기능을 쓸 수 없어요. 고른 도시로 보여 줘요.', wxLoc_error: '위치를 읽지 못했어요. 잠시 뒤에 다시 확인해 보세요.', wxLoc_timeout: '위치를 읽지 못했어요. 잠시 뒤에 다시 확인해 보세요.', wxLoc_unknown: '아직 확인하지 않았어요.',
  swWarnMany: '2개 이상 켜면 작은 노치(최대 4칸)에서 시계·타이머 같은 다른 항목이 밀려날 수 있어요. 최대 3개까지 고를 수 있어요.',
  satMax: '작은 노치에는 정보를 최대 3개까지만 띄울 수 있어요. 다른 항목을 먼저 꺼 주세요.',
  tabOffMsg: '“{t}” 탭이 꺼져 있어요. 모양·동작 › 탭 구성에서 먼저 켜 주세요.',
  tabOffNote: '“{t}” 탭이 꺼져 있어서 이 설정은 쓸 수 없어요. 모양·동작 › 탭 구성에서 켜면 다시 쓸 수 있어요.',
});
Object.assign(STR.en, {
  wxPrivacy: 'Comes from Open-Meteo, a free weather service. With no location and no city nothing is sent; only coordinates rounded to about 1 km are. No account needed.',
  wxTitle: 'Data source & privacy', wxCityTitle: 'Pick a city', wxLocTitle: 'Location service', wxLocCheck: 'Check again', wxLocChecking: 'Checking…',
  wxLoc_ok: 'This PC\'s location can be read.', wxLoc_denied: 'The Windows location service is off or this app is blocked. Turn it on under Windows Settings › Privacy & security › Location.',
  wxLoc_unavailable: 'Location is not available on this PC. The city you picked is used.', wxLoc_error: 'Could not read the location. Try again in a moment.', wxLoc_timeout: 'Could not read the location. Try again in a moment.', wxLoc_unknown: 'Not checked yet.',
  swWarnMany: 'With two or more on, other pills such as the clock or timers may be pushed out (the small notch has four slots). You can choose up to 3.',
  satMax: 'The small notch can show at most 3 info items. Turn another one off first.',
  tabOffMsg: 'The “{t}” tab is off. Turn it on under Look & Behavior › Tabs first.',
  tabOffNote: 'The “{t}” tab is off, so these settings are unavailable. Turn it on under Look & Behavior › Tabs.',
});
// 짧게 줄인 안내 문구와, 페이지 이름이 '모양'으로 바뀐 데 맞춘 문구(위의 값을 덮어쓴다)
Object.assign(STR.ko, {
  winMin: '최소화', winClose: '닫기',
  lkStep1d: '폰이 PC와 같은 와이파이에 있어야 해요. 버튼을 누르고 폰 카메라로 QR을 찍으세요.',
  lkStep2d: '폰에서 Dalu Link를 열고 “QR로 PC와 연결”을 눌러 이 QR을 비춰 주세요.',
  lkFirewall: 'Windows 방화벽이 물으면 “개인 네트워크”를 허용해 주세요. 학교·회사처럼 기기끼리의 접속을 막는 와이파이에서는 폰 핫스팟이나 위의 중계 서버를 쓰세요.',
  swWarnOff: '보조 노치가 꺼져 있어요. “모양 > 보조 노치”를 켜야 여기서 고른 항목이 보여요.',
  tabOffMsg: '“{t}” 탭이 꺼져 있어요. 모양 › 탭 구성에서 먼저 켜 주세요.',
  tabOffNote: '“{t}” 탭이 꺼져 있어서 이 설정은 쓸 수 없어요. 모양 › 탭 구성에서 켜면 다시 쓸 수 있어요.',
});
Object.assign(STR.en, {
  winMin: 'Minimize', winClose: 'Close',
  lkStep1d: 'The phone must be on the same Wi-Fi as this PC. Press the button and scan the QR with the phone camera.',
  lkStep2d: 'Open Dalu Link on the phone, tap “Connect to PC with QR” and scan this QR.',
  lkFirewall: 'If Windows Firewall asks, allow “Private networks”. On Wi-Fi that blocks devices from reaching each other (school, office), use the phone\'s hotspot or the relay server above.',
  swWarnOff: 'The small notch is off. Turn it on under “Appearance > Satellite pill” to see these.',
  tabOffMsg: 'The “{t}” tab is off. Turn it on under Appearance › Tabs first.',
  tabOffNote: 'The “{t}” tab is off, so these settings are unavailable. Turn it on under Appearance › Tabs.',
});
Object.assign(STR.ko, {
  lkApp: '폰 앱 {v}',
  lkAppOk: '최신 버전이에요',
  lkAppNew: '폰 앱 새 버전 {v}',
  lkAppNewD: '폰에서 Dalu Link를 열고 ‘업데이트’를 누르세요',
  lkAppOld: '폰 앱이 오래된 버전이에요',
  lkAppOldD: '아래 “설치 QR 보기”로 새 버전({v})을 한 번 설치해 주세요',
  lkAppNotify: '폰에 알리기',
  lkAppNotified: '폰에 알렸어요',
  lkAppNotifyFail: '알리지 못했어요',
});
Object.assign(STR.en, {
  lkApp: 'Phone app {v}',
  lkAppOk: 'Up to date',
  lkAppNew: 'Phone app update {v}',
  lkAppNewD: 'Open Dalu Link on the phone and tap Update',
  lkAppOld: 'The phone app is out of date',
  lkAppOldD: 'Install the new version ({v}) once with “Show install QR” below',
  lkAppNotify: 'Notify the phone',
  lkAppNotified: 'Phone notified',
  lkAppNotifyFail: 'Could not notify',
});
Object.assign(STR.ko, { rbDone: '버튼 위치를 기본값으로 되돌렸어요' });
Object.assign(STR.en, { rbDone: 'Button positions were reset' });
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
  if (item.special === 'notchStyle') return D.settings.slimNotch ? 'slim' : (D.settings.compact ? 'compact' : 'normal');
  if (item.special === 'animPreset') return matchAnimPreset(D.settings);
  return getPath(D[item.path], item.key, item.def);
}
// 설정이 막히는 이유: ① 그 설정이 속한 탭이 꺼져 있다 ② 작은 노치 정보는 최대 3개
const SAT_KEYS = ['satDday', 'satWeather', 'satPerfCpu', 'satPerfMem', 'satPerfGpu', 'satPerfNet', 'satPhoneBatt', 'satPhoneMissed'];
const SAT_MAX = 3;
const satCount = () => SAT_KEYS.filter((k) => D.settings[k]).length;
const tabIsOff = (tab) => !!tab && parseTabHidden(D.settings.tabHidden).includes(tab);
const tabName = (tab) => (TAB_META[tab] ? tr(TAB_META[tab][1]) : tab);
function blockOf(item) {
  if (item.tab && tabIsOff(item.tab)) return { kind: 'tab', tab: item.tab };
  if (item.group === 'satwidget' && !valueOf(item) && satCount() >= SAT_MAX) return { kind: 'max' };
  return null;
}
const blockMsg = (b) => (b.kind === 'tab' ? S('tabOffMsg').replace('{t}', tabName(b.tab)) : S('satMax'));
const isChanged = (item) => item.def !== undefined && valueOf(item) !== item.def;
const isEnabled = (item) => (item.enabledIf ? !!item.enabledIf(D) : true);

// ---------------------------------------------------------------- 저장 (슬라이더를 끌 때 쏟아지지 않게 모아서 보낸다)
let pending = null, flushTimer = null, flushWait = 140;
// 슬라이더를 끌거나 글자를 칠 때는 쏟아지지 않게 140ms 모아서, 토글·선택·버튼은 30ms 뒤(같은 클릭에서 바뀐 값들만 묶어서) 바로 보낸다.
// (예전에는 모두 140ms 를 기다려서 노치에 반영되기까지 한 박자 느렸다)
function queuePatch(path, key, value, fast) {
  pending = pending || { settings: {}, pomo: {}, water: {} };
  setPath(pending[path], key, value);
  const wait = fast ? 30 : 140;
  if (flushTimer && flushWait <= wait) return;           // 이미 더 빨리 보낼 예정이면 그대로 둔다
  clearTimeout(flushTimer);
  flushWait = wait;
  flushTimer = setTimeout(() => flushPatch(true), wait);
}
// 한 번에 하나만 보낸다: 파이썬은 요청마다 다른 스레드에서 처리해서, 연달아 보내면 순서가 뒤바뀌어 마지막 값이 옛 값으로 덮일 수 있다.
// 보내는 동안 바뀐 값은 모아 두었다가 응답이 오면 이어서 보낸다(같은 키는 마지막 값만 남는다). 창을 닫을 때 등 직접 부르면(인자 없음) 바로 보낸다.
let patchInflight = false;
function flushPatch(viaTimer) {
  clearTimeout(flushTimer);
  flushTimer = null;
  flushWait = 140;
  if (!pending) return;
  if (viaTimer === true && patchInflight) return;              // 응답이 오면 이어서 보낸다
  const patch = pending;
  pending = null;
  for (const sec of Object.keys(patch)) if (!Object.keys(patch[sec]).length) delete patch[sec];
  const api = getApi();
  if (!(api && api.settings_patch && Object.keys(patch).length)) return;
  patchInflight = true;
  const done = () => { patchInflight = false; if (pending) { clearTimeout(flushTimer); flushTimer = setTimeout(() => flushPatch(true), 0); } };
  try {
    const r = api.settings_patch(patch);
    if (r && typeof r.then === 'function') r.then(done, done); else done();
  } catch (e) { done(); }
}

const LOCAL_KEYS = /^(lang|setAnim|setAnimSpeed|bounce|animSpeed|animOff)$/;
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
  if (item.special === 'notchStyle') {
    const slim = value === 'slim', compact = value === 'compact';
    D.settings.slimNotch = slim; D.settings.compact = compact;
    queuePatch('settings', 'slimNotch', slim, true); queuePatch('settings', 'compact', compact, true);
    updateAll();
    return;
  }
  if (item.special === 'animPreset') {
    const p = ANIM_PRESETS[value];
    if (!p) return;
    for (const k of Object.keys(p)) { D.settings[k] = p[k]; queuePatch('settings', k, p[k], true); }
  } else {
    setPath(D[item.path], item.key, value);
    queuePatch(item.path, item.key, value, item.type === 'toggle' || item.type === 'seg' || item.type === 'tiles' || item.type === 'select' || item.type === 'monmap' || item.type === 'posmap' || item.type === 'button');
  }
  if (item.special === 'animPreset' || LOCAL_KEYS.test(item.key || '')) applyLocal();      // 설정 창 자신의 언어·애니메이션 값이 아니면 건드리지 않는다(루트 변수를 쓰면 문서 전체가 다시 계산된다)
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
  const bMin = document.getElementById('btnMin'), bClose = document.getElementById('btnClose');          // 창 버튼의 읽어 주는 이름(화면 낭독기)도 언어를 따른다
  if (bMin) bMin.setAttribute('aria-label', S('winMin'));
  if (bClose) bClose.setAttribute('aria-label', S('winClose'));
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
  row.className = 'row' + (item.indent ? ' indent' : '') + (item.type === 'text' && item.wide && item.desc ? ' stack' : '');
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
  // 막힌 줄(탭이 꺼져 있음 등)을 누르면 조작 대신 이유를 알려 준다(캡처 단계라 스위치 등의 클릭보다 먼저 받는다)
  row.addEventListener('click', (e) => { if (row._block) { e.preventDefault(); e.stopPropagation(); toast(blockMsg(row._block)); } }, true);

  let updateCtl = () => {};
  if (item.type === 'toggle') {
    const sw = document.createElement('button');
    sw.className = 'sw'; sw.setAttribute('role', 'switch');
    sw.addEventListener('click', () => commit(item, !valueOf(item)));
    ctl.appendChild(sw);
    updateCtl = () => { const v = String(!!valueOf(item)); if (sw.getAttribute('aria-checked') !== v) sw.setAttribute('aria-checked', v); };
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
      const t = fmtOf(item)(v);
      if (out.textContent !== t) out.textContent = t;
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
    let segSig = '';
    updateCtl = () => {
      const cur = valueOf(item);
      const sig = cur + '|' + LANG + '|' + btns.map(({ o }) => (o.disabled ? 1 : 0)).join('');
      if (sig === segSig && seg.dataset.placed === '1') return;          // 선택값·언어가 같으면 건드리지 않는다(placeSeg 는 레이아웃을 읽어서 비싸다)
      segSig = sig;
      btns.forEach(({ o, b }) => { const t = tr(o.label); if (b.textContent !== t) b.textContent = t; b.classList.toggle('on', o.v === cur); });
      placeSeg(seg);
      seg.dataset.placed = seg.classList.contains('none') ? '0' : '1';       // 아직 보이지 않아 자리를 못 잡았으면 다음에 다시 시도
    };
    if (window.ResizeObserver) { const ro = new ResizeObserver(() => { if (seg.dataset.placed === '1') placeSeg(seg); }); ro.observe(seg); }      // 글꼴·창 크기 때문에 버튼 폭이 달라지면 강조 막대를 다시 맞춘다
    row._seg = seg;
  } else if (item.type === 'monmap') {
    // 모니터 선택: 연결된 모니터를 윈도우 디스플레이 설정처럼 실제 배치대로 그려 놓고 눌러서 고른다(번호는 윈도우 식별 번호).
    // 노치가 뜨는 모니터에는 위쪽에 작은 노치 표시가 붙는다. 아래 '주 모니터' 버튼은 언제나 주 모니터를 따라간다(기본, 값 0).
    const box = document.createElement('div');
    box.className = 'monmap';
    const stage = document.createElement('div');
    stage.className = 'mm-stage';
    const auto = document.createElement('button');
    auto.type = 'button'; auto.className = 'mm-auto';
    auto.addEventListener('click', () => commit(item, 0));
    box.append(stage, auto);
    ctl.appendChild(box);
    let mmSig = '';
    updateCtl = () => {
      const ms = MONITORS.monitors || [];
      const cur = Number(valueOf(item)) || 0;
      // 노치가 뜨는 모니터: 고른 번호(연결돼 있을 때), 아니면 주 모니터. 파이썬의 답을 기다리지 않고 고르는 즉시 표시가 옮겨 간다.
      const pri = ms.find((m) => m.primary);
      const eff = cur > 0 && ms.some((m) => m.number === cur) ? cur : (pri ? pri.number : MONITORS.current);
      const sig = JSON.stringify([ms.map((m) => [m.number, m.left, m.top, m.width, m.height, m.primary]), cur, eff, LANG]);
      if (sig === mmSig) return;
      mmSig = sig;
      const at = lx('주 모니터', 'Primary monitor', '主显示器', 'メインモニター');
      if (auto.textContent !== at) auto.textContent = at;
      auto.classList.toggle('on', cur === 0);
      auto.setAttribute('aria-pressed', cur === 0 ? 'true' : 'false');
      stage.textContent = '';
      stage.classList.toggle('empty', !ms.length);
      if (!ms.length) { stage.textContent = lx('모니터 목록을 읽지 못했어요.', 'Could not read the monitor list.', '无法读取显示器列表。', 'モニターの一覧を読み取れませんでした。'); return; }
      const W = 340, PAD = 12;
      const minL = Math.min(...ms.map((m) => m.left)), minT = Math.min(...ms.map((m) => m.top));
      const maxR = Math.max(...ms.map((m) => m.left + m.width)), maxB = Math.max(...ms.map((m) => m.top + m.height));
      const bw = maxR - minL, bh = maxB - minT;
      const H = Math.round(Math.max(96, Math.min(190, (W - 2 * PAD) * bh / bw + 2 * PAD)));      // 배치의 가로세로 비율에 맞춰 높이를 조절한다(세로로 쌓으면 길어지고, 울트라와이드는 낮아진다)
      stage.style.height = `${H}px`;
      const sc = Math.min((W - 2 * PAD) / bw, (H - 2 * PAD) / bh);
      const ox = (W - (maxR - minL) * sc) / 2, oy = (H - (maxB - minT) * sc) / 2;
      for (const m of ms) {
        const b = document.createElement('button');
        b.type = 'button'; b.className = 'mm-tile' + (m.number === eff ? ' on' : '');
        const w = Math.max(24, (m.width * sc) - 4), h = Math.max(18, (m.height * sc) - 4);
        b.style.cssText = `left:${(ox + (m.left - minL) * sc + 2).toFixed(1)}px;top:${(oy + (m.top - minT) * sc + 2).toFixed(1)}px;width:${w.toFixed(1)}px;height:${h.toFixed(1)}px`;
        b.title = `${m.number}: ${m.width}×${m.height}${m.primary ? lx(' (주 모니터)', ' (primary)', '（主显示器）', '（メイン）') : ''}`;
        b.setAttribute('aria-pressed', m.number === eff ? 'true' : 'false');
        const num = document.createElement('b');
        num.textContent = String(m.number);
        num.style.fontSize = `${Math.max(11, Math.min(24, Math.min(h, w) * 0.4)).toFixed(0)}px`;
        b.appendChild(num);
        if (w > 66 && h > 46) { const r = document.createElement('small'); r.textContent = `${m.width}×${m.height}`; b.appendChild(r); }
        if (m.primary) { const p = document.createElement('i'); p.className = 'mm-pri'; b.appendChild(p); }
        if (m.number === eff) { const n = document.createElement('i'); n.className = 'mm-notch'; b.appendChild(n); }
        b.addEventListener('click', () => commit(item, m.number));
        stage.appendChild(b);
      }
    };
  } else if (item.type === 'posmap') {
    // 노치 가로 위치: 노치가 뜨는 모니터를 실제 비율로 그리고, 위쪽 가장자리에 다섯 자리를 보여 준다. 자리는 monitors.py 의 notch_center_x 와 같은 식으로 계산한다
    // (모니터 높이 기준 16:9 폭을 5등분, 펼친 노치가 화면 안에 들어오도록 안쪽으로 당김). 모니터 모양이 바뀌면 자리도 바뀐다.
    const box = document.createElement('div');
    box.className = 'posmap';
    const stage = document.createElement('div');
    stage.className = 'pm-stage';
    const cap = document.createElement('div');
    cap.className = 'pm-cap';
    box.append(stage, cap);
    ctl.appendChild(box);
    let pmSig = '';
    const half = 290;                                                  // monitors.py EXPANDED_HALF_CSS
    updateCtl = () => {
      const ms = MONITORS.monitors || [];
      const mon = Number(valueOf({ path: 'settings', key: 'monitor' })) || 0;
      const pri = ms.find((m) => m.primary);
      const eff = mon > 0 && ms.some((m) => m.number === mon) ? mon : (pri ? pri.number : MONITORS.current);
      const m = ms.find((x) => x.number === eff) || { number: eff || 1, left: 0, top: 0, width: 1920, height: 1080, dpi: 96 };
      const cur = Math.max(-2, Math.min(2, Math.round(Number(valueOf(item)) || 0)));
      const ui = Math.max(0.8, Math.min(2, (Number(valueOf({ path: 'settings', key: 'uiScale' })) || 100) / 100));
      const sig = JSON.stringify([m.number, m.width, m.height, m.dpi, ui, cur, LANG]);
      if (sig === pmSig) return;
      pmSig = sig;
      const W = 340, PAD = 14, MAXH = 150;
      const sc = Math.min((W - 2 * PAD) / m.width, (MAXH - 2 * PAD) / m.height);
      const sw = m.width * sc, sh = m.height * sc;
      stage.style.height = `${Math.round(sh + 2 * PAD)}px`;
      stage.textContent = '';
      const screen = document.createElement('div');
      screen.className = 'pm-screen';
      screen.style.cssText = `left:${((W - sw) / 2).toFixed(1)}px;top:${PAD}px;width:${sw.toFixed(1)}px;height:${sh.toFixed(1)}px`;
      const lab = document.createElement('span');
      lab.className = 'pm-lab';
      lab.textContent = `${m.number} · ${m.width}×${m.height}`;
      screen.appendChild(lab);
      stage.appendChild(screen);
      // 자리(물리 픽셀): notch_center_x 와 같은 계산
      const refW = Math.min(m.width, m.height * 16 / 9);
      const margin = half * (m.dpi || 96) / 96 * ui;
      const room = m.width / 2 - margin;
      const step = room < 0 ? 0 : Math.min(refW / 5, room / 2);           // monitors.py notch_center_x 와 같은 식: 다섯 자리는 같은 간격
      const centers = [-2, -1, 0, 1, 2].map((p) => m.width / 2 + p * step);
      const stepPx = step * sc;                                            // 이웃 자리까지의 간격(그림 px)
      const notchW = Math.max(16, Math.min(44, W * 0.12, stepPx > 0 ? stepPx * 0.8 : 44));      // 접힌 노치 표시의 폭: 그림판 폭의 12 %(약 41px, 최대 44px), 이웃 자리와 붙지 않게 간격의 80 % 까지만
      const slotLabels = (item.options || []);
      [-2, -1, 0, 1, 2].forEach((p, i) => {
        const b = document.createElement('button');
        b.type = 'button'; b.className = 'pm-slot' + (p === cur ? ' on' : '');
        b.style.cssText = `left:${((W - sw) / 2 + centers[i] * sc - notchW / 2).toFixed(1)}px;top:${PAD}px;width:${notchW.toFixed(1)}px`;
        const o = slotLabels.find((x) => x.v === p);
        b.title = o ? tr(o.label) : String(p);
        b.setAttribute('aria-pressed', p === cur ? 'true' : 'false');
        b.addEventListener('click', () => commit(item, p));
        stage.appendChild(b);
      });
      const co = slotLabels.find((x) => x.v === cur);
      cap.textContent = co ? tr(co.label) : '';
    };
  } else if (item.type === 'text') {
    const inp = document.createElement('input');
    inp.type = item.secret ? 'password' : 'text'; inp.className = 'txt' + (item.wide ? ' wide' : ''); inp.maxLength = 160; inp.spellcheck = false; inp.autocomplete = 'off';
    inp.addEventListener('input', () => commit(item, inp.value));
    ctl.appendChild(inp);
    updateCtl = () => { inp.placeholder = tr(item.placeholder); if (document.activeElement !== inp) inp.value = String(valueOf(item) || ''); };
  } else if (item.type === 'tiles') {
    // 그림으로 고르기: 선택지마다 작은 노치 그림(pv)과 이름. 누르면 바로 적용된다.
    const box = document.createElement('div');
    box.className = 'tiles';
    box.setAttribute('role', 'radiogroup');
    const tiles = (item.options || []).map((o) => {
      const b = document.createElement('button');
      b.type = 'button'; b.className = 'tile'; b.dataset.v = String(o.v); b.setAttribute('role', 'radio');
      const pv = document.createElement('span');
      pv.className = 'pv pv-' + (o.pv || 'black');
      const lb = document.createElement('span');
      lb.className = 'tile-lab';
      b.append(pv, lb);
      b.addEventListener('click', () => commit(item, o.v));
      box.appendChild(b);
      return { o, b, lb };
    });
    ctl.appendChild(box);
    updateCtl = () => {
      const cur = valueOf(item);
      for (const { o, b, lb } of tiles) {
        const t = tr(o.label);
        if (lb.textContent !== t) lb.textContent = t;
        const on = o.v === cur;
        b.classList.toggle('on', on);
        b.setAttribute('aria-checked', on ? 'true' : 'false');
      }
    };
  } else if (item.type === 'select') {
    // 목록 선택: 항목은 파이썬이 알려 주는 윈도우 알림음 이름(고르면 바로 들려준다)
    const sel = document.createElement('select');
    sel.className = 'sel';
    ctl.appendChild(sel);
    let loaded = false, listSig = '';
    const load = async () => {
      const api = getApi();
      let names = [];
      try { if (api && api.list_system_sounds) names = await api.list_system_sounds(); } catch (e) { names = []; }
      const cur = String(valueOf(item) || '');
      if (cur && !names.includes(cur)) names = [cur].concat(names);
      const sig = names.join('|');
      if (sig !== listSig) {
        listSig = sig;
        sel.textContent = '';
        for (const n of names) { const o = document.createElement('option'); o.value = n; o.textContent = n.replace(/\.wav$/i, ''); sel.appendChild(o); }
      }
      loaded = true;
      sel.value = cur;
    };
    sel.addEventListener('change', () => {
      commit(item, sel.value);
      const api = getApi();
      const st = D.settings;
      if (api && api.chime && st.sound) api.chime('pomo', { type: 'system', volume: st.soundVolume, system: sel.value });
    });
    updateCtl = () => { if (!loaded) load(); else if (document.activeElement !== sel) sel.value = String(valueOf(item) || ''); };
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
    const tt = tr(item.label);
    if (title.textContent !== tt) title.textContent = tt;
    const d = item.descFn === 'monitors' ? monitorDesc() : (item.descFn === 'hotkey' ? hotkeyDesc(item) : tr(item.desc));
    if (desc.textContent !== d) desc.textContent = d;
    const disp = d ? '' : 'none';
    if (desc.style.display !== disp) desc.style.display = disp;
    if (pageTag && pageTag.textContent !== opts.pageTitle) pageTag.textContent = opts.pageTitle;
    const rt = S('reset');
    if (reset.title !== rt) reset.title = rt;
    const blk = blockOf(item);
    row._block = blk;
    row.classList.toggle('blocked', !!blk);
    row.classList.toggle('disabled', !isEnabled(item) || !!blk);
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
  const opts = [{ v: 0, label: { ko: '주 모니터', en: 'Primary', zh: '主显示器', ja: 'メインモニター' } }];
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
  return list + note;
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
    case 'resetButtons':          // 시스템·전원·휴대폰 탭 버튼의 순서를 기본값으로(노치의 순서도 바로 바뀐다)
      for (const k of ['phoneButtons', 'powerButtons', 'sysButtons']) { D.settings[k] = ''; queuePatch('settings', k, '', true); }
      done(S('rbDone'));
      break;
    case 'checkUpdate':
      if (api && api.check_update) api.check_update().then((r) => {
        if (r && r.status === 'new') {
          ABOUT = Object.assign({}, ABOUT, { update: { version: r.version, url: r.url, download: r.download || null } }); updateAll(); done();
          if (r.download) toast(S('updReady')(r.version));              // 앱 안에서 받을 수 있다: 아래 '지금 업데이트'
          else { toast(S('updNew')(r.version)); if (api.open_update_page) api.open_update_page(); }
        }
        else if (r && r.status === 'latest') { ABOUT = Object.assign({}, ABOUT, { update: null }); updateAll(); toast(S('updLatest')); done(); }
        else toast(S('updFail'));
      });
      break;
    case 'applyUpdate':
      if (!api || !api.start_update) break;
      api.start_update().then((r) => {
        if (r && r.status === 'none') { if (api.open_update_page) api.open_update_page(); toast(S('updNoDirect')); return; }
        if (!r || (r.status !== 'started' && r.status !== 'busy')) { toast(S('updErrNet')); return; }
        const label = tr(item.btn), errKey = { hash: 'updErrVerify', size: 'updErrVerify', format: 'updErrVerify', host: 'updErrVerify', run: 'updErrRun', stuck: 'updErrStuck' };
        btn._armed = true; btn.disabled = true;                          // 진행 중에는 글자를 우리가 바꾼다(updateAll 이 덮어쓰지 않게)
        const end = () => { btn._armed = false; btn.disabled = false; btn.textContent = label; };
        const tick = () => api.update_status().then((st) => {
          if (!document.body.contains(btn)) return;
          if (st && st.state === 'downloading') { btn.textContent = S('updProgress')(st.percent || 0); setTimeout(tick, 400); }
          else if (st && st.state === 'installing') { btn.textContent = S('updInstalling'); setTimeout(tick, 1000); }
          else if (st && st.state === 'error') { end(); toast(S(errKey[st.error] || 'updErrNet')); }
          else end();
        }, end);
        tick();
      });
      break;
    case 'openFileFolder': if (api && api.phone_file_folder) api.phone_file_folder().then(() => done()); break;
    case 'clearCache': if (api) api.clear_lyrics_cache().then((r) => done(S('removed')(r ? r.removed : 0))); break;
    case 'testChime': if (api && api.chime) { const st = D.settings; api.chime('pomo', { type: st.soundType, volume: st.soundVolume, file: st.soundFile, system: st.soundSystem }); done(); } break;
    case 'pickSound':
      if (api && api.pick_sound_file) api.pick_sound_file().then((r) => {
        if (r && r.status === 'ok') { setPath(D.settings, 'soundFile', r.path); queuePatch('settings', 'soundFile', r.path, true); updateAll(); done(); }
        else if (r && r.status === 'invalid') toast(S('soundBad'));
      });
      break;
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
        const off = b.placement && (b.placement[k] === 0 || b.placement[k] === 4);
        const v = b.battery[k];
        const c = v < 20 ? 'var(--danger)' : v < 50 ? '#ffc25a' : 'var(--ok)';
        return `<div class="bring${off ? ' off' : ''}"><div class="wrap"><div class="ring" style="--v:${v};--c:${c}"></div><span class="val">${v}</span></div><span>${lab[k]}</span></div>`;
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
      const rows = [[S('aVersion'), a.version || '-'], ...(a.update && a.update.version ? [[S('aUpdate'), S('updAvail')(a.update.version)]] : []), [S('aPython'), a.python || '-'], [S('aWebview'), a.webview || '-'],
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
        inp.addEventListener('change', () => { dirty = true; if (!sending) { clearTimeout(sendTimer); sendBands(); } });
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
    if (res && res.status === 'ok') { say('', false); if (v === 7 && !tableLoaded) loadTable(); }
    else { cur = prev; fail(res); }
    render();
  };
  // 슬라이더를 움직이는 동안에도 이어버드로 보낸다(만지면서 바로 들을 수 있게): 한 번에 하나만 보내고, 보내는 동안 바뀐 값은 모았다가 끝나면 '가장 최근 값' 하나만 이어서 보낸다.
  // 보내는 사이에는 최소 SEND_GAP 간격을 둔다. 놓으면(change) 기다리지 않고 마지막 값을 바로 보낸다. (예전에는 손을 놓고 0.35초 뒤에야 한 번 보내서 드래그하는 동안은 소리가 안 바뀌었다)
  const SEND_GAP = 80;
  let sending = false, dirty = false, lastSendEnd = 0;
  const sendBands = async () => {
    const api = getApi();
    if (!api || !api.buds_set_custom_eq || !usable()) { dirty = false; return; }
    if (sending) return;                                       // 끝나면 dirty 를 보고 이어서 보낸다
    if (busy) { clearTimeout(sendTimer); sendTimer = setTimeout(sendBands, 120); return; }     // 프리셋 버튼을 누른 응답을 기다리는 중
    dirty = false; sending = true; pickedAt = Date.now();
    if (cur !== 7) { cur = 7; render(); }
    const sent = bands.slice();
    let res; try { res = await api.buds_set_custom_eq(sent); } catch (e) { res = { status: 'error' }; }
    sending = false; lastSendEnd = Date.now();
    if (res && res.status === 'ok') { BUDS_CACHE.bands = sent.slice(); say('', false); } else { dirty = false; fail(res); }
    if (dirty) kick(); else render();
  };
  const kick = () => {
    if (sending) return;
    clearTimeout(sendTimer);
    sendTimer = setTimeout(sendBands, Math.max(0, SEND_GAP - (Date.now() - lastSendEnd)));
  };
  const scheduleSend = () => { dirty = true; kick(); };
  reset.addEventListener('click', () => { bands = new Array(N).fill(0); editedAt = Date.now(); renderBands(); dirty = true; if (!sending) { clearTimeout(sendTimer); sendBands(); } });
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
  box.innerHTML = '<div class="badv-row" data-k="nc_one"><div class="badv-t"><div class="row-title"></div><div class="row-desc"></div></div><div class="sw" role="switch"></div></div>'
    + '<div class="beq-msg"></div>';
  const msg = box.querySelector('.beq-msg');
  const ROWS = { nc_one: ['advOne', 'advOneDesc', 'buds_set_nc_one'] };
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
    if (res && res.status === 'ok') say('', false);
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

const TAB_META = {
  music: ['music', { ko: '음악', en: 'Music' }], pomo: ['target', { ko: '집중 (포모도로)', en: 'Focus (Pomodoro)' }], timer: ['timer', { ko: '타이머·스톱워치', en: 'Timer & stopwatch' }],
  water: ['drop', { ko: '물 마시기', en: 'Water' }], shelf: ['folder', { ko: '파일 선반', en: 'File shelf' }], todo: ['checklist', { ko: '할 일', en: 'To-do' }],
  clip: ['clipboard', { ko: '클립보드', en: 'Clipboard' }], agenda: ['calendar', { ko: '일정', en: 'Agenda' }], launcher: ['launch', { ko: '바로가기', en: 'Shortcuts' }], sys: ['sliders', { ko: '시스템 (밝기·볼륨·Wi-Fi)', en: 'System (brightness, volume, Wi-Fi)' }], power: ['power', { ko: '전원 (잠금·다시 시작·종료)', en: 'Power (lock, restart, shut down)' }], perf: ['gauge', { ko: '성능 (CPU·메모리·네트워크)', en: 'Performance (CPU, memory, network)' }], weather: ['cloudsun', { ko: '날씨', en: 'Weather' }],
  plugins: ['plug', { ko: '플러그인', en: 'Plugins' }], buds: ['headphones', { ko: '이어버드', en: 'Earbuds' }],
  phone: ['phone', { ko: '휴대폰 (Dalu Link)', en: 'Phone (Dalu Link)' }],
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
    desc.textContent = tr(L('알림을 한 번이라도 보낸 앱이 여기에 나타나요. 끄면 그 앱의 알림은 알리지 않아요.', 'Apps appear here once they have sent a notification. Turn one off to stop its notifications.'));
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

// 폰 앱별로 노치에 알림을 띄울지 고른다: 알림을 한 번이라도 보낸 앱이 목록에 나타난다(끄면 그 앱의 알림은 노치에 띄우지 않는다). 설정 'phoneNotifyOff'(패키지 이름 쉼표 목록)
const PHONEAPPS_CACHE = { apps: [] };
COMPONENTS.phoneApps = function () {
  const box = document.createElement('div');
  box.className = 'winapps';
  box.innerHTML = '<div class="wa-head"><div class="row-title"></div><div class="row-desc"></div></div><div class="wa-list"></div>';
  const title = box.querySelector('.row-title'), desc = box.querySelector('.row-desc'), list = box.querySelector('.wa-list');
  let apps = PHONEAPPS_CACHE.apps;
  let query = '', loading = false;
  const bar = document.createElement('div');
  box.insertBefore(bar, list);
  const csv = (k) => String(D.settings[k] || '').split(',').map((x) => x.trim()).filter(Boolean);
  const offList = () => csv('phoneNotifyOff');
  const picked = () => D.settings.phoneNotifyMode === 'picked';
  const shown = (pkg) => (picked() ? csv('phoneNotifyOn').includes(pkg) : !offList().includes(pkg));          // 켜짐 = 노치에 띄움
  const put = (k, v) => { D.settings[k] = v; queuePatch('settings', k, v); };
  const setShown = (pkgs, on) => {
    const key = picked() ? 'phoneNotifyOn' : 'phoneNotifyOff';
    let cur = csv(key);
    for (const p of pkgs) {
      const has = cur.includes(p);
      const want = picked() ? on : !on;          // 고른 앱 목록은 '켠 앱', 끈 앱 목록은 '끈 앱'
      if (want && !has) cur.push(p); else if (!want && has) cur = cur.filter((x) => x !== p);
    }
    put(key, cur.join(','));
  };
  const render = () => {
    title.textContent = tr(L('노치에 띄울 앱', 'Apps shown in the notch'));
    desc.textContent = tr(L('알림을 보낸 앱이 여기에 나타나요. 끄면 그 앱의 알림은 노치에 띄우지 않아요.', 'Apps show up here after they send a notification. Turn one off to hide its notifications in the notch.'));
    list.textContent = '';
    if (!bar.firstChild) {
      bar.className = 'wa-bar';
      bar.innerHTML = '<input type="text" class="txt wa-q" spellcheck="false" autocomplete="off"><button type="button" class="btn wa-all"></button><button type="button" class="btn wa-none"></button><button type="button" class="btn wa-load"></button>';
      const qi = bar.querySelector('.wa-q');
      qi.addEventListener('input', () => { query = qi.value.trim().toLowerCase(); render(); });
      const vis = () => apps.filter((a) => !query || a.name.toLowerCase().includes(query) || a.pkg.toLowerCase().includes(query)).map((a) => a.pkg);
      bar.querySelector('.wa-all').addEventListener('click', () => { setShown(vis(), true); updateAll(); });
      bar.querySelector('.wa-none').addEventListener('click', () => { setShown(vis(), false); updateAll(); });
      bar.querySelector('.wa-load').addEventListener('click', async () => {
        const api = getApi(); if (!api || !api.phone_fetch_apps || loading) return;
        loading = true; render();
        let r = null; try { r = await api.phone_fetch_apps(); } catch (e) { r = null; }
        loading = false;
        if (r && r.ok) { apps = r.apps || []; PHONEAPPS_CACHE.apps = apps; toast(tr(L('폰의 앱 목록을 불러왔어요', 'Loaded the phone\'s app list')) + (r.added ? ' (+' + r.added + ')' : '')); }
        else toast(tr(L('폰에서 앱 목록을 받지 못했어요. 폰이 연결돼 있는지 확인해 주세요.', 'Could not get the app list from the phone. Check that it is connected.')));
        render();
      });
    }
    bar.querySelector('.wa-q').placeholder = tr(L('앱 찾기', 'Find an app'));
    bar.querySelector('.wa-all').textContent = tr(L('모두 켜기', 'All on'));
    bar.querySelector('.wa-none').textContent = tr(L('모두 끄기', 'All off'));
    bar.querySelector('.wa-load').textContent = loading ? tr(L('불러오는 중…', 'Loading…')) : tr(L('폰의 앱 불러오기', 'Load the phone\'s apps'));
    bar.querySelector('.wa-load').disabled = loading;
    const shownApps = apps.filter((a) => !query || a.name.toLowerCase().includes(query) || a.pkg.toLowerCase().includes(query));
    if (!apps.length) {
      const e = document.createElement('div'); e.className = 'row-desc wa-empty'; e.textContent = tr(L('아직 알림을 보낸 앱이 없어요. ‘폰의 앱 불러오기’를 누르면 폰에 설치된 앱이 모두 나타나요.', 'No app has sent a notification yet. Press “Load the phone\'s apps” to list every app installed on the phone.')); list.appendChild(e);
    } else if (!shownApps.length) {
      const e = document.createElement('div'); e.className = 'row-desc wa-empty'; e.textContent = tr(L('찾는 앱이 없어요.', 'No matching app.')); list.appendChild(e);
    }
    for (const a of shownApps) {
      const isOff = !shown(a.pkg);
      const row = document.createElement('div');
      row.className = 'wa-row' + (isOff ? ' off' : '');
      row.dataset.pkg = a.pkg;
      row.innerHTML = '<span class="wa-name"></span><span class="wa-n"></span><div class="sw" role="switch"></div>';
      row.querySelector('.wa-name').textContent = a.name;
      row.querySelector('.wa-n').textContent = a.count > 0 ? lx(`${a.count}건`, `${a.count}×`, `${a.count} 条`, `${a.count} 件`) : '';
      const sw = row.querySelector('.sw'); sw.setAttribute('aria-checked', String(!isOff));
      sw.addEventListener('click', () => { setShown([a.pkg], isOff); updateAll(); });
      list.appendChild(row);
    }
  };
  const refresh = async () => {
    const api = getApi();
    if (!api || !api.phone_notify_apps) return;
    let d; try { d = await api.phone_notify_apps(); } catch (e) { return; }
    if (!d) return;
    apps = d.apps || []; PHONEAPPS_CACHE.apps = apps;
    render();
  };
  refresh();
  const timer = setInterval(() => { if (!document.body.contains(box)) { clearInterval(timer); return; } refresh(); }, 3000);
  return { el: box, update: () => { box.classList.toggle('disabled', D.settings.phoneNotify === false); render(); } };
};

COMPONENTS.tabs = function () {
  const box = document.createElement('div');
  box.className = 'card tabs';
  const list = document.createElement('div');
  const foot = document.createElement('div');
  foot.className = 'tabfoot';
  box.append(list, foot);
  let tabSig = '';
  const render = (force) => {
    const sig = D.settings.tabOrder + '|' + D.settings.tabHidden + '|' + LANG;
    if (force !== true && sig === tabSig) return;
    tabSig = sig;
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
    queuePatch('settings', 'tabOrder', order, true); queuePatch('settings', 'tabHidden', hidden, true);
    render();
    if (flashId) { const r = list.querySelector(`.tabrow[data-id="${flashId}"]`); if (r && r.animate && !animOff()) r.animate([{ background: 'rgba(91,140,255,.35)' }, { background: 'transparent' }], { duration: 700 }); }
  };
  render(true);
  return { el: box, update: () => render() };
};

COMPONENTS.plugins = function () {
  const box = document.createElement('div');
  box.className = 'plugwrap';
  let timer = null;
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


// 작은 노치에 띄울 항목을 많이 켜면(작은 노치는 최대 네 칸) 시계·타이머가 밀려날 수 있다는 경고
COMPONENTS.satWarn = function () {
  const box = document.createElement('div');
  box.className = 'card satwarn';
  box.style.cssText = 'padding:10px 14px;font-size:12px;line-height:1.5;border:1px solid rgba(255,180,60,.45);background:rgba(255,180,60,.10)';
  const render = () => {
    const s = D.settings;
    const n = satCount();
    const off = s.satellite === 'off';
    box.hidden = !(n > 0 && off) && n < 2;
    box.textContent = off ? S('swWarnOff') : S('swWarnMany');
  };
  render();
  return { el: box, update: render };
};

// 설정 줄(.row) 모양 그대로 만드는 도우미: 왼쪽 제목·설명, 오른쪽 조작
function compRow(title, desc) {
  const row = document.createElement('div'); row.className = 'row';
  const text = document.createElement('div'); text.className = 'row-text';
  const ti = document.createElement('div'); ti.className = 'row-title'; ti.textContent = title || '';
  const de = document.createElement('div'); de.className = 'row-desc'; de.textContent = desc || '';
  text.append(ti, de);
  const ctl = document.createElement('div'); ctl.className = 'row-ctl comp';          // comp: 되돌리기 점이 차지하는 자리를 비워 둬서, 일반 줄의 조작과 오른쪽 끝이 같다
  row.append(text, ctl);
  return { row, title: ti, desc: de, ctl, text };
}
function compField(extra) { const i = document.createElement('input'); i.className = 'txt' + (extra ? ' ' + extra : ''); i.spellcheck = false; i.autocomplete = 'off'; return i; }
function compBtn(label) { const b = document.createElement('button'); b.className = 'btn'; b.type = 'button'; b.textContent = label; return b; }


// 폰 앱(Dalu Link): 설치 QR(같은 와이파이의 폰이 앱을 받는다), 연결 QR(페어링), 연결된 폰과 해제
let LINK_POLL = null;
const PENDING_SAVES = new Set();          // 입력 뒤 0.5초 기다렸다 저장하는 편집기들: 그 사이에 창을 닫으면 대기 중인 것을 바로 저장한다
window.addEventListener('pagehide', () => { for (const f of Array.from(PENDING_SAVES)) { try { f(); } catch (e) { /* 창이 닫히는 중 */ } } });
COMPONENTS.linkPair = function () {
  if (LINK_POLL) { clearInterval(LINK_POLL); LINK_POLL = null; }
  const box = document.createElement('div');
  box.className = 'linkpair';
  const stat = compRow('', '');
  const s1 = compRow('', ''); const b1 = compBtn(''); s1.ctl.appendChild(b1);
  const qr1 = document.createElement('div'); qr1.className = 'linkqr'; qr1.hidden = true;
  const s2 = compRow('', ''); const b2 = compBtn(''); s2.ctl.appendChild(b2);
  const qr2 = document.createElement('div'); qr2.className = 'linkqr'; qr2.hidden = true;
  const devs = document.createElement('div');
  const note = compRow('', ''); note.title.style.display = 'none';
  const upd = compRow('', ''); const bu = compBtn(''); upd.ctl.appendChild(bu); upd.row.hidden = true;          // 폰 앱 버전(Dalu 에 든 앱 파일보다 낮으면 '폰에 알리기')
  box.append(stat.row, upd.row, s1.row, qr1, s2.row, qr2, devs, note.row);
  let st = null, pairExpiry = 0, timer = null, wasConnected = false;
  const fmt = (k, o) => Object.keys(o || {}).reduce((a, x) => a.replace('{' + x + '}', o[x]), S(k));
  const showQr = (el, svg, line1, line2) => {
    el.textContent = '';
    const w = document.createElement('div'); w.innerHTML = svg || ''; el.appendChild(w);
    const sv = w.querySelector('svg');          // 크기 속성만 있고 viewBox 가 없는 그림이 와도 상자에 꽉 차게 맞춘다
    if (sv) { if (!sv.getAttribute('viewBox') && sv.getAttribute('width') && sv.getAttribute('height')) sv.setAttribute('viewBox', '0 0 ' + sv.getAttribute('width') + ' ' + sv.getAttribute('height')); sv.removeAttribute('width'); sv.removeAttribute('height'); }
    const a = document.createElement('div'); a.className = 'qrnote'; a.textContent = line1 || ''; el.appendChild(a);
    const b = document.createElement('div'); b.className = 'qrnote dim'; b.textContent = line2 || ''; el.appendChild(b);
    el.hidden = false;
    return b;
  };
  const labels = () => {
    s1.title.textContent = S('lkStep1'); s1.desc.textContent = S('lkStep1d'); b1.textContent = S('lkShowInstall');
    s2.title.textContent = S('lkStep2'); s2.desc.textContent = S('lkStep2d'); b2.textContent = S('lkShowPair');
    note.desc.textContent = S('lkFirewall');
    render();
  };
  const render = () => {
    const on = !!D.settings.linkOn;
    s1.row.hidden = s2.row.hidden = !on; if (!on) { qr1.hidden = qr2.hidden = true; }
    if (!on) { stat.title.textContent = S('lkOff'); stat.desc.textContent = ''; devs.textContent = ''; upd.row.hidden = true; return; }
    if (st && st.enabled && !st.listening) { stat.title.textContent = S('lkServerErr'); stat.desc.textContent = ''; return; }
    if (st && st.connected) {
      const d = (st.devices || []).find((x) => x.connected) || (st.devices || [])[0];
      stat.title.textContent = fmt('lkConnected', { n: d ? d.name : '' });
      stat.desc.textContent = st.battery != null ? fmt('lkBatt', { p: st.battery }) + (st.charging ? ' · ' + S('lkCharging') : '') : '';
    } else { stat.title.textContent = S('lkNone'); stat.desc.textContent = ''; }
    // 중계 서버(모바일 데이터용) 상태: 켜 둔 경우에만 한 줄 보여 준다
    if (D.settings.linkRelayOn) {
      const rl = st && st.relay;
      const line = S('lkRelay_' + ((rl && rl.state) || 'off'));          // 중계 서버는 기본 서버만 쓴다(주소를 적을 일이 없다)
      stat.desc.textContent = (stat.desc.textContent ? stat.desc.textContent + ' · ' : '') + line;
    }
    // 폰 앱 버전: 연결된 폰의 앱이 Dalu 에 든 앱 파일보다 낮으면 알린다(새 설치가 필요한 옛 앱은 아래 '설치 QR 보기'로)
    {
      const pd = ((st && st.devices) || []).find((x) => x.connected), apk = st && st.apk;
      if (pd && apk) {
        const ac = pd.app_code || 0;
        upd.row.hidden = false;
        if (ac > 0 && ac >= apk.code) { upd.title.textContent = fmt('lkApp', { v: pd.app_name }); upd.desc.textContent = S('lkAppOk'); bu.hidden = true; }
        else if (ac > 0) { upd.title.textContent = fmt('lkAppNew', { v: apk.name }); upd.desc.textContent = S('lkAppNewD'); bu.hidden = false; bu.textContent = S('lkAppNotify'); }
        else { upd.title.textContent = S('lkAppOld'); upd.desc.textContent = fmt('lkAppOldD', { v: apk.name }); bu.hidden = true; }
      } else upd.row.hidden = true;
    }
    devs.textContent = '';
    for (const d of (st && st.devices) || []) {
      const r = compRow(d.name, '');
      const f = compBtn(S('lkForget')); f.addEventListener('click', async () => { const api = getApi(); if (api && api.link_forget) { await api.link_forget(d.id); refresh(); } });
      r.ctl.appendChild(f); devs.appendChild(r.row);
    }
  };
  const refresh = async () => {
    const api = getApi(); if (!api || !api.link_status) return;
    try { st = await api.link_status(); } catch (e) { return; }
    if (st && st.connected && !wasConnected && !qr2.hidden) { qr2.hidden = true; pairExpiry = 0; showToastSafe(S('lkJustConnected')); }
    wasConnected = !!(st && st.connected);
    render();
  };
  const showToastSafe = (m) => { try { if (typeof toast === 'function') toast(m); } catch (e) { /* 알림 문구는 없어도 된다 */ } };
  bu.addEventListener('click', async () => {
    const api = getApi(); if (!api || !api.link_app_notify) return;
    let r = null; try { r = await api.link_app_notify(); } catch (e) { r = null; }
    showToastSafe(S(r && r.ok ? 'lkAppNotified' : 'lkAppNotifyFail'));
  });
  b1.addEventListener('click', async () => {
    const api = getApi(); if (!api || !api.link_apk_start) return;
    let r = null; try { r = await api.link_apk_start(); } catch (e) { r = null; }
    if (!r || !r.ok) { qr1.hidden = false; qr1.textContent = S(r && r.error === 'noapk' ? 'lkNoApk' : (r && r.error === 'nonet' ? 'lkNoNet' : 'lkErr')); return; }
    showQr(qr1, r.svg, r.url, fmt('lkOpenFor', { m: 15 }) + ' · ' + r.mb + ' MB');
  });
  b2.addEventListener('click', async () => {
    const api = getApi(); if (!api || !api.link_pair_start) return;
    let r = null; try { r = await api.link_pair_start(); } catch (e) { r = null; }
    if (!r || !r.ok) { qr2.hidden = false; qr2.textContent = S('lkServerErr'); return; }
    pairExpiry = r.expires * 1000;
    const line = showQr(qr2, r.svg, (r.hosts || []).join(', ') + ':' + r.port + (r.relay ? ' · ' + S('lkRelayQr') : ''), '');
    clearInterval(timer);
    timer = setInterval(() => {
      if (!document.body.contains(box)) { clearInterval(timer); return; }          // 이 설정 화면을 떠났다
      const left = Math.round((pairExpiry - Date.now()) / 1000);
      if (qr2.hidden || left <= 0) { clearInterval(timer); if (!qr2.hidden) { line.textContent = S('lkExpired'); } return; }
      line.textContent = fmt('lkExpires', { s: left });
    }, 1000);
  });
  labels();
  refresh();
  LINK_POLL = setInterval(() => { if (!document.body.contains(box)) { clearInterval(LINK_POLL); LINK_POLL = null; return; } refresh(); }, 2000);          // 다른 설정 탭으로 가면 멈춘다
  return { el: box, update: labels };
};

const WX_LOC = { status: '' };      // 윈도우 위치 서비스 상태(이 창을 여는 동안 기억)
// 날씨 도시 고르기: '검색'을 눌렀을 때만 입력한 이름을 서버(Open-Meteo 지오코딩)로 보낸다. 도시를 고르면 그때부터 날씨가 켜진다(따로 켜는 스위치는 없다)
COMPONENTS.weatherCity = function () {
  const box = document.createElement('div');
  box.className = 'wxcity';
  const info = compRow(S('wxTitle'), S('wxPrivacy'));
  const loc = compRow(S('wxLocTitle'), '');
  const locBtn = compBtn(S('wxLocCheck')); loc.ctl.appendChild(locBtn);
  const city = compRow(S('wxCityTitle'), '');
  city.row.classList.add('stack');          // 제목·설명 한 줄, 그 아래에 입력칸(늘어남) + 검색·지우기
  const inp = compField('wide'); inp.maxLength = 60;
  const go = compBtn(''); const clr = compBtn('');
  city.ctl.append(inp, go, clr);
  const res = document.createElement('div');
  box.append(info.row, loc.row, city.row, res);
  const locUi = () => { loc.row.hidden = !D.settings.weatherLocate; loc.title.textContent = S('wxLocTitle'); locBtn.textContent = S('wxLocCheck'); loc.desc.textContent = S('wxLoc_' + (WX_LOC.status || 'unknown')) || ''; };
  const locCheck = async (force) => {
    const api = getApi(); if (!api || !api.location_check) return;
    loc.desc.textContent = S('wxLocChecking');
    let r = null; try { r = await api.location_check(!!force); } catch (e) { r = null; }
    WX_LOC.status = (r && r.status) || 'error'; locUi();
  };
  locBtn.addEventListener('click', () => locCheck(true));
  const put = (k, v) => commit({ path: 'settings', key: k, type: 'toggle' }, v);
  const setCity = (c) => { put('weatherCity', c ? (c.label || c.name) : ''); put('weatherLat', c ? c.lat : 0); put('weatherLon', c ? c.lon : 0); };
  const labels = () => {
    info.title.textContent = S('wxTitle'); info.desc.textContent = S('wxPrivacy'); city.title.textContent = S('wxCityTitle');
    inp.placeholder = S('wxSearchPh'); go.textContent = S('wxSearchBtn'); clr.textContent = S('wxClearCity');
    city.desc.textContent = D.settings.weatherCity ? S('wxCityNow').replace('{c}', D.settings.weatherCity) : S('wxCityNone');
    clr.disabled = !D.settings.weatherCity;
    locUi();
  };
  const msgRow = (text) => { const r = compRow(text, ''); r.title.style.fontWeight = '400'; r.title.style.color = 'var(--dim)'; res.appendChild(r.row); };
  const search = async () => {
    const q = inp.value.trim(); if (q.length < 2) return;
    const api = getApi(); if (!api || !api.weather_search) return;
    res.textContent = ''; msgRow(S('wxSearching'));
    let r = null; try { r = await api.weather_search(q); } catch (e) { r = null; }
    res.textContent = '';
    if (!r || r.status !== 'ok') { msgRow(S('wxSearchFail')); return; }
    if (!r.items.length) { msgRow(S('wxNoResult')); return; }
    for (const c of r.items) {
      const row = compRow(c.label || c.name, '');
      const pick = compBtn(S('wxPick')); pick.addEventListener('click', () => { setCity(c); res.textContent = ''; inp.value = ''; labels(); });
      row.ctl.appendChild(pick); res.appendChild(row.row);
    }
  };
  go.addEventListener('click', search);
  inp.addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); search(); } });
  clr.addEventListener('click', () => { setCity(null); labels(); });
  labels();
  if (!WX_LOC.status && D.settings.weatherLocate) locCheck(false);          // 위치를 읽는 것만(서버로는 아무것도 보내지 않음) 한 번 확인해서 상태를 보여 준다
  return { el: box, update: labels };
};

// 직접 만드는 D-day 목록(이름 + 날짜 + 완료/삭제): 일정 탭 맨 위에 보인다. 완료한 것은 숨겨지고 여기서 되돌릴 수 있다
COMPONENTS.ddayEditor = function () {
  const box = document.createElement('div');
  box.className = 'ddedit';
  let items = [];
  let saveTimer = null;
  const flushDd = async () => { clearTimeout(saveTimer); PENDING_SAVES.delete(flushDd); const api = getApi(); if (!api || !api.dday_set) return; await api.dday_set(items.filter((x) => x.name && x.date)); };
  const save = () => {
    clearTimeout(saveTimer);
    PENDING_SAVES.add(flushDd);
    saveTimer = setTimeout(flushDd, 500);
  };
  const render = () => {
    box.textContent = '';
    const head = compRow(S('ddTitle'), S('ddHint'));
    const add = compBtn('+ ' + S('ddAdd'));
    add.addEventListener('click', () => {
      if (items.length >= 40) { toast(S('ddFull')); return; }
      const t = new Date(), p = (x) => String(x).padStart(2, '0');
      items.push({ id: 'd' + Date.now().toString(36), name: '', date: `${t.getFullYear()}-${p(t.getMonth() + 1)}-${p(t.getDate())}`, done: false, cal: false }); render();
    });
    head.ctl.appendChild(add); box.appendChild(head.row);
    items.forEach((it, idx) => {
      const row = compRow('', '');
      row.text.textContent = '';
      const nm = compField('wide'); nm.maxLength = 30; nm.placeholder = S('ddName'); nm.value = it.name || '';
      if (it.done) { nm.style.opacity = '0.5'; nm.style.textDecoration = 'line-through'; }
      nm.addEventListener('input', () => { it.name = nm.value; save(); });
      row.text.appendChild(nm);
      const dt = compField(); dt.type = 'date'; dt.value = it.date || '';
      dt.addEventListener('change', () => { it.date = dt.value; save(); });
      const done = compBtn(it.done ? S('ddRestore') : S('ddDone2')); done.classList.add('dd-done');          // 폭을 맞춰서 줄마다 날짜 칸 위치가 같게
      done.addEventListener('click', () => { it.done = !it.done; save(); render(); });
      const rm = compBtn(''); rm.innerHTML = uiIconSvg('close', 14); rm.title = S('ddDel');
      rm.addEventListener('click', () => { items.splice(idx, 1); save(); render(); });
      row.ctl.append(dt, done, rm);
      box.appendChild(row.row);
    });
    if (!items.length) { const e = compRow(S('ddEmpty'), ''); e.title.style.cssText = 'font-weight:400;color:var(--dim)'; box.appendChild(e.row); }
  };
  const api = getApi();
  if (api && api.dday_get) api.dday_get().then((d) => { items = ((d && d.items) || []).map((x) => Object.assign({}, x)); render(); }, () => render());
  render();
  return { el: box, update: () => {} };
};

COMPONENTS.launcher = function () {
  const box = document.createElement('div');
  box.className = 'card lnedit';
  let items = LAUNCHER.map((x) => Object.assign({}, x));
  let saveTimer = null;
  const flushLn = async () => {
    clearTimeout(saveTimer); PENDING_SAVES.delete(flushLn);
    const api = getApi(); if (!api) return;
    const r = await api.launcher_set(items);
    if (r && r.status === 'ok') { LAUNCHER = r.items; }
  };
  const save = () => {
    clearTimeout(saveTimer);
    PENDING_SAVES.add(flushLn);
    saveTimer = setTimeout(flushLn, 500);
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
    if (sec.tab || sec.offNote) {
      const note = document.createElement('div');
      note.className = 'secnote';
      const upd = () => {
        let msg = '';
        if (sec.tab && tabIsOff(sec.tab)) msg = S('tabOffNote').replace('{t}', tabName(sec.tab));
        else if (sec.offNote && sec.offNote.when(D)) msg = tr(sec.offNote.text);
        if (note.textContent !== msg) note.textContent = msg;
        note.hidden = !msg;
        note.classList.toggle('tabnote', !!(sec.tab && tabIsOff(sec.tab)));
      };
      block.appendChild(note);
      renderedRows.push({ item: { id: 'note' }, el: note, update: upd });
    }
    const compOnly = sec.items.filter((it) => it.type !== 'hidden').every((it) => it.type === 'custom' && !it.card);          // card: true 이면 컴포넌트도 다른 설정처럼 카드 안에 둔다   // 컴포넌트만 있는 구역은 바깥 카드 없이 컴포넌트가 자기 모양을 정한다
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
        if (it.tab) {
          el.addEventListener('click', (e) => { if (el.classList.contains('tab-blocked')) { e.preventDefault(); e.stopPropagation(); toast(S('tabOffMsg').replace('{t}', tabName(it.tab))); } }, true);
          renderedRows.push({ item: it, el, update: () => { c.update(); el.classList.toggle('tab-blocked', tabIsOff(it.tab)); } });
        } else renderedRows.push({ item: it, el, update: c.update });
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
    b.innerHTML = `${icon(p.icon)}<span>${tr(p.nav || p.title)}</span>`;          // 사이드바에는 짧은 이름(nav)이 있으면 그것을 쓴다(한 줄에 들어가게)
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
  $('btnClose').addEventListener('click', async () => {
    flushPatch();
    try { await Promise.all(Array.from(PENDING_SAVES).map((f) => f())); } catch (e) { /* 저장 실패는 닫기를 막지 않는다 */ }          // 대기 중인 D-day·바로가기 편집을 저장한 뒤 닫는다
    const api = getApi(); if (api) api.settings_close();
  });
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
