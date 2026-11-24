import { describe, expect, it, vi } from 'vitest';
import { BACKEND_SIGNAL_TIMEOUT_MS, requestBackendSignal } from '../src/core/backendSignal';
import { mountOverlay } from '../src/overlay/mountOverlay';
import type { CaptureRequest } from '../src/core/contracts';

const request: CaptureRequest = {
  type: 'capture-answer',
  platform: 'gemini',
  prompt: 'Explain calibration.',
  answer: 'Calibration compares confidence with accuracy.',
  answerHash: 'a'.repeat(64),
};

const config = {
  mode: 'api' as const,
  apiBaseUrl: 'http://127.0.0.1:8000',
  participantId: '00000000-0000-0000-0000-000000000001',
  sessionToken: 'session-token',
};

it('sends an authenticated capture and validates the backend response', async () => {
  const fetchImpl = vi.fn<typeof fetch>().mockResolvedValue(
    new Response(JSON.stringify({
      status: 'signal',
      confidence: 'high',
      score: 0.85,
      explanation: 'Mock response.',
      modelVersion: 'mock-v1',
      processingLatencyMs: 0,
    }), { status: 200 }),
  );

  await expect(requestBackendSignal(request, config, fetchImpl)).resolves.toMatchObject({
    status: 'signal',
    confidence: 'high',
    modelVersion: 'mock-v1',
  });
  expect(fetchImpl).toHaveBeenCalledWith(
    'http://127.0.0.1:8000/v1/signal',
    expect.objectContaining({
      method: 'POST',
      headers: expect.objectContaining({ Authorization: 'Bearer session-token' }),
    }),
  );
  expect(JSON.parse(fetchImpl.mock.calls[0][1]?.body as string)).toMatchObject({
    platform: 'gemini',
    answer_hash: 'a'.repeat(64),
  });
});

describe('backend request safety', () => {
  it('rejects non-HTTPS production endpoints', async () => {
    await expect(requestBackendSignal(request, { ...config, apiBaseUrl: 'http://api.example.test' }))
      .rejects.toThrow('HTTPS');
  });

  it('rejects malformed backend responses', async () => {
    const fetchImpl = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ status: 'signal', confidence: 'invalid' }), { status: 200 }),
    );
    await expect(requestBackendSignal(request, config, fetchImpl)).rejects.toThrow('Backend returned 200');
  });

  it('rejects backend errors without exposing response content', async () => {
    const fetchImpl = vi.fn<typeof fetch>().mockResolvedValue(
      new Response('private prompt content', { status: 503 }),
    );
    await expect(requestBackendSignal(request, config, fetchImpl)).rejects.toThrow('Backend returned 503');
  });

  it('requires both participant and session configuration', async () => {
    await expect(requestBackendSignal(request, { ...config, sessionToken: '' })).rejects.toThrow(
      'participant ID and session token',
    );
  });
});

describe('backend signal timeout', () => {
  it('waits 25 s for slow providers, keeping the Checking overlay up, then aborts', async () => {
    vi.useFakeTimers();
    try {
      let aborted = false;
      const fetchImpl = vi.fn<typeof fetch>().mockImplementation(
        (_url, init) =>
          new Promise<Response>((_resolve, reject) => {
            init?.signal?.addEventListener('abort', () => {
              aborted = true;
              reject(new DOMException('Aborted', 'AbortError'));
            });
          }),
      );
      const container = document.createElement('article');
      document.body.append(container);
      const host = mountOverlay(container, { status: 'checking', modelVersion: 'api' });

      const pending = requestBackendSignal(request, config, fetchImpl);
      const outcome = pending.then(() => 'resolved', () => 'rejected');

      await vi.advanceTimersByTimeAsync(20_000);
      expect(aborted).toBe(false);
      expect(host.shadowRoot?.textContent).toContain('Checking answer');

      await vi.advanceTimersByTimeAsync(BACKEND_SIGNAL_TIMEOUT_MS - 20_000);
      expect(aborted).toBe(true);
      await expect(outcome).resolves.toBe('rejected');
      expect(BACKEND_SIGNAL_TIMEOUT_MS).toBe(25_000);
    } finally {
      vi.useRealTimers();
    }
  });
});
