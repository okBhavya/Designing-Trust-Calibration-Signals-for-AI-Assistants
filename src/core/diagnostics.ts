import type { PlatformId } from './contracts';

const enabled = import.meta.env.DEV;

export function diagnostic(
  event: string,
  details: { platform?: PlatformId; count?: number; streaming?: boolean; status?: string } = {},
): void {
  if (!enabled) return;
  console.debug(`[CalibrAI] ${event}`, details);
}
