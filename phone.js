// 휴대폰 탭 + 작은 노치 항목(폰 배터리·부재중). 폰은 폰 앱(Dalu Link)으로만 다룬다: 상태는 폰이 보내 주고, 버튼은 폰 앱에 명령을 보낸다.
// 폰 상태는 파이썬이 캐시해 둔 값을 받아 온다: 탭이 열려 있으면 2초마다, 작은 노치 항목을 켜 두었으면 5초마다.
const phoneS = { st: null, busy: false, sig: '', card: null, cardUntil: 0, sending: false, call: null, dial: false, dialSeq: 0, dialTimer: null };
const PHONE_CARD_SHOW_MS = 60000;        // 알림이 오고 이 시간 안에는 휴대폰 탭에 답장 카드가 뜬다
const PHONE_CARD_HOVER_MS = 25000;       // 알림이 오고 이 시간 안에 노치를 펼치면(알림을 보고 마우스를 올리면) 휴대폰 탭으로 바로 간다
const PHONE_REFRESH_MS = 2000;
const PHONE_SAT_REFRESH_MS = 5000;
const PHONE_MAX_BUTTONS = 8;
const PHONE_RINGER_NEXT = { sound: 'vibrate', vibrate: 'mute', mute: 'sound' };      // 누를 때마다 소리 → 진동 → 무음
const PHONE_RINGER_IC = { sound: 'volume', vibrate: 'vibrate', mute: 'mute' };
// 지금 만들어진 버튼. (파일 전송·전화·메시지는 다음 단계에서 이 목록에 추가된다)
const PHONE_ACTIONS = {
  ringer: { ic: 'volume', name: 'phoneRinger_sound' },
  dnd: { ic: 'moon', name: 'phoneDnd' },
  ring: { ic: 'bell', name: 'phoneRing' },
  call: { ic: 'call', name: 'phoneCall' },
  files: { ic: 'folder', name: 'phoneFiles' },
  media: { ic: 'image', name: 'phoneMedia' },
  mirror: { ic: 'monitor', name: 'phoneMirror' },
  sms: { ic: 'chat', name: 'phoneSms' },
};
const PHONE_DEFAULT_BUTTONS = ['call', 'sms', 'ringer', 'dnd', 'files', 'media', 'ring', 'mirror'];

function phoneButtons() {
  const raw = String((store.settings && store.settings.phoneButtons) || '').split(',').map((x) => x.trim());
  const ok = (k) => PHONE_ACTIONS[k] && (k !== 'mirror' || !!(store.settings && store.settings.linkMirror));          // '화면 보기'는 설정에서 켰을 때만 보인다
  const list = raw.filter((k, i) => ok(k) && raw.indexOf(k) === i).slice(0, PHONE_MAX_BUTTONS);
  return list.length ? list : PHONE_DEFAULT_BUTTONS.filter(ok);
}

async function phoneLoad() {
  const api = getApi();
  if (!api || !api.phone_status || phoneS.busy) return;
  phoneS.busy = true;
  try {
    const d = await api.phone_status();
    if (d && typeof d === 'object') {
      phoneS.st = d;
      // 통화 상태는 폰이 보낸 값이 기준이다(탭을 늦게 열어도, 이벤트를 놓쳐도 맞춘다)
      const c = d.state === 'ok' && d.call ? d.call : null;
      const was = phoneS.call;
      phoneS.call = c ? { state: c.state, incoming: !!c.incoming, number: c.number || '', name: c.name || '', t: (was && was.t) || Date.now(), t0: c.state === 'active' ? ((was && was.t0) || Date.now()) : 0, audio: d.callAudio || (was && was.audio) || null, rec: d.callRec ? !!d.callRec.on : (was ? was.rec : undefined), recT0: d.callRec && d.callRec.on ? d.callRec.t0 : (was ? was.recT0 : 0) } : null;
      if (!!was !== !!phoneS.call || (was && phoneS.call && (was.state !== phoneS.call.state || was.name !== phoneS.call.name))) phoneCallSync();
      renderPhone(); phoneAckLater();
    }
  } catch (e) { /* 이전 값 유지 */ }
  phoneS.busy = false;
  if (phoneS.again) { phoneS.again = false; phoneLoad(); }          // 가져오는 사이에 다시 요청이 왔다면 끝난 뒤 한 번 더
}
// 가져오는 중이면 겹쳐 요청하지 않고, 끝난 뒤 한 번 더 가져오게 표시만 한다
function phoneReload() { if (phoneS.busy) phoneS.again = true; else phoneLoad(); }
// 휴대폰 탭을 3초 이상 보고 있으면 부재중 표시를 '봤다'로 친다(작은 노치의 부재중 알약도 사라진다)
function phoneAckLater() {
  const st = phoneS.st;
  if (!(page === 'phone' && isExpanded && st && st.missed > 0) || phoneS.ackTimer) return;
  phoneS.ackTimer = setTimeout(async () => {
    phoneS.ackTimer = null;
    if (!(page === 'phone' && isExpanded)) return;
    const api = getApi(); if (!api || !api.phone_ack_missed) return;
    try { await api.phone_ack_missed(); } catch (e) { /* 다음에 다시 */ }
    phoneLoad();          // 이미 가져오는 중이면 건너뛴다(그 요청이 최신 값을 가져온다)
  }, 3000);
}

function phoneBuildTiles() {
  const grid = $('phGrid'); if (!grid) return;
  const keys = phoneButtons(), sig = keys.join(',');
  if (sig === phoneS.sig && grid.children.length) return;
  phoneS.sig = sig;
  grid.innerHTML = '';
  for (const k of keys) {
    const b = document.createElement('button');
    b.className = 'ltile'; b.dataset.k = k; b.type = 'button';
    b.innerHTML = '<span class="ic"><svg viewBox="0 0 24 24"></svg></span><span class="nm"></span>';
    b.addEventListener('click', (e) => { e.stopPropagation(); phoneAct(b); });
    grid.appendChild(b);
  }
}

function renderPhone() {
  if (!$('phGrid')) return;
  const bk = $('phBack'); if (bk) bk.setAttribute('aria-label', t('phoneBack'));          // 읽어 주는 이름은 지금 언어를 따른다(툴팁은 없다)
  phoneBuildTiles();
  phoneRenderCard();
  phoneRenderCall();
  phoneRenderDial();
  const st = phoneS.st || {}, ok = st.state === 'ok';
  document.body.classList.toggle('phone-link', ok);          // 선반에 '휴대폰으로 보내기' 칸
  phoneRenderXfer();
  phoneRenderMedia();
  phoneRenderSms();
  $('phGrid').classList.toggle('off', !ok);
  $('phMsg').hidden = ok || !phoneS.st;
  if (!ok && phoneS.st) setText($('phMsgTx'), t(st.state === 'unavailable' ? 'phoneUnavail' : (st.enabled === false ? 'phoneLinkOff' : 'phoneNoPhone')));
  $('phOpen').hidden = st.state === 'unavailable';
  // 머리: 배터리, 부재중
  const batt = $('phBatt'), miss = $('phMiss');
  // 배터리 아이콘은 잔량만큼 채워서 그린다(예전에는 항상 같은 빈 아이콘이라 91% 여도 배터리가 없어 보였다)
  const pct = ok && st.battery != null ? Math.max(0, Math.min(100, Number(st.battery) || 0)) : null;
  batt.innerHTML = pct != null ? `<svg viewBox="0 0 24 24" aria-hidden="true">${typeof batteryIconInner === 'function' ? batteryIconInner(pct, !!st.charging) : ''}</svg>${pct}%` : '';
  batt.classList.toggle('low', pct != null && pct <= 20 && !st.charging);
  batt.classList.toggle('chg', pct != null && !!st.charging);
  batt.removeAttribute('title');
  miss.innerHTML = ok && st.missed > 0 ? (uiIconSvg('missed', 12) || '') + t('phoneMissedN', { n: st.missed }) : '';
  for (const b of $$('#phGrid .ltile')) {
    const k = b.dataset.k, nm = b.querySelector('.nm');
    let ic = PHONE_ACTIONS[k].ic, label = t(PHONE_ACTIONS[k].name), on = false;
    if (k === 'ringer') { const m = st.ringer || 'sound'; ic = PHONE_RINGER_IC[m]; label = t('phoneRinger_' + m); }
    else if (k === 'dnd') on = !!st.dnd;
    else if (k === 'ring' && phoneS.finding) { on = true; label = t('phoneRinging'); }
    else if (k === 'call') on = !!phoneS.dial;
    if (((k === 'ringer' || k === 'dnd') && st.ringer == null) || ((k === 'call' || k === 'files' || k === 'media' || k === 'sms' || k === 'mirror') && !ok)) b.classList.add('dis'); else b.classList.remove('dis');
    sysSetIc(b.querySelector('svg'), ic);
    if (nm && nm.textContent !== label) nm.textContent = label;
    b.classList.toggle('on', on);
  }
}

