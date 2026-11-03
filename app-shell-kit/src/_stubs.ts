// Stubs for names this module imports from the host application. Replace each with the host's real implementation.
// They only keep the imports resolvable; calling a stubbed function throws.
/* eslint-disable @typescript-eslint/no-explicit-any */
function notProvided(name: string): any {
  const fn: any = (..._args: any[]) => { throw new Error(`${name}: the host must provide this`) }
  return fn
}

export const UsagePanel: any = notProvided('UsagePanel')
export const useAuthUser: any = notProvided('useAuthUser')
export const useSignOut: any = notProvided('useSignOut')
