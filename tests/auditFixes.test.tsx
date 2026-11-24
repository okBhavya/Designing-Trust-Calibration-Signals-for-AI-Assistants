import { describe, expect, it, vi } from 'vitest';
import { requestCachedBackendSignal } from '../src/core/backendSignal';
import type { CaptureRequest, SignalResponse } from '../src/core/contracts';
import { signalCacheKey, type SignalCacheStorage } from '../src/core/signalCache';

const hash = 'a'.repeat(64);
const request: CaptureRequest = {
  type: 'capture-answer',
  platform: 'claude',
  prompt: 'Private prompt text',
  answer: 'Private answer text',
  answerHash: hash,
};
const config = {
  mode: 'api' as const,
  apiBaseUrl: 'http://127.0.0.1:8000',
  participantId: '00000000-0000-0000-0000-000000000001',
  sessionToken: 'session-token',
};
const backendSignal: SignalResponse = {
  status: 'signal',
  confidence: 'high',
  assessmentState: 'abstained',
  score: 0.85,
  explanation: 'Mock response.',
  modelVersion: 'mock-v1',
};

function memoryStorage(): SignalCacheStorage & { items: Record<string, unknown> } {
  const items: Record<string, unknown> = {};
  return {
    items,
    get: async (key) => (key in items ? { [key]: items[key] } : {}),
    set: async (values) => void Object.assign(items, values),
  };
}

const okFetch = () =>
  vi.fn<typeof fetch>().mockImplementation(async () => new Response(JSON.stringify(backendSignal), { status: 200 }));

describe('bug 1: signal cache by answer hash', () => {
  it('serves a repeat capture from session storage without a second request', async () => {
    const storage = memoryStorage();
    const fetchImpl = okFetch();
    await expect(requestCachedBackendSignal(request, config, storage, fetchImpl)).resolves.toMatchObject(backendSignal);
    await expect(requestCachedBackendSignal(request, config, storage, fetchImpl)).resolves.toMatchObject(backendSignal);
    expect(fetchImpl).toHaveBeenCalledTimes(1);
    expect(storage.items[signalCacheKey(config.participantId, hash)]).toMatchObject(backendSignal);
  });

  it('keeps cache entries separate per participant', async () => {
    const storage = memoryStorage();
    const fetchImpl = okFetch();
    await requestCachedBackendSignal(request, config, storage, fetchImpl);
    await requestCachedBackendSignal(
      request,
      { ...config, participantId: '00000000-0000-0000-0000-000000000002' },
      storage,
      fetchImpl,
    );
    expect(fetchImpl).toHaveBeenCalledTimes(2);
  });

  it('does not cache failures and still delivers when storage is broken', async () => {
    const storage = memoryStorage();
    const failing = vi.fn<typeof fetch>().mockResolvedValue(new Response('', { status: 503 }));
    await expect(requestCachedBackendSignal(request, config, storage, failing)).rejects.toThrow('503');
    expect(storage.items).toEqual({});

    const broken: SignalCacheStorage = {
      get: () => Promise.reject(new Error('unavailable')),
      set: () => Promise.reject(new Error('unavailable')),
    };
    await expect(requestCachedBackendSignal(request, config, broken, okFetch())).resolves.toMatchObject(backendSignal);
  });
});
