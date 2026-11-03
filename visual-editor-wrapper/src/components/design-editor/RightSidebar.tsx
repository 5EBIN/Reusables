'use client';

import { useState } from 'react';
import { ChevronDown } from 'lucide-react';
import type { DesignToken } from '@/_stubs';
import type { Component } from 'grapesjs';

interface Props {
  selectedComponent: Component | null | undefined;
  tokens: DesignToken;
  onTokensChange: (tokens: DesignToken) => void;
}

// ── StyleInspector: isolated sub-component so getStyle() is read at mount time ──
function StyleInspector({ component, open, onToggle }: { component: Component | null | undefined; open: boolean; onToggle: () => void }) {
  // getStyle() returns a plain object { 'font-size': '16px', ... }
  const styles = (component?.getStyle?.() ?? {}) as Record<string, string>;
  const sv = (prop: string) => styles[prop] ?? '';
  const set = (prop: string, val: string) => component?.setStyle?.({ [prop]: val });

  const inputStyle = { height: 28, background: '#1a1a1a', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 4, fontFamily: 'var(--mono)', fontSize: 12, color: 'rgba(255,255,255,0.9)', padding: '0 8px', width: '100%', outline: 'none' } as React.CSSProperties;
  const labelStyle = { fontSize: 11, color: 'rgba(255,255,255,0.3)', fontFamily: 'var(--sans)', marginBottom: 2 } as React.CSSProperties;

  // A render helper, not a component: a component declared here would be a new type on every render and remount its input.
  const field = (prop: string, placeholder: string) => (
    <div key={prop}>
      <div style={labelStyle}>{prop}</div>
      <input style={inputStyle} placeholder={placeholder} defaultValue={sv(prop)} onBlur={e => set(prop, e.target.value)} />
    </div>
  );

  return (
    <div>
      <SectionHeader title="Style" open={open} onToggle={onToggle} />
      {open && (
        <div className="p-3 space-y-3" style={{ background: '#161616' }}>
          <div>
            <div style={{ ...labelStyle, marginBottom: 6 }}>Typography</div>
            <div className="grid grid-cols-2 gap-1.5">
              {field('font-size', '16px')}
              {field('font-weight', '400')}
              {field('color', '#000')}
              {field('line-height', '1.5')}
              {field('letter-spacing', '0')}
              {field('text-align', 'left')}
            </div>
          </div>
          <div>
            <div style={{ ...labelStyle, marginBottom: 6 }}>Spacing</div>
            <div className="grid grid-cols-2 gap-1.5">
              {field('padding', '0')}
              {field('margin', '0')}
              {field('width', 'auto')}
              {field('height', 'auto')}
            </div>
          </div>
          <div>
            <div style={{ ...labelStyle, marginBottom: 6 }}>Appearance</div>
            <div className="grid grid-cols-2 gap-1.5">
              {field('background-color', '#fff')}
              {field('border-radius', '0')}
              {field('border', 'none')}
              {field('opacity', '1')}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

const S = {
  sidebar:  { width: 280, background: '#111111', borderLeft: '1px solid rgba(255,255,255,0.06)' },
  header:   { height: 32, borderBottom: '1px solid rgba(255,255,255,0.06)', cursor: 'pointer', userSelect: 'none' as const },
  input:    { height: 28, background: '#1a1a1a', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 4, fontFamily: 'var(--mono)', fontSize: 12, color: 'rgba(255,255,255,0.9)', padding: '0 8px', width: '100%', outline: 'none' },
  label:    { fontSize: 11, color: 'rgba(255,255,255,0.3)', fontFamily: 'var(--sans)', marginBottom: 4 },
  swatch:   { width: 20, height: 20, borderRadius: 4, border: '1px solid rgba(255,255,255,0.15)', cursor: 'pointer', flexShrink: 0 },
};

function SectionHeader({ title, open, onToggle }: { title: string; open: boolean; onToggle: () => void }) {
  return (
    <div className="flex items-center justify-between px-3 flex-shrink-0" style={S.header} onClick={onToggle}>
      <span className="text-[11px] uppercase tracking-[1.5px] font-medium" style={{ color: 'rgba(255,255,255,0.3)', fontFamily: 'var(--sans)' }}>
        {title}
      </span>
      <ChevronDown
        className="w-3 h-3 transition-transform duration-150"
        style={{ color: 'rgba(255,255,255,0.25)', transform: open ? 'rotate(0deg)' : 'rotate(-90deg)' }}
      />
    </div>
  );
}

const TAILWIND_SUGGESTIONS = {
  Layout:     ['flex', 'grid', 'block', 'hidden', 'flex-col', 'items-center', 'justify-between', 'justify-center', 'gap-4', 'gap-8', 'w-full', 'h-full', 'max-w-lg', 'max-w-4xl', 'mx-auto', 'overflow-hidden'],
  Spacing:    ['p-4', 'p-6', 'p-8', 'px-4', 'px-6', 'py-4', 'py-8', 'py-12', 'py-16', 'py-24', 'm-4', 'mt-4', 'mb-6', 'mb-8'],
  Typography: ['text-sm', 'text-base', 'text-lg', 'text-xl', 'text-2xl', 'text-4xl', 'font-medium', 'font-semibold', 'font-bold', 'font-extrabold', 'tracking-tight', 'leading-relaxed', 'text-center', 'uppercase'],
  Colors:     ['text-white', 'text-gray-400', 'text-gray-500', 'text-green-400', 'bg-gray-900', 'bg-gray-950', 'bg-green-600', 'border-gray-700', 'border-gray-800'],
  Effects:    ['rounded-lg', 'rounded-xl', 'rounded-2xl', 'shadow-lg', 'shadow-xl', 'opacity-80', 'transition-all', 'hover:opacity-90', 'border', 'overflow-hidden'],
};

export default function RightSidebar({ selectedComponent, tokens, onTokensChange }: Props) {
  const [openStyle,    setOpenStyle]    = useState(true);
  const [openTokens,   setOpenTokens]   = useState(false);
  const [openTailwind, setOpenTailwind] = useState(false);
  const [twSearch,     setTwSearch]     = useState('');
  const [appliedClasses, setAppliedClasses] = useState<string[]>([]);
  const [hidden,       setHidden]       = useState(false);

  const updateColor = (key: keyof DesignToken['colors'], value: string) => {
    const next = { ...tokens, colors: { ...tokens.colors, [key]: value } };
    onTokensChange(next);
  };

  const applyTailwindClass = (cls: string) => {
    if (!selectedComponent) return;
    const current: string = selectedComponent.getClasses?.().join(' ') ?? '';
    if (!current.includes(cls)) {
      selectedComponent.addClass?.(cls);
      setAppliedClasses(prev => [...prev.filter(c => c !== cls), cls]);
    }
  };

  const removeTailwindClass = (cls: string) => {
    selectedComponent?.removeClass?.(cls);
    setAppliedClasses(prev => prev.filter(c => c !== cls));
  };

  const allSuggestions = Object.values(TAILWIND_SUGGESTIONS).flat();
  const filtered = twSearch
    ? allSuggestions.filter(c => c.includes(twSearch.toLowerCase()))
    : allSuggestions;

  const TOKEN_SWATCHES = [
    { label: 'Primary',      key: 'primary',       val: '#1a6b47' },
    { label: 'Accent',       key: 'accent',        val: 'var(--accent)' },
    { label: 'Background',   key: 'background',    val: '#080808' },
    { label: 'Surface',      key: 'surface',       val: '#161616' },
    { label: 'Text',         key: 'text',          val: '#ffffff' },
    { label: 'Text dim',     key: 'textSecondary', val: 'rgba(255,255,255,0.5)' },
    { label: 'Gray 1',       key: 'border',        val: '#1e1e1e' },
  ] as const;

  if (hidden) {
    return (
      <button
        onClick={() => setHidden(false)}
        title="Show panel"
        className="flex-shrink-0 flex items-center justify-center transition-all"
        style={{
          width: 18, alignSelf: 'stretch',
          background: '#111111', borderLeft: '1px solid rgba(255,255,255,0.06)',
          color: 'rgba(255,255,255,0.25)', fontSize: 12, cursor: 'pointer',
        }}
        onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.color = 'var(--accent)'; }}
        onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.color = 'rgba(255,255,255,0.25)'; }}
      >
        ‹
      </button>
    );
  }

  return (
    <div className="flex flex-col flex-shrink-0 overflow-y-auto" style={{ ...S.sidebar, scrollbarWidth: 'none' }}>
      {/* Hide button */}
      <div className="flex justify-end px-2 pt-1.5 flex-shrink-0">
        <button
          onClick={() => setHidden(true)}
          title="Hide panel"
          style={{ color: 'rgba(255,255,255,0.2)', fontSize: 13, lineHeight: 1, cursor: 'pointer', padding: '2px 4px' }}
          onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.color = 'rgba(255,255,255,0.7)'; }}
          onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.color = 'rgba(255,255,255,0.2)'; }}
        >
          ✕
        </button>
      </div>

      {/* Empty state */}
      {!selectedComponent && (
        <div className="flex-1 flex items-center justify-center p-6">
          <p className="text-[12px] text-center" style={{ color: 'rgba(255,255,255,0.2)', fontFamily: 'var(--mono)', lineHeight: 1.6 }}>
            Select an element<br/>to inspect
          </p>
        </div>
      )}

      {/* ── STYLE section ── */}
      {selectedComponent && (
        <StyleInspector
          key={selectedComponent.getId?.() ?? 'component'}
          component={selectedComponent}
          open={openStyle}
          onToggle={() => setOpenStyle(o => !o)}
        />
      )}

      {/* ── DESIGN TOKENS section ── */}
      <div>
        <SectionHeader title="Design Tokens" open={openTokens} onToggle={() => setOpenTokens(!openTokens)} />
        {openTokens && (
          <div className="p-3 space-y-2" style={{ background: '#161616' }}>
            {TOKEN_SWATCHES.map(({ label, key, val }) => (
              <div key={key} className="flex items-center gap-2">
                <input
                  type="color"
                  defaultValue={tokens.colors[key] ?? val}
                  onChange={e => updateColor(key, e.target.value)}
                  style={S.swatch as React.CSSProperties}
                />
                <div className="flex-1 min-w-0">
                  <p style={{ ...S.label, marginBottom: 0 }}>{label}</p>
                  <p style={{ ...S.label, marginBottom: 0, fontFamily: 'var(--mono)', fontSize: 10 }}>
                    {tokens.colors[key] ?? val}
                  </p>
                </div>
              </div>
            ))}
            <div className="pt-1">
              <p style={S.label}>Border Radius</p>
              <input
                style={S.input}
                value={tokens.borderRadius}
                onChange={e => onTokensChange({ ...tokens, borderRadius: e.target.value })}
              />
            </div>
          </div>
        )}
      </div>

      {/* ── TAILWIND section ── */}
      <div>
        <SectionHeader title="Tailwind" open={openTailwind} onToggle={() => setOpenTailwind(!openTailwind)} />
        {openTailwind && (
          <div className="p-3 space-y-2" style={{ background: '#161616' }}>
            <input
              value={twSearch}
              onChange={e => setTwSearch(e.target.value)}
              placeholder="Search classes..."
              style={S.input}
            />
            {appliedClasses.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {appliedClasses.map(cls => (
                  <span
                    key={cls}
                    className="flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] cursor-pointer"
                    style={{ background: 'color-mix(in srgb, var(--accent) 15%, transparent)', color: 'var(--accent)', fontFamily: 'var(--mono)', border: '1px solid color-mix(in srgb, var(--accent) 20%, transparent)' }}
                    onClick={() => removeTailwindClass(cls)}
                    title="Click to remove"
                  >
                    {cls} <span style={{ opacity: 0.6 }}>×</span>
                  </span>
                ))}
              </div>
            )}
            <div className="flex flex-wrap gap-1 max-h-48 overflow-y-auto" style={{ scrollbarWidth: 'none' }}>
              {filtered.slice(0, 60).map(cls => (
                <button
                  key={cls}
                  onClick={() => applyTailwindClass(cls)}
                  className="px-1.5 py-0.5 rounded text-[10px] transition-all"
                  style={{ background: '#1e1e1e', color: 'rgba(255,255,255,0.5)', fontFamily: 'var(--mono)', border: '1px solid rgba(255,255,255,0.06)' }}
                  onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.borderColor = 'color-mix(in srgb, var(--accent) 30%, transparent)'; (e.currentTarget as HTMLButtonElement).style.color = 'var(--accent)'; }}
                  onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.borderColor = 'rgba(255,255,255,0.06)'; (e.currentTarget as HTMLButtonElement).style.color = 'rgba(255,255,255,0.5)'; }}
                >
                  {cls}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
