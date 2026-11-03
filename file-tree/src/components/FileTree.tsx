import { useMemo } from 'react'
import { Tree, type NodeRendererProps } from 'react-arborist'
import { buildFileTree, type FileEntry, type TreeNode } from '@/lib/fileTreeTransform'

export interface FileTreeProps {
  files: readonly FileEntry[]
  height: number
  selectedPath?: string | null
  onOpen: (file: FileEntry) => void
  /** Extra text shown after a file name (a status, a count). */
  note?: (file: FileEntry) => string | null
}

/** A virtualised file tree (react-arborist): folders first, arrow keys move, Right opens and Left closes a folder. */
export function FileTree({ files, height, selectedPath, onOpen, note }: FileTreeProps) {
  const data = useMemo(() => buildFileTree(files), [files])
  function Row({ node, style, dragHandle }: NodeRendererProps<TreeNode>) {
    const isFolder = node.isInternal
    const file = node.data.file
    return (
      <div ref={dragHandle} style={style} role="treeitem" aria-selected={!!file && file.file_path === selectedPath}
        onClick={() => { if (isFolder) node.toggle(); else if (file) onOpen(file) }}>
        <span aria-hidden="true">{isFolder ? (node.isOpen ? '▾ ' : '▸ ') : '  '}</span>
        {node.data.name}
        {file && note?.(file) ? <small> {note(file)}</small> : null}
      </div>
    )
  }
  return (
    <Tree<TreeNode> data={data} idAccessor="id" openByDefault disableDrag disableEdit disableMultiSelection indent={14} rowHeight={28} height={height} width="100%">
      {Row}
    </Tree>
  )
}
