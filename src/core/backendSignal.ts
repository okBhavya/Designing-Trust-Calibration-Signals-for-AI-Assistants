import type { CaptureRequest, SignalResponse } from './contracts';
import { isSignalResponse } from '../signals/response';
import type { ExtensionRuntimeConfig } from './runtimeConfig';

export async function requestBackendSignal(
  request: CaptureRequest,
  config: ExtensionRuntimeConfig,
  fetchImpl: typeof fetch = fetch,
): Promise<SignalResponse> {
  if (!config.participantId || !config.sessionToken) {
    throw new Error('API mode requires a participant ID and session token');
  }
  const endpoint = new URL(config.apiBaseUrl);
  if (endpoint.protocol !== 'https:' && endpoint.hostname !== '127.0.0.1' && endpoint.hostname !== 'localhost') {
    throw new Error('API mode requires HTTPS outside local development');
  }
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 8_000);
  try {
    const response = await fetchImpl(`${endpoint.toString().replace(/\/$/, '')}/v1/signal`, {
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