async function phoneAct(btn) {
  const k = btn.dataset.k, api = getApi(), st = phoneS.st || {};
  if (k === 'call') { phoneToggleDial(); return; }          // 전화 걸기 패널(번호·연락처)
  if (k === 'files') { phonePickFiles(); return; }
  if (k === 'media') { phoneMediaOpen(); return; }
  if (k === 'mirror') { phoneMirrorOpen(); return; }
  if (k === 'sms') { phoneSmsOpen(); return; }          // 문자 대화 목록          // 폰의 최근 사진·동영상 보기          // 파일 선택 창 -> 폰으로 보내기
  if (!api || btn.classList.contains('busy')) return;
  btn.classList.add('busy');
  let r = null;
  try {
    if (k === 'ringer') r = await api.phone_set_ringer(PHONE_RINGER_NEXT[st.ringer || 'sound'] || 'sound');
    else if (k === 'dnd') r = await api.phone_set_dnd(!st.dnd);
    else if (k === 'ring' && api.link_find) {                          // 울리기·멈추기 모두 PC 에서 된다
      const on = !phoneS.finding;
      r = await api.link_find(on);
      if (r && r.ok) phoneS.finding = !!r.on;
    }
  } catch (e) { r = null; }
  btn.classList.remove('busy');
  if (!r || !r.ok) {
    btn.classList.add('fail'); setTimeout(() => btn.classList.remove('fail'), 900);
    showToast(t(r && r.error === 'policy' ? 'phoneNeedPolicy' : (r && r.error === 'nolink' ? 'phoneReplyNoLink' : 'phoneFail')));
  }
  await phoneLoad();
}

// '화면 보기': 폰 화면 창을 연다(폰에서 알림을 눌러 허용해야 시작된다)
async function phoneMirrorOpen() {
  const api = getApi(); if (!api || !api.phone_screen_open) return;
  let r = null;
  try { r = await api.phone_screen_open(); } catch (e) { r = null; }
  if (r && r.ok) showToast(t('phoneMirrorOpened'));
  else showToast(t(r && r.error === 'off' ? 'phoneMirrorOff' : (r && r.error === 'nolink' ? 'phoneReplyNoLink' : 'phoneFail')));
}

function phoneOpen() {          // 폰 앱 연결 설정(설정 › 폰 앱)을 연다
  const api = getApi(); if (api && api.open_settings) api.open_settings('link');          // 설정 페이지 id 는 'link'(Dalu Link)
}

// 작은 노치용 항목: 부재중은 있을 때만, 배터리는 켜 두었으면 항상
function phoneSatWanted() { const s = store.settings; return tabVisibleId('phone') && !!(s.satPhoneBatt || s.satPhoneMissed); }
function phoneSatItems() {
  const st = phoneS.st, s = store.settings, out = [];
  if (!st || st.state !== 'ok' || !tabVisibleId('phone')) return out;
  if (s.satPhoneMissed && st.missed > 0) out.push({ id: 'phone-miss', kind: 'phone', page: 'phone', running: false, text: t('phoneMissedN', { n: st.missed }), icon: 'missed', pct: 100 });
  if (s.satPhoneBatt && st.battery != null) out.push({ id: 'phone-batt', kind: 'phone', page: 'phone', running: false, text: st.battery + '%', icon: 'phone', pct: 100 });
  return out;
}

function initPhone() {
  if (!$('phGrid')) return;
  phoneBuildTiles();
  initPhoneCall();
  initPhoneFiles();
  initPhoneMedia();
  initPhoneSms();
  $('phOpen').addEventListener('click', (e) => { e.stopPropagation(); phoneOpen(); });
  sysSetIc($('phCardX').querySelector('svg'), 'close');
  $('phCardX').addEventListener('click', (e) => { e.stopPropagation(); phoneCardClose(); });
  $('phCardSend').addEventListener('click', (e) => { e.stopPropagation(); phoneSendReply(); });
  const mute = $('phCardMute');
  if (mute) { sysSetIc(mute.querySelector('svg'), 'bellOff'); mute.addEventListener('click', (e) => { e.stopPropagation(); phoneMuteApp(); }); }
  for (const b of $$('#phSnz .ph-snz')) b.addEventListener('click', (e) => { e.stopPropagation(); phoneSnoozeApp(Number(b.dataset.h)); });          // 1시간·6시간·24시간 차단
  $('phCardIn').addEventListener('keydown', (e) => { if (e.key === 'Enter' && !e.isComposing) { e.preventDefault(); phoneSendReply(); } e.stopPropagation(); });
  $('phCardIn').addEventListener('input', () => document.querySelector('.ph-card-reply').classList.remove('err'));
  langHooks.push(() => { phoneS.sig = ''; renderPhone(); });
  setInterval(() => { if (page === 'phone' && isExpanded && !document.hidden) phoneLoad(); }, PHONE_REFRESH_MS);
  setInterval(() => {
    if (phoneSatWanted() && typeof satOn === 'function' && satOn() && !isExpanded && !document.hidden) phoneLoad().then(() => { if (typeof renderSat === 'function') renderSat(); });
  }, PHONE_SAT_REFRESH_MS);
}


