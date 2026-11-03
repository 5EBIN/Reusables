'use client'

import { useState, useEffect, useRef } from 'react'
import type { ElementProperties } from '@/hooks/useElementProperties'

interface Props {
  properties: ElementProperties
  position: { x: number; y: number }   // screen coords (relative to canvas)
  canvasRect: DOMRect                   // bounding rect of the canvas div
  onApplyChange: (change: StyleChange) => void
  onClose: () => void
  isPatching: boolean
}

export interface StyleChange {
  action: 'style_element'
  elementSelector: string
  changes: Record<string, string>
}

const FONT_FAMILIES = [
  'Inter, sans-serif',
  'DM Sans, sans-serif',
  'Syne, sans-serif',
  'DM Mono, monospace',
  'Georgia, serif',
  'Playfair Display, serif',
  'system-ui, sans-serif',
]

const FONT_SIZES = ['12px','14px','16px','18px','20px','24px','28px','32px','36px','48px','64px','72px']
const TEXT_ALIGNS = ['left','center','right','justify']
const OBJECT_FITS = ['cover','contain','fill','none','scale-down']

function clampPosition(
  x: number,
  y: number,
  canvasRect: DOMRect,
  panelW = 260,
  panelH = 420
): { left: number; top: number } {
  const maxLeft = canvasRect.width - panelW - 8
  const maxTop = canvasRect.height - panelH - 8
  return {
    left: Math.max(8, Math.min(x + 12, maxLeft)),
    top: Math.max(8, Math.min(y - 40, maxTop)),
  }
}

