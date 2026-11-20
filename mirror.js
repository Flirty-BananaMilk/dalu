// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
// Copyright (c) 2026 Flirty_BananaMilk — 상업적 이용 금지, 자세한 내용은 LICENSE
// 폰 화면 보기 창: PC 안(127.0.0.1)의 서버에서 H.264 조각을 받아 WebCodecs 로 풀어 그린다. 조작은 같은 연결로 되돌려 보낸다.
// 프레임(바이너리): 첫 바이트 1 = 상태(JSON), 2 = 보통 프레임, 3 = 키프레임, 이어서 8바이트 시각 + Annex-B H.264.

const STR = {
  ko: { title: 'Dalu · 폰 화면', waiting: '폰에서 허용해 주세요', waitingSub: '폰에 뜬 알림을 누르고, 안드로이드가 묻는 ‘지금 시작’을 눌러 주세요.', connecting: '연결하는 중…', connectingSub: '', starting: '화면을 불러오는 중…', startingSub: '',
        denied: '폰에서 허용하지 않았어요', deniedSub: '다시 하려면 휴대폰 탭의 ‘화면 보기’를 눌러 주세요.', stopped: '화면 공유가 끝났어요', stoppedSub: '', stoppedLink: '폰과 연결이 끊겼어요', stoppedLinkSub: '연결이 돌아오면 휴대폰 탭에서 다시 시작해 주세요.',
        error: '화면을 시작하지 못했어요', errorSub: '폰의 Dalu Link 가 최신인지 확인하고 다시 해 주세요.', nodecoder: '이 PC 에서는 화면을 풀 수 없어요', nodecoderSub: 'H.264 디코더(WebView2)를 쓸 수 없는 환경이에요.',
        sharing: '폰 화면 공유 중', send: '보내기', stop: '끝내기', type: '폰에 글자 보내기', typeView: '보기 전용',
        noctl: '조작은 꺼져 있어요(설정 › Dalu Link)', inputfail: '조작이 안 돼요: 폰 앱의 ‘복사 감지’(접근성)를 켜 주세요', black: '검은 화면은 폰이 꺼져 있거나 보안 화면(은행 앱 등)일 수 있어요',
        back: '뒤로', home: '홈', recents: '최근 앱', notifications: '알림창' },
  en: { title: 'Dalu · Phone screen', waiting: 'Allow it on your phone', waitingSub: 'Tap the notification on the phone, then “Start now” in the Android prompt.', connecting: 'Connecting…', connectingSub: '', starting: 'Loading the screen…', startingSub: '',
        denied: 'The phone did not allow it', deniedSub: 'Press “Screen” on the Phone tab to try again.', stopped: 'Screen sharing ended', stoppedSub: '', stoppedLink: 'Lost the connection to the phone', stoppedLinkSub: 'Start again from the Phone tab once it is back.',
        error: 'Could not start the screen', errorSub: 'Check that Dalu Link on the phone is up to date and try again.', nodecoder: 'This PC cannot decode the screen', nodecoderSub: 'The H.264 decoder (WebView2) is not available here.',
        sharing: 'Sharing the phone screen', send: 'Send', stop: 'End', type: 'Send text to the phone', typeView: 'View only',
        noctl: 'Control is off (Settings › Dalu Link)', inputfail: 'Control does not work: turn on “Copy detection” (accessibility) in the phone app', black: 'A black screen can mean the phone is off or showing a secure screen (banking app …)',
        back: 'Back', home: 'Home', recents: 'Recent apps', notifications: 'Notifications' },
  zh: { title: 'Dalu · 手机屏幕', waiting: '请在手机上允许', waitingSub: '点按手机上的通知，再点按安卓询问的“立即开始”。', connecting: '正在连接…', connectingSub: '', starting: '正在载入屏幕…', startingSub: '',
        denied: '手机没有允许', deniedSub: '请在手机标签页点按“屏幕”重试。', stopped: '屏幕共享已结束', stoppedSub: '', stoppedLink: '与手机的连接已断开', stoppedLinkSub: '连接恢复后请在手机标签页重新开始。',
        error: '无法启动屏幕', errorSub: '请确认手机上的 Dalu Link 是最新版本后重试。', nodecoder: '这台电脑无法解码屏幕', nodecoderSub: '此处无法使用 H.264 解码器（WebView2）。',
        sharing: '正在共享手机屏幕', send: '发送', stop: '结束', type: '向手机发送文字', typeView: '仅查看',
        noctl: '控制已关闭（设置 › Dalu Link）', inputfail: '无法控制：请在手机应用中打开“复制检测”（无障碍）', black: '黑屏可能是手机已熄屏或正显示安全界面（银行应用等）',
        back: '返回', home: '主页', recents: '最近任务', notifications: '通知栏' },
  ja: { title: 'Dalu · スマホ画面', waiting: 'スマホで許可してください', waitingSub: 'スマホの通知をタップし、Android が尋ねる「今すぐ開始」をタップしてください。', connecting: '接続中…', connectingSub: '', starting: '画面を読み込み中…', startingSub: '',
        denied: 'スマホで許可されませんでした', deniedSub: 'もう一度するにはスマホタブの「画面」を押してください。', stopped: '画面共有が終了しました', stoppedSub: '', stoppedLink: 'スマホとの接続が切れました', stoppedLinkSub: '接続が戻ったらスマホタブからもう一度始めてください。',
        error: '画面を開始できませんでした', errorSub: 'スマホの Dalu Link が最新か確認してやり直してください。', nodecoder: 'この PC では画面をデコードできません', nodecoderSub: 'H.264 デコーダー（WebView2）が使えない環境です。',
        sharing: 'スマホの画面を共有中', send: '送信', stop: '終了', type: 'スマホに文字を送る', typeView: '表示のみ',
        noctl: '操作はオフです（設定 › Dalu Link）', inputfail: '操作できません：スマホアプリの「コピー検出」（ユーザー補助）をオンにしてください', black: '黒い画面はスマホが消灯中か保護された画面（銀行アプリなど）の可能性があります',
        back: '戻る', home: 'ホーム', recents: '最近のアプリ', notifications: '通知パネル' },
};

