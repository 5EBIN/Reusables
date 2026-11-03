// Which folders of a file tree are closed, remembered per scope. A folder missing from the saved map is open (a new folder shows up open).
// Pure (the caller passes the storage text), erasable TypeScript only (node --test imports it).
export type OpenMap = Record<string, boolean>

export const treeOpenKey = (projectId: string): string => `app-tree-open:${projectId}`

/** The saved map, or {} when there is none or it is not a map of booleans (an old or damaged value is ignored, never trusted). */
export function parseOpenMap(raw: string | null | undefined): OpenMap {
  if (!raw) return {}
  try {
    const v: unknown = JSON.parse(raw)
    if (typeof v !== "object" || v === null || Array.isArray(v)) return {}
    const out: OpenMap = {}
    for (const [k, val] of Object.entries(v)) if (typeof val === "boolean") out[k] = val
    return out
  } catch { return {} }
}

/** The map after a folder was toggled. Open is the default, so only a closed folder is stored (the map stays small and a re-opened folder leaves it). */
export function toggleOpen(map: OpenMap, id: string): OpenMap {
  const open = map[id] ?? true
  const next = { ...map }
  if (open) next[id] = false
  else delete next[id]
  return next
}

export const isFolderOpen = (map: OpenMap, id: string): boolean => map[id] ?? true
