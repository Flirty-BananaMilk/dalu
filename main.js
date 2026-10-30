// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
// Copyright (c) 2026 Flirty_BananaMilk — 상업적 이용 금지, 자세한 내용은 LICENSE
// ========================================================
// 시작 및 전역 입력 연결 (호버/드래그/휠/버튼/컨텍스트 메뉴)
// ========================================================

const INTERACTIVE = '.btn-ctrl, .prog-hit, .btn-pin, .dots, .pill, .stepper, .sw, input, .shcard, .trow, .chart';

function bindAll(sel, handler) {
  for (const el of $$(sel)) el.addEventListener('click', (e) => { e.stopPropagation(); handler(e); });
}

function bindInput() {
  island.addEventListener('mouseenter', onIslandEnter);
  island.addEventListener('mouseleave', onIslandLeave);

  // 페이지 전환: 도트 클릭 / 마우스 휠
  $('pageDots').addEventListener('click', (e) => {
    const dot = e.target.closest('i');
    if (!dot) return;
    e.stopPropagation();
    setPage(dot.dataset.p);
  });
  // 휠/트랙패드는 '이벤트 하나'가 아니라 '제스처 하나'에 페이지를 한 번만 넘긴다.
  // 트랙패드 관성 스크롤은 1초 넘게 이벤트가 이어지므로, 고정 시간 잠금(380ms)을 쓰면 한 번 쓸 때 페이지가 여러 번
  // 연달아 넘어가고 그때마다 애니메이션이 중간에 끊겨 다시 시작된다(실측: 한 번 쓸면 9번).
  // 이벤트가 WHEEL_GESTURE_GAP 이상 끊기면 제스처가 끝난 것으로 본다. 일반 휠의 '칸'들은 보통 그보다 간격이 길어 각각 한 번씩 넘어간다.
  const WHEEL_GESTURE_GAP = 170;     // ms
  const WHEEL_THRESHOLD = 50;        // 누적 deltaY 가 이 값을 넘어야 넘긴다 (손가락이 살짝 스친 정도는 무시)
  const WHEEL_MIN_INTERVAL = 350;    // ms: 연달아 넘길 때 애니메이션이 겹치지 않게
  let wheelAcc = 0, wheelFired = false, wheelIdleTimer = null, wheelLastFire = 0;
  island.addEventListener('wheel', (e) => {
    if (e.ctrlKey) {                 // Ctrl+휠: 마스터 볼륨 (접힌 상태에서도)
      e.preventDefault();
      if (e.deltaY) volWheel(e.deltaY < 0 ? 1 : -1);
      return;
    }
    if (!isExpanded) return;
    // 스크롤 가능한 목록 위에서는 페이지를 넘기지 않는다 (할 일 목록, 선반 카드)
    const sc = e.target.closest('.tlist, .shcards, .lyr.static, .pchips, .pgrid, .lgrid');
    if (sc && (sc.scrollHeight > sc.clientHeight || sc.scrollWidth > sc.clientWidth)) return;
    clearTimeout(wheelIdleTimer);
    wheelIdleTimer = setTimeout(() => { wheelAcc = 0; wheelFired = false; }, WHEEL_GESTURE_GAP);   // 제스처 종료
    if (wheelFired) return;                     // 이 제스처에서는 이미 넘겼다 (관성 꼬리는 무시)
    // 방향이 바뀌면 누적을 새로 시작한다
    if (wheelAcc !== 0 && Math.sign(e.deltaY) !== Math.sign(wheelAcc)) wheelAcc = 0;
    wheelAcc += e.deltaY;
    if (Math.abs(wheelAcc) < WHEEL_THRESHOLD) return;
    const now = performance.now();
    if (now - wheelLastFire < WHEEL_MIN_INTERVAL) { wheelAcc = 0; return; }
    wheelFired = true;
    wheelLastFire = now;
    stepPage(wheelAcc > 0 ? 1 : -1);
    wheelAcc = 0;
  }, { passive: false });     // Ctrl+휠에서 브라우저 확대를 막으려면 preventDefault 가 필요하다

  btnPin.addEventListener('click', (e) => { e.stopPropagation(); togglePin(); });

  // Double Click toggles Pin
  island.addEventListener('dblclick', (e) => {
    if (e.target.closest(INTERACTIVE) || e.target.closest('.lyr') || e.target.closest('.tlist')) return;
    togglePin();
  });

  // 노치는 움직이지 않는다(위치는 모니터 위쪽 가운데로 고정). 끌어서 조절하는 것은 재생바뿐이다.

  // Media Playback Controls (music / lyrics 두 페이지에 같은 버튼이 있다)
  bindAll('.js-toggle', () => mediaAct('toggle'));
  bindAll('.js-prev', () => mediaAct('prev'));
  bindAll('.js-next', () => mediaAct('next'));
  bindAll('.js-lyr-toggle', toggleLyrics);
  bindAll('.js-shuffle', toggleShuffle);
  bindAll('.js-repeat', cycleRepeat);
  // 재생바: 누른 채로 끌면 미리보기(바와 시간)가 따라 움직이고, 놓는 순간 그 위치로 이동한다. 한 번 눌러도 그 위치로 이동한다.
  for (const el of $$('.js-seek')) {
    el.addEventListener('click', (e) => e.stopPropagation());   // 끌기가 끝난 뒤의 click 이 노치의 다른 동작(접기 등)으로 번지지 않게
    const ratioOf = (e) => {
      const rect = el.getBoundingClientRect();
      return Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    };
    el.addEventListener('pointerdown', (e) => {
      if (e.button !== 0 || !(state.duration > 0)) return;
      e.preventDefault();
      scrub.active = true;
      scrub.ratio = ratioOf(e);
      el.classList.add('scrubbing');
      try { el.setPointerCapture(e.pointerId); } catch (_) { /* 캡처를 못 해도 창 안에서는 동작한다 */ }
      paintScrub();
    });
    el.addEventListener('pointermove', (e) => {
      if (!scrub.active) return;
      scrub.ratio = ratioOf(e);
      paintScrub();
    });
    const end = (e, commit) => {
      if (!scrub.active) return;
      scrub.active = false;
      el.classList.remove('scrubbing');
      try { el.releasePointerCapture(e.pointerId); } catch (_) { /* 이미 풀림 */ }
      if (commit) seekTo(scrub.ratio * state.duration);
    };
    el.addEventListener('pointerup', (e) => end(e, true));
    el.addEventListener('pointercancel', (e) => end(e, false));
    el.addEventListener('lostpointercapture', (e) => end(e, false));
  }

  // 컨텍스트 메뉴
  window.addEventListener('contextmenu', openContextMenu);
  window.addEventListener('click', (e) => {
    if (!e.target.closest('#contextMenu')) closeContextMenu();
  });
  // 창 밖을 클릭하거나 Esc 를 눌러도 메뉴가 열린 채 남지 않도록
  window.addEventListener('blur', closeContextMenu);
  window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeContextMenu();
  });

  $('menuPin').addEventListener('click', () => { closeContextMenu(); togglePin(); });
  $('menuLyrics').addEventListener('click', () => { closeContextMenu(); toggleLyrics(); });
  $('menuSound').addEventListener('click', () => { closeContextMenu(); toggleSound(); });
  $('menuLang').addEventListener('click', () => { closeContextMenu(); toggleLang(); });
  $('menuCompact').addEventListener('click', () => {
    compactMode = !compactMode;   // 크기 계산이 compactMode 를 읽으므로 먼저 토글
    store.settings.compact = compactMode;
    saveStoreSoon();
    island.classList.toggle('compact', compactMode);
    miniIdx = -1;
    closeContextMenu();
    scheduleRegion();
  });
  let clickThroughActive = false;
  $('menuClickThrough').addEventListener('click', () => {
    closeContextMenu();
    clickThroughActive = !clickThroughActive;
    const api = getApi();
    if (api) {
      api.toggle_click_through(clickThroughActive);
      showToast(t(clickThroughActive ? 'ctOn' : 'ctOff'));
    }
  });
  window.__setClickThrough = (v) => { clickThroughActive = v; };
  $('menuSettings').addEventListener('click', () => {
    closeContextMenu();
    const api = getApi();
    if (api && api.open_settings) api.open_settings();
  });
  $('menuExit').addEventListener('click', () => {
    const api = getApi();
    if (api) api.close_app();
  });
}