export default function FloatingPropertyPanel({
  properties,
  position,
  canvasRect,
  onApplyChange,
  onClose,
  isPatching,
}: Props) {
  const [local, setLocal] = useState<ElementProperties>(properties)
  const pendingRef = useRef<Record<string, string>>({})

  // A different element was selected: start from its properties (state adjusted during render, not in an effect) and drop pending edits.
  const [shownSelector, setShownSelector] = useState(properties.selector)
  if (properties.selector !== shownSelector) {
    setShownSelector(properties.selector)
    setLocal(properties)
  }
  useEffect(() => {
    pendingRef.current = {}
  }, [properties.selector])

  const { left, top } = clampPosition(position.x, position.y, canvasRect)

  const handleChange = (key: string, value: string) => {
    setLocal(prev => ({ ...prev, [key]: value }))
    pendingRef.current[key] = value
  }

  const handleCommit = () => {
    if (Object.keys(pendingRef.current).length === 0) return
    onApplyChange({
      action: 'style_element',
      elementSelector: local.selector,
      changes: { ...pendingRef.current },
    })
    pendingRef.current = {}
  }

  const { elementType } = local

  return (
    <div
      className="absolute z-30 rounded-xl border shadow-2xl overflow-hidden"
      style={{
        left,
        top,
        width: 260,
        background: 'var(--surface)',
        borderColor: 'var(--border)',
        fontFamily: 'DM Sans, sans-serif',
      }}
      onMouseDown={e => e.stopPropagation()}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between px-3 py-2 border-b"
        style={{ borderColor: 'var(--border)' }}
      >
        <span className="text-xs font-semibold uppercase tracking-widest"
              style={{ color: 'var(--green-light)', fontFamily: 'DM Mono, monospace' }}>
          {local.tagName.toLowerCase()}
        </span>
        <button
          onClick={onClose}
          className="w-5 h-5 rounded flex items-center justify-center text-xs opacity-50 hover:opacity-100 transition-opacity"
          style={{ color: 'var(--text)' }}
        >
          ✕
        </button>
      </div>

      {/* Controls */}
      <div className="p-3 flex flex-col gap-3 overflow-y-auto" style={{ maxHeight: 380 }}>

        {/* ── TYPOGRAPHY (text + button) ── */}
        {(elementType === 'text' || elementType === 'button') && (
          <>
            <Section label="Typography">
              <Row label="Font">
                <select
                  value={local.fontFamily || ''}
                  onChange={e => handleChange('fontFamily', e.target.value)}
                  onBlur={handleCommit}
                  className="w-full text-xs rounded px-2 py-1"
                  style={inputStyle}
                >
                  {FONT_FAMILIES.map(f => (
                    <option key={f} value={f}>{f.split(',')[0]}</option>
                  ))}
                </select>
              </Row>

              <Row label="Size">
                <select
                  value={local.fontSize || '16px'}
                  onChange={e => { handleChange('fontSize', e.target.value); handleCommit() }}
                  className="w-full text-xs rounded px-2 py-1"
                  style={inputStyle}
                >
                  {FONT_SIZES.map(s => <option key={s} value={s}>{s}</option>)}
                </select>
              </Row>

              <Row label="Style">
                <div className="flex gap-1">
                  <Toggle
                    active={local.fontWeight === 'bold' || Number(local.fontWeight) >= 700}
                    onClick={() => {
                      const next = (local.fontWeight === 'bold' || Number(local.fontWeight) >= 700)
                        ? '400' : 'bold'
                      handleChange('fontWeight', next)
                      pendingRef.current['fontWeight'] = next
                      handleCommit()
                    }}
                    label="B"
                    title="Bold"
                    bold
                  />
                  <Toggle
                    active={local.fontStyle === 'italic'}
                    onClick={() => {
                      const next = local.fontStyle === 'italic' ? 'normal' : 'italic'
                      handleChange('fontStyle', next)
                      pendingRef.current['fontStyle'] = next
                      handleCommit()
                    }}
                    label="I"
                    title="Italic"
                    italic
                  />
                  <Toggle
                    active={local.textDecoration?.includes('underline') ?? false}
                    onClick={() => {
                      const next = local.textDecoration?.includes('underline') ? 'none' : 'underline'
                      handleChange('textDecoration', next)
                      pendingRef.current['textDecoration'] = next
                      handleCommit()
                    }}
                    label="U"
                    title="Underline"
                    underline
                  />
                </div>
              </Row>

              <Row label="Align">
                <div className="flex gap-1">
                  {TEXT_ALIGNS.map(align => (
                    <Toggle
                      key={align}
                      active={local.textAlign === align}
                      onClick={() => {
                        handleChange('textAlign', align)
                        pendingRef.current['textAlign'] = align
                        handleCommit()
                      }}
                      label={alignIcon(align)}
                      title={align}
                    />
                  ))}
                </div>
              </Row>

              <Row label="Line H">
                <input
                  type="text"
                  value={local.lineHeight || 'normal'}
                  onChange={e => handleChange('lineHeight', e.target.value)}
                  onBlur={handleCommit}
                  className="w-full text-xs rounded px-2 py-1"
                  style={inputStyle}
                  placeholder="1.5"
                />
              </Row>

              <Row label="Spacing">
                <input
                  type="text"
                  value={local.letterSpacing || '0px'}
                  onChange={e => handleChange('letterSpacing', e.target.value)}
                  onBlur={handleCommit}
                  className="w-full text-xs rounded px-2 py-1"
                  style={inputStyle}
                  placeholder="0px"
                />
              </Row>
            </Section>

            <Section label="Color">
              <Row label="Text">
                <ColorInput
                  value={rgbToHex(local.color || '#ffffff')}
                  onChange={v => handleChange('color', v)}
                  onCommit={handleCommit}
                />
              </Row>
              {elementType === 'button' && (
                <Row label="Background">
                  <ColorInput
                    value={rgbToHex(local.backgroundColor || '#000000')}
                    onChange={v => handleChange('backgroundColor', v)}
                    onCommit={handleCommit}
                  />
                </Row>
              )}
            </Section>
          </>
        )}

        {/* ── BACKGROUND (container + input + generic) ── */}
        {(elementType === 'container' || elementType === 'input' || elementType === 'generic') && (
          <Section label="Color">
            <Row label="Background">
              <ColorInput
                value={rgbToHex(local.backgroundColor || '#000000')}
                onChange={v => handleChange('backgroundColor', v)}
                onCommit={handleCommit}
              />
            </Row>
            {(elementType === 'input' || elementType === 'generic') && (
              <Row label="Text">
                <ColorInput
                  value={rgbToHex(local.color || '#ffffff')}
                  onChange={v => handleChange('color', v)}
                  onCommit={handleCommit}
                />
              </Row>
            )}
          </Section>
        )}

        {/* ── BORDER ── */}
        {elementType !== 'image' && (
          <Section label="Border">
            <Row label="Radius">
              <SliderInput
                value={parsePx(local.borderRadius || '0px')}
                min={0} max={64} unit="px"
                onChange={v => handleChange('borderRadius', `${v}px`)}
                onCommit={handleCommit}
              />
            </Row>
            <Row label="Color">
              <ColorInput
                value={rgbToHex(local.borderColor || '#000000')}
                onChange={v => handleChange('borderColor', v)}
                onCommit={handleCommit}
              />
            </Row>
            <Row label="Width">
              <SliderInput
                value={parsePx(local.borderWidth || '0px')}
                min={0} max={16} unit="px"
                onChange={v => handleChange('borderWidth', `${v}px`)}
                onCommit={handleCommit}
              />
            </Row>
          </Section>
        )}

        {/* ── OPACITY ── */}
        <Section label="Opacity">
          <Row label="">
            <SliderInput
              value={Math.round(parseFloat(local.opacity || '1') * 100)}
              min={0} max={100} unit="%"
              onChange={v => handleChange('opacity', String(v / 100))}
              onCommit={handleCommit}
            />
          </Row>
        </Section>

        {/* ── ROTATION (image + generic) ── */}
        {(elementType === 'image' || elementType === 'generic') && (
          <Section label="Transform">
            <Row label="Rotate">
              <SliderInput
                value={parseDeg(local.rotation || '0deg')}
                min={-180} max={180} unit="°"
                onChange={v => handleChange('rotation', `${v}deg`)}
                onCommit={handleCommit}
              />
            </Row>
          </Section>
        )}

        {/* ── IMAGE SPECIFIC ── */}
        {elementType === 'image' && (
          <Section label="Image">
            <Row label="Fit">
              <select
                value={local.objectFit || 'cover'}
                onChange={e => { handleChange('objectFit', e.target.value); handleCommit() }}
                className="w-full text-xs rounded px-2 py-1"
                style={inputStyle}
              >
                {OBJECT_FITS.map(f => <option key={f} value={f}>{f}</option>)}
              </select>
            </Row>
            <Row label="Radius">
              <SliderInput
                value={parsePx(local.borderRadius || '0px')}
                min={0} max={64} unit="px"
                onChange={v => handleChange('borderRadius', `${v}px`)}
                onCommit={handleCommit}
              />
            </Row>
          </Section>
        )}

        {/* ── CONTAINER SPECIFIC ── */}
        {elementType === 'container' && (
          <Section label="Spacing">
            <Row label="Padding">
              <input
                type="text"
                value={local.padding || '0px'}
                onChange={e => handleChange('padding', e.target.value)}
                onBlur={handleCommit}
                className="w-full text-xs rounded px-2 py-1"
                style={inputStyle}
                placeholder="16px"
              />
            </Row>
            <Row label="Gap">
              <input
                type="text"
                value={local.gap || '0px'}
                onChange={e => handleChange('gap', e.target.value)}
                onBlur={handleCommit}
                className="w-full text-xs rounded px-2 py-1"
                style={inputStyle}
                placeholder="8px"
              />
            </Row>
          </Section>
        )}

      </div>

      {/* Apply button */}
      <div className="px-3 py-2 border-t" style={{ borderColor: 'var(--border)' }}>
        <button
          onClick={handleCommit}
          disabled={isPatching}
          className="w-full text-xs font-semibold py-1.5 rounded-lg transition-opacity disabled:opacity-40"
          style={{
            background: 'var(--green)',
            color: '#fff',
          }}
        >
          {isPatching ? 'Applying...' : 'Apply'}
        </button>
      </div>
    </div>
  )
}

