import type { ReactNode } from 'react'
import { cx } from '@/lib/cx'

export interface Column<Row> { key: string; header: ReactNode; cell: (row: Row) => ReactNode; align?: 'left' | 'right'; className?: string }

/** A plain data table: sticky-free, scrolls sideways inside its own box on a narrow screen, and says so when it is empty. */
export function Table<Row>({ columns, rows, rowKey, caption, empty = 'Nothing to show', className }: {
  columns: Column<Row>[]
  rows: Row[]
  rowKey: (row: Row) => string
  /** The table's accessible name. */
  caption: string
  empty?: ReactNode
  className?: string
}) {
  return (
    <div className={cx('overflow-x-auto rounded-r3 border border-line2 bg-card', className)}>
      <table className="w-full border-collapse text-sm text-t1">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr className="border-b border-line2 bg-sunk">
            {columns.map(c => (
              <th key={c.key} scope="col" className={cx('px-3 py-2 text-xs font-semibold uppercase tracking-wide text-t3', c.align === 'right' ? 'text-right' : 'text-left', c.className)}>{c.header}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 && <tr><td colSpan={columns.length} className="px-3 py-6 text-center text-t3">{empty}</td></tr>}
          {rows.map(r => (
            <tr key={rowKey(r)} className="border-b border-line last:border-b-0 hover:bg-hover">
              {columns.map(c => <td key={c.key} className={cx('px-3 py-2 align-top', c.align === 'right' && 'text-right', c.className)}>{c.cell(r)}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
