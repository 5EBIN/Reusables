'use client';

import { useEffect, useRef } from 'react';
import type { DesignToken } from '@/_stubs';
import { BLOCKS } from './blockDefs';
import type { Editor, Plugin } from 'grapesjs';

interface Props {
  pageId: string;
  initialHtml: string;
  tokens: DesignToken;
  onSave: (pageId: string, html: string, tree: unknown) => void;
  onEditorReady: (editor: unknown) => void;
}

// ── Bug 1 fix: pure static object, zero React references ────────────────────
const STYLE_MANAGER_CONFIG = {
  sectors: [
    {
      name: 'Typography',
      open: true,
      properties: [
        {
          type: 'select', property: 'font-family', label: 'Font',
          options: [
            { id: 'DM Sans, sans-serif',   label: 'DM Sans'  },
            { id: 'Syne, sans-serif',       label: 'Syne'     },
            { id: 'DM Mono, monospace',     label: 'DM Mono'  },
            { id: 'Inter, sans-serif',      label: 'Inter'    },
            { id: 'Georgia, serif',         label: 'Georgia'  },
          ],
        },
        { type: 'number', property: 'font-size',      label: 'Size',          units: ['px', 'rem', 'em'], min: 0 },
        {
          type: 'select', property: 'font-weight', label: 'Weight',
          options: [
            { id: '300', label: 'Light' }, { id: '400', label: 'Regular' },
            { id: '500', label: 'Medium' }, { id: '600', label: 'SemiBold' },
            { id: '700', label: 'Bold' },
          ],
        },
        { type: 'number', property: 'line-height',    label: 'Line height',   units: ['', 'px'] },
        { type: 'number', property: 'letter-spacing', label: 'Letter spacing', units: ['px', 'em'] },
        {
          type: 'select', property: 'text-align', label: 'Align',
          options: [
            { id: 'left', label: 'Left' }, { id: 'center', label: 'Center' },
            { id: 'right', label: 'Right' }, { id: 'justify', label: 'Justify' },
          ],
        },
        { type: 'color', property: 'color', label: 'Color' },
      ],
    },
    {
      name: 'Spacing',
      open: false,
      properties: [
        {
          type: 'composite', property: 'padding', label: 'Padding',
          properties: [
            { type: 'number', property: 'padding-top',    units: ['px', 'rem'] },
            { type: 'number', property: 'padding-right',  units: ['px', 'rem'] },
            { type: 'number', property: 'padding-bottom', units: ['px', 'rem'] },
            { type: 'number', property: 'padding-left',   units: ['px', 'rem'] },
          ],
        },
        {
          type: 'composite', property: 'margin', label: 'Margin',
          properties: [
            { type: 'number', property: 'margin-top',    units: ['px', 'rem', 'auto'] },
            { type: 'number', property: 'margin-right',  units: ['px', 'rem', 'auto'] },
            { type: 'number', property: 'margin-bottom', units: ['px', 'rem', 'auto'] },
            { type: 'number', property: 'margin-left',   units: ['px', 'rem', 'auto'] },
          ],
        },
        { type: 'number', property: 'width',      label: 'Width',      units: ['px', '%', 'vw', 'rem'] },
        { type: 'number', property: 'height',     label: 'Height',     units: ['px', '%', 'vh', 'rem', 'auto'] },
        { type: 'number', property: 'max-width',  label: 'Max width',  units: ['px', '%', 'rem'] },
        { type: 'number', property: 'min-height', label: 'Min height', units: ['px', 'vh', 'rem'] },
      ],
    },
    {
      name: 'Appearance',
      open: false,
      properties: [
        { type: 'color', property: 'background-color', label: 'Background' },
        { type: 'number', property: 'border-radius', label: 'Radius', units: ['px', '%'] },
        {
          type: 'composite', property: 'border', label: 'Border',
          properties: [
            { type: 'number', property: 'border-width', units: ['px'] },
            {
              type: 'select', property: 'border-style',
              options: [
                { id: 'none', label: 'None' }, { id: 'solid', label: 'Solid' },
                { id: 'dashed', label: 'Dashed' }, { id: 'dotted', label: 'Dotted' },
              ],
            },
            { type: 'color', property: 'border-color' },
          ],
        },
        { type: 'slider', property: 'opacity', label: 'Opacity', min: 0, max: 1, step: 0.01 },
        {
          type: 'select', property: 'overflow', label: 'Overflow',
          options: [
            { id: 'visible', label: 'Visible' }, { id: 'hidden', label: 'Hidden' },
            { id: 'scroll', label: 'Scroll' }, { id: 'auto', label: 'Auto' },
          ],
        },
      ],
    },
    {
      name: 'Layout (Flex)',
      open: false,
      properties: [
        {
          type: 'select', property: 'display', label: 'Display',
          options: [
            { id: 'block', label: 'Block' }, { id: 'flex', label: 'Flex' },
            { id: 'grid', label: 'Grid' }, { id: 'inline', label: 'Inline' },
            { id: 'none', label: 'Hidden' },
          ],
        },
        {
          type: 'select', property: 'flex-direction', label: 'Direction',
          options: [
            { id: 'row', label: 'Row' }, { id: 'column', label: 'Column' },
            { id: 'row-reverse', label: 'Row reverse' }, { id: 'column-reverse', label: 'Col reverse' },
          ],
        },
        {
          type: 'select', property: 'justify-content', label: 'Justify',
          options: [
            { id: 'flex-start', label: 'Start' }, { id: 'center', label: 'Center' },
            { id: 'flex-end', label: 'End' }, { id: 'space-between', label: 'Space between' },
            { id: 'space-around', label: 'Space around' },
          ],
        },
        {
          type: 'select', property: 'align-items', label: 'Align',
          options: [
            { id: 'flex-start', label: 'Start' }, { id: 'center', label: 'Center' },
            { id: 'flex-end', label: 'End' }, { id: 'stretch', label: 'Stretch' },
          ],
        },
        { type: 'number', property: 'gap', label: 'Gap', units: ['px', 'rem'] },
      ],
    },
    {
      name: 'Effects',
      open: false,
      properties: [
        {
          type: 'select', property: 'box-shadow', label: 'Shadow',
          options: [
            { id: 'none',                               label: 'None'   },
            { id: '0 1px 3px rgba(0,0,0,0.12)',         label: 'Small'  },
            { id: '0 4px 12px rgba(0,0,0,0.15)',        label: 'Medium' },
            { id: '0 8px 30px rgba(0,0,0,0.2)',         label: 'Large'  },
            { id: '0 20px 60px rgba(0,0,0,0.3)',        label: 'XLarge' },
          ],
        },
        {
          type: 'select', property: 'transition', label: 'Transition',
          options: [
            { id: 'none',             label: 'None'   },
            { id: 'all 0.15s ease',   label: 'Fast'   },
            { id: 'all 0.3s ease',    label: 'Normal' },
            { id: 'all 0.5s ease',    label: 'Slow'   },
          ],
        },
        {
          type: 'select', property: 'cursor', label: 'Cursor',
          options: [
            { id: 'default',     label: 'Default'  },
            { id: 'pointer',     label: 'Pointer'  },
            { id: 'text',        label: 'Text'     },
            { id: 'not-allowed', label: 'Disabled' },
          ],
        },
      ],
    },
  ],
};

