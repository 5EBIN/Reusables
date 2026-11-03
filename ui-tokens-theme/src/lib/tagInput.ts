// What TagInput adds. Pure, erasable TypeScript only (node --test imports it).

/** The list with `raw` added: trimmed, empty ignored, a duplicate (any letter case) ignored. Returns the SAME array when nothing was added, so a caller can tell. */
export function addTag(list: string[], raw: string): string[] {
  const tag = raw.trim().replace(/,+$/, "").trim()
  if (!tag) return list
  if (list.some(t => t.toLowerCase() === tag.toLowerCase())) return list
  return [...list, tag]
}
