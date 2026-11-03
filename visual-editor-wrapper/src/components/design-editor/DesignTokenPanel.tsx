import { X } from 'lucide-react';
import type { DesignToken } from '@/_stubs';

interface Props {
  tokens: DesignToken;
  onChange: (tokens: DesignToken) => void;
  onClose: () => void;
}

export default function DesignTokenPanel({ tokens, onChange, onClose }: Props) {
  const updateColor = (key: keyof DesignToken['colors'], value: string) => {
    onChange({ ...tokens, colors: { ...tokens.colors, [key]: value } });
  };

  const updateTypo = (key: keyof DesignToken['typography'], value: string) => {
    onChange({ ...tokens, typography: { ...tokens.typography, [key]: value } });
  };

  return (
    <div className="w-72 bg-surface-900 border-l border-surface-700 overflow-y-auto shrink-0">
      <div className="px-4 py-3 border-b border-surface-700 flex items-center justify-between">
        <span className="text-sm font-semibold text-white">Design Tokens</span>
        <button onClick={onClose} className="p-1 rounded hover:bg-surface-700 text-surface-400">
          <X className="w-4 h-4" />
        </button>
      </div>

      <div className="p-4 space-y-6">
        {/* Colors */}
        <div>
          <h4 className="text-xs font-semibold text-surface-400 uppercase tracking-wider mb-3">Colors</h4>
          <div className="space-y-2">
            {(Object.keys(tokens.colors) as (keyof DesignToken['colors'])[]).map((key) => (
              <div key={key} className="flex items-center gap-2">
                <input
                  type="color"
                  value={tokens.colors[key]}
                  onChange={(e) => updateColor(key, e.target.value)}
                  className="w-8 h-8 rounded cursor-pointer border border-surface-600 bg-transparent"
                />
                <div className="flex-1">
                  <p className="text-xs font-medium text-surface-300 capitalize">{key.replace(/([A-Z])/g, ' $1')}</p>
                  <p className="text-[10px] text-surface-500 font-mono">{tokens.colors[key]}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Typography */}
        <div>
          <h4 className="text-xs font-semibold text-surface-400 uppercase tracking-wider mb-3">Typography</h4>
          <div className="space-y-3">
            <div>
              <label className="text-xs text-surface-400 mb-1 block">Body Font</label>
              <input
                className="input-field text-sm"
                value={tokens.typography.fontFamily}
                onChange={(e) => updateTypo('fontFamily', e.target.value)}
              />
            </div>
            <div>
              <label className="text-xs text-surface-400 mb-1 block">Heading Font</label>
              <input
                className="input-field text-sm"
                value={tokens.typography.headingFont}
                onChange={(e) => updateTypo('headingFont', e.target.value)}
              />
            </div>
            <div>
              <label className="text-xs text-surface-400 mb-1 block">Base Font Size</label>
              <input
                className="input-field text-sm"
                value={tokens.typography.baseFontSize}
                onChange={(e) => updateTypo('baseFontSize', e.target.value)}
              />
            </div>
          </div>
        </div>

        {/* Border Radius */}
        <div>
          <h4 className="text-xs font-semibold text-surface-400 uppercase tracking-wider mb-3">Shape</h4>
          <div>
            <label className="text-xs text-surface-400 mb-1 block">Border Radius</label>
            <input
              className="input-field text-sm"
              value={tokens.borderRadius}
              onChange={(e) => onChange({ ...tokens, borderRadius: e.target.value })}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
