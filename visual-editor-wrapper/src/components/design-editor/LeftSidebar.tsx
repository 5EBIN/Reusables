'use client';

import { useState } from 'react';
import { FileText, Layers, Layout, Image as ImageIcon, Plus, Trash2 } from 'lucide-react';
import type { PageDesign } from '@/_stubs';
import { BLOCKS, CATEGORIES } from './blockDefs';

type PanelId = 'pages' | 'layers' | 'blocks' | 'assets';

interface Props {
  pages: PageDesign[];
  activePage: string;
  onPageSelect: (id: string) => void;
  onPageAdd: () => void;
  onPageRemove: (id: string) => void;
  editor?: unknown;
}

const ICONS: { id: PanelId; icon: React.ReactNode; label: string }[] = [
  { id: 'pages',  icon: <FileText className="w-4 h-4" />, label: 'Pages'  },
  { id: 'layers', icon: <Layers   className="w-4 h-4" />, label: 'Layers' },
  { id: 'blocks', icon: <Layout   className="w-4 h-4" />, label: 'Blocks' },
  { id: 'assets', icon: <ImageIcon className="w-4 h-4" />, label: 'Assets' },
];

const S = {
  panel:   { background: '#111111', borderRight: '1px solid rgba(255,255,255,0.06)' },
  section: { background: '#161616' },
  header:  { height: 32, borderBottom: '1px solid rgba(255,255,255,0.06)', fontFamily: 'var(--sans)' },
  input:   { height: 28, background: '#1a1a1a', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 4, fontFamily: 'var(--mono)', fontSize: 12, color: 'rgba(255,255,255,0.9)' },
};

