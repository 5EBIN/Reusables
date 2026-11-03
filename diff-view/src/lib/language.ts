// Monaco language detection from a file path's extension.
// Extracted from code/page.tsx so DiffView (mini + full modes) and the editor
// itself share one source instead of two independently-maintained maps.

const LANGUAGE_MAP: Record<string, string> = {
  ts: 'typescript', tsx: 'typescript', js: 'javascript', jsx: 'javascript',
  py: 'python', java: 'java', go: 'go', rs: 'rust',
  css: 'css', html: 'html', json: 'json', yml: 'yaml', yaml: 'yaml',
  md: 'markdown', sh: 'shell', dockerfile: 'dockerfile',
}

export function getLanguage(path: string): string {
  const ext = path.split('.').pop()?.toLowerCase() ?? ''
  return LANGUAGE_MAP[ext] || 'plaintext'
}