// Python 쪽 감시 스레드가 Ctrl+호버로 클릭 투과를 해제했을 때 호출됨
function onClickThroughReleased() {
  if (window.__setClickThrough) window.__setClickThrough(false);
  showToast(t('ctOff'));
}

// pywebview 브리지가 준비될 때까지 잠깐 기다린다 (저장된 설정을 읽어야 하므로)
function waitForApi(ms) {
  return new Promise((resolve) => {
    const t0 = performance.now();
    (function check() {
      const api = getApi();
      if ((api && api.load_data) || performance.now() - t0 > ms) resolve();      // api 객체만 먼저 생기고 메서드가 아직 없을 수 있다
      else setTimeout(check, 40);
    })();
  });
}

async function startApp() {
  for (const el of $$('.ic-chat')) el.innerHTML = `<path d="${ICONS.chat}"/>`;

  await waitForApi(3000);
  await loadStore();
  lang = normLang(store.settings.lang);
  compactMode = !!store.settings.compact;
  island.classList.toggle('compact', compactMode);
  applyPrefs();

  bindInput();
  initFeatures();
  initFeatures2();
  if (typeof initSatellite === 'function') initSatellite();
  applyLang();

  updateClock();
  setInterval(updateClock, 1000);
  updateView();
  pollState();
  requestAnimationFrame(animationFrame);

  // 초기 클릭 영역 (pywebview 브리지가 준비되면 한 번만)
  let initialRegionApplied = false;
  const applyInitialRegion = () => {
    if (initialRegionApplied) return;
    const api = getApi();
    if (api && api.collapse_window) {
      initialRegionApplied = true;
      scheduleRegion(true);
    } else {
      setTimeout(applyInitialRegion, 60);
    }
  };
  window.addEventListener('pywebviewready', applyInitialRegion);
  applyInitialRegion();

  // 창 크기가 바뀌면(시작 직후 크기 보정, 재배치, DPI 변경) 노치 위치가 달라지므로 클릭 영역을 다시 맞춘다
  window.addEventListener('resize', () => {
    if (initialRegionApplied) scheduleRegion(true);
  });
}

startApp();