export default function LeftSidebar({ pages, activePage, onPageSelect, onPageAdd, onPageRemove }: Props) {
  const [panel, setPanel]     = useState<PanelId>('blocks');
  const [hidden, setHidden] = useState(false);
  const [blockSearch, setBlockSearch] = useState('');
  const [activeCategory, setActiveCategory] = useState<string>('All');

  const iconBtn = (active: boolean) => ({
    width: 40, height: 40, display: 'flex', alignItems: 'center', justifyContent: 'center',
    cursor: 'pointer', transition: 'all 100ms ease', borderRadius: 8, margin: '2px auto',
    background: active ? 'color-mix(in srgb, var(--accent) 10%, transparent)' : 'transparent',
    color:      active ? 'var(--accent)' : 'rgba(255,255,255,0.4)',
  });

  const handleAddBlock = () => {
    // Click-to-add not supported in iframe mode — use drag-and-drop instead
  };

  const filteredBlocks = BLOCKS.filter(b => {
    const matchCat  = activeCategory === 'All' || b.category === activeCategory;
    const matchText = b.label.toLowerCase().includes(blockSearch.toLowerCase());
    return matchCat && matchText;
  });

  if (hidden) {
    return (
      <button
        onClick={() => setHidden(false)}
        title="Show panel"
        className="flex-shrink-0 flex items-center justify-center transition-all"
        style={{
          width: 18, alignSelf: 'stretch',
          background: '#161616', borderRight: '1px solid rgba(255,255,255,0.06)',
          color: 'rgba(255,255,255,0.25)', fontSize: 12, cursor: 'pointer',
        }}
        onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.color = 'var(--accent)'; }}
        onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.color = 'rgba(255,255,255,0.25)'; }}
      >
        ›
      </button>
    );
  }


  return (
    <div className="flex flex-shrink-0" style={{ width: 260 }}>
      {/* Icon rail */}
      <div className="flex flex-col items-center py-2" style={{ width: 40, ...S.panel }}>
        {ICONS.map(({ id, icon, label }) => (
          <button
            key={id}
            title={label}
            onClick={() => setPanel(id)}
            style={iconBtn(panel === id) as React.CSSProperties}
            onMouseEnter={e => { if (panel !== id) (e.currentTarget as HTMLButtonElement).style.color = 'rgba(255,255,255,0.9)'; }}
            onMouseLeave={e => { if (panel !== id) (e.currentTarget as HTMLButtonElement).style.color = 'rgba(255,255,255,0.4)'; }}
          >
            {icon}
          </button>
        ))}
        <div className="flex-1" />
        <button
          onClick={() => setHidden(true)}
          style={{ ...iconBtn(false) as React.CSSProperties, margin: '2px auto 8px', fontSize: 14 }}
          title="Hide panel"
        >
          ✕
        </button>
      </div>

      {/* Panel content */}
      <div className="flex flex-col flex-1 overflow-hidden" style={S.section}>

        {/* ── Pages ── */}
        {panel === 'pages' && (
          <>
            <div className="flex items-center justify-between px-3 flex-shrink-0" style={S.header}>
              <span className="text-[11px] uppercase tracking-[1.5px] font-medium" style={{ color: 'rgba(255,255,255,0.3)', fontFamily: 'var(--sans)' }}>Pages</span>
              <button onClick={onPageAdd} title="Add page" style={{ color: 'rgba(255,255,255,0.4)', cursor: 'pointer' }}
                onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.color = 'var(--accent)'; }}
                onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.color = 'rgba(255,255,255,0.4)'; }}
              >
                <Plus className="w-3.5 h-3.5" />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto py-1" style={{ scrollbarWidth: 'none' }}>
              {pages.map(page => {
                const active = page.id === activePage;
                return (
                  <div
                    key={page.id}
                    className="group flex items-center gap-2 px-3 py-2 transition-all duration-[120ms]"
                    style={{
                      borderLeft: `2px solid ${active ? 'var(--accent)' : 'transparent'}`,
                      background: active ? 'color-mix(in srgb, var(--accent) 12%, transparent)' : 'transparent',
                      color:      active ? 'rgba(255,255,255,0.9)' : 'rgba(255,255,255,0.5)',
                      cursor: 'pointer',
                    }}
                    onClick={() => onPageSelect(page.id)}
                    onMouseEnter={e => { if (!active) (e.currentTarget as HTMLDivElement).style.background = '#252525'; }}
                    onMouseLeave={e => { if (!active) (e.currentTarget as HTMLDivElement).style.background = 'transparent'; }}
                  >
                    <FileText className="w-3.5 h-3.5 flex-shrink-0" />
                    <span className="text-[13px] truncate flex-1" style={{ fontFamily: 'var(--sans)' }}>{page.name}</span>
                    <Trash2
                      className="w-3 h-3 opacity-0 group-hover:opacity-100 flex-shrink-0 transition-opacity"
                      style={{ color: 'rgba(255,255,255,0.3)' }}
                      onClick={e => { e.stopPropagation(); onPageRemove(page.id); }}
                    />
                  </div>
                );
              })}
            </div>
          </>
        )}

        {/* ── Layers ── always mounted so GrapesJS layerManager can appendTo it at init ── */}
        <div style={{ display: panel === 'layers' ? 'flex' : 'none', flexDirection: 'column', flex: 1, overflow: 'hidden' }}>
          <div className="flex items-center px-3 flex-shrink-0" style={S.header}>
            <span className="text-[11px] uppercase tracking-[1.5px] font-medium" style={{ color: 'rgba(255,255,255,0.3)', fontFamily: 'var(--sans)' }}>Layers</span>
          </div>
          <div id="app-layers" className="flex-1 overflow-y-auto" style={{ scrollbarWidth: 'none' }} />
        </div>

        {/* ── Blocks ── */}
        {panel === 'blocks' && (
          <>
            <div className="flex items-center px-3 flex-shrink-0" style={S.header}>
              <span className="text-[11px] uppercase tracking-[1.5px] font-medium" style={{ color: 'rgba(255,255,255,0.3)', fontFamily: 'var(--sans)' }}>Blocks</span>
            </div>
            <div className="px-2 py-2 flex-shrink-0 border-b" style={{ borderColor: 'rgba(255,255,255,0.06)' }}>
              <input
                value={blockSearch}
                onChange={e => setBlockSearch(e.target.value)}
                placeholder="Search blocks..."
                className="w-full px-2.5 outline-none bg-transparent"
                style={S.input as React.CSSProperties}
              />
            </div>
            <div className="flex gap-1 px-2 py-1.5 flex-wrap flex-shrink-0 border-b" style={{ borderColor: 'rgba(255,255,255,0.06)' }}>
              {['All', ...CATEGORIES].map(cat => (
                <button
                  key={cat}
                  onClick={() => setActiveCategory(cat)}
                  className="px-2 py-0.5 rounded text-[10.5px] transition-all"
                  style={{
                    fontFamily: 'var(--sans)',
                    background: activeCategory === cat ? 'color-mix(in srgb, var(--accent) 15%, transparent)' : 'transparent',
                    color:      activeCategory === cat ? 'var(--accent)' : 'rgba(255,255,255,0.4)',
                    border:     `1px solid ${activeCategory === cat ? 'color-mix(in srgb, var(--accent) 30%, transparent)' : 'transparent'}`,
                  }}
                >
                  {cat}
                </button>
              ))}
            </div>
            <div className="flex-1 overflow-y-auto p-2" style={{ scrollbarWidth: 'none', userSelect: 'none' }}>
              <div className="grid grid-cols-2 gap-2">
                {filteredBlocks.map(block => (
                  <div
                    key={block.id}
                    draggable
                    onClick={() => handleAddBlock()}
                    onDragStart={e => {
                      e.dataTransfer.setData('application/app-block', JSON.stringify({
                        id:    block.id,
                        label: block.label,
                        html:  block.content,
                      }));
                      e.dataTransfer.effectAllowed = 'copy';
                    }}
                    onDragEnd={() => {}}
                    title={block.label}
                    className="flex flex-col rounded-lg overflow-hidden text-left transition-all duration-150 border"
                    style={{ background: '#1e1e1e', borderColor: 'rgba(255,255,255,0.06)', cursor: 'grab' }}
                    onMouseEnter={e => {
                      const el = e.currentTarget as HTMLDivElement;
                      el.style.borderColor = 'color-mix(in srgb, var(--accent) 40%, transparent)';
                      el.style.transform = 'scale(1.02)';
                    }}
                    onMouseLeave={e => {
                      const el = e.currentTarget as HTMLDivElement;
                      el.style.borderColor = 'rgba(255,255,255,0.06)';
                      el.style.transform = '';
                    }}
                  >
                    <div
                      className="w-full flex items-center justify-center"
                      style={{ height: 52, background: '#141414', pointerEvents: 'none' }}
                      dangerouslySetInnerHTML={{ __html: block.media }}
                    />
                    <div className="px-2 py-1.5" style={{ pointerEvents: 'none' }}>
                      <span className="text-[11px] font-medium" style={{ color: 'rgba(255,255,255,0.6)', fontFamily: 'var(--sans)' }}>
                        {block.label}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </>
        )}

        {/* ── Assets ── */}
        {panel === 'assets' && (
          <>
            <div className="flex items-center px-3 flex-shrink-0" style={S.header}>
              <span className="text-[11px] uppercase tracking-[1.5px] font-medium" style={{ color: 'rgba(255,255,255,0.3)', fontFamily: 'var(--sans)' }}>Assets</span>
            </div>
            <div className="flex-1 flex items-center justify-center p-6">
              <p className="text-[12px] text-center" style={{ color: 'rgba(255,255,255,0.2)', fontFamily: 'var(--mono)' }}>
                Asset library coming soon
              </p>
            </div>
          </>
        )}

      </div>
    </div>
  );
}