function injectEditorStyles() {
  const id = 'app-gjs-overrides';
  if (document.getElementById(id)) return;
  const s = document.createElement('style');
  s.id = id;
  s.textContent = `
    .gjs-cv-canvas { background: #0d0d0d !important; }
    .gjs-frame-wrapper { border: none !important; }
    .gjs-selected { outline: 2px solid rgba(45,179,112,0.8) !important; outline-offset: 1px; }
    .gjs-selected-parent { outline: 1px dashed rgba(45,179,112,0.3) !important; }
    .gjs-hovered { outline: 1px dashed rgba(45,179,112,0.4) !important; }
    .gjs-resizer-h {
      background: #2db370 !important; border: 1px solid #2db370 !important;
      width: 8px !important; height: 8px !important; border-radius: 2px !important;
    }
    .gjs-badge { background: #2db370 !important; color: #fff !important; font-size: 10px !important; border-radius: 3px !important; }
    .gjs-toolbar { background: #111 !important; border: 1px solid rgba(255,255,255,0.08) !important; border-radius: 6px !important; }
    .gjs-toolbar-item { color: rgba(255,255,255,0.7) !important; }
    .gjs-toolbar-item:hover { color: #fff !important; background: rgba(255,255,255,0.06) !important; }
    .gjs-placeholder { border: 2px dashed #2db370 !important; background: rgba(45,179,112,0.06) !important; }
    .gjs-placeholder-int { background: rgba(45,179,112,0.1) !important; }
    .gjs-sm-sector-title { background: #1a1a1a !important; color: rgba(255,255,255,0.6) !important; font-size: 11px !important; text-transform: uppercase; letter-spacing: 1px; border-bottom: 1px solid rgba(255,255,255,0.06) !important; }
    .gjs-sm-property { padding: 4px 8px !important; }
    .gjs-sm-label { color: rgba(255,255,255,0.4) !important; font-size: 11px !important; font-family: var(--sans) !important; }
    .gjs-sm-field input, .gjs-sm-field select { background: #1a1a1a !important; border: 1px solid rgba(255,255,255,0.1) !important; color: rgba(255,255,255,0.9) !important; border-radius: 4px !important; font-size: 12px !important; }
    .gjs-field { background: #1a1a1a !important; border-color: rgba(255,255,255,0.1) !important; }
    .gjs-field input { color: rgba(255,255,255,0.9) !important; }
  `;
  document.head.appendChild(s);
}

