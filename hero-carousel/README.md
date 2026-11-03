# hero-carousel

**Category:** landing  
**Origin:** extracted from a production Next.js/FastAPI app.

## What it does
A timed slide carousel: blocks appear at `data-at` times, pause on hover/focus/offscreen, reduced-motion shows the finished frame. Invented example slides.

## Problem it solved
Marketing animations that stay accessible.

## Public interface
* `components/landing/HeroCarousel.tsx`: `function HeroCarousel()`
* `components/landing/Status.tsx`: `type StatusKind`
* `components/landing/Status.tsx`: `function Status(`
* `components/landing/slides.tsx`: `type Slide`
* `components/landing/slides.tsx`: `const SLIDES: Slide[]`

## Dependencies
JavaScript (`deps.json`): `lucide-react`, `react`

## Stubs and what the host must provide
No stubs: every import resolves inside the module.

## Known limits
Slides are examples; write your own markup with the same classes.

## Quality
B  
Tests copied: 0 (copied from the source, not run here).

## How to reuse
Edit `slides.tsx`.
