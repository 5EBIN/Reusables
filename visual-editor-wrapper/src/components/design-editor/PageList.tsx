import { Plus, Trash2, FileText } from 'lucide-react';
import type { PageDesign } from '@/_stubs';
import clsx from 'clsx';

interface Props {
  pages: PageDesign[];
  activePage: string;
  onSelect: (id: string) => void;
  onAdd: (page: PageDesign) => void;
  onRemove: (id: string) => void;
}

export default function PageList({ pages, activePage, onSelect, onAdd, onRemove }: Props) {
  const handleAdd = () => {
    const name = prompt('Page name (e.g., Profile, Orders):');
    if (name?.trim()) {
      const id = name.trim().toLowerCase().replace(/\s+/g, '-');
      onAdd({
        id,
        name: name.trim(),
        route: `/${id}`,
        layout: '',
        components: [],
      });
    }
  };

  return (
    <div className="w-48 bg-surface-900 border-r border-surface-700 flex flex-col shrink-0">
      <div className="px-3 py-3 border-b border-surface-700 flex items-center justify-between">
        <span className="text-xs font-semibold text-surface-400 uppercase tracking-wider">Pages</span>
        <button onClick={handleAdd} className="p-1 rounded hover:bg-surface-700 text-surface-400 hover:text-white">
          <Plus className="w-4 h-4" />
        </button>
      </div>
      <div className="flex-1 overflow-y-auto py-2 px-2 space-y-0.5">
        {pages.map((page) => (
          <div
            key={page.id}
            className={clsx(
              'flex items-center gap-2 px-2.5 py-2 rounded-lg cursor-pointer group transition-colors',
              activePage === page.id
                ? 'bg-accent/15 text-accent-light'
                : 'text-surface-400 hover:bg-surface-800 hover:text-white'
            )}
            onClick={() => onSelect(page.id)}
          >
            <FileText className="w-4 h-4 shrink-0" />
            <span className="text-sm font-medium truncate flex-1">{page.name}</span>
            {pages.length > 1 && (
              <button
                onClick={(e) => { e.stopPropagation(); onRemove(page.id); }}
                className="opacity-0 group-hover:opacity-100 p-0.5 rounded hover:bg-surface-700 text-surface-500 hover:text-danger"
              >
                <Trash2 className="w-3 h-3" />
              </button>
            )}
          </div>
        ))}
      </div>
      <div className="px-3 py-2 border-t border-surface-700">
        <p className="text-[10px] text-surface-500 text-center">
          {pages.length} page{pages.length !== 1 ? 's' : ''}
        </p>
      </div>
    </div>
  );
}