const $ = (id) => document.getElementById(id);
let S = STR.ko;
let info = null;
let ws = null;
let decoder = null;
let decoderCfg = '';
let needKey = true;
let tsCounter = 0;
let control = false;
let state = { state: 'connecting' };
let frames = 0;
let gotFrame = false;
let reconnectTimer = null;
let noticeTimer = null;
let dec = { w: 0, h: 0 };
const canvas = $('screen');
const g2d = canvas.getContext('2d');

function icon(path) { return '<svg viewBox="0 0 24 24"><path d="' + path + '"/></svg>'; }

function applyStrings() {
  document.documentElement.lang = S === STR.en ? 'en' : (S === STR.zh ? 'zh' : (S === STR.ja ? 'ja' : 'ko'));
  document.title = S.title;
  $('stop').textContent = S.stop;
  $('bSend').textContent = S.send;
  $('typed').placeholder = control ? S.type : S.typeView;
  $('badgeText').textContent = S.sharing;
  const k = { bBack: S.back, bHome: S.home, bRecents: S.recents, bNotif: S.notifications };
  for (const id of Object.keys(k)) { $(id).title = k[id]; $(id).setAttribute('aria-label', k[id]); }
}

function setControlUi() {
  for (const id of ['bBack', 'bHome', 'bRecents', 'bNotif', 'bSend']) $(id).disabled = !control;
  $('typed').disabled = !control;
  $('typed').placeholder = control ? S.type : S.typeView;
  canvas.classList.toggle('ctl', control);
}

function showMsg(title, sub, pulse) {
  $('msgTitle').textContent = title;
  $('msgSub').textContent = sub || '';
  $('msg').classList.remove('hide');
  $('msg').classList.toggle('static', !pulse);
  canvas.classList.remove('on');
  $('badge').classList.remove('on');
}

function hideMsg() {
  $('msg').classList.add('hide');
  canvas.classList.add('on');
  $('badge').classList.add('on');
}

function notice(text, ms) {
  const n = $('notice');
  n.textContent = text;
  n.classList.add('on');
  clearTimeout(noticeTimer);
  noticeTimer = setTimeout(() => n.classList.remove('on'), ms || 4200);
}

