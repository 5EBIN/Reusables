import type { ReactNode } from 'react';
import { Check } from 'lucide-react';
import { Status } from './Status';

/**
 * The slides of the hero carousel. Every `.b` block carries data-at (ms from the start of its slide, when it appears); the engine in HeroCarousel adds `.on` to it at that time.
 * Everything starts with `.on`, so the server-rendered page, a browser without JS and reduced motion all show the finished frame. The sample data is invented.
 */
export type Slide = { title: string; duration: number; body: ReactNode };

const STEPS = [
  ['Request', 'REQ-1'],
  ['Review', 'REV-2'],
  ['Build', 'v3'],
  ['Check', '2 checks'],
  ['Release', 'A. Example'],
];

export const SLIDES: Slide[] = [
  {
    title: 'One request, end to end',
    duration: 8000,
    body: (
      <>
        <div className="b on t3 xs" data-at="0">Example Workspace</div>
        <div className="b on card pad" data-at="300">
          <div style={{ fontWeight: 600 }}>A user can export their own report.</div>
          <div className="t2 sm">Checks: access, logging</div>
        </div>
        <div className="b on col gap4" data-at="1800">
          <div className="row sm"><Status kind="pass" /><span className="mono">CHK-01</span><span className="t2">Export is logged</span></div>
          <div className="row sm"><Status kind="pass" /><span className="mono">CHK-02</span><span className="t2">Owner only</span></div>
          <div className="row sm"><Status kind="neutral" /><span className="mono">CHK-03</span><span className="t2">Not applicable here</span></div>
        </div>
        <div className="b on notice pass" data-at="4500"><Check className="i" aria-hidden="true" /><span>Approved by A. Example.</span></div>
      </>
    ),
  },
  {
    title: 'Every step is recorded',
    duration: 6000,
    body: (
      <>
        <div className="b on t3 xs" data-at="0">History</div>
        <div className="b on chain" data-at="150">
          {STEPS.map(([k, v], i) => (
            <div key={k} className="node on" data-on={600 + i * 700}>
              <div className="k">{k}</div>
              <div className="sm">{v}</div>
            </div>
          ))}
        </div>
        <div className="b on t2 sm" data-at="4300">Each step has a time and an actor.</div>
      </>
    ),
  },
];