// ---------------------------------------------------------------- 폰 알림: 노치에 띄우고, 카드에서 답장한다
function phoneCardActive() { return !!(phoneS.card && Date.now() < phoneS.cardUntil); }
// 폰 알림 카드가 떠 있으면 휴대폰 탭이 커진다(내용이 길수록 더 크게): 알림을 마우스로 가리켰을 때 내용을 다 읽을 수 있게
function phoneCardBig(base) {
  if (((phoneS.media && phoneS.media.open) || (phoneS.sms && phoneS.sms.open)) && island.dataset.pmed === '1') return { w: Math.max(base.w, 480), h: Math.max(base.h, 226), e: base.e };
  const h = phoneCardH();
  if (h) return { w: Math.max(base.w, 480), h: Math.max(base.h, h), e: base.e };
  if (island.dataset.pxf === '1') return { w: base.w, h: Math.max(base.h, phoneXferH(phoneXferList().length)), e: base.e };          // 전송 카드
  return base;
}
// 카드 높이(px): 글이 많을수록 크게(최대 300). 카드가 없으면 0
function phoneCardH() {
  if (!phoneCardActive() || phoneCallVisible() || phoneS.dial || phonePanelOpen() || (phoneS.st && phoneS.st.state !== 'ok')) return 0;
  const c = phoneS.card, msgs = Array.isArray(c.messages) ? c.messages : [];
  let lines = 0, last = null;
  const multiS = new Set(msgs.map((m) => m.sender || '')).size > 1;
  if (msgs.length) {
    for (const m of msgs) {
      if (m.sender && (multiS || m.sender !== c.sender) && m.sender !== last) lines += 1;
      last = m.sender;
      lines += Math.max(1, Math.ceil((m.text || '').length / 33));
    }
  } else {
    lines = Math.max(1, Math.ceil((c.body || '').length / 33));
  }
  const px = 38 + 22 + lines * 18 + (c.noReply ? 0 : 38) + 34;
  return Math.max(150, Math.min(270, px));          // 창 높이(EXPANDED_HEIGHT 360)에서 알림 띠(38)·독(23)·스프링 여유를 뺀 안
}
// 노치 크기(CSS)를 카드에 맞춘다: .island[data-s=phone][data-pcard=1] 의 --h 가 --pch
function phoneCardSizeSync() {
  const h = phoneCardH();
  const was = island.dataset.pcard === '1' ? island.style.getPropertyValue('--pch') : '';
  if (h) { island.style.setProperty('--pch', h + 'px'); island.dataset.pcard = '1'; }
  else if (island.dataset.pcard !== '0') island.dataset.pcard = '0';
  if ((h ? h + 'px' : '') !== was && typeof scheduleRegion === 'function') scheduleRegion();
}
function phoneNotifyIn(e) {
  if (store.settings.phoneNotify === false || !tabVisibleId('phone')) return;
  const who = (e.group && e.conv) ? e.conv : (e.sender || e.app || '');
  const kind = e.kind || 'app';
  const ic = kind === 'missed' ? 'missed' : (kind === 'call' ? 'call' : 'phone');
  const viewingSame = (kind === 'app' || kind === 'sms') && page === 'phone' && isExpanded && phoneCardActive() && !phonePanelOpen() && !phoneCallVisible() && phoneS.card.app === (e.app || '') && ((phoneS.card.key && phoneS.card.key === e.key) || phoneS.card.sender === (e.conv || e.sender || ''));          // 지금 그 채팅방 카드를 보는 중이면 카드만 바뀐다
  const img = (kind === 'app' || kind === 'sms') ? (e.icon || '') : '';
  const sub = [img ? '' : (kind === 'app' || kind === 'sms' ? e.app : ''), e.body].filter(Boolean).join(' · ');
  if (!viewingSame) notify({ icon: ic, img, tone: kind === 'missed' || kind === 'call' ? 'red' : 'blue', title: who, sub, ms: 5200, key: 'phone-' + e.id });
  playChime('todo');
  const noReply = e.source === 'link' && e.canReply === false;          // 폰 앱: 이 알림은 답장 동작이 없다 -> 카드는 보여 주되 답장 칸은 숨긴다
  if (kind === 'app' || kind === 'sms') {                              // 전화·부재중은 통화 화면이 따로 보여 준다
    phoneS.card = phoneMergeCard(phoneS.card, { id: e.id, app: e.app || '', sender: e.conv || e.sender || '', body: e.body || '', lines: Array.isArray(e.lines) ? e.lines : [], kind, t: Date.now(), key: e.key || '', pkg: e.pkg || '', source: e.source || '', noReply, icon: e.icon || '', conv: e.conv || '', group: !!e.group, messages: Array.isArray(e.messages) ? e.messages.slice(-12) : [] });
    phoneS.cardUntil = Date.now() + PHONE_CARD_SHOW_MS;
    if (page === 'phone') renderPhone();
  }
}
// 폰 앱에서 알림이 지워졌다(폰에서 읽거나 지움): 같은 알림의 답장 카드는 닫는다
// 같은 채팅방(같은 앱·같은 이름)에서 알림이 이어서 오면 카드 하나에 대화로 이어 붙인다(카카오톡·Discord 는 메시지마다 알림이 따로 오기도 한다)
function phoneMergeCard(old, nu) {
  if (!old || Date.now() >= phoneS.cardUntil || old.app !== nu.app || !((old.key && old.key === nu.key) || old.sender === nu.sender)) return nu;          // 같은 알림 키(= 같은 채팅방; 방 안에서 말하는 사람이 바뀌어도) 또는 같은 이름
  const seed = Array.isArray(old.messages) && old.messages.length ? old.messages.slice() : (old.body ? [{ sender: old.sender, text: old.body }] : []);
  let add = nu.messages.length ? nu.messages : (nu.body ? [{ sender: nu.sender, text: nu.body }] : []);
  const sig = (m) => (m.sender || '') + '' + (m.text || '');
  const lastIdx = add.findIndex((m) => seed.length && sig(m) === sig(seed[seed.length - 1]));
  if (lastIdx >= 0) add = add.slice(lastIdx + 1);          // 알림이 지금까지의 대화 전체를 다시 보내 준 경우: 이미 있는 부분은 뺀다
  const all = seed.concat(add.filter((m) => !(seed.length && sig(m) === sig(seed[seed.length - 1])))).slice(-12);
  nu.messages = all;
  nu.group = !!(nu.group || old.group);
  if (!nu.icon) nu.icon = old.icon || '';
  if (!nu.pkg) nu.pkg = old.pkg || '';
  return nu;
}
function phoneNotifyGone(e) {
  if (phoneS.card && phoneS.card.key && phoneS.card.key === e.key) phoneCardClose();
}
// 폰 앱 연결이 바뀌었다: 휴대폰 탭 상태를 바로 다시 읽는다
function phoneLinkState(e) {
  phoneS.finding = false;
  if (typeof phoneReload === 'function') phoneReload();
}
// 알림을 보고 노치를 펼치면 휴대폰 탭(답장 카드)으로 바로 간다
function phoneOnExpand() {
  if (page === 'phone' && phoneS.newMedia && Date.now() - phoneS.newMedia.t < PHONE_CARD_HOVER_MS && !(phoneS.media && phoneS.media.open) && !(phoneS.sms && phoneS.sms.open) && !phoneS.dial && !phoneCallVisible()) { const pre = phoneS.newMedia.items; phoneS.newMedia = null; phoneMediaOpen(pre); return; }
  if (phoneS.newMedia && Date.now() - phoneS.newMedia.t < PHONE_CARD_HOVER_MS && !phoneCallVisible() && !phoneCardActive()) {          // 새 사진 알림을 보고 노치를 펼치면 '폰 사진'이 그 사진을 골라 둔 채 열린다
    const pre = phoneS.newMedia.items; phoneS.newMedia = null;
    if (typeof setPage === 'function') setPage('phone', 1);
    phoneMediaOpen(pre);
    return;
  }
  if (page === 'phone') return;
  if (phoneCallVisible()) { if (typeof setPage === 'function') setPage('phone', 1); return; }          // 전화가 오는 동안에는 펼치면 바로 통화 카드로
  if (!phoneCardActive()) return;
  if (Date.now() - phoneS.card.t > PHONE_CARD_HOVER_MS) return;
  if (typeof setPage === 'function') setPage('phone', 1);
}
// 카드 제목: 단체방이면 '단체톡' 표시(방 이름을 알림이 주지 않는 앱이 많다 — 카카오톡은 제목에 마지막 말한 사람만 넣는다)와 지금까지 말한 사람들
function phoneCardTitle(c) {
  if (!c.group) return c.sender;
  if (c.conv) return c.conv;
  const names = [];
  for (const m of (c.messages || [])) if (m.sender && !names.includes(m.sender)) names.push(m.sender);
  if (c.sender && !names.includes(c.sender)) names.push(c.sender);
  return names.length ? names.slice(0, 4).join(', ') + (names.length > 4 ? ' …' : '') : c.sender;
}
function phoneRenderCard() {
  const card = $('phCard'), grid = $('phGrid');
  if (!card) return;
  const on = phoneCardActive() && (!phoneS.st || phoneS.st.state === 'ok') && !phoneCallVisible() && !phoneS.dial && !phonePanelOpen();          // 문자·폰 사진 화면이 열려 있으면 알림 카드로 덮지 않는다(팝업 띠로만 알리고, 닫으면 카드가 남아 있다)
  card.hidden = !on;
  grid.classList.toggle('card', on);
  phoneCardSizeSync();
  if (!on) return;
  const c = phoneS.card;
  const ap = $('phCardApp');          // 앱 이름 대신 앱 아이콘(없으면 앱 이름)
  if (c.icon && /^data:image\/png;base64,[A-Za-z0-9+/=]+$/.test(c.icon)) {
    if (!ap.firstElementChild || ap.firstElementChild.src !== c.icon) { ap.textContent = ''; const im = document.createElement('img'); im.src = c.icon; im.alt = c.app; ap.appendChild(im); }
    ap.title = c.app;
  } else { ap.title = ''; setText(ap, c.app); }
  setText($('phCardWho'), phoneCardTitle(c));
  const bd = $('phCardBody'), msgs = Array.isArray(c.messages) ? c.messages : [];
  if (msgs.length) {
    // 이어서 온 대화: 보낸 사람이 바뀔 때마다 이름을 굵게, 그 아래에 글을 줄마다
    const csig = 'm|' + c.sender + '|' + JSON.stringify(msgs.map((m) => [m.sender, m.text]));
    if (bd._sig !== csig) {
    bd._sig = csig;
    bd.textContent = '';
    let last = null;
    const multi = new Set(msgs.map((m) => m.sender || '')).size > 1;          // 말하는 사람이 둘 이상이면 이름을 항상 붙인다
    for (const m of msgs) {
      if (m.sender && (multi || m.sender !== c.sender) && m.sender !== last) { const w = document.createElement('div'); w.className = 'ph-th-who'; w.textContent = m.sender; bd.appendChild(w); }
      last = m.sender;
      const d = document.createElement('div'); d.className = 'ph-th-msg'; d.textContent = m.text || ''; bd.appendChild(d);
    }
    bd.scrollTop = bd.scrollHeight;                          // 가장 최근 메시지가 보이게
    }
  } else {
    const csig = 'b|' + (c.body || '');
    if (bd._sig !== csig) { bd._sig = csig; setText(bd, c.body); bd.scrollTop = 0; }
  }
  const mb = $('phCardMute'); if (mb) mb.hidden = !c.pkg;          // 패키지 이름을 아는 알림(폰 앱 연결)만 '이 앱 끄기'
  card.classList.toggle('no-reply', !!c.noReply);          // 답장 동작이 없는 알림: 답장 칸 없이 내용만 크게
  card.classList.toggle('long', (c.body || '').length > 90 || msgs.length > 1);
}
// 카드의 '이 앱 끄기': 이 앱의 알림을 더는 띄우지 않는다(설정 › Dalu Link 에서 다시 켤 수 있다)
async function phoneMuteApp() {
  const c = phoneS.card, api = getApi();
  if (!c || !c.pkg || !api || !api.phone_notify_app_set) return;
  let r = null;
  const sz = $('phSnz');          // 임시 차단 단추(패키지 이름을 아는 알림만)
  if (sz) { sz.hidden = !c.pkg; for (const b of $$('#phSnz .ph-snz')) { b.textContent = t('phoneSnooze' + b.dataset.h); b.setAttribute('aria-label', t('phoneSnoozeAria', { h: b.dataset.h })); } }
  try { r = await api.phone_notify_app_set(c.pkg, false); } catch (e) { r = null; }
  if (r && r.ok) { showToast(t('phoneMutedApp', { app: c.app || r.app || c.pkg })); phoneCardClose(); }
  else showToast(t('phoneFail'));
}
function phoneCardClose() {
  phoneS.card = null; phoneS.cardUntil = 0;
  const inp = $('phCardIn'); if (inp) { inp.value = ''; inp.blur(); }
  renderPhone();
}
const PHONE_REPLY_ERR = { empty: 'phoneReplyFail', toolong: 'phoneReplyFail', nolink: 'phoneReplyNoLink', gone: 'phoneReplyGoneLink', canceled: 'phoneReplyGoneLink', timeout: 'phoneReplyFail' };
async function phoneSendReply() {
  const c = phoneS.card, inp = $('phCardIn'), row = document.querySelector('.ph-card-reply');
  if (!c || !inp || phoneS.sending) return;
// 카드의 '1시간/6시간/24시간 차단': 이 앱의 알림을 그 시간 동안만 띄우지 않는다(시간이 지나면 저절로 풀린다)
async function phoneSnoozeApp(h) {
  const c = phoneS.card, api = getApi();
  if (!c || !c.pkg || !api || !api.phone_notify_snooze) return;
  let r = null;
  try { r = await api.phone_notify_snooze(c.pkg, h); } catch (e) { r = null; }
  if (r && r.ok) { showToast(t('phoneSnoozedApp', { app: c.app || r.app || c.pkg, h })); phoneCardClose(); }
  else showToast(t('phoneFail'));
}
  const text = inp.value.trim();
  if (!text) return;
  const api = getApi(); if (!api || !api.link_reply) return;
  phoneS.sending = true; row.classList.add('busy'); row.classList.remove('err');
  let r = null;
  try {
    if (c.key) r = await api.link_reply(c.key, text);          // 폰 앱이 그 알림의 답장 동작을 실행한다
    else r = { ok: false, error: 'gone' };
  } catch (e) { r = null; }
  phoneS.sending = false; row.classList.remove('busy');
  if (r && r.ok) { showToast(t('phoneReplySent')); phoneCardClose(); return; }
  row.classList.add('err');
  showToast(t(PHONE_REPLY_ERR[r && r.error] || 'phoneReplyFail'));
}


