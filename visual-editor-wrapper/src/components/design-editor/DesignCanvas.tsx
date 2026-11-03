'use client';

import { useRef, useEffect, useCallback, useState } from 'react';
import { useElementProperties } from '@/hooks/useElementProperties';
import type { ElementProperties } from '@/hooks/useElementProperties';

export interface BlockDelta {
  action: 'insert_block';
  blockId: string;
  blockLabel: string;
  blockHtml: string;
  insertAfterSelector: string | null;
}

export interface MoveDelta {
  action: 'move_element';
  elementSelector: string;
  direction: 'up' | 'down';
}

interface Props {
  pageId: string;
  html: string;
  onDropBlock: (delta: BlockDelta | MoveDelta) => void;
  onMoveElement: (delta: BlockDelta | MoveDelta) => void;
  isPatching: boolean;
  viewport: 'desktop' | 'tablet' | 'mobile';
  onElementClick: (
    properties: ElementProperties,
    position: { x: number; y: number }
  ) => void;
  onCanvasClickEmpty: () => void;
}

const VIEWPORT_WIDTHS = { desktop: '100%', tablet: '768px', mobile: '375px' };

// Scripts are disabled in the canvas sandbox (see the iframe below), so the old Tailwind CDN
// <link> (which points at a JS URL, not CSS) is not injected; only wrap bare fragments.
function wrapDocument(rawHtml: string): string {
  if (/<html[\s>]/i.test(rawHtml)) return rawHtml;
  return `<!DOCTYPE html><html><head><style>body{margin:0}</style></head><body>${rawHtml}</body></html>`;
}

function getSelectorForElement(el: Element): string {
  if (el.id) return `#${el.id}`;
  const tag = el.tagName.toLowerCase();
  const parent = el.parentElement;
  if (!parent) return tag;
  const siblings = Array.from(parent.children).filter(c => c.tagName === el.tagName);
  const index = siblings.indexOf(el);
  return index === 0 ? tag : `${tag}:nth-of-type(${index + 1})`;
}

