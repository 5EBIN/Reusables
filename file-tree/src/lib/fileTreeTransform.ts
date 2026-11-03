/**
 * fileTreeTransform.ts
 * Converts the flat FileEntry[] from the API into a nested TreeNode[]
 * that react-arborist consumes.
 *
 * Leaves have NO `children` field  → arborist infers them as leaves.
 * Folders have `children: TreeNode[]` (may be empty while subtree is building).
 *
 * Pure function — memoize at the call site with useMemo.
 */

export interface FileEntry {
  file_path: string
  status?: string
  code?: string
  revision?: number
  added_lines?: number
  removed_lines?: number
  [extra: string]: unknown   // anything else the host keeps on a file
}

export interface TreeNode {
  id: string             // folder = accumulated path; leaf = full file_path (stable, unique)
  name: string           // single path segment shown in the row
  children?: TreeNode[]  // present ↔ folder; absent ↔ leaf
  file?: FileEntry       // leaf-only payload
}

export function buildFileTree(files: readonly FileEntry[]): TreeNode[] {
  const root: TreeNode = { id: '__root__', name: '', children: [] }

  for (const file of files) {
    const parts = file.file_path.split('/').filter(Boolean)
    let cursor = root
    let acc = ''

    for (let i = 0; i < parts.length; i++) {
      const part = parts[i]
      acc = acc ? `${acc}/${part}` : part
      const isLeaf = i === parts.length - 1

      if (isLeaf) {
        cursor.children!.push({ id: file.file_path, name: part, file })
      } else {
        let dir = cursor.children!.find(c => c.id === acc && c.children !== undefined)
        if (!dir) {
          dir = { id: acc, name: part, children: [] }
          cursor.children!.push(dir)
        }
        cursor = dir
      }
    }
  }

  // Folders before files, then alpha within each group.
  const sort = (nodes: TreeNode[]): TreeNode[] => {
    nodes.sort((a, b) => {
      const af = a.children !== undefined
      const bf = b.children !== undefined
      if (af !== bf) return af ? -1 : 1
      return a.name.localeCompare(b.name)
    })
    for (const n of nodes) if (n.children) sort(n.children)
    return nodes
  }

  return sort(root.children!)
}

/** Every file under a node (the node itself when it is a file). */
export function filesUnder(node: TreeNode): FileEntry[] {
  if (node.file) return [node.file]
  return (node.children ?? []).flatMap(filesUnder)
}