// ---------------------------------------------------------------- 전화: 걸려 오는 전화(받기·거절), 통화 중(끊기), 전화 걸기(번호·연락처 검색), 부재중
function phoneCallVisible() { return !!(phoneS.call && (!phoneS.st || phoneS.st.state === 'ok')); }

// 폰 앱이 통화 상태를 알려 왔다
function phoneCallIn(e) {
  if (e.state === 'idle') {
    phoneS.call = null;
    phoneCallSync();
    if (e.missed && typeof notify === 'function') notify({ icon: 'missed', tone: 'red', ms: 6000, title: t('phoneMissedCall'), sub: e.name || e.number || t('phoneUnknownNumber') });
    renderPhone();
    if (typeof phoneReload === 'function') phoneReload();
    return;
  }
  const prev = phoneS.call;
  phoneS.call = { state: e.state, incoming: !!e.incoming, number: e.number || '', name: e.name || '', t: (prev && prev.t) || Date.now(), t0: e.state === 'active' ? ((prev && prev.t0) || Date.now()) : 0, audio: (prev && prev.audio) || null, rec: prev ? prev.rec : undefined, recT0: prev ? prev.recT0 : 0 };
  // 펼쳐서 쓰는 중이면 알림 띠로 알린다(접혀 있을 때는 큰 노치가 통화 정보로 바뀌고 보조 노치가 받기/거절이 된다)
  if (!prev && e.state === 'ringing' && e.incoming && isExpanded && typeof notify === 'function') notify({ icon: 'callring', tone: 'green', ms: 8000, key: 'phonecall', title: e.name || e.number || t('phoneUnknownNumber'), sub: t('phoneCalling') });
  phoneCallSync();
  if (page === 'phone') renderPhone();
}

function phoneRenderCall() {
  const el = $('phCall'); if (!el) return;
  const c = phoneS.call, on = phoneCallVisible();
  el.hidden = !on;
  if (!on) return;
  const ringing = c.state === 'ringing' && c.incoming;
  el.classList.toggle('ring', ringing);
  setText($('phCallSt'), ringing ? t('phoneCalling') : t('phoneInCall') + (c.t0 ? ' · ' + phoneFmtDur(Date.now() - c.t0) : ''));
  setText($('phCallWho'), c.name || c.number || t('phoneUnknownNumber'));
  setText($('phCallNum'), c.name ? c.number : '');
  $('phAns').hidden = !ringing;
  for (const id of ['phSpk', 'phMute', 'phRec']) $(id).hidden = ringing;          // 통화 중에만 스피커·음소거·녹음
  $('phSpk').classList.toggle('on', !!(c.audio && c.audio.speaker));
  $('phMute').classList.toggle('on', !!(c.audio && c.audio.mute));
  $('phRec').classList.toggle('on', !!c.rec);
  setText($('phRec'), t('phoneRecord') + (c.rec && c.recT0 ? ' ' + phoneFmtDur(Date.now() - c.recT0) : ''));
  setText($('phEnd'), t(ringing ? 'phoneDecline' : 'phoneHangup'));
  $('phGrid').classList.add('card');
}

async function phoneCallAct(kind) {
  const api = getApi(), btn = $(kind === 'answer' ? 'phAns' : 'phEnd');
  if (!api || !btn || btn.classList.contains('busy')) return;
  btn.classList.add('busy');
  let r = null;
  try { r = kind === 'answer' ? await api.phone_call_answer() : await api.phone_call_end(); } catch (e) { r = null; }
  btn.classList.remove('busy');
  if (!r || !r.ok) showToast(t(r && r.error === 'perm' ? 'phoneNeedCallPerm' : (r && r.error === 'nolink' ? 'phoneReplyNoLink' : 'phoneFail')));
}

function phoneIsNumber(q) { return /^\+?[0-9 ()\-.]+$/.test(q) && (q.match(/[0-9]/g) || []).length >= 3; }

function phoneToggleDial(on) {
  phoneS.dial = on === undefined ? !phoneS.dial : !!on;
  if (phoneS.dial) phoneCloseOthers('dial');
  const inp = $('phDialIn'), list = $('phDialList');
  if (!phoneS.dial) { if (inp) { inp.value = ''; inp.blur(); } if (list) list.textContent = ''; phoneS.dialSeq++; }
  renderPhone();
  if (phoneS.dial && inp) setTimeout(() => inp.focus(), 60);
}

function phoneRenderDial() {
  const el = $('phDial'); if (!el) return;
  const on = phoneS.dial && !phoneCallVisible() && (!phoneS.st || phoneS.st.state === 'ok');
  el.hidden = !on;
  $('phoneLayer').classList.toggle('dial-on', on);          // 전화 걸기 화면에도 뒤로 버튼
  if (on) $('phGrid').classList.add('card');
}

function phoneDialMsg(text) {
  const list = $('phDialList'); list.textContent = '';
  if (!text) return;
  const d = document.createElement('div'); d.className = 'ph-dial-msg'; d.textContent = text; list.appendChild(d);
}

// 연락처 검색: 글자를 멈춘 뒤 한 번만 폰에 묻는다. 결과는 화면에만 두고 저장하지 않는다.
async function phoneDialSearch() {
  const inp = $('phDialIn'), list = $('phDialList'), api = getApi();
  const q = inp.value.trim(), seq = ++phoneS.dialSeq;
  if (!q || phoneIsNumber(q) || !api || !api.phone_contacts) { list.textContent = ''; return; }
  let r = null;
  try { r = await api.phone_contacts(q); } catch (e) { r = null; }
  if (seq !== phoneS.dialSeq || !phoneS.dial) return;            // 그 사이 글자가 바뀌었거나 패널이 닫혔다
  if (!r || !r.ok) { phoneDialMsg(t(r && r.error === 'perm' ? 'phoneContactsPerm' : 'phoneFail')); return; }
  if (!r.items || !r.items.length) { phoneDialMsg(t('phoneNoContacts')); return; }
  list.textContent = '';
  for (const it of r.items.slice(0, 15)) {
    const row = document.createElement('div'); row.className = 'ph-dial-item'; row.title = it.number;
    const b = document.createElement('b'); b.textContent = it.name || it.number;
    const sp = document.createElement('span'); sp.textContent = it.number;
    row.append(b, sp);
    row.addEventListener('click', (ev) => { ev.stopPropagation(); phoneDial(it.number); });
    list.appendChild(row);
  }
}

async function phoneDial(number) {
  const api = getApi(), row = document.querySelector('.ph-dial-row');
  if (!api || !api.phone_dial || !row || row.classList.contains('busy')) return;
  row.classList.add('busy'); row.classList.remove('err');
  let r = null;
  try { r = await api.phone_dial(number); } catch (e) { r = null; }
  row.classList.remove('busy');
  if (r && r.ok) { showToast(t('phoneDialing')); phoneToggleDial(false); return; }
  row.classList.add('err');
  showToast(t(r && r.error === 'number' ? 'phoneBadNumber' : (r && r.error === 'perm' ? 'phoneNeedCallPerm' : (r && r.error === 'nolink' ? 'phoneReplyNoLink' : 'phoneFail'))));
}

function phoneDialGo() {
  const q = $('phDialIn').value.trim();
  if (!q) return;
  if (phoneIsNumber(q)) phoneDial(q); else phoneDialSearch();
}

function initPhoneCall() {
  if (!$('phCall')) return;
  $('phAns').addEventListener('click', (e) => { e.stopPropagation(); phoneCallAct('answer'); });
  $('phEnd').addEventListener('click', (e) => { e.stopPropagation(); phoneCallAct('end'); });
  $('phSpk').addEventListener('click', (e) => { e.stopPropagation(); phoneCallAudio('speaker'); });
  $('phMute').addEventListener('click', (e) => { e.stopPropagation(); phoneCallAudio('mute'); });
  $('phRec').addEventListener('click', (e) => { e.stopPropagation(); phoneCallRecord(); });
  sysSetIc($('phDialX').querySelector('svg'), 'close');
  $('phDialX').addEventListener('click', (e) => { e.stopPropagation(); phoneToggleDial(false); });
  $('phDialGo').addEventListener('click', (e) => { e.stopPropagation(); phoneDialGo(); });
  const inp = $('phDialIn');
  inp.addEventListener('input', () => {
    document.querySelector('.ph-dial-row').classList.remove('err');
    clearTimeout(phoneS.dialTimer);
    phoneS.dialTimer = setTimeout(phoneDialSearch, 300);
  });
  inp.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.isComposing) { e.preventDefault(); phoneDialGo(); }
    else if (e.key === 'Escape') { e.preventDefault(); phoneToggleDial(false); }
    e.stopPropagation();
  });
  langHooks.push(() => renderPhone());
}


// ---------------------------------------------------------------- 통화 화면(접힌 큰 노치의 통화 정보, 보조 노치 버튼, 통화 시간, 스피커·음소거)
function phoneFmtDur(ms) {
  const sec = Math.max(0, Math.floor(ms / 1000)), h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), r = sec % 60;
  const two = (n) => String(n).padStart(2, '0');
  return h ? `${h}:${two(m)}:${two(r)}` : `${two(m)}:${two(r)}`;
}

// 통화 상태가 바뀔 때: 큰 노치(접힌 뷰)와 보조 노치를 다시 맞춘다
function phoneCallSync() {
  const on = phoneCallVisible(), c = phoneS.call;
  island.dataset.call = on ? '1' : '0';
  island.dataset.callRing = on && c.state === 'ringing' && c.incoming ? '1' : '0';
  phoneCallMini();
  if (typeof updateView === 'function') updateView();
  if (typeof renderSat === 'function') renderSat();
}

