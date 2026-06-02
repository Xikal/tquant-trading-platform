export const PUBLIC_API_PATHS = [
  "/app/bootstrap",
] as const

const PUBLIC_API_PREFIXES = [
  "/auth/",
  "/app/update/android",
] as const

export function isPublicApiPath(path: string): boolean {
  return PUBLIC_API_PATHS.some((publicPath) => path === publicPath)
    || PUBLIC_API_PREFIXES.some((prefix) => path.startsWith(prefix))
}