// ---------------------------------------------------------------- 상태
function onState(s) {
  state = s || state;
  if (typeof s.control === 'boolean') { control = s.control; setControlUi(); }
  switch (s.state) {
    case 'waiting': case 'consent': gotFrame = false; showMsg(S.waiting, S.waitingSub, true); break;
    case 'running':
      if (!gotFrame) showMsg(S.starting, S.startingSub, true);
      else hideMsg();
      break;
    case 'denied': closeDecoder(); showMsg(S.denied, S.deniedSub, false); break;
    case 'error': closeDecoder(); showMsg(S.error, S.errorSub, false); break;
    case 'stopped': closeDecoder(); gotFrame = false; if (s.why === 'link') showMsg(S.stoppedLink, S.stoppedLinkSub, false); else showMsg(S.stopped, S.stoppedSub, false); break;
    case 'idle': break;
  }
  if (s.notice === 'noctl') notice(S.noctl);
  if (s.notice === 'inputfail') notice(S.inputfail);
  if (s.state === 'running' && s.w && s.h) {
    const api = window.pywebview && window.pywebview.api;
    if (api && api.mirror_fit) { try { api.mirror_fit(s.w, s.h); } catch (e) { /* 창 크기 맞추기는 없어도 된다 */ } }
  }
}

// ---------------------------------------------------------------- 디코더
let decoderGen = 0;          // 디코더를 만드는 동안(await) 닫히거나 다시 연결됐는지 알려 주는 번호
function closeDecoder() {
  decoderGen++;
  try { if (decoder && decoder.state !== 'closed') decoder.close(); } catch (e) { /* 이미 닫힘 */ }
  decoder = null; decoderCfg = ''; needKey = true;
}

function nalList(b) {
  const out = [];
  for (let i = 0; i + 3 < b.length; i++) {
    if (b[i] === 0 && b[i + 1] === 0) {
      if (b[i + 2] === 1) { out.push({ type: b[i + 3] & 31, at: i + 3 }); i += 2; }
      else if (b[i + 2] === 0 && i + 4 < b.length && b[i + 3] === 1) { out.push({ type: b[i + 4] & 31, at: i + 4 }); i += 3; }
    }
  }
  return out;
}

function codecFrom(b) {
  const sps = nalList(b).find((n) => n.type === 7);
  if (!sps || sps.at + 3 >= b.length) return '';
  const hx = (v) => v.toString(16).padStart(2, '0');
  return 'avc1.' + hx(b[sps.at + 1]) + hx(b[sps.at + 2]) + hx(b[sps.at + 3]);
}

function draw(frame) {
  if (canvas.width !== frame.displayWidth || canvas.height !== frame.displayHeight) {
    canvas.width = frame.displayWidth; canvas.height = frame.displayHeight;
    dec = { w: frame.displayWidth, h: frame.displayHeight };
  }
  g2d.drawImage(frame, 0, 0);
  frame.close();
  frames++;
  if (!gotFrame) { gotFrame = true; hideMsg(); }
}

async function ensureDecoder(keyData) {
  const codec = codecFrom(keyData);
  if (!codec) return false;
  if (decoder && decoder.state !== 'closed' && decoderCfg === codec) return true;
  closeDecoder();
  const gen = decoderGen;
  if (typeof VideoDecoder === 'undefined') { showMsg(S.nodecoder, S.nodecoderSub, false); return false; }
  const cfgs = [{ codec, hardwareAcceleration: 'prefer-hardware', optimizeForLatency: true, avc: { format: 'annexb' } }, { codec, optimizeForLatency: true, avc: { format: 'annexb' } }];          // 마지막 후보(avc 형식 미지정)는 뺐다: 기본이 AVCC 라서 Annex-B 스트림을 잘못 읽어 깨진 화면이 나왔다
  let cfg = null;
  for (const c of cfgs) {
    try { const r = await VideoDecoder.isConfigSupported(c); if (r && r.supported) { cfg = r.config || c; break; } } catch (e) { /* 다음 설정 */ }
  }
  if (gen !== decoderGen) return false;          // 기다리는 사이에 닫히거나 다시 연결됐다: 뒤늦게 디코더를 만들지 않는다
  if (!cfg) { showMsg(S.nodecoder, S.nodecoderSub, false); return false; }
  decoder = new VideoDecoder({
    output: draw,
    error: () => { closeDecoder(); requestKey(); },
  });
  decoder.configure(cfg);
  decoderCfg = codec;
  return true;
}