function injectTokensToCanvas(editor: Editor, tokens: DesignToken) {
  try {
    const frames = editor.Canvas.getFrames?.() ?? [];
    frames.forEach((frame) => {
      const doc = frame.view?.getEl()?.contentDocument;
      if (!doc?.head) return;
      let style = doc.getElementById('app-tokens');
      if (!style) {
        style = doc.createElement('style');
        style.id = 'app-tokens';
        doc.head.appendChild(style);
      }
      style.textContent = `
        :root {
          --color-primary:   ${tokens.colors.primary};
          --color-accent:    ${tokens.colors.accent};
          --color-bg:        ${tokens.colors.background};
          --color-surface:   ${tokens.colors.surface};
          --color-text:      ${tokens.colors.text};
          --color-text-sec:  ${tokens.colors.textSecondary};
          --color-border:    ${tokens.colors.border};
          --border-radius:   ${tokens.borderRadius};
          --font-body:       ${tokens.typography.fontFamily};
          --font-heading:    ${tokens.typography.headingFont};
        }
        html, body { margin: 0; width: 100%; min-height: 100vh; box-sizing: border-box; overflow-x: hidden; }
      `;
    });
  } catch { /* iframe not ready */ }
}

// ── Bug 2 fix: iframe pointer-event bridge ───────────────────────────────────
function wireIframeDragBridge(editor: Editor) {
  try {
    const canvasEl  = editor.Canvas.getElement() as HTMLElement;
    const canvasDoc = editor.Canvas.getDocument() as Document;
    if (!canvasEl || !canvasDoc) return;

    const bridge = (e: DragEvent) => {
      const rect = canvasEl.getBoundingClientRect();
      if (
        e.clientX >= rect.left && e.clientX <= rect.right &&
        e.clientY >= rect.top  && e.clientY <= rect.bottom
      ) {
        try {
          const cloned = new DragEvent('dragover', {
            bubbles: true, cancelable: true,
            clientX: e.clientX - rect.left,
            clientY: e.clientY - rect.top,
          });
          canvasDoc.dispatchEvent(cloned);
        } catch { /* cross-origin iframe */ }
      }
    };

    document.addEventListener('dragover', bridge);
    return () => document.removeEventListener('dragover', bridge);
  } catch { return () => {}; }
}

// Injected directly into the canvas iframe <head>
const CANVAS_BASE_CSS = `html,body{margin:0;min-height:100vh;box-sizing:border-box;}`;

// getHtml() throws if the internal wrapper component isn't ready yet.
// Always call this instead of editor.getHtml() directly.
export function safeGetHtml(editor: Editor): string {
  try {
    if (!editor?.getWrapper?.()) return '';
    return editor.getHtml() ?? '';
  } catch {
    return '';
  }
}

function safeRefresh(editor: Editor) {
  try { editor?.refresh(); } catch { /* canvas not ready */ }
}

const CANVAS_STYLES = [
  `data:text/css;charset=utf-8,${encodeURIComponent(CANVAS_BASE_CSS)}`,
  'https://cdn.tailwindcss.com',
  'https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=DM+Sans:wght@400;500;600;700&display=swap',
];

