// ╔══════════════════════════════════════════════════════════════════════════╗
// ║  DO NOT REMOVE — GrapesJS core editor component                         ║
// ║                                                                          ║
// ║  Part of the full visual design editor surface (see ui-design/page.tsx).║
// ║  Will be wired into the orchestration pipeline in a future milestone to  ║
// ║  support in-graph UI editing with changes fed back to the worker nodes.  ║
// ╚══════════════════════════════════════════════════════════════════════════╝
import { useEffect, useRef } from 'react';
import type { DesignToken } from '@/_stubs';
import type { Editor, Plugin } from 'grapesjs';

interface Props {
  pageId: string;
  initialHtml: string;
  tokens: DesignToken;
  onSave: (pageId: string, html: string) => void;
}

/**
 * GrapesJS Editor Wrapper
 * 
 * Integrates GrapesJS drag-and-drop builder with:
 * - Tailwind CSS blocks
 * - Custom component blocks for common UI patterns
 * - Design token theming
 * - HTML+Tailwind output (as per reference doc Section 6)
 * 
 * In production: grapesjs + grapesjs-tailwind + grapesjs-blocks-basic
 * are imported as npm modules. The component tree JSON is stored
 * internally while HTML is the output format (ref doc Section 13.1).
 */
export default function GrapesEditor({ pageId, initialHtml, tokens, onSave }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const editorRef = useRef<Editor | null>(null);
  const pageIdRef = useRef(pageId);

  useEffect(() => {
    pageIdRef.current = pageId;
  }, [pageId]);

  // The editor is created once per page. It must read the CURRENT html, tokens and save callback, but it must not be re-created when
  // they change, so they are read through a ref that is refreshed after every render (declared before the effect that creates the editor).
  const latestRef = useRef({ initialHtml, tokens, onSave });
  useEffect(() => {
    latestRef.current = { initialHtml, tokens, onSave };
  });

  useEffect(() => {
    if (!containerRef.current) return;

    // Dynamic import pattern for GrapesJS
    const loadEditor = async () => {
      try {
        const grapesjs = await import('grapesjs');
        const gjsPresetWebpage = await import('grapesjs-preset-webpage').catch(() => null);
        const gjsBlocksBasic = await import('grapesjs-blocks-basic').catch(() => null);

        if (editorRef.current) {
          editorRef.current.destroy();
        }

        const plugins: Plugin[] = [];
        const pluginsOpts: Record<string, Record<string, unknown>> = {};

        if (gjsBlocksBasic?.default) {
          plugins.push(gjsBlocksBasic.default);
        }
        if (gjsPresetWebpage?.default) {
          plugins.push(gjsPresetWebpage.default);
          pluginsOpts['grapesjs-preset-webpage'] = {
            blocksBasicOpts: { flexGrid: true },
          };
        }

        const editor = grapesjs.default.init({
          container: containerRef.current!,
          height: '100%',
          width: 'auto',
          fromElement: false,
          components: latestRef.current.initialHtml || getDefaultTemplate(latestRef.current.tokens),
          storageManager: false,
          plugins,
          pluginsOpts,

          canvas: {
            styles: [
              'https://cdn.jsdelivr.net/npm/tailwindcss@3.4/dist/tailwind.min.css',
              'https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap',
            ],
          },

          deviceManager: {
            devices: [
              { name: 'Desktop', width: '' },
              { name: 'Tablet', width: '768px', widthMedia: '992px' },
              { name: 'Mobile', width: '375px', widthMedia: '480px' },
            ],
          },

          styleManager: {
            sectors: [
              {
                name: 'Layout',
                open: true,
                properties: [
                  'display', 'flex-direction', 'justify-content', 'align-items',
                  'flex-wrap', 'gap', 'width', 'height', 'max-width', 'min-height',
                  'margin', 'padding', 'overflow',
                ],
              },
              {
                name: 'Typography',
                properties: [
                  'font-family', 'font-size', 'font-weight', 'letter-spacing',
                  'color', 'line-height', 'text-align', 'text-decoration', 'text-transform',
                ],
              },
              {
                name: 'Appearance',
                properties: [
                  'background-color', 'background', 'border-radius',
                  'border', 'box-shadow', 'opacity',
                ],
              },
            ],
          },
        });

        // Add custom Tailwind blocks
        addCustomBlocks(editor, latestRef.current.tokens);

        // Auto-save on change
        editor.on('component:update', () => {
          const html = editor.getHtml();
          latestRef.current.onSave(pageIdRef.current, html);
        });

        editorRef.current = editor;
      } catch (err) {
        console.error('Failed to load GrapesJS:', err);
      }
    };

    loadEditor();

    return () => {
      if (editorRef.current) {
        editorRef.current.destroy();
        editorRef.current = null;
      }
    };
  }, [pageId]);

  return (
    <div className="h-full w-full">
      <div ref={containerRef} className="h-full w-full" />
      {/* Fallback if GrapesJS hasn't loaded */}
      {!editorRef.current && (
        <div className="absolute inset-0 flex items-center justify-center bg-surface-900">
          <div className="text-center">
            <div className="w-12 h-12 border-4 border-accent/30 border-t-accent rounded-full animate-spin mx-auto mb-4" />
            <p className="text-surface-400 text-sm">Loading Design Editor...</p>
            <p className="text-surface-500 text-xs mt-2">Initializing GrapesJS with Tailwind blocks</p>
          </div>
        </div>
      )}
    </div>
  );
}