function phoneCallMini() {
  const c = phoneS.call;
  if (!c || !phoneCallVisible()) return;
  const ringing = c.state === 'ringing' && c.incoming;
  sysSetIc($('mcIco').querySelector('svg'), ringing ? 'callring' : 'call');
  setText($('mcWho'), c.name || c.number || t('phoneUnknownNumber'));
  setText($('mcTime'), ringing ? t('phoneCalling') : (c.t0 ? phoneFmtDur(Date.now() - c.t0) : ''));
  const rec = !ringing && !!c.rec;
  $('mcRec').hidden = !rec;
  setText($('mcRec'), rec ? '● ' + (c.recT0 ? phoneFmtDur(Date.now() - c.recT0) : t('phoneRecord')) : '');
}

// 보조 노치: 오는 전화는 받기(오른쪽)·거절(왼쪽), 통화 중에는 끊기
function phoneCallSatItems() {
  if (!phoneCallVisible()) return [];
  const c = phoneS.call;
  if (c.state === 'ringing' && c.incoming) {
    return [
      { id: 'phone-call-answer', kind: 'phone', page: 'phone', running: false, text: t('phoneAnswer'), icon: 'call', tone: 'ans' },
      { id: 'phone-call-end', kind: 'phone', page: 'phone', running: false, text: t('phoneDecline'), icon: 'callend', tone: 'end' },
    ];
  }
  return [{ id: 'phone-call-end', kind: 'phone', page: 'phone', running: false, text: t('phoneHangup'), icon: 'callend', tone: 'end' }];
}

// 스피커폰 / 마이크 음소거. 폰이 실제로 바뀌었는지 다시 읽어 와서 보여 주고, 안드로이드가 막으면 그대로 알려 준다.
async function phoneCallAudio(kind) {
  const api = getApi(), c = phoneS.call, btn = $(kind === 'speaker' ? 'phSpk' : 'phMute');
  if (!api || !api.phone_call_audio || !c || !btn || btn.classList.contains('busy')) return;
  const cur = c.audio || { speaker: false, mute: false };
  btn.classList.add('busy');
  let r = null;
  try { r = await api.phone_call_audio(kind === 'speaker' ? !cur.speaker : null, kind === 'mute' ? !cur.mute : null); } catch (e) { r = null; }
  btn.classList.remove('busy');
  if (r && typeof r.speaker === 'boolean') c.audio = { speaker: !!r.speaker, mute: !!r.mute };
  if (!r || !r.ok) showToast(t(phoneCallErr(r)));
  renderPhone();
}

// 통화 중 폰 앱 통화 화면의 버튼을 대신 누르는 요청이 실패한 이유를 알려 주는 문구
function phoneCallErr(r) {
  const e = r && r.error;
  return e === 'refused' ? 'phoneAudioRefused' : e === 'perm' ? 'phoneNeedCallPerm' : e === 'not_visible' ? 'phoneNeedCallScreen' : e === 'no_button' ? 'phoneNoButton' : e === 'unavailable' ? 'phoneNeedA11y' : 'phoneFail';
}

// 통화 녹음: 전화 앱의 '녹음' 버튼을 폰이 대신 누른다(켜짐 여부를 읽을 수 있을 때만 켜진 것으로 표시한다)
async function phoneCallRecord() {
  const api = getApi(), c = phoneS.call, btn = $('phRec');
  if (!api || !api.phone_call_record || !c || !btn || btn.classList.contains('busy')) return;
  btn.classList.add('busy');
  let r = null;
  try { r = await api.phone_call_record(typeof c.rec === 'boolean' ? !c.rec : null); } catch (e) { r = null; }
  btn.classList.remove('busy');
  if (r && typeof r.on === 'boolean') { if (r.on && !c.rec) c.recT0 = Date.now(); c.rec = r.on; if (!r.on) c.recT0 = 0; }
  if (!r || !r.ok) showToast(t(phoneCallErr(r)));
  phoneCallMini();
  renderPhone();
}

// 폰에서 직접(또는 자동 녹음으로) 스피커·음소거·녹음이 바뀌었다
function phoneCallAudioIn(e) {
  const c = phoneS.call;
  if (!c) return;
  c.audio = { speaker: !!e.speaker, mute: !!e.mute };
  const was = !!c.rec;
  c.rec = !!e.rec;
  if (c.rec && !was) c.recT0 = Date.now() - (e.recMs || 0);
  if (!c.rec) c.recT0 = 0;
  phoneCallMini();
  if (page === 'phone') renderPhone();
}

// 통화 시간은 1초마다 갱신한다(큰 노치의 통화 정보와 통화 카드)
setInterval(() => {
  if (phoneS.card && !phoneCardActive()) phoneCardClose();          // 카드 표시 시간이 지났다: 닫고 노치 크기를 되돌린다
  if (!phoneCallVisible()) return;
  phoneCallMini();
  if (page === 'phone' && isExpanded) phoneRenderCall();
}, 1000);


// ---------------------------------------------------------------- 파일 주고받기: 선택 창·끌어다 놓기·진행 카드
const PHONE_FILE_ERR = { declined: 'phoneFileDeclined', nolink: 'phoneFileNoLink', toobig: 'phoneFileTooBig', space: 'phoneFileSpace', hash: 'phoneFileHash', canceled: 'phoneFileCanceled' };
const PHONE_FILE_ACTIVE = ['waiting', 'sending', 'receiving'];
phoneS.files = {};
phoneS.xferHide = 0;

function phoneFileErrKey(code) { return PHONE_FILE_ERR[code] || 'phoneFileFailed'; }
function phoneFmtSize(n) {
  n = Number(n) || 0;
  if (n >= 1073741824) return (n / 1073741824).toFixed(1) + ' GB';
  if (n >= 1048576) return (n / 1048576).toFixed(n >= 10485760 ? 0 : 1) + ' MB';
  if (n >= 1024) return Math.round(n / 1024) + ' KB';
  return n + ' B';
}

async function phonePickFiles() {
  const api = getApi();
  if (!api || !api.phone_pick_files) return;
  let r = null;
  try { r = await api.phone_pick_files(); } catch (e) { r = null; }
  if (r && r.ok) { renderPhone(); return; }
  if (r && r.error === 'none') return;                      // 선택 창을 그냥 닫았다
  showToast(t(r && r.error === 'nolink' ? 'phoneFileNoLink' : phoneFileErrKey(r && r.failed && r.failed[0] && r.failed[0].error)));
}

// 끌어다 놓은 파일을 폰으로 보낸다(선반의 '휴대폰으로 보내기' 칸에 놓았을 때)
async function phoneSendPaths(paths) {
  const api = getApi();
  if (!api || !api.phone_send_files || !paths || !paths.length) return;
  let r = null;
  try { r = await api.phone_send_files(paths); } catch (e) { r = null; }
  if (!r || !r.ok) showToast(t(r && r.error === 'nolink' ? 'phoneFileNoLink' : phoneFileErrKey(r && r.error)));
  else { if (typeof setPage === 'function') setPage('phone', 1); }
}

function phoneFileEvent(e) {
  if (!e || !e.fid) return;
  const f = phoneS.files[e.fid] || (phoneS.files[e.fid] = { t: Date.now(), fid: e.fid });
  const was = f.state;
  f.dir = e.dir; f.name = e.name || f.name || ''; f.size = e.size || 0; f.done = e.done || 0; f.state = e.state; f.error = e.error || ''; f.bps = e.bps || 0;
  if (e.path) f.path = e.path;
  const fin = !PHONE_FILE_ACTIVE.includes(f.state);
  if (fin && !f.fin) {
    f.fin = Date.now();
    if (typeof notify === 'function' && isExpanded && page !== 'phone') {          // 접혀 있으면 큰 노치가, 휴대폰 탭이면 전송 카드가 결과를 보여 준다
      const ok = f.state === 'done';
      notify({ icon: ok ? 'folder' : 'missed', tone: ok ? 'blue' : 'red', ms: 4200, key: 'phonefile-' + f.fid, title: f.name, sub: t(ok ? (f.dir === 'in' ? 'phoneFileGot' : 'phoneFileSent') : phoneFileErrKey(f.error)) });
    }
  }
  const keys = Object.keys(phoneS.files);
  if (keys.length > 80) {          // 끝난 것부터 오래된 순으로 잊는다(차례를 기다리는 전송은 남긴다)
    const act = (k) => (PHONE_FILE_ACTIVE.includes(phoneS.files[k].state) ? 1 : 0);
    for (const k of keys.sort((a, b) => act(a) - act(b) || phoneS.files[a].t - phoneS.files[b].t).slice(0, keys.length - 80)) delete phoneS.files[k];
  }
  if (page === 'phone') renderPhone();
  phoneXferSync();
  if (fin && f.fin && Date.now() - f.fin < 200) { playChime(f.state === 'done' ? 'water' : 'todo'); setTimeout(phoneXferSync, XFER_DONE_SHOW_MS + 150); }          // 끝나면 소리로도 알린다
}

function phoneXferList() {
  const now = Date.now(), out = [];
  for (const f of Object.values(phoneS.files)) {
    if (phoneS.xferHide && f.t <= phoneS.xferHide) continue;          // '뒤로'로 닫은 목록: 그 뒤에 시작한 전송이 있을 때까지 타일을 보여 준다(전송은 계속된다)
    if (PHONE_FILE_ACTIVE.includes(f.state) || (f.fin && now - f.fin < 12000)) out.push(f);
  }
  return out.sort((a, b) => (PHONE_FILE_ACTIVE.includes(b.state) - PHONE_FILE_ACTIVE.includes(a.state)) || b.t - a.t).slice(0, 3);
}
// 전송 카드가 보일 때 노치 높이(px): 줄 수만큼 커진다
function phoneXferH(rows) { return Math.max(132, Math.min(232, 62 + 50 * Math.max(1, rows))); }
function phoneXferActive() { return Object.values(phoneS.files).some((f) => PHONE_FILE_ACTIVE.includes(f.state)); }