let chainPending = 0;
let frameChain = Promise.resolve();          // 프레임은 한 줄로 차례대로 처리한다(디코더를 만드는 동안 뒤따라 온 프레임이 먼저 처리되지 않게)

async function onFrame(isKey, data) {
  if (isKey) {
    if (!(await ensureDecoder(data))) return;
    needKey = false;
  } else if (needKey || !decoder || decoder.state === 'closed') {
    return;                                                  // 키프레임 없이 시작할 수 없다
  }
  if (decoder.decodeQueueSize > 8 && !isKey) { needKey = true; requestKey(); return; }          // 밀려서 보통 프레임을 버렸다: 참조가 끊겼으니 다음 키프레임을 받을 때까지 기다리며 새로 요청한다           // 밀리면 보통 프레임은 건너뛴다(다음 키프레임에서 따라잡는다)
  try {
    decoder.decode(new EncodedVideoChunk({ type: isKey ? 'key' : 'delta', timestamp: (tsCounter += 33333), data }));
  } catch (e) {
    closeDecoder(); requestKey();
  }
}

// ---------------------------------------------------------------- 연결
function send(obj) { if (ws && ws.readyState === 1) ws.send(JSON.stringify(obj)); }
function requestKey() { send({ t: 'key' }); }

async function getInfo() {
  for (let i = 0; i < 40; i++) {
    const api = window.pywebview && window.pywebview.api;
    if (api && api.mirror_info) {
      try { const r = await api.mirror_info(); if (r && r.ok) return r; } catch (e) { /* 다시 */ }
    }
    await new Promise((r) => setTimeout(r, 150));
  }
  return null;
}

function connect() {
  if (!info) return;
  clearTimeout(reconnectTimer);
  if (ws) { ws.onclose = null; ws.onmessage = null; }          // 옛 소켓의 onclose 가 새 연결을 다시 끊지 않게
  try { if (ws) ws.close(); } catch (e) { /* 이미 닫힘 */ }
  ws = new WebSocket('ws://127.0.0.1:' + info.port + '/v/' + info.token);
  ws.binaryType = 'arraybuffer';
  ws.onopen = () => { requestKey(); };
  ws.onmessage = (ev) => {
    const buf = new Uint8Array(ev.data);
    if (!buf.length) return;
    if (buf[0] === 1) {
      try { onState(JSON.parse(new TextDecoder().decode(buf.subarray(1)))); } catch (e) { /* 깨진 상태는 무시 */ }
    } else if (buf[0] === 2 || buf[0] === 3) {
      const isKey = buf[0] === 3, data = buf.subarray(9);
      if (chainPending > 40 && !isKey) return;          // 디코딩이 밀리면 보통 프레임은 버린다(메모리에 끝없이 쌓이지 않게). 키프레임은 항상 처리한다
      chainPending++;
      frameChain = frameChain.then(() => onFrame(isKey, data)).catch(() => {}).then(() => { chainPending--; });
    }
  };
  ws.onclose = () => { if (state.state !== 'stopped' && state.state !== 'idle') reconnectTimer = setTimeout(async () => { try { info = (await getInfo()) || info; } catch (e) { /* 이전 정보로 다시 시도 */ } connect(); }, 1200); };
}

async function mirrorReconnect() { try { info = (await getInfo()) || info; } catch (e) { /* 이전 정보로 */ } gotFrame = false; closeDecoder(); showMsg(S.waiting, S.waitingSub, true); connect(); }
window.mirrorReconnect = mirrorReconnect;

// ---------------------------------------------------------------- 조작(PC 마우스 → 폰 손가락)
const MOVE_PX = 9;
const LONG_MS = 520;
let down = null;
let lastWheel = 0;