export default function GrapesCanvas({ pageId, initialHtml, tokens, onSave, onEditorReady }: Props) {
  const containerRef  = useRef<HTMLDivElement>(null);
  const editorRef     = useRef<Editor | null>(null);
  const pageIdRef     = useRef(pageId);
  const saveTimer     = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const bridgeClean   = useRef<(() => void) | undefined>(undefined);
  const observerRef   = useRef<ResizeObserver | null>(null);

  useEffect(() => { pageIdRef.current = pageId; }, [pageId]);

  useEffect(() => {
    if (!containerRef.current) return;

    const init = async () => {
      try {
        const grapesjs = (await import('grapesjs')).default;

        // ── Bug 3 fix: official plugins ──────────────────────────────────
        const gjsBlocksBasic = await import('grapesjs-blocks-basic').then(m => m.default).catch(() => null);
        const gjsForms       = await import('grapesjs-plugin-forms').then(m => m.default).catch(() => null);

        const plugins: Plugin[] = [];
        const pluginsOpts: Record<string, Record<string, unknown>> = {};

        if (gjsBlocksBasic) {
          plugins.push(gjsBlocksBasic);
          pluginsOpts['grapesjs-blocks-basic'] = {
            blocks: ['column1','column2','column3','text','link','image','video',
                     'link-block','quote','text-basic'],
            flexGrid: true,
            stylePrefix: 'gjs-',
            addBasicStyle: true,
          };
        }
        if (gjsForms) {
          plugins.push(gjsForms);
          pluginsOpts['grapesjs-plugin-forms'] = {
            blocks: ['form','input','textarea','select','button','label','checkbox','radio'],
          };
        }

        editorRef.current?.destroy();
        editorRef.current = null;

        const editor = grapesjs.init({
          container: containerRef.current!,
          height: '100%',
          width: '100%',
          fromElement: false,
          components: initialHtml,
          storageManager: false,
          panels:        { defaults: [] },
          canvas:        { styles: CANVAS_STYLES, scripts: [] },
          deviceManager: {
            devices: [
              { name: 'Desktop', width: '1440px' },
              { name: 'Tablet',  width: '768px',  widthMedia: '992px' },
              { name: 'Mobile',  width: '375px',  widthMedia: '480px' },
            ],
          },
          // ── Bug 1 fix: pure static config ─────────────────────────────
          styleManager:  STYLE_MANAGER_CONFIG,
          layerManager:  { appendTo: '#app-layers' },
          plugins,
          pluginsOpts,
        });

        injectEditorStyles();

        // Register our custom blocks with GrapesJS so drag works natively
        BLOCKS.forEach(block => {
          editor.BlockManager.add(block.id, {
            label:    block.label,
            category: { id: block.category, label: block.category },
            content:  block.content,
            media:    block.media,
            select:   true,
          });
        });

        // Gate saves behind this flag — getHtml() throws if called before load
        let editorLoaded = false;

        editor.on('load', () => {
          editorLoaded = true;
          bridgeClean.current = wireIframeDragBridge(editor);
          injectTokensToCanvas(editor, tokens);

          // Refresh INSIDE load — canvas is guaranteed ready at this point
          requestAnimationFrame(() => {
            requestAnimationFrame(() => {
              safeRefresh(editor);
              window.dispatchEvent(new Event('resize'));
              setTimeout(() => safeRefresh(editor), 300);
            });
          });

          // Watch the mount div for size changes after canvas is ready
          if (containerRef.current && typeof ResizeObserver !== 'undefined') {
            observerRef.current = new ResizeObserver(() => {
              requestAnimationFrame(() => safeRefresh(editor));
            });
            observerRef.current.observe(containerRef.current);
          }
        });

        editor.on('canvas:frame:load', () => injectTokensToCanvas(editor, tokens));

        editor.on('component:update', () => {
          if (!editorLoaded) return;
          clearTimeout(saveTimer.current);
          saveTimer.current = setTimeout(() => {
            try {
              onSave(pageIdRef.current, safeGetHtml(editor), editor.getComponents()?.toJSON() ?? []);
            } catch { /* editor internal model not ready or mid-destroy */ }
          }, 800);
        });

        editorRef.current = editor;
        onEditorReady(editor);
      } catch (err) {
        console.error('[GrapesCanvas] init failed:', err);
      }
    };

    init();

    return () => {
      clearTimeout(saveTimer.current);
      bridgeClean.current?.();
      observerRef.current?.disconnect();
      observerRef.current = null;
      editorRef.current?.destroy();
      editorRef.current = null;
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pageId]);

  useEffect(() => {
    if (editorRef.current) injectTokensToCanvas(editorRef.current, tokens);
  }, [tokens]);

  return (
    <div
      style={{
        flex: 1,
        minHeight: 0,
        width: '100%',
        position: 'relative',
        overflow: 'hidden',
        background: '#0d0d0d',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {/* Dot-grid backdrop */}
      <div
        style={{
          position: 'absolute', inset: 0, pointerEvents: 'none',
          backgroundImage: 'radial-gradient(circle, rgba(255,255,255,0.04) 1px, transparent 1px)',
          backgroundSize: '24px 24px',
        }}
      />
      {/* GrapesJS mount — all four properties required for the iframe to fill correctly */}
      <div
        ref={containerRef}
        style={{
          flex: 1,
          minHeight: 0,
          width: '100%',
          height: '100%',
          position: 'relative',
          overflow: 'hidden',
        }}
      />
    </div>
  );
}
