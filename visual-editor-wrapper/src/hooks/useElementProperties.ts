import { useCallback } from 'react'

export type ElementType =
  | 'text'
  | 'button'
  | 'image'
  | 'container'
  | 'input'
  | 'generic'

export interface ElementProperties {
  // identity
  selector: string
  elementType: ElementType
  tagName: string

  // typography (text, button)
  fontFamily?: string
  fontSize?: string
  fontWeight?: string
  fontStyle?: string          // 'italic' | 'normal'
  textDecoration?: string     // 'underline' | 'none'
  color?: string
  lineHeight?: string
  letterSpacing?: string
  textAlign?: string

  // background
  backgroundColor?: string

  // box
  borderRadius?: string
  borderColor?: string
  borderWidth?: string
  padding?: string
  opacity?: string
  width?: string
  height?: string
  gap?: string

  // image specific
  objectFit?: string
  rotation?: string           // from transform: rotate(Xdeg)
}

const TEXT_TAGS = new Set(['H1','H2','H3','H4','H5','H6','P','SPAN','A','LABEL','LI','TD','TH'])
const BUTTON_TAGS = new Set(['BUTTON'])
const IMAGE_TAGS = new Set(['IMG'])
const CONTAINER_TAGS = new Set(['DIV','SECTION','NAV','HEADER','FOOTER','ARTICLE','ASIDE','MAIN'])
const INPUT_TAGS = new Set(['INPUT','TEXTAREA','SELECT'])

export function detectElementType(tagName: string): ElementType {
  const t = tagName.toUpperCase()
  if (TEXT_TAGS.has(t)) return 'text'
  if (BUTTON_TAGS.has(t)) return 'button'
  if (IMAGE_TAGS.has(t)) return 'image'
  if (CONTAINER_TAGS.has(t)) return 'container'
  if (INPUT_TAGS.has(t)) return 'input'
  return 'generic'
}

function extractRotation(transform: string): string {
  const match = transform.match(/rotate\(([^)]+)\)/)
  return match ? match[1] : '0deg'
}

export function useElementProperties() {
  const readProperties = useCallback(
    (el: Element, selector: string): ElementProperties => {
      const styles = (el.ownerDocument?.defaultView ?? window).getComputedStyle(el)

      const tagName = el.tagName
      const elementType = detectElementType(tagName)

      const base: ElementProperties = {
        selector,
        elementType,
        tagName,
        backgroundColor: styles.backgroundColor || '',
        borderRadius: styles.borderRadius || '0px',
        borderColor: styles.borderColor || '',
        borderWidth: styles.borderWidth || '0px',
        opacity: styles.opacity || '1',
        width: styles.width || 'auto',
        height: styles.height || 'auto',
        rotation: extractRotation(styles.transform || ''),
      }

      if (elementType === 'text' || elementType === 'button') {
        Object.assign(base, {
          fontFamily: styles.fontFamily || '',
          fontSize: styles.fontSize || '16px',
          fontWeight: styles.fontWeight || '400',
          fontStyle: styles.fontStyle || 'normal',
          textDecoration: styles.textDecoration || 'none',
          color: styles.color || '',
          lineHeight: styles.lineHeight || 'normal',
          letterSpacing: styles.letterSpacing || '0px',
          textAlign: styles.textAlign || 'left',
          padding: styles.padding || '0px',
        })
      }

      if (elementType === 'container') {
        Object.assign(base, {
          padding: styles.padding || '0px',
          gap: styles.gap || '0px',
        })
      }

      if (elementType === 'image') {
        Object.assign(base, {
          objectFit: styles.objectFit || 'cover',
        })
      }

      if (elementType === 'input') {
        Object.assign(base, {
          color: styles.color || '',
          fontSize: styles.fontSize || '16px',
          padding: styles.padding || '0px',
        })
      }

      return base
    },
    []
  )

  return { readProperties }
}
