import type { SignalResponse } from './contracts';
import { isSignalResponse } from '../signals/response';

/** The subset of chrome.storage.session used by the cache. */
export interface SignalCacheStorage {
  get(keys: string): Promise<Record<string, unknown>>;
  set(items: Record<string, unknown>): Promise<void>;
}

export function signalCacheKey(participantId: string, answerHash: string): string {
  return `signal:${participantId}:${answerHash}`;
}

export async function getCachedSignal(
  storage: SignalCacheStorage,
  participantId: string,
  answerHash: string,
): Promise<SignalResponse | undefined> {
  const key = signalCacheKey(participantId, answerHash);
  try {
    const value = (await storage.get(key))[key];
    return isSignalResponse(value) ? value : undefined;
  } catch {
    return undefined;
  }
}

/** Only completed signals are cached; failures are retried on the next capture. */
export async function storeCachedSignal(
  storage: SignalCacheStorage,
  participantId: string,
  answerHash: string,
  signal: SignalResponse,
): Promise<void> {
  if (signal.status !== 'signal') return;
  try {
    await storage.set({ [signalCacheKey(participantId, answerHash)]: signal });
  } catch {
    // A cache write failure must never block delivering the signal.
  }
}