function phoneRenderXfer() {
  const box = $('phXfer'), grid = $('phGrid');
  if (!box) return;
  const list = phoneXferList();
  const on = list.length > 0 && !phoneCallVisible() && !phoneS.dial && !phoneCardActive() && !(phoneS.media && phoneS.media.open) && !(phoneS.sms && phoneS.sms.open);
  box.hidden = !on;
  const sms = $('phSms'), med = $('phMedia');
  const panel = (sms && !sms.hidden) || (med && !med.hidden);          // 문자·갤러리 패널이 열려 있는 동안은 타일을 계속 숨겨 둔다(1초마다 이 함수만 불릴 때 표시가 지워져 타일이 패널 밑에 비치던 것)
  grid.classList.toggle('xfer', on || !!panel);
  $('phoneLayer').classList.toggle('xfer-on', on);
  const sig = on ? phoneXferH(list.length) : 0;
  if (sig !== phoneS.xferSig) {          // 카드가 켜지거나 줄 수가 바뀔 때만 노치 크기를 다시 맞춘다
    phoneS.xferSig = sig;
    island.dataset.pxf = on ? '1' : '0';
    if (on) island.style.setProperty('--pxh', sig + 'px');
    if (typeof scheduleRegion === 'function') scheduleRegion();
  }
  if (!on) { box.textContent = ''; return; }
  box.textContent = '';
  for (const f of list) {
    const active = PHONE_FILE_ACTIVE.includes(f.state), pct = f.size > 0 ? Math.min(100, Math.floor(f.done * 100 / f.size)) : (f.state === 'done' ? 100 : 0);
    const row = document.createElement('div'); row.className = 'ph-xrow' + (f.state === 'done' ? ' done' : (active ? '' : ' fail'));
    const top = document.createElement('div'); top.className = 'ph-xtop';
    const nm = document.createElement('span'); nm.className = 'ph-xname'; nm.textContent = f.name; top.appendChild(nm);
    if (active) {
      const x = document.createElement('button'); x.className = 'ph-xbtn'; x.textContent = t('phoneFileCancel'); x.dataset.act = 'cancel'; x.dataset.fid = f.fid; top.appendChild(x);
    } else if (f.state === 'done' && f.dir === 'in' && f.path) {
      const o = document.createElement('button'); o.className = 'ph-xbtn'; o.textContent = t('phoneFileOpen'); o.dataset.act = 'open'; o.dataset.fid = f.fid; top.appendChild(o);
      const d = document.createElement('button'); d.className = 'ph-xbtn'; d.textContent = t('phoneFileFolder'); d.dataset.act = 'folder'; d.dataset.fid = f.fid; top.appendChild(d);
    }
    row.appendChild(top);
    const bar = document.createElement('div'); bar.className = 'ph-xbar'; const fill = document.createElement('i'); fill.style.width = pct + '%'; bar.appendChild(fill); row.appendChild(bar);
    const meta = document.createElement('div'); meta.className = 'ph-xmeta';
    const m1 = document.createElement('span');
    if (active) m1.textContent = f.state === 'waiting' ? t('phoneFileWaiting') : t(f.dir === 'in' ? 'phoneFileReceiving' : 'phoneFileSending') + ' · ' + pct + '%' + (f.bps > 0 ? ' · ' + phoneFmtSize(f.bps) + '/s' : '');
    else if (f.state === 'done') { m1.className = 'ok'; m1.textContent = t(f.dir === 'in' ? 'phoneFileGot' : 'phoneFileSent') + ' · ' + phoneFmtSize(f.size); }
    else { m1.className = 'err'; m1.textContent = t(phoneFileErrKey(f.error)); }
    meta.appendChild(m1); row.appendChild(meta);
    box.appendChild(row);
  }
}

// 접힌 큰 노치에 보여 줄 전송 진행: 전송 중이면 진행률·속도, 끝난 뒤에는 3.5초 동안 결과
const XFER_DONE_SHOW_MS = 3500;
function phoneXferMini() {
  const now = Date.now(), act = [];
  let fin = null;
  for (const f of Object.values(phoneS.files)) {
    if (PHONE_FILE_ACTIVE.includes(f.state)) act.push(f);
    else if (f.fin && now - f.fin < XFER_DONE_SHOW_MS && (!fin || f.fin > fin.fin)) fin = f;
  }
  if (act.length) return { mode: 'active', list: act };
  if (fin) return { mode: 'fin', f: fin };
  return null;
}
function phoneXferMiniOn() { return !!phoneXferMini() && !phoneCallVisible(); }
function phoneXferMiniRender() {
  const m = phoneXferMini(), on = !!m && !phoneCallVisible();
  island.dataset.xfer = on ? '1' : '0';
  if (!on) { island.dataset.xferS = ''; return; }
  let name, meta, pct, st = '', dir;
  if (m.mode === 'active') {
    const size = m.list.reduce((a, f) => a + (f.size || 0), 0), done = m.list.reduce((a, f) => a + (f.done || 0), 0), bps = m.list.reduce((a, f) => a + (f.bps || 0), 0);
    pct = size > 0 ? Math.min(100, Math.floor(done * 100 / size)) : 0;
    name = m.list.length === 1 ? m.list[0].name : t('phoneFileN', { n: m.list.length });
    meta = (m.list.every((f) => f.state === 'waiting') ? t('phoneFileWaiting') : pct + '%' + (bps > 0 ? ' · ' + phoneFmtSize(bps) + '/s' : ''));
    dir = m.list.every((f) => f.dir === 'in') ? 'in' : 'out';
  } else {
    const f = m.f, ok = f.state === 'done';
    name = f.name; pct = ok ? 100 : (f.size > 0 ? Math.floor(f.done * 100 / f.size) : 0);
    meta = ok ? t(f.dir === 'in' ? 'phoneFileGot' : 'phoneFileSent') : t(phoneFileErrKey(f.error));
    st = ok ? 'ok' : 'fail'; dir = f.dir;
  }
  island.dataset.xferS = st;
  sysSetIc($('mxIco').querySelector('svg'), st === 'ok' ? 'check' : (st === 'fail' ? 'close' : (dir === 'in' ? 'download' : 'upload')));
  setText($('mxName'), name);
  setText($('mxMeta'), meta);
  $('mxBar').style.width = pct + '%';
}
function phoneXferSync() {
  const was = island.dataset.xfer === '1';
  phoneXferMiniRender();
  // 진행률이 바뀔 때마다 뷰·작은 노치를 다시 계산하지 않는다(보조 노치가 깜빡이던 원인): 전송 화면이 켜지거나 꺼질 때만
  if (was !== (island.dataset.xfer === '1') && typeof updateView === 'function') updateView();
}

// 작은 노치: 파일을 주고받는 동안 진행률 항목
function phoneFileSatItems() {
  if (!phoneXferActive() || phoneXferMiniOn()) return [];          // 접힌 큰 노치가 진행 상황을 보여 주는 동안에는 중복해서 띄우지 않는다
  const act = Object.values(phoneS.files).filter((f) => PHONE_FILE_ACTIVE.includes(f.state));
  const size = act.reduce((a, f) => a + (f.size || 0), 0), done = act.reduce((a, f) => a + (f.done || 0), 0);
  const pct = size > 0 ? Math.min(100, Math.floor(done * 100 / size)) : 0;
  return [{ id: 'phone-file', kind: 'phone', page: 'phone', running: true, text: pct + '%', icon: 'folder', pct }];
}

function initPhoneFiles() {
  const back = $('phBack');
  if (back) {
    sysSetIc(back.querySelector('svg'), 'back');
    back.setAttribute('aria-label', t('phoneBack'));          // 마우스를 올려도 말풍선은 뜨지 않는다(화면 읽기용 이름만)
    back.addEventListener('click', (e) => { e.stopPropagation(); if (phoneS.dial) { phoneToggleDial(false); return; } if (phoneS.sms && phoneS.sms.open) { phoneSmsBack(); return; } if (phoneS.media && phoneS.media.open) { phoneMediaClose(); return; } phoneS.xferHide = Date.now(); renderPhone(); if (typeof updateView === 'function') updateView(); });
  }
  const box = $('phXfer');
  if (box) box.addEventListener('click', async (e) => {
    const b = e.target.closest('.ph-xbtn'); if (!b) return;
    e.stopPropagation();
    const api = getApi(); if (!api) return;
    const f = phoneS.files[b.dataset.fid]; if (!f) return;
    try {
      if (b.dataset.act === 'cancel' && api.phone_file_cancel) await api.phone_file_cancel(f.fid);
      else if (b.dataset.act === 'open' && api.phone_file_open) await api.phone_file_open(f.path, false);
      else if (b.dataset.act === 'folder' && api.phone_file_open) await api.phone_file_open(f.path, true);
    } catch (err) { /* 무시 */ }
  });
  const pdz = $('phDrop'); if (pdz) sysSetIc(pdz.querySelector('svg'), 'phone');
  const z = $('shPhone');
  if (z) {
    sysSetIc(z.querySelector('svg'), 'phone');
    z.addEventListener('dragenter', (e) => { e.preventDefault(); z.classList.add('over'); });
    z.addEventListener('dragover', (e) => { e.preventDefault(); z.classList.add('over'); });
    z.addEventListener('dragleave', () => z.classList.remove('over'));
  }
  setInterval(() => { if (page === 'phone' && isExpanded && Object.keys(phoneS.files).length) phoneRenderXfer(); }, 1000);          // 진행 표시만(전체를 다시 그리면 문자 스크롤과 사진 선택이 흔들린다)
  setInterval(() => { if (phoneXferMini() || island.dataset.xfer === '1') phoneXferSync(); }, 1000);
}


