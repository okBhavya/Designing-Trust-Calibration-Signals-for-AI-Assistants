import type { CaptureRequest, SignalResponse } from './contracts';
import { isSignalResponse } from '../signals/response';
import type { ExtensionRuntimeConfig } from './runtimeConfig';
import { getCachedSignal, storeCachedSignal, type SignalCacheStorage } from './signalCache';

/**
 * How long the background worker waits for POST /v1/signal. The selfconsistency provider makes
 * 7 LLM calls (about 8-20 s); the backend gives up at 20 s, so this leaves headroom.
 * The overlay keeps showing "Checking answer" for the whole wait.
 */
export const BACKEND_SIGNAL_TIMEOUT_MS = 25_000;

export function resolveApiEndpoint(config: ExtensionRuntimeConfig): string {
  if (!config.participantId || !config.sessionToken) {
    throw new Error('API mode requires a participant ID and session token');
  }
  const endpoint = new URL(config.apiBaseUrl);
  if (endpoint.protocol !== 'https:' && endpoint.hostname !== '127.0.0.1' && endpoint.hostname !== 'localhost') {
    throw new Error('API mode requires HTTPS outside local development');
  }
  return endpoint.toString().replace(/\/$/, '');
}

export async function requestBackendSignal(
  request: CaptureRequest,
  config: ExtensionRuntimeConfig,
  fetchImpl: typeof fetch = fetch,
): Promise<SignalResponse> {
  const base = resolveApiEndpoint(config);
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), BACKEND_SIGNAL_TIMEOUT_MS);
  try {
    const response = await fetchImpl(`${base}/v1/signal`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${config.sessionToken}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        participant_id: config.participantId,
        platform: request.platform,
        answer_hash: request.answerHash,
        prompt: request.prompt,
        answer: request.answer,
      }),
      signal: controller.signal,
    });
    if (!response.ok) {
      throw new Error(`Backend returned ${response.status}`);
    }
    const body: unknown = await response.json();
    if (!isSignalResponse(body)) {
      throw new Error(`Backend returned ${response.status}`);
    }
    return body;
  } finally {
    clearTimeout(timeout);
  }
}

/** Returns a cached signal for this participant and answer, so a page reload does not re-request it. */
export async function requestCachedBackendSignal(
  request: CaptureRequest,
  config: ExtensionRuntimeConfig,
  storage: SignalCacheStorage,
  fetchImpl: typeof fetch = fetch,
): Promise<SignalResponse> {
  const cached = await getCachedSignal(storage, config.participantId, request.answerHash);
  if (cached) return cached;
  const signal = await requestBackendSignal(request, config, fetchImpl);
  await storeCachedSignal(storage, config.participantId, request.answerHash, signal);
  return signal;
}