// ── Sub-components ──────────────────────────────────

function Section({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      {label && (
        <div className="text-xs font-semibold mb-1.5 uppercase tracking-wider"
             style={{ color: 'var(--text-muted)', fontFamily: 'DM Mono, monospace' }}>
          {label}
        </div>
      )}
      <div className="flex flex-col gap-1.5">{children}</div>
    </div>
  )
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-2">
      {label && (
        <span className="text-xs w-14 flex-shrink-0"
              style={{ color: 'var(--text-muted)' }}>
          {label}
        </span>
      )}
      <div className="flex-1">{children}</div>
    </div>
  )
}

function Toggle({
  active, onClick, label, title, bold, italic, underline
}: {
  active: boolean
  onClick: () => void
  label: string
  title: string
  bold?: boolean
  italic?: boolean
  underline?: boolean
}) {
  return (
    <button
      title={title}
      onClick={onClick}
      className="w-7 h-7 rounded text-xs flex items-center justify-center transition-colors"
      style={{
        background: active ? 'var(--green)' : 'var(--surface2)',
        color: active ? '#fff' : 'var(--text-muted)',
        fontWeight: bold ? 'bold' : 'normal',
        fontStyle: italic ? 'italic' : 'normal',
        textDecoration: underline ? 'underline' : 'none',
      }}
    >
      {label}
    </button>
  )
}