// ---------------------------------------------------------------- 폰 사진·동영상 보기(읽기 전용 목록 + 고른 것만 가져오기)
phoneS.media = { open: false, kind: 'all', items: [], sel: new Set(), more: false, loading: false, err: '', seq: 0 };

function phoneMediaOpen(pre) {
  phoneCloseOthers('media');
  const m = phoneS.media;
  m.open = true; m.items = Array.isArray(pre) ? pre.slice() : []; m.sel = new Set(m.items.map((_, i) => i)); m.err = ''; m.more = false;          // pre: 방금 찍은 사진(미리 골라 둔다)
  phoneMediaLoad(true);
  renderPhone();
}
function phoneMediaClose() {
  phoneS.media.open = false; phoneS.media.items = []; phoneS.media.sel = new Set(); phoneS.media.seq++; phoneS.media.loading = false;
  renderPhone();
}
async function phoneMediaLoad(reset) {
  const m = phoneS.media, api = getApi();
  if (!api || !api.phone_media_list || (m.loading && !reset)) return;          // 처음부터 다시 읽기(종류를 바꿈)는 읽는 중이어도 새로 시작한다: 앞의 답은 버린다
  m.loading = true; m.err = '';
  const seq = ++m.seq;
  const last = reset || !m.items.length ? null : m.items[m.items.length - 1];
  renderPhone();
  let r = null;
  try { r = await api.phone_media_list(m.kind, last ? last.t : 0, last ? last.id : 0); } catch (e) { r = null; }          // 마지막 항목의 시각 + id 다음부터(같은 시각의 사진이 빠지지 않게)
  if (seq !== m.seq) return;                                // 더 새로운 요청이 있다(읽는 중 표시는 그 요청의 것)
  m.loading = false;
  if (!m.open) return;
  if (r && r.ok) {
    const seen = new Set(m.items.map((x) => x.k + x.id));
    for (const it of r.items || []) if (!seen.has(it.k + it.id)) m.items.push(it);
    m.more = !!r.more;
  } else {
    m.err = r && r.error === 'perm' ? 'pmPerm' : (r && r.error === 'nolink' ? 'phoneFileNoLink' : 'pmFail');
  }
  renderPhone();
}
function phoneFmtDurMs(ms) { const s = Math.round((Number(ms) || 0) / 1000), m = Math.floor(s / 60); return m + ':' + String(s % 60).padStart(2, '0'); }

function phoneRenderMedia() {
  const box = $('phMedia'); if (!box) return;
  const m = phoneS.media, st = phoneS.st || {};
  const on = m.open && st.state === 'ok' && !phoneCallVisible() && !phoneS.dial;
  box.hidden = !on;
  $('phoneLayer').classList.toggle('media-on', on);
  phonePanelSync();
  $('phGrid').classList.toggle('xfer', on || $('phGrid').classList.contains('xfer'));
  if (!on) { if (m.open && phoneS.st && st.state !== 'ok') phoneS.media.open = false; return; }          // 상태를 아직 못 읽었다면(null) 방금 연 갤러리를 닫지 않는다
  for (const b of $$('#pmSeg button')) b.classList.toggle('on', b.dataset.k === m.kind);
  const g = $('pmGrid'), msg = $('pmMsg');
  const gsig = JSON.stringify([m.items.map((it) => [it.k, it.id != null ? it.id : it.name, it.th ? 1 : 0]), [...m.sel], !!m.more, !!m.loading, t('pmGet')]);
  if (g._sig !== gsig) {
  g._sig = gsig;
  g.textContent = '';
  for (let i = 0; i < m.items.length; i++) {
    const it = m.items[i], b = document.createElement('button');
    b.type = 'button'; b.className = 'pm-it' + (m.sel.has(i) ? ' sel' : ''); b.dataset.i = String(i); b.title = it.name;
    if (it.th) { const im = document.createElement('img'); im.src = it.th; im.alt = ''; b.appendChild(im); }
    if (it.k === 'v') { const d = document.createElement('span'); d.className = 'pm-dur'; d.textContent = phoneFmtDurMs(it.dur); b.appendChild(d); }
    const c = document.createElement('i'); c.className = 'pm-chk'; b.appendChild(c);
    g.appendChild(b);
  }
  if (m.more && !m.loading) { const mb = document.createElement('button'); mb.type = 'button'; mb.className = 'pm-more'; mb.dataset.more = '1'; mb.textContent = t('pmMore'); g.appendChild(mb); }
  }
  const text = m.loading && !m.items.length ? t('pmLoading') : (m.err ? t(m.err) : (!m.items.length && !m.loading ? t('pmEmpty') : ''));
  msg.hidden = !text; msg.textContent = text;
  const n = m.sel.size, gb = $('pmGet'), cb = $('pmCopy');
  gb.disabled = n === 0; gb.textContent = t('pmGet') + (n ? ' ' + n : '');
  cb.disabled = n === 0; cb.textContent = t('pmCopy') + (n ? ' ' + n : '');
}

function initPhoneMedia() {
  const box = $('phMedia'); if (!box) return;
  $('pmSeg').addEventListener('click', (e) => {
    const b = e.target.closest('button'); if (!b) return; e.stopPropagation();
    const m = phoneS.media; if (m.kind === b.dataset.k) return;
    m.kind = b.dataset.k; m.items = []; m.sel = new Set(); m.more = false; phoneMediaLoad(true);
  });
  $('pmGrid').addEventListener('click', (e) => {
    e.stopPropagation();
    const m = phoneS.media;
    if (e.target.closest('.pm-more')) { phoneMediaLoad(false); return; }
    const b = e.target.closest('.pm-it'); if (!b) return;
    const i = Number(b.dataset.i);
    if (m.sel.has(i)) m.sel.delete(i); else if (m.sel.size < 20) m.sel.add(i);
    renderPhone();
  });
  // '가져오기'는 받은 파일을 폴더에 두고, '복사'는 같은 길로 받은 뒤 그 파일들을 클립보드에 올린다(붙여넣기는 Ctrl+V)
  const pull = async (e, copy) => {
    e.stopPropagation();
    const m = phoneS.media, api = getApi();
    if (!api || !api.phone_media_pull || !m.sel.size) return;
    const items = Array.from(m.sel).sort((a, b) => a - b).map((i) => ({ id: m.items[i].id, k: m.items[i].k }));
    $('pmGet').disabled = true; $('pmCopy').disabled = true;
    let r = null;
    try { r = copy ? await api.phone_media_pull(items, true) : await api.phone_media_pull(items); } catch (err) { r = null; }
    if (r && r.ok) { showToast(t(copy ? 'pmCopying' : 'pmPulling', { n: r.started })); phoneMediaClose(); }
    else { showToast(t(r && r.error === 'perm' ? 'pmPerm' : (r && r.error === 'nolink' ? 'phoneFileNoLink' : 'pmFail'))); renderPhone(); }
  };
  $('pmGet').addEventListener('click', (e) => pull(e, false));
  $('pmCopy').addEventListener('click', (e) => pull(e, true));
}


// 폰에 새 사진·동영상이 생겼다
function phoneNewMediaIn(e) {
  if (store.settings.linkNewPhoto === false || !tabVisibleId('phone') || !Array.isArray(e.items) || !e.items.length) return;
  const old = phoneS.newMedia && Date.now() - phoneS.newMedia.t < 20000 ? phoneS.newMedia.items : [];
  const seen = new Set(), items = [];
  for (const it of e.items.concat(old)) { const k = it.k + it.id; if (!seen.has(k)) { seen.add(k); items.push(it); } }
  phoneS.newMedia = { items: items.slice(0, 20), t: Date.now() };
  const n = phoneS.newMedia.items.length;
  notify({ icon: 'image', tone: 'blue', ms: 5000, key: 'phonenewmedia', title: t('pmNewTitle'), sub: n === 1 ? phoneS.newMedia.items[0].name : t('pmNewSub', { n }) });
  playChime('todo');
}


// 사진·문자·전화 걸기 화면은 한 번에 하나만 열린다: 하나를 열 때 나머지를 닫는다(겹침 방지)
function phoneCloseOthers(keep) {
  if (keep !== 'media' && phoneS.media && phoneS.media.open) { phoneS.media.open = false; phoneS.media.items = []; phoneS.media.sel = new Set(); phoneS.media.seq++; phoneS.media.loading = false; }
  if (keep !== 'sms' && phoneS.sms && phoneS.sms.open) { phoneS.sms.open = false; phoneS.sms.seq++; }
  if (keep !== 'dial' && phoneS.dial) { phoneS.dial = false; phoneS.dialSeq++; const i = $('phDialIn'); if (i) { i.value = ''; i.blur(); } const l = $('phDialList'); if (l) l.textContent = ''; }
}

// 문자·폰 사진 화면이 열려 있는가
function phonePanelOpen() { return !!((phoneS.media && phoneS.media.open) || (phoneS.sms && phoneS.sms.open)); }

