/** The chat sites the content script runs on. */
export const SITE_HOST_PERMISSIONS = ['https://chatgpt.com/*', 'https://claude.ai/*', 'https://gemini.google.com/*'];

/** Local API ports (8010 when another dev server holds 8000). Development builds only. */
export const LOCAL_API_HOST_PERMISSIONS = ['http://127.0.0.1:8000/*', 'http://127.0.0.1:8010/*'];

/**
 * Normalizes WXT_API_ORIGIN (for example `https://calibrai-api.onrender.com`) to a bare origin.
 * Returns undefined when unset; throws when it is not an https origin, so a typo fails the build
 * instead of shipping an extension that cannot reach its backend.
 */
export function parseApiOrigin(value: string | undefined): string | undefined {
  const trimmed = value?.trim();
  if (!trimmed) return undefined;
  let url: URL;
  try {
    url = new URL(trimmed);
  } catch {
    throw new Error(`WXT_API_ORIGIN is not a URL: ${trimmed}`);
  }
  if (url.protocol !== 'https:') throw new Error(`WXT_API_ORIGIN must use https: ${trimmed}`);
  if ((url.pathname !== '/' && url.pathname !== '') || url.search || url.hash || url.username || url.password) {
    throw new Error(`WXT_API_ORIGIN must be an origin only, without a path: ${trimmed}`);
  }
  return url.origin;
}

/** host_permissions for a build: the chat sites, the deployed API, and local APIs in development builds. */
export function hostPermissions(apiOrigin: string | undefined, mode: string): string[] {
  const origin = parseApiOrigin(apiOrigin);
  return [
    ...SITE_HOST_PERMISSIONS,
    ...(origin ? [`${origin}/*`] : []),
    ...(mode === 'production' ? [] : LOCAL_API_HOST_PERMISSIONS),
  ];
}