function ColorInput({
  value, onChange, onCommit
}: {
  value: string
  onChange: (v: string) => void
  onCommit: () => void
}) {
  return (
    <div className="flex items-center gap-1.5">
      <input
        type="color"
        value={value}
        onChange={e => onChange(e.target.value)}
        onBlur={onCommit}
        className="w-7 h-7 rounded cursor-pointer border-0 p-0"
        style={{ background: 'none' }}
      />
      <input
        type="text"
        value={value}
        onChange={e => onChange(e.target.value)}
        onBlur={onCommit}
        className="flex-1 text-xs rounded px-2 py-1"
        style={inputStyle}
        placeholder="#000000"
      />
    </div>
  )
}

function SliderInput({
  value, min, max, unit, onChange, onCommit
}: {
  value: number
  min: number
  max: number
  unit: string
  onChange: (v: number) => void
  onCommit: () => void
}) {
  return (
    <div className="flex items-center gap-1.5">
      <input
        type="range"
        min={min}
        max={max}
        value={value}
        onChange={e => onChange(Number(e.target.value))}
        onMouseUp={onCommit}
        onTouchEnd={onCommit}
        className="flex-1 h-1 accent-green-500"
      />
      <span className="text-xs w-10 text-right"
            style={{ color: 'var(--text-muted)' }}>
        {value}{unit}
      </span>
    </div>
  )
}

// ── Utilities ───────────────────────────────────────

const inputStyle: React.CSSProperties = {
  background: 'var(--surface2)',
  color: 'var(--text)',
  border: '1px solid var(--border)',
  outline: 'none',
}

function parsePx(value: string): number {
  return Math.round(parseFloat(value) || 0)
}

function parseDeg(value: string): number {
  return Math.round(parseFloat(value) || 0)
}

function alignIcon(align: string): string {
  const text: Record<string, string> = {
    left: '←', center: '↔', right: '→', justify: '≡'
  }
  return text[align] ?? align[0]
}

function rgbToHex(rgb: string): string {
  if (!rgb || rgb === 'transparent' || rgb === 'rgba(0, 0, 0, 0)') return '#000000'
  if (rgb.startsWith('#')) return rgb
  const match = rgb.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/)
  if (!match) return '#000000'
  const [, r, g, b] = match
  return '#' + [r, g, b].map(n => parseInt(n).toString(16).padStart(2, '0')).join('')
}