function norm(e) {
  const r = canvas.getBoundingClientRect();
  const w = r.width || 1, h = r.height || 1;          // 크기가 0 인 순간(창을 줄이는 중)에 0 으로 나누지 않는다
  return { x: Math.min(1, Math.max(0, (e.clientX - r.left) / w)), y: Math.min(1, Math.max(0, (e.clientY - r.top) / h)) };
}

function sendIn(o) { if (control) send(Object.assign({ t: 'in' }, o)); }

canvas.addEventListener('contextmenu', (e) => { e.preventDefault(); });
canvas.addEventListener('pointerdown', (e) => {
  if (!control) return;
  canvas.focus();
  if (e.button === 2) { sendIn({ k: 'key', a: 'back' }); return; }          // 오른쪽 클릭 = 뒤로
  if (e.button !== 0) return;
  canvas.setPointerCapture(e.pointerId);
  down = { x: e.clientX, y: e.clientY, t: performance.now(), n: norm(e), moved: false };
});
canvas.addEventListener('pointermove', (e) => {
  if (!down) return;
  if (Math.hypot(e.clientX - down.x, e.clientY - down.y) > MOVE_PX) down.moved = true;
});
canvas.addEventListener('pointerup', (e) => {
  if (!down || e.button !== 0) return;          // 왼쪽 버튼을 뗄 때만(드래그 중에 오른쪽 버튼을 떼도 끝나지 않게)
  const d = down; down = null;
  const dt = performance.now() - d.t;
  const n = norm(e);
  if (!d.moved) sendIn({ k: dt >= LONG_MS ? 'long' : 'tap', x: n.x, y: n.y });
  else sendIn({ k: 'swipe', x1: d.n.x, y1: d.n.y, x2: n.x, y2: n.y, ms: Math.round(Math.min(900, Math.max(90, dt))) });
});
canvas.addEventListener('pointercancel', () => { down = null; });
canvas.addEventListener('wheel', (e) => {
  if (!control) return;
  e.preventDefault();
  const now = performance.now();
  if (now - lastWheel < 140) return;
  lastWheel = now;
  const n = norm(e);
  const dy = Math.sign(e.deltaY) * 0.28;                          // 휠을 아래로 = 손가락을 위로 쓸기
  sendIn({ k: 'swipe', x1: n.x, y1: Math.min(0.95, Math.max(0.05, n.y + dy / 2)), x2: n.x, y2: Math.min(0.95, Math.max(0.05, n.y - dy / 2)), ms: 180 });
}, { passive: false });

for (const b of document.querySelectorAll('#bar button[data-k]')) b.addEventListener('click', () => sendIn({ k: 'key', a: b.dataset.k }));
$('stop').addEventListener('click', () => { send({ t: 'stop' }); });

function sendTyped() {
  const el = $('typed');
  if (el.value) { sendIn({ k: 'text', s: el.value }); el.value = ''; } else sendIn({ k: 'enter' });
}
$('bSend').addEventListener('click', sendTyped);
$('typed').addEventListener('keydown', (e) => {
  if (e.isComposing) return;
  if (e.key === 'Enter') { e.preventDefault(); sendTyped(); }
  else if (e.key === 'Backspace' && !$('typed').value) { e.preventDefault(); sendIn({ k: 'bs' }); }
});
window.addEventListener('keydown', (e) => { if (e.key === 'Escape' && document.activeElement !== $('typed')) sendIn({ k: 'key', a: 'back' }); });

// 검은 화면 안내: 몇 초 동안 프레임이 하나도 안 풀리면 이유를 알려 준다
setInterval(() => { if (state.state === 'running' && gotFrame && frames === 0) notice(S.black); frames = 0; }, 9000);

(async function init() {
  const lang = new URLSearchParams(location.search).get('lang');
  S = (Object.prototype.hasOwnProperty.call(STR, lang) && STR[lang]) || STR.ko;
  applyStrings();
  setControlUi();
  showMsg(S.connecting, S.connectingSub, true);
  info = await getInfo();
  if (!info) { showMsg(S.error, S.errorSub, false); return; }
  S = (Object.prototype.hasOwnProperty.call(STR, info.lang) && STR[info.lang]) || STR.en;
  control = !!info.control;
  applyStrings();
  setControlUi();
  connect();
})();