// 사진·문자 패널이 열리면 노치가 커진다(같은 크기)
function phonePanelSync() {
  const st = phoneS.st || {}, ok = st.state === 'ok' && !phoneCallVisible() && !phoneS.dial;
  const on = ok && !!((phoneS.media && phoneS.media.open) || (phoneS.sms && phoneS.sms.open));
  if (on !== (island.dataset.pmed === '1')) { island.dataset.pmed = on ? '1' : '0'; if (typeof scheduleRegion === 'function') scheduleRegion(); if (typeof updateView === 'function') updateView(); }
}

// ---------------------------------------------------------------- 문자: 대화 목록, 대화, 새 문자 보내기
phoneS.sms = { open: false, view: 'list', threads: [], tid: 0, addr: '', name: '', msgs: [], loading: false, err: '', isNew: false, seq: 0 };

function phoneSmsOpen() {
  phoneCloseOthers('sms');
  const m = phoneS.sms;
  Object.assign(m, { open: true, view: 'list', threads: [], err: '', isNew: false, msgs: [], tid: 0 });
  phoneSmsLoadThreads();
  renderPhone();
}
function phoneSmsClose() { const m = phoneS.sms; m.open = false; m.seq++; renderPhone(); }
function phoneSmsBack() {
  const m = phoneS.sms;
  if (m.view === 'chat') { m.view = 'list'; m.isNew = false; m.seq++; phoneSmsLoadThreads(); renderPhone(); } else phoneSmsClose();
}
function phoneSmsErr(r) { return r && r.error === 'perm' ? 'smPerm' : (r && r.error === 'nolink' ? 'phoneFileNoLink' : 'smFail'); }
async function phoneSmsLoadThreads() {
  const m = phoneS.sms, api = getApi();
  if (!api || !api.phone_sms_threads) return;
  const seq = ++m.seq; m.loading = true; m.err = ''; renderPhone();
  let r = null;
  try { r = await api.phone_sms_threads(); } catch (e) { r = null; }
  if (seq !== m.seq || !m.open) return;
  m.loading = false;
  if (r && r.ok) m.threads = r.threads || []; else m.err = phoneSmsErr(r);
  renderPhone();
}
async function phoneSmsOpenThread(tid, addr, name) {
  const m = phoneS.sms, api = getApi();
  Object.assign(m, { view: 'chat', tid, addr, name, msgs: [], isNew: false, err: '' });
  const seq = ++m.seq; m.loading = true; renderPhone();
  if (!api || !api.phone_sms_messages) return;
  let r = null;
  try { r = await api.phone_sms_messages(tid); } catch (e) { r = null; }
  if (seq !== m.seq || !m.open) return;
  m.loading = false;
  if (r && r.ok) { m.msgs = r.messages || []; if (r.addr) m.addr = r.addr; if (r.name) m.name = r.name; } else m.err = phoneSmsErr(r);
  renderPhone();
}
function phoneSmsNew() {
  const m = phoneS.sms;
  Object.assign(m, { view: 'chat', tid: 0, addr: '', name: '', msgs: [], isNew: true, err: '' });
  for (const id of ['smTo', 'smIn']) { const e = $(id); if (e) e.value = ''; }
  const sg = $('smSug'); if (sg) sg.textContent = '';
  const mm = $('smMsgs'); if (mm) mm._sig = undefined;
  m.seq++; renderPhone();
  setTimeout(() => { const i = $('smTo'); if (i) i.focus(); }, 50);
}
let smSugTimer = null;
async function phoneSmsSuggest() {
  const q = $('smTo').value.trim(), box = $('smSug'), api = getApi();
  box.textContent = '';
  if (!q || /^[+\d\s()-]+$/.test(q) || !api || !api.phone_contacts) return;          // 번호를 쓰는 중이면 연락처를 찾지 않는다
  let r = null;
  try { r = await api.phone_contacts(q); } catch (e) { r = null; }
  if (!phoneS.sms.open || phoneS.sms.view !== 'chat' || $('smTo').value.trim() !== q || !r || !r.ok) return;          // 그 사이에 패널을 닫았거나 다른 화면으로 갔다면 그리지 않는다
  for (const c of (r.items || []).slice(0, 4)) {
    const b = document.createElement('button'); b.type = 'button';
    const a = document.createElement('span'); a.textContent = c.name; const n = document.createElement('span'); n.textContent = c.number; n.style.color = 'var(--dim)';
    b.appendChild(a); b.appendChild(n);
    b.addEventListener('click', (e) => { e.stopPropagation(); $('smTo').value = c.number; phoneS.sms.name = c.name; box.textContent = ''; $('smIn').focus(); });
    box.appendChild(b);
  }
}
async function phoneSmsSend() {
  const m = phoneS.sms, api = getApi(), inp = $('smIn');
  const text = inp.value.trim();
  if (!api || !api.phone_sms_send || !text || m.sending) return;
  const to = m.isNew ? $('smTo').value.trim() : m.addr;
  if (!to) { showToast(t('smNoAddr')); return; }
  m.sending = true; $('smGo').disabled = true;
  let r = null;
  try { r = await api.phone_sms_send(to, text); } catch (e) { r = null; }
  m.sending = false; $('smGo').disabled = false;
  if (r && r.ok) {
    inp.value = '';
    m.msgs.push({ id: 0, out: true, body: text, t: Date.now() });
    if (m.isNew) { m.addr = to; m.isNew = false; }
    showToast(t('smSent'));
    renderPhone();
  } else {
    showToast(t(r && r.error === 'number' ? 'phoneBadNumber' : (r && r.error === 'perm' ? 'smPerm' : (r && r.error === 'nolink' ? 'phoneFileNoLink' : 'smSendFail'))));
  }
}

function phoneRenderSms() {
  const box = $('phSms'); if (!box) return;
  const m = phoneS.sms, st = phoneS.st || {};
  const on = m.open && st.state === 'ok' && !phoneCallVisible() && !phoneS.dial;
  box.hidden = !on;
  $('phoneLayer').classList.toggle('sms-on', on);
  phonePanelSync();
  if (on) $('phGrid').classList.add('xfer');          // 패널이 열려 있는 동안 타일은 숨긴다
  if (!on) { if (m.open && phoneS.st && st.state !== 'ok') m.open = false; return; }
  const list = $('smList'), chat = $('smChat'), msg = $('smMsg');
  list.hidden = m.view !== 'list'; chat.hidden = m.view !== 'chat';
  let text = '';
  if (m.view === 'list') {
    const lsig = JSON.stringify(m.threads.map((th) => [th.tid, th.name, th.addr, th.snip, th.out, th.unread])) + t('smNew');
    if (list._sig !== lsig) {
    list._sig = lsig;
    list.textContent = '';
    const nb = document.createElement('button'); nb.type = 'button'; nb.className = 'sm-row new'; nb.dataset.act = 'new';
    nb.innerHTML = ''; const w = document.createElement('span'); w.className = 'sm-who'; w.textContent = '+ ' + t('smNew'); nb.appendChild(w); list.appendChild(nb);
    for (const th of m.threads) {
      const b = document.createElement('button'); b.type = 'button'; b.className = 'sm-row'; b.dataset.tid = String(th.tid); b.dataset.addr = th.addr; b.dataset.name = th.name;
      const who = document.createElement('span'); who.className = 'sm-who'; who.textContent = th.name || th.addr; b.appendChild(who);
      const sn = document.createElement('span'); sn.className = 'sm-snip'; sn.textContent = (th.out ? t('smYou') + ': ' : '') + th.snip; b.appendChild(sn);
      if (th.unread > 0) { const d = document.createElement('i'); d.className = 'sm-dot'; b.appendChild(d); }
      list.appendChild(b);
    }
    }
    text = m.loading && !m.threads.length ? t('pmLoading') : (m.err ? t(m.err) : (!m.threads.length && !m.loading ? t('smEmpty') : ''));
  } else {
    $('smToRow').hidden = !m.isNew;
    const ms = $('smMsgs');
    const msig = JSON.stringify(m.msgs.map((x) => [x.out ? 1 : 0, x.body]));
    if (ms._sig !== msig) {
      const atEnd = ms._sig === undefined || ms.scrollHeight - ms.scrollTop - ms.clientHeight < 40;          // 위쪽을 읽고 있었다면 새 글이 와도 스크롤을 그대로 둔다
      const keep = ms.scrollTop;
      ms._sig = msig;
      ms.textContent = '';
      for (const x of m.msgs) { const d = document.createElement('div'); d.className = 'sm-b ' + (x.out ? 'out' : 'in'); d.textContent = x.body; ms.appendChild(d); }
      ms.scrollTop = atEnd ? ms.scrollHeight : keep;
    }
    text = m.loading && !m.msgs.length ? t('pmLoading') : (m.err ? t(m.err) : '');
  }
  msg.hidden = !text; msg.textContent = text;
}

function initPhoneSms() {
  if (!$('phSms')) return;
  $('smList').addEventListener('click', (e) => {
    e.stopPropagation();
    const b = e.target.closest('.sm-row'); if (!b) return;
    if (b.dataset.act === 'new') phoneSmsNew(); else phoneSmsOpenThread(Number(b.dataset.tid), b.dataset.addr || '', b.dataset.name || '');
  });
  $('smGo').addEventListener('click', (e) => { e.stopPropagation(); phoneSmsSend(); });
  $('smIn').addEventListener('keydown', (e) => { if (e.key === 'Enter' && !e.isComposing) { e.preventDefault(); phoneSmsSend(); } e.stopPropagation(); });
  $('smTo').addEventListener('keydown', (e) => { if (e.key === 'Enter' && !e.isComposing) { e.preventDefault(); $('smIn').focus(); } e.stopPropagation(); });
  $('smTo').addEventListener('input', () => { clearTimeout(smSugTimer); smSugTimer = setTimeout(phoneSmsSuggest, 300); });
}
