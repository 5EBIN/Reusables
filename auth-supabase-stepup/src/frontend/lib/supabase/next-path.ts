/** `next` is a same-site path or nothing: never an absolute or protocol-relative URL (open-redirect guard). */
export function safeNext(v: string | null | undefined, fallback = "/overview"): string {
  if (!v || !v.startsWith("/") || v.startsWith("//") || v.includes("\\") || /[\r\n]/.test(v)) return fallback;
  return v;
}
