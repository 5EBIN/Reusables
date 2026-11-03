'use client'

import type { ComponentProps } from 'react'
import Dialog from './Dialog'

/** A panel that slides in from the right. It IS the Dialog (same focus trap, Esc, focus return and `blocking`), seated on the right edge: nothing is duplicated. */
export function Sheet(props: Omit<ComponentProps<typeof Dialog>, 'placement'>) {
  return <Dialog {...props} placement="right" />
}
