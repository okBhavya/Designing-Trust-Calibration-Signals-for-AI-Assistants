import type { PlatformId } from './contracts';

/** On in development, or in a build made with WXT_DIAGNOSTICS=1 (for debugging a site in the field). */
const enabled = import.meta.env.DEV || import.meta.env.WXT_DIAGNOSTICS === '1';

export function diagnostic(
  event: string,
  details: { platform?: PlatformId; count?: number; streaming?: boolean; status?: string; length?: number } = {},
): void {
  if (!enabled) return;
  console.info(`[CalibrAI] ${event}`, details);
}
