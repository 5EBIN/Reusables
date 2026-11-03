'use client';

import { useState } from 'react';
import { Undo2, Redo2, Eye, EyeOff, Monitor, Tablet, Smartphone, Check, Wand2 } from 'lucide-react';

type Viewport = 'desktop' | 'tablet' | 'mobile';

interface Props {
  pageName: string;
  viewport: Viewport;
  onViewportChange: (v: Viewport) => void;
  onUndo: () => void;
  onRedo: () => void;
  onFinalize: () => void;
  onPreviewToggle: () => void;
  previewing: boolean;
  onGenerate: () => void;
  isGenerating: boolean;
}

const VIEWPORTS: { id: Viewport; icon: React.ReactNode; label: string }[] = [
  { id: 'desktop', icon: <Monitor className="w-3.5 h-3.5" />, label: 'Desktop' },
  { id: 'tablet',  icon: <Tablet  className="w-3.5 h-3.5" />, label: 'Tablet'  },
  { id: 'mobile',  icon: <Smartphone className="w-3.5 h-3.5" />, label: 'Mobile' },
];

export default function TopToolbar({
  pageName, viewport, onViewportChange, onUndo, onRedo,
  onFinalize, onPreviewToggle, previewing, onGenerate, isGenerating,
}: Props) {
  const [editing, setEditing] = useState(false);
  const [nameVal, setNameVal] = useState(pageName);

  const iconBtn = 'flex items-center justify-center w-8 h-8 rounded-lg transition-all duration-100 text-[rgba(255,255,255,0.4)] hover:text-white hover:bg-[#1e1e1e] active:scale-95';
  const divider = <div className="w-px h-5 mx-1" style={{ background: 'rgba(255,255,255,0.06)' }} />;

  return (
    <div
      className="flex items-center justify-between px-4 flex-shrink-0"
      style={{
        height: 48,
        background: '#111111',
        borderBottom: '1px solid rgba(255,255,255,0.06)',
        fontFamily: 'var(--sans)',
      }}
    >
      {/* Left: Logo + page name */}
      <div className="flex items-center gap-3 min-w-0">
        <div className="flex items-center gap-1 flex-shrink-0">
          <span style={{ color: 'white', fontSize: 14, fontWeight: 700 }}>Platform</span>
          <span style={{ color: 'var(--accent)', fontSize: 14, fontWeight: 700 }}>AI</span>
        </div>
        <div className="w-px h-4" style={{ background: 'rgba(255,255,255,0.1)' }} />
        {editing ? (
          <input
            autoFocus
            value={nameVal}
            onChange={e => setNameVal(e.target.value)}
            onBlur={() => setEditing(false)}
            onKeyDown={e => e.key === 'Enter' && setEditing(false)}
            className="bg-transparent border-none outline-none text-white text-[13px] font-medium min-w-0"
            style={{ fontFamily: 'var(--mono)', width: Math.max(nameVal.length * 8, 80) }}
          />
        ) : (
          <span
            className="text-[13px] font-medium cursor-text truncate"
            style={{ fontFamily: 'var(--mono)', color: 'rgba(255,255,255,0.7)' }}
            onClick={() => setEditing(true)}
          >
            {nameVal}
          </span>
        )}
      </div>

      {/* Center: Viewport switcher */}
      <div className="flex items-center gap-0.5 p-1 rounded-lg" style={{ background: '#1a1a1a', border: '1px solid rgba(255,255,255,0.06)' }}>
        {VIEWPORTS.map(vp => (
          <button
            key={vp.id}
            onClick={() => onViewportChange(vp.id)}
            title={vp.label}
            className="flex items-center gap-1.5 px-3 h-[26px] rounded-md text-[12px] font-medium transition-all duration-100"
            style={{
              background: viewport === vp.id ? 'var(--accent)' : 'transparent',
              color:      viewport === vp.id ? '#fff'    : 'rgba(255,255,255,0.4)',
              fontFamily: 'var(--sans)',
            }}
          >
            {vp.icon}
            <span>{vp.label}</span>
          </button>
        ))}
      </div>

      {/* Right: Actions */}
      <div className="flex items-center gap-1">
        <button
          onClick={onGenerate}
          disabled={isGenerating}
          className="flex items-center gap-1.5 px-3 h-[30px] rounded-lg text-[12px] font-medium transition-all duration-150 disabled:opacity-50"
          style={{ fontFamily: 'var(--sans)', background: 'color-mix(in srgb, var(--accent) 12%, transparent)', color: 'var(--accent)', border: '1px solid color-mix(in srgb, var(--accent) 20%, transparent)' }}
        >
          <Wand2 className="w-3.5 h-3.5" />
          {isGenerating ? 'Generating…' : 'AI Generate'}
        </button>
        {divider}
        <button onClick={onUndo}  className={iconBtn} title="Undo"><Undo2 className="w-4 h-4" /></button>
        <button onClick={onRedo}  className={iconBtn} title="Redo"><Redo2 className="w-4 h-4" /></button>
        {divider}
        <button
          onClick={onPreviewToggle}
          className={iconBtn}
          title={previewing ? 'Exit preview' : 'Preview'}
          style={{ color: previewing ? 'var(--accent)' : undefined }}
        >
          {previewing ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
        </button>
        {divider}
        <button
          onClick={onFinalize}
          className="flex items-center gap-1.5 px-4 h-[36px] rounded-lg text-[13px] font-semibold text-white transition-all duration-150 active:scale-[0.98]"
          style={{
            background: 'var(--accent)',
            boxShadow: '0 0 12px color-mix(in srgb, var(--accent) 25%, transparent)',
          }}
          onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.background = '#25a563'; (e.currentTarget as HTMLButtonElement).style.transform = 'scale(1.01)'; }}
          onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.background = 'var(--accent)'; (e.currentTarget as HTMLButtonElement).style.transform = ''; }}
        >
          <Check className="w-3.5 h-3.5" />
          Finalize Design
        </button>
      </div>
    </div>
  );
}
