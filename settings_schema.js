// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
// Copyright (c) 2026 Flirty_BananaMilk — 상업적 이용 금지, 자세한 내용은 LICENSE
// ========================================================
// 설정 항목 정의 (설정 창이 이걸 보고 화면을 만든다). 항목을 추가하려면 여기에 한 줄만 넣으면 된다.
//   path: 'settings' | 'pomo' | 'water'  (data.json 의 섹션)   key: 'a.b' 처럼 점으로 중첩 가능
//   type: toggle | slider | seg | button | info | custom
//   enabledIf(data): false 면 흐리게 하고 못 건드리게 한다
// 기본값(def)은 app.js 의 DEFAULT_STORE 와 같아야 한다 (테스트가 둘을 비교한다).
// ========================================================
const L = (ko, en) => ({ ko, en });
const pct = (v) => `${v}%`;
const ms = (v) => (v >= 1000 ? `${(v / 1000).toFixed(v % 1000 ? 1 : 0)}초` : `${v}ms`);
const msEn = (v) => (v >= 1000 ? `${(v / 1000).toFixed(v % 1000 ? 1 : 0)}s` : `${v}ms`);

const SETTINGS_PAGES = [
  {
    id: 'general', icon: 'sliders', title: L('일반', 'General'),
    sections: [
      { title: L('기본', 'Basics'), items: [
        { id: 'lang', type: 'seg', path: 'settings', key: 'lang', def: 'ko', label: L('언어', 'Language'),
          options: [{ v: 'ko', label: L('한국어', '한국어') }, { v: 'en', label: L('English', 'English') }, { v: 'zh', label: L('简体中文', '简体中文') }, { v: 'ja', label: L('日本語', '日本語') }] },
        { id: 'autostart', type: 'toggle', special: 'autostart', label: L('윈도우 시작 시 자동 실행', 'Launch at Windows startup'),
          desc: L('로그인하면 노치가 자동으로 뜹니다.', 'The notch appears automatically when you sign in.') },
        { id: 'sound', type: 'toggle', path: 'settings', key: 'sound', def: true, label: L('알림음', 'Notification sounds'),
          desc: L('포모도로 종료, 물 마시기 알림 등에서 소리를 냅니다.', 'Play a chime for the Pomodoro timer and water reminders.') },
      ] },
      { title: L('시계', 'Clock'), items: [
        { id: 'clock24', type: 'toggle', path: 'settings', key: 'clock24', def: true, label: L('24시간제', '24-hour clock'),
          desc: L('끄면 오전/오후(12시간제)로 표시합니다.', 'Off shows a 12-hour clock.') },
        { id: 'clockSeconds', type: 'toggle', path: 'settings', key: 'clockSeconds', def: false, label: L('초 표시', 'Show seconds') },
      ] },
      { title: L('단축키', 'Hotkeys'), items: [
        { id: 'hotkeysOn', type: 'toggle', path: 'settings', key: 'hotkeysOn', def: true, label: L('전역 단축키 사용', 'Enable global hotkeys'),
          desc: L('어떤 앱이 앞에 있어도 동작합니다. 다른 프로그램이 쓰는 조합이면 등록되지 않아요.', 'Work in any app. Combinations already used elsewhere cannot be registered.') },
        { id: 'hkToggle', type: 'text', path: 'settings', key: 'hkToggle', def: 'Ctrl+Alt+N', placeholder: L('예: Ctrl+Alt+N', 'e.g. Ctrl+Alt+N'), descFn: 'hotkey', label: L('노치 펼치기/접기', 'Expand / collapse the notch'), enabledIf: (d) => d.settings.hotkeysOn },
        { id: 'hkSettings', type: 'text', path: 'settings', key: 'hkSettings', def: 'Ctrl+Alt+S', placeholder: L('예: Ctrl+Alt+S', 'e.g. Ctrl+Alt+S'), descFn: 'hotkey', label: L('설정 열기', 'Open settings'), enabledIf: (d) => d.settings.hotkeysOn },
        { id: 'hkMixer', type: 'text', path: 'settings', key: 'hkMixer', def: 'Ctrl+Alt+V', placeholder: L('예: Ctrl+Alt+V', 'e.g. Ctrl+Alt+V'), descFn: 'hotkey', label: L('볼륨 믹서 열기', 'Open the volume mixer'), enabledIf: (d) => d.settings.hotkeysOn },
        { id: 'hkCapture', type: 'text', path: 'settings', key: 'hkCapture', def: 'Ctrl+Alt+P', placeholder: L('예: Ctrl+Alt+P', 'e.g. Ctrl+Alt+P'), descFn: 'hotkey', label: L('캡처 모드 켜기/끄기 (스크린샷·녹화용)', 'Toggle capture mode (screenshots & video)'), enabledIf: (d) => d.settings.hotkeysOn },
        { id: 'hkLyrics', type: 'text', path: 'settings', key: 'hkLyrics', def: 'Ctrl+Alt+L', placeholder: L('예: Ctrl+Alt+L', 'e.g. Ctrl+Alt+L'), descFn: 'hotkey', label: L('가사 켜기/끄기', 'Toggle lyrics'), enabledIf: (d) => d.settings.hotkeysOn },
      ] },
      { title: L('앱', 'App'), items: [
        { id: 'restart', type: 'button', action: 'restart', label: L('앱 재시작', 'Restart app'), btn: L('재시작', 'Restart'),
          desc: L('설정이 이상하게 적용될 때 다시 시작해 보세요.', 'Try this if something does not look right.') },
        { id: 'recenter', type: 'button', action: 'recenter', label: L('노치를 화면 가운데로', 'Re-center the notch'), btn: L('가운데로', 'Center') },
      ] },
    ],
  },
  {
    id: 'media', icon: 'music', title: L('가사·미디어', 'Lyrics & Media'),
    sections: [
      { title: L('가사', 'Lyrics'), items: [
        { id: 'lyricsOn', type: 'toggle', path: 'settings', key: 'lyricsOn', def: true, label: L('가사 표시', 'Show lyrics'),
          desc: L('끄면 곡 정보만 보입니다.', 'Off shows only track info.') },
        { id: 'wordSync', type: 'toggle', path: 'settings', key: 'wordSync', def: true, label: L('단어 단위 하이라이트', 'Word-by-word highlight'),
          desc: L('끄면 줄 단위로만 강조합니다 (단어 싱크가 있는 곡에서).', 'Off highlights whole lines only.'), enabledIf: (d) => d.settings.lyricsOn },
        { id: 'lyricSize', type: 'slider', path: 'settings', key: 'lyricSize', def: 100, min: 70, max: 140, step: 5, fmt: pct,
          label: L('가사 글자 크기', 'Lyric size'), enabledIf: (d) => d.settings.lyricsOn },
        { id: 'lyricGlow', type: 'toggle', path: 'settings', key: 'lyricGlow', def: true, label: L('가사 글로우', 'Lyric glow'),
          desc: L('지금 부르는 단어에 은은한 빛을 줍니다.', 'A soft glow on the word being sung.'), enabledIf: (d) => d.settings.lyricsOn },
      ] },
      { title: L('다른 앱의 음악 (Spotify, 브라우저 등)', 'Other apps (Spotify, browsers…)'), items: [
        { id: 'smtcOn', type: 'toggle', path: 'settings', key: 'smtcOn', def: true, label: L('다른 앱의 재생 정보 표시', 'Show media from other apps'),
          desc: L('윈도우 미디어 컨트롤에 올라온 곡을 보여 주고 제어합니다.', 'Reads and controls what Windows media controls report.') },
        { id: 'mediaPriority', type: 'seg', path: 'settings', key: 'mediaPriority', def: 'auto', label: L('둘 다 재생 중일 때', 'When both are playing'),
          desc: L('Cider와 다른 앱이 동시에 재생 중일 때 노치가 어느 쪽을 보여 줄지 정합니다.', 'Which one the notch shows when Cider and another app are playing at the same time.'),
          options: [{ v: 'auto', label: L('보던 쪽 유지', 'Keep current') }, { v: 'cider', label: L('Cider 우선', 'Prefer Cider') }, { v: 'other', label: L('다른 앱 우선', 'Prefer other')}],
          enabledIf: (d) => d.settings.smtcOn },
        { id: 'extLyrics', type: 'toggle', path: 'settings', key: 'extLyrics', def: true, label: L('외부 가사 검색', 'Search lyrics online'),
          desc: L('Cider가 아닌 앱의 곡 제목·아티스트·길이를 가사 서비스에 보내 가사를 찾습니다.', 'Sends the title, artist and length of non-Cider tracks to lyric services.'),
          enabledIf: (d) => d.settings.smtcOn },
        { id: 'extApple', type: 'toggle', path: 'settings', key: 'extApple', def: true, label: L('Apple Music (Cider 경유)', 'Apple Music (via Cider)'),
          desc: L('Cider가 켜져 있고 로그인돼 있으면, 어떤 앱에서 듣든 같은 곡의 Apple Music 가사(단어 싱크)를 Cider에서 받아 옵니다. 품질이 가장 좋아 먼저 시도해요.', 'With Cider running and signed in, finds the same song on Apple Music and fetches its word-synced lyrics through Cider, whatever app is playing. Best quality, tried first.'), indent: true,
          enabledIf: (d) => d.settings.smtcOn && d.settings.extLyrics },
        { id: 'extNetease', type: 'toggle', path: 'settings', key: 'extNetease', def: true, label: L('NetEase', 'NetEase'),
          desc: L('단어 싱크가 있는 곡이 많고 한·일·중 곡에 강합니다.', 'Often has word-level sync; strong for Asian songs.'), indent: true,
          enabledIf: (d) => d.settings.smtcOn && d.settings.extLyrics },
        { id: 'extLrclib', type: 'toggle', path: 'settings', key: 'extLrclib', def: true, label: L('LRCLIB', 'LRCLIB'),
          desc: L('오픈 가사 DB. 서양권 곡에 강합니다.', 'Open lyrics database; strong for Western songs.'), indent: true,
          enabledIf: (d) => d.settings.smtcOn && d.settings.extLyrics },
        { id: 'appFilterMode', type: 'seg', path: 'settings', key: 'appFilterMode', def: 'off', label: L('앱 필터', 'App filter'),
          options: [{ v: 'off', label: L('끔', 'Off') }, { v: 'allow', label: L('이 앱만', 'Only these') }, { v: 'block', label: L('이 앱 제외', 'Except these') }],
          desc: L('어떤 앱의 재생 정보를 보여 줄지 정합니다. Cider는 항상 표시됩니다.', 'Choose which apps may appear as media sources. Cider always does.'), enabledIf: (d) => d.settings.smtcOn },
        { id: 'appFilterList', type: 'text', path: 'settings', key: 'appFilterList', def: '', placeholder: L('예: spotify, chrome', 'e.g. spotify, chrome'),
          label: L('필터에 쓸 앱 이름', 'Apps for the filter'), desc: L('쉼표로 구분합니다. 앱 이름의 일부만 써도 됩니다.', 'Comma-separated; part of the name is enough.'), indent: true,
          enabledIf: (d) => d.settings.smtcOn && d.settings.appFilterMode !== 'off' },
        { id: 'clearCache', type: 'button', action: 'clearCache', label: L('가사 캐시 지우기', 'Clear lyric cache'), btn: L('지우기', 'Clear'),
          desc: L('찾은 가사와 “없음” 결과를 모두 지워 다음에 다시 찾습니다.', 'Forgets found lyrics and “not found” results.') },
      ] },
      { title: L('시각 효과', 'Visuals'), items: [
        { id: 'visualizer', type: 'toggle', path: 'settings', key: 'visualizer', def: true, label: L('음악 비주얼라이저', 'Music visualizer'),
          desc: L('PC에서 나는 소리에 맞춰 움직이는 막대. 끄면 오디오 분석도 멈춰 CPU를 아낍니다.', 'Bars that follow system audio. Off also stops the audio analysis.') },
        { id: 'vizGain', type: 'slider', path: 'settings', key: 'vizGain', def: 100, min: 50, max: 200, step: 10, fmt: pct, label: L('비주얼라이저 민감도', 'Visualizer sensitivity'),
          enabledIf: (d) => d.settings.visualizer },
        { id: 'artGlow', type: 'toggle', path: 'settings', key: 'artGlow', def: true, label: L('앨범 색 배경빛', 'Album-colored glow'),
          desc: L('앨범 아트의 색이 노치 안쪽에 은은하게 번집니다.', 'The cover art tints the inside of the notch.') },
        { id: 'glowStrength', type: 'slider', path: 'settings', key: 'glowStrength', def: 100, min: 30, max: 160, step: 10, fmt: pct, label: L('배경빛 세기', 'Glow strength'),
          enabledIf: (d) => d.settings.artGlow },
      ] },
    ],
  },
  {
    id: 'notify', icon: 'bell', title: L('알림', 'Notifications'),
    sections: [
      { title: L('윈도우 알림', 'Windows notifications'), items: [
        { id: 'winNotify', type: 'toggle', path: 'settings', key: 'winNotify', def: false, label: L('윈도우 알림이 오면 작은 동그라미로 알리기', 'Show a small circle when a Windows notification arrives'),
          desc: L('다른 앱(메신저 등)의 알림이 오면 큰 노치 옆에 종 모양 동그라미와 빨간 점이 떠서 “알림이 왔다”는 것만 알려 줘요. 누르면 윈도우 알림 센터가 열리고, 알림 센터를 열거나 윈도우에서 알림을 처리해도 사라져요. 알림의 제목·내용은 읽거나 저장하지 않고 어느 앱에서 왔는지만 봅니다. 윈도우 설정 › 개인 정보 및 보안 › 알림에서 알림 접근을 허용해야 해요.',
            'When another app (messenger, etc.) sends a Windows notification, a small circle with a bell and a red dot appears beside the notch — just a sign that one arrived. Click it to open the Windows notification center; it also goes away when you open the notification center or handle the notifications in Windows. Titles and contents are never read or stored; only the sending app is noted. Allow notification access in Windows Settings › Privacy & security › Notifications.') },
        { id: 'winNotifyIgnore', type: 'text', path: 'settings', key: 'winNotifyIgnore', def: '', placeholder: L('예: chrome, discord', 'e.g. chrome, discord'),
          label: L('알림을 무시할 앱', 'Apps to ignore'),
          desc: L('쉼표로 구분합니다. 앱 이름의 일부만 써도 돼요. 이 앱들의 알림은 동그라미로 알리지 않아요. 아래 “알림을 보낸 앱” 목록에서 끈 앱도 여기에 들어가요.', 'Comma-separated; part of the name is enough. Notifications from these apps do not show the circle. Apps you switch off in the “Apps that sent notifications” list below are added here too.'),
          indent: true, enabledIf: (d) => d.settings.winNotify },
        { id: 'winNotifyApps', type: 'custom', component: 'winApps' },
      ] },
      { title: L('보여 줄 알림', 'Show alerts for'), items: [
        { id: 'n_volume', type: 'toggle', path: 'settings', key: 'notify.volume', def: true, label: L('볼륨', 'Volume') },
        { id: 'n_brightness', type: 'toggle', path: 'settings', key: 'notify.brightness', def: true, label: L('밝기', 'Brightness') },
        { id: 'n_caps', type: 'toggle', path: 'settings', key: 'notify.caps', def: true, label: L('Caps Lock', 'Caps Lock') },
        { id: 'n_num', type: 'toggle', path: 'settings', key: 'notify.num', def: true, label: L('Num Lock', 'Num Lock') },
        { id: 'n_scroll', type: 'toggle', path: 'settings', key: 'notify.scroll', def: true, label: L('Scroll Lock', 'Scroll Lock') },
        { id: 'n_lang', type: 'toggle', path: 'settings', key: 'notify.lang', def: true, label: L('입력 언어 전환', 'Input language') },
        { id: 'n_power', type: 'toggle', path: 'settings', key: 'notify.power', def: true, label: L('충전기 연결/해제', 'Charger plugged / unplugged') },
        { id: 'n_battery_low', type: 'toggle', path: 'settings', key: 'notify.battery_low', def: true, label: L('배터리 부족', 'Low battery') },
        { id: 'n_net', type: 'toggle', path: 'settings', key: 'notify.net', def: true, label: L('인터넷 연결/끊김', 'Internet connected / lost') },
        { id: 'n_audio', type: 'toggle', path: 'settings', key: 'notify.audio_device', def: true, label: L('헤드폰·오디오 출력 변경', 'Headphones / audio output') },
        { id: 'n_buds', type: 'toggle', path: 'settings', key: 'notify.buds', def: true, label: L('이어버드 연결', 'Earbuds connected') },
        { id: 'n_buds_low', type: 'toggle', path: 'settings', key: 'notify.buds_low', def: true, label: L('이어버드 배터리 부족', 'Earbuds low battery') },
        { id: 'n_buds_alert', type: 'toggle', path: 'settings', key: 'notify.buds_alert', def: true, label: L('이어버드 충전 중지 경고', 'Earbuds charging-stopped warning'),
          desc: L('땀이나 얼룩 때문에 충전이 중지되면 이어버드가 보내는 신호를 받아 알려 줘요. 이어버드 탭의 “충전 상태·경고 항상 받기”가 켜져 있어야 해요.', 'Shows the warning earbuds send when sweat or a stain stops charging. Needs “Always watch charging status & warnings” (Earbuds tab) to be on.'),
          enabledIf: (d) => d.settings.budsWatch },
        { id: 'mediaKeys', type: 'toggle', path: 'settings', key: 'mediaKeys', def: true, label: L('미디어 키를 누르면 곡 보여 주기', 'Show the track on media keys'),
          desc: L('키보드의 재생/일시정지·이전·다음 키를 누를 때 노치가 곡 정보를 잠깐 보여 줍니다.', 'The notch briefly shows the track when you press a media key.') },
        { id: 'upNext', type: 'toggle', path: 'settings', key: 'upNext', def: true, label: L('다음 곡 미리 보여 주기', 'Show what plays next'),
          desc: L('곡이 끝나기 조금 전에 대기열의 다음 곡을 알려 줍니다 (Cider 재생 중일 때).', 'Shortly before a song ends, shows the next one in the queue (Cider only).') },
        { id: 'upNextSec', type: 'slider', path: 'settings', key: 'upNextSec', def: 12, min: 5, max: 40, step: 1, fmt: (v) => `${v}초 전`, fmtEn: (v) => `${v}s before the end`,
          label: L('다음 곡을 보여 줄 시점', 'When to show it'), enabledIf: (d) => d.settings.upNext },
        { id: 'n_capture', type: 'toggle', path: 'settings', key: 'notify.capture_mode', def: true, label: L('캡처 모드 안내', 'Capture mode notice'),
          desc: L('스크린샷·녹화용 캡처 모드를 켤 때 “캡처 모드 켜짐”으로 알려 줘요. 끄면 캡처 모드는 그대로 켜지고 안내만 보이지 않아요.', 'Shows “Capture mode on” when capture mode starts for screenshots or recording. Turn it off to keep capture mode but hide the notice.') },
        { id: 'n_track', type: 'toggle', path: 'settings', key: 'notify.track', def: true, label: L('곡이 바뀔 때 잠깐 보여 주기', 'Peek when the track changes'),
          desc: L('노치가 접혀 있을 때 새 곡 정보를 잠깐 펼쳐 보여 줍니다.', 'Briefly expands the notch for the new track.') },
      ] },
      { title: L('표시 방식', 'Behavior'), items: [
        { id: 'peekTime', type: 'slider', path: 'settings', key: 'peekTime', def: 100, min: 50, max: 250, step: 10, fmt: pct, label: L('알림 표시 시간', 'Alert duration'),
          desc: L('100%가 기본 길이입니다.', '100% is the default length.') },
        { id: 'testNotify', type: 'button', action: 'testNotify', label: L('테스트 알림', 'Send a test alert'), btn: L('보내기', 'Send') },
      ] },
    ],
  },
  {
    id: 'look', icon: 'palette', title: L('모양·동작', 'Look & Behavior'),
    sections: [
      { title: L('모양', 'Appearance'), items: [
        { id: 'theme', type: 'seg', path: 'settings', key: 'theme', def: 'black', label: L('테마', 'Theme'),
          options: [{ v: 'black', label: L('검정', 'Black') }, { v: 'glass', label: L('유리', 'Glass') }, { v: 'tint', label: L('앨범 색', 'Album tint') }],
          desc: L('유리: 가장자리에 빛이 도는 느낌, 앨범 색: 노치 아래쪽이 앨범 색으로 물듭니다. 노치 리퀴드 글래스 “전체”와 함께 쓰면 뒤 화면이 비치는 유리 위에 이 색이 얹혀요.', 'Glass adds a rim light; Album tint colors the bottom of the notch. With Liquid Glass “Full” the colour is laid over the see-through glass.') },
        { id: 'glassNotch', type: 'seg', path: 'settings', key: 'glassNotch', def: 'controls', label: L('노치 리퀴드 글래스', 'Liquid Glass notch'),
          options: [{ v: 'off', label: L('끔', 'Off') }, { v: 'controls', label: L('컨트롤', 'Controls') }, { v: 'full', label: L('전체', 'Full') }],
          desc: L('컨트롤: 노치 안의 버튼·타일이 뒤의 빛을 굴절시키는 유리가 됩니다. 전체: 노치 본체도 뒤의 화면을 비춥니다 — 이를 위해 노치 창을 화면 캡처에서 제외해요. 스크린샷·녹화에 노치가 어떻게 찍힐지는 아래 “캡처·영상 녹화에서 노치”에서 정해요.',
                  'Controls: buttons and tiles become lenses that refract the light behind them. Full: the notch body also reflects the screen behind it — the notch window is excluded from screen capture for this, and how the notch appears in screenshots and recordings is set under “Notch in screenshots & video” below.') },
        { id: 'glassStrength', type: 'slider', path: 'settings', key: 'glassStrength', def: 100, min: 0, max: 200, step: 10, fmt: pct, label: L('굴절 세기', 'Refraction strength'),
          desc: L('뒤의 빛·화면이 유리 가장자리에서 휘는 정도예요. 0%는 굴절 없이 반사광만, 너무 높으면 가장자리가 일그러져 보여요.', 'How strongly the light and screen behind bend at the glass edge. 0% keeps only the reflections; very high values distort the edges.'),
          indent: true, enabledIf: (d) => d.settings.glassNotch !== 'off' },
        { id: 'glassRim', type: 'toggle', path: 'settings', key: 'glassRim', def: true, label: L('노치 테두리 선', 'Notch outline'),
          desc: L('리퀴드 글래스 “전체”에서 노치 둘레를 따라 도는 밝은 선입니다. 끄면 테두리 없이 유리만 보여요.', 'The bright outline running around the notch in Liquid Glass “Full”. Turn it off to show only the glass.'),
          indent: true, enabledIf: (d) => d.settings.glassNotch === 'full' },
        { id: 'captureNotch', type: 'seg', path: 'settings', key: 'captureNotch', def: 'auto', label: L('캡처·영상 녹화에서 노치', 'Notch in screenshots & video'),
          desc: L('스크린샷·화면 녹화에 노치가 찍히는 방식을 정해요. “가리기”는 노치가 찍히지 않아요(노치 뒤 화면은 실시간으로 비쳐요). “자동”은 평소엔 가리다가, PrintScreen·Win+Shift+S·Win+Alt+R을 누르거나 OBS·반디캠 같은 녹화 프로그램이 켜져 있는 동안만 찍혀요(그동안 노치 뒤 화면은 멈춰요. 아주 빠른 PrintScreen은 놓칠 수 있어요). “표시”는 항상 찍히고, 노치 유리 뒤 화면은 정지 화면이 돼요. NVIDIA(지포스) 녹화는 가려진 창을 “보호된 콘텐츠”로 보고 바탕화면 녹화를 거부하기도 해서, 엔비디아로 영상을 찍을 때는 “표시”로 바꿔야 해요.', 'Chooses how the notch shows up in screenshots and screen recordings. “Hidden” keeps it out of them (the screen behind the notch shows through live). “Auto” keeps it out normally and shows it only while you press PrintScreen, Win+Shift+S or Win+Alt+R, or while a recorder such as OBS or Bandicam is running (the screen behind the notch freezes meanwhile; a very quick PrintScreen can be missed). “Shown” always puts it in, and the screen behind the notch glass becomes a still picture. NVIDIA recording may refuse to capture the desktop when a window is hidden from capture (“protected content”), so switch to “Shown” when you record with NVIDIA.'),
          options: [{ v: 'hide', label: L('가리기', 'Hidden') }, { v: 'auto', label: L('자동', 'Auto') }, { v: 'show', label: L('표시', 'Shown') }],
          indent: true, enabledIf: (d) => d.settings.glassNotch === 'full' },
        { id: 'monitor', type: 'seg', path: 'settings', key: 'monitor', def: 0, optionsFrom: 'monitors', label: L('노치를 띄울 모니터', 'Show the notch on'),
          descFn: 'monitors' },
        { id: 'uiScale', type: 'slider', path: 'settings', key: 'uiScale', def: 100, min: 80, max: 200, step: 5, fmt: pct,
          label: L('노치 크기', 'Notch size'),
          desc: L('노치와 그 안의 글자·버튼·가사까지 함께 커지고 작아져요. 화면이 커서 노치가 작게 보이거나 멀리서 볼 때 키우세요.', 'Scales the notch and everything in it — text, buttons, lyrics. Raise it on a big screen or when you sit far away.') },
        { id: 'compact', type: 'toggle', path: 'settings', key: 'compact', def: false, label: L('작은 노치', 'Compact notch'),
          desc: L('접혀 있을 때 더 작게 보입니다.', 'A smaller collapsed notch.') },
        { id: 'satellite', type: 'seg', path: 'settings', key: 'satellite', def: 'full', label: L('보조 노치', 'Satellite pill'),
          options: [{ v: 'off', label: L('끔', 'Off') }, { v: 'timer', label: L('타이머만', 'Timer only') }, { v: 'full', label: L('타이머+시계', 'Timer + clock') }],
          desc: L('음악이 나올 때 큰 노치 옆에 작은 노치가 두 개 붙고, 하나에 정보를 둘까지 담아 진행 중인 포모도로·타이머·스톱워치와 현재 시간을 보여 줘요(최대 네 개, 둘을 담으면 폭이 넓어져요). 오른쪽이 먼저, 그 뒤에 왼쪽이 나와요. 누르면 그 항목의 페이지가 열려요.', 'While music plays, two small pills sit beside the notch, each holding up to two items (up to four): your running Pomodoro, timer, stopwatch and the time. A pill holding two items gets wider. The right one appears first, then the left. Click an item to open its page.') },
        { id: 'compactClock', type: 'toggle', path: 'settings', key: 'compactClock', def: true, label: L('작은 노치에서 시계 표시', 'Clock in the compact notch'),
          desc: L('작은 노치로 음악이 나올 때 가운데에 현재 시간을 보여 줍니다.', 'Shows the time in the middle while music plays in the compact notch.'), indent: true,
          enabledIf: (d) => d.settings.compact },
      ] },
      { title: L('탭 구성', 'Tabs'), items: [
        { id: 'tabOrder', type: 'hidden', path: 'settings', key: 'tabOrder', def: 'music,pomo,timer,water,shelf,todo,clip,agenda,launcher,plugins,buds' },
        { id: 'tabHidden', type: 'hidden', path: 'settings', key: 'tabHidden', def: '' },
        { id: 'tabsConfig', type: 'custom', component: 'tabs' },
      ] },
      { title: L('펼침/접힘', 'Expand & collapse'), items: [
        { id: 'tabDock', type: 'toggle', path: 'settings', key: 'tabDock', def: true, label: L('페이지 점에 마우스를 올리면 아이콘으로', 'Icons when hovering the page dots'),
          desc: L('노치 아래의 작은 점 위에 마우스를 올리면 점이 탭 아이콘으로 바뀌어 누르기 쉬워요. 이때 노치 아래가 잠깐 조금 늘어나요.', 'Hover the small dots under the notch and they turn into tab icons that are easy to click. The notch grows a little at the bottom meanwhile.') },
        { id: 'tabDockDelay', type: 'slider', path: 'settings', key: 'tabDockDelay', def: 130, min: 0, max: 800, step: 10, fmt: ms, fmtEn: msEn, enabledIf: (d) => d.settings.tabDock !== false,
          label: L('아이콘이 나타나기까지 걸리는 시간', 'Delay before the icons appear'), desc: L('페이지 점 위에 마우스를 얼마나 올려 두어야 아이콘으로 바뀌는지 정합니다. 0이면 바로 바뀝니다.', 'How long the cursor must stay on the page dots before they turn into icons. 0 shows them right away.') },
        { id: 'tabDockLeave', type: 'slider', path: 'settings', key: 'tabDockLeave', def: 260, min: 0, max: 2000, step: 10, fmt: ms, fmtEn: msEn, enabledIf: (d) => d.settings.tabDock !== false,
          label: L('아이콘이 사라지기까지 걸리는 시간', 'Delay before the icons go away'), desc: L('마우스가 아이콘에서 벗어난 뒤 다시 작은 점으로 돌아가기까지 기다리는 시간입니다.', 'How long the icons stay after the cursor leaves them before they shrink back to dots.') },
        { id: 'tabDockMargin', type: 'slider', path: 'settings', key: 'tabDockMargin', def: 10, min: 4, max: 15, step: 1, fmt: (v) => `${v}px`, fmtEn: (v) => `${v}px`, enabledIf: (d) => d.settings.tabDock !== false,
          label: L('아이콘 위아래 여백', 'Space above & below the icons'), desc: L('아이콘 위쪽(내용과의 간격)과 아래쪽(노치 끝과의 간격)에 같은 여백을 둡니다. 키우면 아이콘이 아래로 내려가고, 아이콘이 보이는 동안 노치가 그만큼 더 길어집니다.', 'The same gap is kept above the icons (to the content) and below them (to the notch edge). A bigger gap makes the notch a little taller while the icons are shown.') },
        { id: 'hoverDelay', type: 'slider', path: 'settings', key: 'hoverDelay', def: 0, min: 0, max: 800, step: 50, fmt: ms, fmtEn: msEn,
          label: L('마우스를 올린 뒤 펼침 지연', 'Delay before expanding on hover'), desc: L('실수로 스칠 때 펼쳐지는 것을 막습니다.', 'Avoids expanding when the cursor just passes by.') },
        { id: 'collapseDelay', type: 'slider', path: 'settings', key: 'collapseDelay', def: 850, min: 200, max: 2500, step: 50, fmt: ms, fmtEn: msEn,
          label: L('마우스를 뗀 뒤 접힘 지연', 'Delay before collapsing'),
          desc: L('마우스가 노치에서 벗어난 뒤 접히기까지 기다리는 시간입니다.', 'How long the notch waits after the cursor leaves before it collapses.') },
        { id: 'idleMin', type: 'slider', path: 'settings', key: 'idleMin', def: 2, min: 1, max: 10, step: 1, fmt: (v) => `${v}분`, fmtEn: (v) => `${v} min`,
          label: L('일시정지 후 시계로 돌아가기까지', 'Return to the clock after pausing'),
          desc: L('음악을 멈춘 뒤 이 시간이 지나면 노치가 시계(대기 화면)로 돌아갑니다.', 'After music has been paused this long, the notch goes back to the clock.') },
      ] },
      { title: L('눈 캐릭터', 'Eyes character'), items: [
        { id: 'pet', type: 'toggle', path: 'settings', key: 'pet', def: true, label: L('눈 캐릭터', 'Eyes character'),
          desc: L('한동안 입력이 없으면 시계 대신 눈이 나타나 두리번거리고, 더 지나면 졸아요.', 'Appears when you are idle, looks around, then dozes off.') },
        { id: 'petAfter', type: 'slider', path: 'settings', key: 'petAfter', def: 45, min: 10, max: 300, step: 5, fmt: (v) => `${v}초`, fmtEn: (v) => `${v}s`,
          label: L('나타나기까지 입력 없는 시간', 'Idle time before it appears'), enabledIf: (d) => d.settings.pet },
      ] },
      { title: L('전체화면', 'Fullscreen'), items: [
        { id: 'fullscreenMode', type: 'seg', path: 'settings', key: 'fullscreenMode', def: 'yield', label: L('전체화면 앱이 켜지면', 'When a fullscreen app is on'),
          options: [{ v: 'yield', label: L('비켜나기', 'Step aside') }, { v: 'hide', label: L('숨기기', 'Hide') }, { v: 'hidepeek', label: L('숨기고 미디어 키만', 'Hide, keys peek') }, { v: 'show', label: L('그대로', 'Keep') }],
          desc: L('비켜나기: 항상 위만 풀어 게임이 앞에 오게 합니다. 숨기기: 완전히 숨깁니다. 숨기고 미디어 키만: 완전히 숨기되 미디어 키를 누르면 4초 동안 보입니다. 그대로: 전체화면 앱 위에도 계속 보입니다.', 'Step aside lets the game stay on top; “Hide” hides it completely; “Hide, keys peek” hides it but shows it for 4 s on a media key; “Keep” leaves it on top of the fullscreen app.') },
      ] },
    ],
  },
  {
    id: 'anim', icon: 'sparkle', title: L('애니메이션', 'Animation'),
    sections: [
      { title: L('미리보기', 'Preview'), items: [
        { id: 'animPreview', type: 'custom', component: 'animPreview' },
      ] },
      { title: L('노치 · 한 번에 고르기', 'Notch · Presets'), items: [
        { id: 'animPreset', type: 'seg', special: 'animPreset', label: L('프리셋', 'Preset'),
          options: [{ v: 'off', label: L('끔', 'Off') }, { v: 'minimal', label: L('최소', 'Minimal') }, { v: 'normal', label: L('보통', 'Normal') }, { v: 'lively', label: L('화려', 'Lively') }, { v: 'custom', label: L('직접', 'Custom'), disabled: true }],
          desc: L('“끔”은 모든 애니메이션을 끕니다(성능이 부족하거나 움직임이 불편할 때, 크기 변화도 즉시 일어납니다). 아래 항목을 직접 바꾸면 “직접”으로 표시됩니다.', '“Off” turns all animation off (for low-end PCs or motion sensitivity; size changes become instant). Changing the options below switches this to “Custom”.') },
      ] },
      { title: L('노치 · 세부 조절', 'Notch · Fine tuning'), items: [
        { id: 'animSpeed', type: 'slider', path: 'settings', key: 'animSpeed', def: 100, min: 50, max: 200, step: 10, fmt: (v) => `${(v / 100).toFixed(1)}×`,
          label: L('속도', 'Speed'), desc: L('2.0×는 두 배 빠르게, 0.5×는 절반 속도로 움직입니다.', '2.0× is twice as fast, 0.5× is half speed.'), enabledIf: (d) => !d.settings.animOff },
        { id: 'bounce', type: 'slider', path: 'settings', key: 'bounce', def: 100, min: 0, max: 200, step: 10, fmt: pct,
          label: L('탄성 (튕김)', 'Bounce'), desc: L('0%는 튕기지 않고 부드럽게 멈추고, 높을수록 통통 튑니다.', '0% settles smoothly; higher overshoots more.'), enabledIf: (d) => !d.settings.animOff },
        { id: 'entrance', type: 'toggle', path: 'settings', key: 'entrance', def: true, label: L('항목이 차례로 나타나는 연출', 'Staggered entrance'),
          desc: L('페이지가 열릴 때 글자·버튼이 하나씩 떠오릅니다.', 'Items rise in one after another when a page opens.'), enabledIf: (d) => !d.settings.animOff },
        { id: 'pageAnim', type: 'seg', path: 'settings', key: 'pageAnim', def: 'slide', label: L('페이지 전환', 'Page transition'),
          options: [{ v: 'slide', label: L('밀면서 전환', 'Slide') }, { v: 'fade', label: L('페이드', 'Fade') }], enabledIf: (d) => !d.settings.animOff },
        { id: 'animOff', type: 'hidden', path: 'settings', key: 'animOff', def: false },      // 프리셋 “끔”이 바꾸는 값(화면에는 따로 항목을 두지 않는다)
      ] },
      { title: L('설정 창', 'Settings window'), items: [
        { id: 'setAnim', type: 'toggle', path: 'settings', key: 'setAnim', def: true, label: L('설정 창 애니메이션', 'Settings window animation'),
          desc: L('이 설정 창 자신의 움직임만 켜고 끕니다. 노치의 애니메이션 설정과는 별개예요.', 'Only this window’s own motion. Independent of the notch animation settings above.') },
        { id: 'setAnimSpeed', type: 'slider', path: 'settings', key: 'setAnimSpeed', def: 100, min: 50, max: 200, step: 10, fmt: (v) => `${(v / 100).toFixed(1)}×`,
          label: L('설정 창 애니메이션 속도', 'Settings window animation speed'), desc: L('노치 속도를 느리게 보려고 낮춰도 이 창은 영향받지 않습니다.', 'Slowing the notch down to inspect it does not slow this window.'),
          enabledIf: (d) => d.settings.setAnim !== false },
      ] },
    ],
  },
  {
    id: 'tools', icon: 'clip', title: L('클립보드·일정', 'Clipboard & Agenda'),
    sections: [
      { title: L('클립보드 기록', 'Clipboard history'), items: [
        { id: 'clipboardOn', type: 'toggle', path: 'settings', key: 'clipboardOn', def: false, label: L('클립보드 기록 사용', 'Keep a clipboard history'),
          desc: L('복사한 글을 노치의 “클립보드” 페이지에 모아 둡니다. 컴퓨터를 끄면 사라지고(디스크에 저장하지 않음) 비밀번호 관리자처럼 기록 제외 표시를 한 복사는 저장하지 않아요. 복사한 내용에 민감한 글이 있을 수 있으니 필요할 때만 켜 두세요.',
                  'Collects what you copy on the notch’s “Clipboard” page. Kept in memory only (never written to disk) and copies marked “exclude from history” (e.g. password managers) are skipped. Turn it on only when needed.') },
        { id: 'clipClearNow', type: 'button', action: 'clipClear', label: L('기록 모두 지우기', 'Clear history now'), btn: L('지우기', 'Clear'), enabledIf: (d) => d.settings.clipboardOn },
      ] },
      { title: L('캘린더 (읽기 전용)', 'Calendar (read-only)'), items: [
        { id: 'calendarUrl', type: 'text', path: 'settings', key: 'calendarUrl', def: '', placeholder: L('iCal(.ics) 주소 또는 파일 경로', 'iCal (.ics) address or file path'), wide: true,
          label: L('캘린더 주소', 'Calendar address'),
          desc: L('구글 캘린더: 설정 › 캘린더 설정 › “iCal 형식의 비공개 주소”를 붙여 넣으세요. 이 주소로 일정을 읽기만 합니다(계정 로그인 없음). 주소를 아는 사람은 일정을 볼 수 있으니 남에게 보여 주지 마세요.',
                  'Google Calendar: Settings › your calendar › “Secret address in iCal format”. The app only reads events from it (no sign-in). Anyone with the address can see your events, so keep it private.') },
        { id: 'calendarRemindMin', type: 'slider', path: 'settings', key: 'calendarRemindMin', def: 10, min: 1, max: 60, step: 1, fmt: (v) => `${v}분 전`, fmtEn: (v) => `${v} min before`,
          label: L('일정 알림 시점', 'Remind me'), enabledIf: (d) => !!String(d.settings.calendarUrl || '').trim() },
        { id: 'agendaView', type: 'seg', path: 'settings', key: 'agendaView', def: 'list', label: L('일정 보기 방식', 'Agenda view'),
          options: [{ v: 'list', label: L('목록', 'List') }, { v: 'week', label: L('주', 'Week') }, { v: 'month', label: L('월', 'Month') }],
          desc: L('일정 페이지에서 바로 바꿀 수도 있어요. 주·월 보기에서는 지난 날의 일정도 볼 수 있습니다.', 'You can also switch on the agenda page itself. Week and month views also show past days.'),
          enabledIf: (d) => !!String(d.settings.calendarUrl || '').trim() },
        { id: 'weekStart', type: 'seg', path: 'settings', key: 'weekStart', def: 'sun', label: L('한 주의 시작', 'Week starts on'),
          options: [{ v: 'sun', label: L('일요일', 'Sunday') }, { v: 'mon', label: L('월요일', 'Monday') }],
          enabledIf: (d) => !!String(d.settings.calendarUrl || '').trim() },
        { id: 'calendarTest', type: 'button', action: 'calendarTest', label: L('지금 불러오기', 'Load now'), btn: L('불러오기', 'Load'),
          desc: L('주소가 맞는지 확인하고 앞으로 7일의 일정 수를 알려 줍니다.', 'Checks the address and reports how many events are in the next 7 days.'), enabledIf: (d) => !!String(d.settings.calendarUrl || '').trim() },
      ] },
    ],
  },
  {
    id: 'mixer', icon: 'volume', title: L('볼륨 믹서', 'Volume mixer'),
    sections: [
      { title: L('소리', 'Sound'), items: [{ id: 'mixerPanel', type: 'custom', component: 'mixer' }] },
    ],
  },
  {
    id: 'plugins', icon: 'puzzle', title: L('플러그인·바로가기', 'Plugins & Shortcuts'),
    sections: [
      { items: [
        { id: 'pluginsEnabled', type: 'hidden', path: 'settings', key: 'pluginsEnabled', def: '' },
        { id: 'pluginsCatalog', type: 'custom', component: 'plugins' },
      ] },
      { title: L('내 바로가기 (노치의 “바로가기” 페이지)', 'My shortcuts (the notch “Shortcuts” page)'), items: [
        { id: 'launcherEditor', type: 'custom', component: 'launcher' },
      ] },
    ],
  },
  {
    id: 'focus', icon: 'timer', title: L('집중·물·할 일', 'Focus, Water & To-do'),
    sections: [
      { title: L('포모도로', 'Pomodoro'), items: [
        { id: 'focusDnd', type: 'toggle', path: 'settings', key: 'focusDnd', def: true, label: L('집중 시간 동안 방해 금지', 'Do Not Disturb while focusing'),
          desc: L('집중이 진행되는 동안 윈도우의 방해 금지를 켜서 알림 배너와 소리를 막고, 멈추거나 끝나면 원래대로 돌립니다. 이미 방해 금지를 켜 둔 상태였다면 건드리지 않아요.',
                  'Turns on Windows Do Not Disturb while a focus session runs, and restores it when you pause or finish. If it was already on, it is left alone.') },
        { id: 'focusMin', type: 'slider', path: 'pomo', key: 'focusMin', def: 25, min: 5, max: 90, step: 5, fmt: (v) => `${v}분`, fmtEn: (v) => `${v} min`, label: L('집중 시간', 'Focus length') },
        { id: 'breakMin', type: 'slider', path: 'pomo', key: 'breakMin', def: 5, min: 1, max: 30, step: 1, fmt: (v) => `${v}분`, fmtEn: (v) => `${v} min`, label: L('휴식 시간', 'Break length') },
      ] },
      { title: L('물 마시기', 'Water'), items: [
        { id: 'waterOn', type: 'toggle', path: 'water', key: 'enabled', def: true, label: L('물 마시기 알림', 'Water reminders') },
        { id: 'goalMl', type: 'slider', path: 'water', key: 'goalMl', def: 2000, min: 500, max: 4000, step: 100, fmt: (v) => `${(v / 1000).toFixed(1)} L`, label: L('하루 목표', 'Daily goal') },
        { id: 'bottleMl', type: 'slider', path: 'water', key: 'bottleMl', def: 250, min: 100, max: 1000, step: 50, fmt: (v) => `${v} ml`, label: L('한 번에 마시는 양', 'Glass size') },
        { id: 'intervalMin', type: 'slider', path: 'water', key: 'intervalMin', def: 60, min: 15, max: 180, step: 15, fmt: (v) => `${v}분`, fmtEn: (v) => `${v} min`,
          label: L('알림 간격', 'Reminder interval'), enabledIf: (d) => d.water.enabled },
        { id: 'startHour', type: 'slider', path: 'water', key: 'startHour', def: 9, min: 0, max: 23, step: 1, fmt: (v) => `${v}시`, fmtEn: (v) => `${v}:00`,
          label: L('알림 시작 시각', 'Reminders start'), enabledIf: (d) => d.water.enabled },
        { id: 'endHour', type: 'slider', path: 'water', key: 'endHour', def: 21, min: 1, max: 24, step: 1, fmt: (v) => `${v}시`, fmtEn: (v) => `${v}:00`,
          label: L('알림 종료 시각', 'Reminders end'), enabledIf: (d) => d.water.enabled },
      ] },
      { title: L('할 일', 'To-do'), items: [
        { id: 'todoRemind', type: 'toggle', path: 'settings', key: 'todoRemind', def: true, label: L('마감 알림', 'Due-date reminders'),
          desc: L('마감 시각이 되면 알려 줍니다.', 'Alerts you when a task is due.') },
        { id: 'todoLeadMin', type: 'seg', path: 'settings', key: 'todoLeadMin', def: 0, label: L('마감 미리 알림', 'Heads-up before due'),
          desc: L('마감 시각이 되기 조금 전에 한 번 먼저 알려 줍니다.', 'Gives you one early alert shortly before a task is due.'),
          options: [{ v: 0, label: L('끔', 'Off') }, { v: 5, label: L('5분 전', '5 min before') }, { v: 10, label: L('10분 전', '10 min before') }, { v: 15, label: L('15분 전', '15 min before') }],
          enabledIf: (d) => d.settings.todoRemind !== false },
        { id: 'snoozeMin', type: 'slider', path: 'settings', key: 'snoozeMin', def: 10, min: 5, max: 60, step: 5, fmt: (v) => `${v}분`, fmtEn: (v) => `${v} min`,
          label: L('미루기 시간', 'Snooze length'),
          desc: L('할 일 줄의 시계 버튼, 물 페이지의 시계 버튼으로 알림을 이만큼 미룹니다.', 'How long the clock button on a task or on the water page delays its reminder.') },
      ] },
    ],
  },
  {
    id: 'buds', icon: 'headphones', title: L('이어버드', 'Earbuds'),
    sections: [
      { title: L('상태', 'Status'), items: [{ id: 'budsStatus', type: 'custom', component: 'budsStatus' }] },
      { title: L('소리', 'Sound'), items: [{ id: 'budsEq', type: 'custom', component: 'budsEq' }] },
      { title: L('고급', 'Advanced'), items: [{ id: 'budsAdvanced', type: 'custom', component: 'budsAdvanced' }] },
      { title: L('알림', 'Alerts'), items: [
        { id: 'budsLowPct', type: 'slider', path: 'settings', key: 'budsLowPct', def: 20, min: 5, max: 50, step: 5, fmt: pct, label: L('배터리 부족 알림 기준', 'Low-battery threshold'),
          desc: L('알림을 켜고 끄는 건 설정 › 알림에서 해요.', 'Turning the alert on or off is under Settings › Notifications.'),
          enabledIf: (d) => d.settings.notify.buds_low },
        { id: 'budsWatch', type: 'toggle', path: 'settings', key: 'budsWatch', def: true, label: L('충전 상태·경고 항상 받기', 'Always watch charging status & warnings'),
          desc: L('이어버드와의 제어 연결을 계속 열어 두어 좌/우 충전 중 표시와 충전 중지 경고를 놓치지 않아요. 삼성 Galaxy Buds 앱이 이미 연결을 쓰고 있으면 동작하지 않고, 끄면 소음 제어·이퀄라이저 같은 설정을 바꿀 때만 연결해요.',
                  'Keeps the earbuds control connection open so left/right charging status and charging-stopped warnings are never missed. It cannot work while the Samsung Galaxy Buds app holds the connection; when off, it connects only when you change a setting such as noise control or the equalizer.') },
      ] },
    ],
  },
  {
    id: 'about', icon: 'info', title: L('정보', 'About'),
    sections: [
      { title: L('앱 정보', 'About'), items: [{ id: 'aboutInfo', type: 'custom', component: 'about' }] },
      { title: L('관리', 'Maintenance'), items: [
        { id: 'exportSettings', type: 'button', action: 'exportSettings', label: L('설정 내보내기', 'Export settings'), btn: L('내보내기', 'Export'),
          desc: L('설정을 파일로 저장합니다. 할 일·선반·물 기록 같은 개인 데이터와 캘린더 주소는 포함하지 않아요.', 'Saves your settings to a file. Personal data (to-dos, shelf, water log) is not included, nor is the calendar address.') },
        { id: 'importSettings', type: 'button', action: 'importSettings', label: L('설정 가져오기', 'Import settings'), btn: L('가져오기', 'Import'),
          desc: L('내보낸 파일에서 설정을 불러옵니다. 현재 설정은 덮어써집니다.', 'Loads settings from an exported file, replacing the current ones.') },
        { id: 'openData', type: 'button', action: 'openData', label: L('데이터 폴더 열기', 'Open data folder'), btn: L('열기', 'Open'),
          desc: L('설정, 할 일, 물 기록, 가사 캐시가 저장되는 곳입니다.', 'Where settings, to-dos, water log and caches live.') },
        { id: 'openLog', type: 'button', action: 'openLog', label: L('로그 보기', 'Show log file'), btn: L('보기', 'Show') },
        { id: 'resetAll', type: 'button', action: 'resetAll', danger: true, label: L('모든 설정 초기화', 'Reset all settings'), btn: L('초기화', 'Reset'),
          desc: L('설정을 기본값으로 되돌립니다. 할 일·선반·물 기록은 지워지지 않습니다.', 'Restores defaults. To-dos, shelf and water log are kept.') },
      ] },
    ],
  },
];

// 모든 항목의 기본값 -> { settings: {...}, pomo: {...}, water: {...} }
function schemaDefaults() {
  const out = { settings: {}, pomo: {}, water: {} };
  for (const page of SETTINGS_PAGES) for (const sec of page.sections) for (const it of sec.items) {
    if (it.path && it.key && 'def' in it) setPath(out[it.path], it.key, it.def);
  }
  return out;
}

if (typeof module !== 'undefined') module.exports = { SETTINGS_PAGES, schemaDefaults };