export default function DesignCanvas({ pageId, html, onDropBlock, isPatching, viewport, onElementClick, onCanvasClickEmpty }: Props) {
  const iframeRef  = useRef<HTMLIFrameElement>(null);
  const [dragOverSelector, setDragOverSelector] = useState<string | null>(null);
  const [isDragging,       setIsDragging]       = useState(false);
  const { readProperties } = useElementProperties();

  // Track global drag state so overlay is transparent when not dragging (allows iframe scroll)
  useEffect(() => {
    const onStart = () => setIsDragging(true);
    const onEnd   = () => { setIsDragging(false); setDragOverSelector(null); };
    window.addEventListener('dragstart', onStart);
    window.addEventListener('dragend',   onEnd);
    return () => {
      window.removeEventListener('dragstart', onStart);
      window.removeEventListener('dragend',   onEnd);
    };
  }, []);

  // Highlight drop target inside the iframe
  useEffect(() => {
    const iframe = iframeRef.current;
    if (!iframe?.contentDocument) return;
    const doc = iframe.contentDocument;
    doc.querySelectorAll('[data-app-highlight]').forEach(el => {
      (el as HTMLElement).style.outline = '';
      el.removeAttribute('data-app-highlight');
    });
    if (dragOverSelector) {
      const target = doc.querySelector(dragOverSelector);
      if (target) {
        (target as HTMLElement).style.outline = '2px dashed #2db370';
        target.setAttribute('data-app-highlight', '1');
      }
    }
  }, [dragOverSelector]);

  const handleOverlayDragOver = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    const iframe = iframeRef.current;
    if (!iframe?.contentDocument) return;
    const rect = iframe.getBoundingClientRect();
    const el   = iframe.contentDocument.elementFromPoint(e.clientX - rect.left, e.clientY - rect.top);
    if (!el || el === iframe.contentDocument.body) { setDragOverSelector(null); return; }

    let target: Element = el;
    const blockTags = ['SECTION','ARTICLE','NAV','HEADER','FOOTER','MAIN','DIV','ASIDE'];
    while (target.parentElement && !blockTags.includes(target.tagName)) {
      target = target.parentElement;
    }
    setDragOverSelector(getSelectorForElement(target));
  }, []);

  const handleOverlayDragLeave = useCallback(() => setDragOverSelector(null), []);

  const handleOverlayDrop = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    const raw = e.dataTransfer.getData('application/app-block');
    if (!raw) return;
    let blockData: { id: string; label: string; html: string };
    try { blockData = JSON.parse(raw); } catch { return; }
    onDropBlock({
      action: 'insert_block',
      blockId: blockData.id,
      blockLabel: blockData.label,
      blockHtml: blockData.html,
      insertAfterSelector: dragOverSelector,
    });
    setDragOverSelector(null);
  }, [dragOverSelector, onDropBlock]);

  // Stable refs so the iframe click handler always sees latest callbacks
  const onElementClickRef    = useRef(onElementClick);
  const onCanvasClickEmptyRef = useRef(onCanvasClickEmpty);
  const readPropertiesRef    = useRef(readProperties);
  useEffect(() => { onElementClickRef.current    = onElementClick;    }, [onElementClick]);
  useEffect(() => { onCanvasClickEmptyRef.current = onCanvasClickEmpty; }, [onCanvasClickEmpty]);
  useEffect(() => { readPropertiesRef.current    = readProperties;    }, [readProperties]);

  // Attach click listener inside the iframe so the overlay stays pointer-events:none (scroll works)
  useEffect(() => {
    const iframe = iframeRef.current;
    if (!iframe) return;

    function attachClick() {
      const doc = iframe!.contentDocument;
      if (!doc) return;

      const handler = (e: MouseEvent) => {
        const el = e.target as Element | null;
        if (!el || el === doc.body || el === doc.documentElement) {
          onCanvasClickEmptyRef.current();
          return;
        }
        const selector   = getSelectorForElement(el);
        const properties = readPropertiesRef.current(el, selector);

        const iframeRect = iframe!.getBoundingClientRect();
        const canvasEl   = iframe!.parentElement;
        const canvasRect = canvasEl ? canvasEl.getBoundingClientRect() : iframeRect;

        onElementClickRef.current(properties, {
          x: iframeRect.left - canvasRect.left + e.clientX,
          y: iframeRect.top  - canvasRect.top  + e.clientY,
        });
      };

      doc.addEventListener('click', handler);
      return () => doc.removeEventListener('click', handler);
    }

    let cleanup: (() => void) | undefined;
    const onLoad = () => {
      cleanup?.();
      cleanup = attachClick();
    };

    iframe.addEventListener('load', onLoad);
    // Attach immediately if already loaded
    cleanup = attachClick();

    return () => {
      iframe.removeEventListener('load', onLoad);
      cleanup?.();
    };
  }, [pageId]); // re-run when pageId changes (iframe key remount)

  const iframeWidth = VIEWPORT_WIDTHS[viewport];

  return (
    <div
      className="relative flex-1 min-h-0 overflow-auto flex justify-center"
      style={{ background: '#0d0d0d', backgroundImage: 'radial-gradient(circle, rgba(255,255,255,0.04) 1px, transparent 1px)', backgroundSize: '24px 24px' }}
    >
      {/* Patching overlay */}
      {isPatching && (
        <div className="absolute inset-0 z-20 flex items-center justify-center bg-black/50 backdrop-blur-sm">
          <div className="flex items-center gap-3 px-5 py-3 rounded-xl border"
            style={{ background: '#1a1a1a', borderColor: 'rgba(45,179,112,0.3)' }}>
            <div className="w-4 h-4 border-2 border-green-400 border-t-transparent rounded-full animate-spin" />
            <span className="text-sm font-medium" style={{ color: '#2db370' }}>Applying change…</span>
          </div>
        </div>
      )}

      {/* Drag overlay — only active during drag so iframe scroll is never blocked */}
      <div
        className="absolute inset-0 z-10"
        style={{ pointerEvents: (isDragging && !isPatching) ? 'auto' : 'none' }}
        onDragOver={handleOverlayDragOver}
        onDragLeave={handleOverlayDragLeave}
        onDrop={handleOverlayDrop}
      />

      <iframe
        ref={iframeRef}
        key={pageId}
        srcDoc={wrapDocument(html)}
        sandbox="allow-same-origin"
        title={`canvas-${pageId}`}
        style={{
          width: iframeWidth,
          height: '100%',
          minHeight: '100%',
          border: 'none',
          background: '#fff',
          display: 'block',
          flexShrink: 0,
        }}
      />
    </div>
  );
}