function addCustomBlocks(editor: Editor, tokens: DesignToken) {
  const bm = editor.BlockManager;

  // Hero Section
  bm.add('hero', {
    label: 'Hero Section',
    category: 'Sections',
    content: `
      <section class="relative py-24 px-6" style="background-color: ${tokens.colors.background}">
        <div class="max-w-4xl mx-auto text-center">
          <h1 class="text-5xl font-extrabold tracking-tight mb-6" style="color: ${tokens.colors.text}">
            Build Something Amazing
          </h1>
          <p class="text-xl mb-8" style="color: ${tokens.colors.textSecondary}">
            A brief description of your product and its value proposition.
          </p>
          <div class="flex items-center justify-center gap-4">
            <a href="#" class="px-8 py-3 rounded-lg font-semibold text-white" style="background-color: ${tokens.colors.primary}">Get Started</a>
            <a href="#" class="px-8 py-3 rounded-lg font-semibold border" style="color: ${tokens.colors.text}; border-color: ${tokens.colors.border}">Learn More</a>
          </div>
        </div>
      </section>`,
  });

  // Card
  bm.add('card', {
    label: 'Card',
    category: 'Components',
    content: `
      <div class="rounded-xl p-6 border" style="background-color: ${tokens.colors.surface}; border-color: ${tokens.colors.border}">
        <h3 class="text-lg font-semibold mb-2" style="color: ${tokens.colors.text}">Card Title</h3>
        <p class="text-sm" style="color: ${tokens.colors.textSecondary}">Card description goes here.</p>
      </div>`,
  });

  // Login Form
  bm.add('login-form', {
    label: 'Login Form',
    category: 'Forms',
    content: `
      <div class="max-w-md mx-auto p-8 rounded-xl border" style="background-color: ${tokens.colors.surface}; border-color: ${tokens.colors.border}">
        <h2 class="text-2xl font-bold mb-6 text-center" style="color: ${tokens.colors.text}">Sign In</h2>
        <div class="space-y-4">
          <div>
            <label class="block text-sm font-medium mb-1" style="color: ${tokens.colors.textSecondary}">Email</label>
            <input type="email" placeholder="you@example.com" class="w-full px-4 py-2.5 rounded-lg border text-sm" style="background-color: ${tokens.colors.background}; border-color: ${tokens.colors.border}; color: ${tokens.colors.text}" />
          </div>
          <div>
            <label class="block text-sm font-medium mb-1" style="color: ${tokens.colors.textSecondary}">Password</label>
            <input type="password" placeholder="••••••••" class="w-full px-4 py-2.5 rounded-lg border text-sm" style="background-color: ${tokens.colors.background}; border-color: ${tokens.colors.border}; color: ${tokens.colors.text}" />
          </div>
          <button class="w-full py-2.5 rounded-lg font-semibold text-white" style="background-color: ${tokens.colors.primary}">Sign In</button>
          <p class="text-center text-sm" style="color: ${tokens.colors.textSecondary}">
            <a href="#" style="color: ${tokens.colors.primary}">Forgot password?</a>
          </p>
        </div>
      </div>`,
  });

  // Dashboard Header
  bm.add('dashboard-header', {
    label: 'Dashboard Header',
    category: 'Sections',
    content: `
      <header class="flex items-center justify-between px-6 py-4 border-b" style="background-color: ${tokens.colors.surface}; border-color: ${tokens.colors.border}">
        <h1 class="text-xl font-bold" style="color: ${tokens.colors.text}">Dashboard</h1>
        <div class="flex items-center gap-4">
          <span class="text-sm" style="color: ${tokens.colors.textSecondary}">Welcome back</span>
          <div class="w-8 h-8 rounded-full" style="background-color: ${tokens.colors.primary}"></div>
        </div>
      </header>`,
  });

  // Stats Grid
  bm.add('stats-grid', {
    label: 'Stats Grid',
    category: 'Components',
    content: `
      <div class="grid grid-cols-1 md:grid-cols-4 gap-4 p-6">
        ${['Total Users', 'Revenue', 'Orders', 'Growth'].map((label) => `
          <div class="rounded-xl p-5 border" style="background-color: ${tokens.colors.surface}; border-color: ${tokens.colors.border}">
            <p class="text-sm font-medium" style="color: ${tokens.colors.textSecondary}">${label}</p>
            <p class="text-2xl font-bold mt-1" style="color: ${tokens.colors.text}">0</p>
          </div>`).join('')}
      </div>`,
  });

  // Data Table
  bm.add('data-table', {
    label: 'Data Table',
    category: 'Components',
    content: `
      <div class="rounded-xl border overflow-hidden" style="border-color: ${tokens.colors.border}">
        <table class="w-full">
          <thead>
            <tr style="background-color: ${tokens.colors.surface}">
              <th class="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider" style="color: ${tokens.colors.textSecondary}">Name</th>
              <th class="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider" style="color: ${tokens.colors.textSecondary}">Status</th>
              <th class="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider" style="color: ${tokens.colors.textSecondary}">Date</th>
              <th class="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider" style="color: ${tokens.colors.textSecondary}">Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr style="border-top: 1px solid ${tokens.colors.border}">
              <td class="px-4 py-3 text-sm" style="color: ${tokens.colors.text}">Item name</td>
              <td class="px-4 py-3"><span class="px-2 py-1 rounded-full text-xs font-medium" style="background-color: ${tokens.colors.success}20; color: ${tokens.colors.success}">Active</span></td>
              <td class="px-4 py-3 text-sm" style="color: ${tokens.colors.textSecondary}">Jan 1, 2026</td>
              <td class="px-4 py-3 text-sm" style="color: ${tokens.colors.primary}">Edit</td>
            </tr>
          </tbody>
        </table>
      </div>`,
  });
}

function getDefaultTemplate(tokens: DesignToken): string {
  return `
    <div style="min-height: 100vh; background-color: ${tokens.colors.background}; font-family: ${tokens.typography.fontFamily}">
      <nav class="px-6 py-4 border-b flex items-center justify-between" style="background-color: ${tokens.colors.surface}; border-color: ${tokens.colors.border}">
        <span class="text-lg font-bold" style="color: ${tokens.colors.text}">Your App</span>
        <div class="flex gap-4">
          <a href="#" class="text-sm font-medium" style="color: ${tokens.colors.textSecondary}">Home</a>
          <a href="#" class="text-sm font-medium" style="color: ${tokens.colors.textSecondary}">About</a>
          <a href="#" class="px-4 py-1.5 rounded-lg text-sm font-medium text-white" style="background-color: ${tokens.colors.primary}">Sign In</a>
        </div>
      </nav>
      <main class="py-16 px-6">
        <div class="max-w-4xl mx-auto text-center">
          <h1 class="text-4xl font-bold mb-4" style="color: ${tokens.colors.text}">Welcome to Your App</h1>
          <p class="text-lg" style="color: ${tokens.colors.textSecondary}">Start designing by dragging components from the sidebar.</p>
        </div>
      </main>
    </div>`;
}
