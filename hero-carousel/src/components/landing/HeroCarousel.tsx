'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { Pause, Play } from 'lucide-react';
import { SLIDES } from './slides';

const HOLD = 1500;        // ms a finished slide stays before the next one slides in

type Engine = { i: number; el: number; hover: boolean; focus: boolean; user: boolean; offscreen: boolean };

/**
 * The hero window with three auto-playing slides. The server renders slide A finished (and so does a browser without JS or with reduced motion); on mount the engine, unless reduced motion is
 * asked for, resets the blocks and replays them on a timer. It pauses on hover, on keyboard focus, while the tab is hidden, while the window is off-screen, and from the pause button.
 * Time is kept in a ref and blocks are switched by class, so a frame costs no React render.
 */
export default function HeroCarousel() {
  const root = useRef<HTMLDivElement>(null);
  const eng = useRef<Engine>({ i: 0, el: 0, hover: false, focus: false, user: false, offscreen: false });
  const [index, setIndex] = useState(0);
  const [reduce, setReduce] = useState(false);
  const [userPaused, setUserPaused] = useState(false);

  /** Show slide i from its start, or finished when `finished` (reduced motion). */
  const show = useCallback((i: number, finished: boolean) => {
    const r = root.current;
    if (!r) return;
    eng.current.i = i;
    eng.current.el = 0;
    r.querySelectorAll<HTMLElement>('.slide').forEach((s, j) => {
      s.classList.toggle('act', j === i);
      s.querySelectorAll('.b').forEach((b) => b.classList.toggle('on', finished));
      s.querySelectorAll('.node').forEach((n) => n.classList.toggle('on', finished));
      s.querySelectorAll<HTMLElement>('[data-clr]').forEach((b) => { b.style.opacity = finished ? '0.4' : ''; });
      const count = s.querySelector('[data-cnt]');
      if (count) count.textContent = finished ? '0' : '3';
    });
    r.querySelectorAll<HTMLElement>('.prog button b').forEach((bar, j) => { bar.style.width = finished && j === i ? '100%' : '0'; });
    setIndex(i);
  }, []);

  useEffect(() => {
    const r = root.current;
    if (!r) return;
    const still = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    setReduce(still);
    show(0, still);
    if (still) return;

    const e = eng.current;
    const slides = [...r.querySelectorAll<HTMLElement>('.slide')];
    const bars = [...r.querySelectorAll<HTMLElement>('.prog button b')];
    const on = (name: keyof Engine, v: boolean) => () => { (e[name] as boolean) = v; };
    const enter = on('hover', true), leave = on('hover', false);
    const focusIn = (ev: FocusEvent) => { if ((ev.target as HTMLElement).matches(':focus-visible')) e.focus = true; };   // a mouse click on a segment must not freeze the show
    const focusOut = on('focus', false);
    r.addEventListener('mouseenter', enter); r.addEventListener('mouseleave', leave);
    r.addEventListener('focusin', focusIn); r.addEventListener('focusout', focusOut);
    const seen = new IntersectionObserver(([entry]) => { e.offscreen = !entry.isIntersecting; }, { threshold: 0.2 });
    seen.observe(r);

    let last = performance.now();
    let raf = 0;
    const tick = (now: number) => {
      const dt = Math.min(now - last, 100);          // a background tab must not make the show jump
      last = now;
      if (!(e.hover || e.focus || e.user || e.offscreen || document.hidden)) {
        e.el += dt;
        const s = slides[e.i];
        s.querySelectorAll<HTMLElement>('.b[data-at]').forEach((b) => { if (e.el >= Number(b.dataset.at)) b.classList.add('on'); });
        s.querySelectorAll<HTMLElement>('.node').forEach((n) => { if (e.el >= Number(n.dataset.on)) n.classList.add('on'); });
        let cleared = 0;
        s.querySelectorAll<HTMLElement>('[data-clr]').forEach((b) => { if (e.el >= Number(b.dataset.clr)) { b.style.opacity = '0.4'; cleared += 1; } else { b.style.opacity = ''; } });
        const count = s.querySelector('[data-cnt]');
        if (count) count.textContent = String(3 - cleared);
        const total = SLIDES[e.i].duration + HOLD;
        bars[e.i].style.width = `${Math.min(100, (e.el / total) * 100)}%`;
        if (e.el > total) show((e.i + 1) % SLIDES.length, false);
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => {
      cancelAnimationFrame(raf);
      seen.disconnect();
      r.removeEventListener('mouseenter', enter); r.removeEventListener('mouseleave', leave);
      r.removeEventListener('focusin', focusIn); r.removeEventListener('focusout', focusOut);
    };
  }, [show]);

  const toggle = () => { eng.current.user = !eng.current.user; setUserPaused(eng.current.user); };

  return (
    <div className="window" id="car" ref={root} role="group" aria-roledescription="carousel" aria-label="How Platform works">
      <div className="wbar">
        <b /><b /><b />
        <span className="spc" />
        <span>{SLIDES[index].title}</span>
        <span className="spc" />
        {!reduce && (
          <button type="button" className="btn quiet icon sm" onClick={toggle} aria-label={userPaused ? 'Play the demo' : 'Pause the demo'}>
            {userPaused ? <Play className="i" aria-hidden="true" /> : <Pause className="i" aria-hidden="true" />}
          </button>
        )}
      </div>
      <div className="slides">
        {SLIDES.map((s, i) => (
          <div key={s.title} className={`slide${i === 0 ? ' act' : ''}`} role="group" aria-roledescription="slide" aria-label={`Slide ${i + 1} of ${SLIDES.length}`}>
            <h3>{s.title}</h3>
            {s.body}
          </div>
        ))}
      </div>
      <div className="prog">
        {SLIDES.map((s, i) => (
          <button key={s.title} type="button" aria-current={i === index} aria-label={`Slide ${i + 1} of ${SLIDES.length}: ${s.title}`} onClick={() => show(i, reduce)}>
            <i><b style={i === 0 ? { width: '100%' } : undefined} /></i>
            {s.title}
          </button>
        ))}
      </div>
      <div className="sr" aria-live={reduce || userPaused ? 'polite' : 'off'}>{SLIDES[index].title}</div>
    </div>
  );
}
