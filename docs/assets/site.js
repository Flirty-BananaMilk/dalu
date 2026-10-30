/* Dalu site: draws the app's own animation frames in step with the scroll. Without this file the page still shows every scene in its final state. */
(() => {
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const pinned = CSS.supports('animation-timeline: view()');
  if (reduce || !pinned) return;
  const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
  const seqs = [];
  document.querySelectorAll('canvas[data-seq]').forEach((cv) => {
    const track = cv.closest('.track');
    if (!track) return;
    const n = +cv.dataset.n, from = +cv.dataset.from, to = +cv.dataset.to;
    const frames = new Array(n);
    const ctx = cv.getContext('2d');
    const stills = cv.parentElement.querySelectorAll('.seq__still, .seq__first');
    let drawn = -1, started = false;
    const pad = (i) => String(i).padStart(2, '0');
    const get = (i) => frames[i] || (frames[i] = Object.assign(new Image(), { src: `${cv.dataset.src}/${cv.dataset.seq}-${pad(i)}.webp`, decoding: 'async' }));
    const draw = (i) => {
      // the nearest loaded frame at or before i, so a slow connection never shows a blank notch
      for (let k = i; k >= 0; k--) { const im = get(k); if (im.complete && im.naturalWidth) { if (drawn !== k) { ctx.clearRect(0, 0, cv.width, cv.height); ctx.drawImage(im, 0, 0, cv.width, cv.height); drawn = k; } return true; } }
      return false;
    };
    const start = () => {
      if (started) return; started = true;
      for (let i = 0; i < n; i++) get(i);
      const first = get(0); const show = () => { cv.hidden = false; stills.forEach((s) => { s.hidden = true; }); update(); };
      if (first.complete && first.naturalWidth) show(); else first.addEventListener('load', show, { once: true });
    };
    const update = () => {
      const r = track.getBoundingClientRect();
      const span = r.height - innerHeight;
      if (span <= 0) return;
      const p = clamp(-r.top / span, 0, 1);
      const f = clamp((p - from) / (to - from), 0, 1);
      draw(Math.round(f * (n - 1)));
    };
    new IntersectionObserver((es) => { if (es.some((e) => e.isIntersecting)) start(); }, { rootMargin: '150% 0px' }).observe(track);
    seqs.push(update);
  });
  if (!seqs.length) return;
  let ticking = false;
  const onScroll = () => { if (ticking) return; ticking = true; requestAnimationFrame(() => { ticking = false; seqs.forEach((u) => u()); }); };
  addEventListener('scroll', onScroll, { passive: true });
  addEventListener('resize', onScroll, { passive: true });
})();
