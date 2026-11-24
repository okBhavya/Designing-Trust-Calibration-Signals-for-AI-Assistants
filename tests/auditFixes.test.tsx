import { act } from 'react';
import { describe, expect, it, vi } from 'vitest';
import { requestCachedBackendSignal } from '../src/core/backendSignal';
import type { CaptureRequest, SignalResponse } from '../src/core/contracts';
import { isOverlayEventMessage, postBackendEvent, sendOverlayEvent, type OverlayEventMessage } from '../src/core/events';
import { signalCacheKey, type SignalCacheStorage } from '../src/core/signalCache';
import { modeModelVersion } from '../src/core/runtimeConfig';
import { activeSiteStatus } from '../src/core/activeSite';
import { geminiAdapter } from '../src/adapters/gemini';
import { isSignalResponse } from '../src/signals/response';
import { mountOverlay } from '../src/overlay/mountOverlay';

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

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

describe('bug 2: Gemini detects each answer once', () => {
  it('resolves message-content and nested matches to the outermost .model-response', () => {
    document.body.innerHTML = `
      <div class="user-query">First?</div>
      <div class="model-response" data-message-author-role="model">
        <message-content class="model-response-text"><p>First answer.</p></message-content>
      </div>
      <div class="user-query">Second?</div>
      <div class="model-response">
        <message-content class="model-response-text"><p>Second answer.</p></message-content>
      </div>`;
    const answers = geminiAdapter.findAnswers(document);
    expect(answers).toHaveLength(2);
    expect(answers.map((answer) => answer.container.className)).toEqual(['model-response', 'model-response']);
    expect(answers.map((answer) => answer.answer)).toEqual(['First answer.', 'Second answer.']);
  });
});

describe('bug 3: overlay events', () => {
  const event: OverlayEventMessage = {
    type: 'overlay-event',
    eventType: 'explanation_opened',
    platform: 'claude',
    answerHash: hash,
    modelVersion: 'reliability-fixture-v1',
    assessmentState: 'medium',
  };

  it('posts an event without prompt or answer text', async () => {
    const fetchImpl = vi.fn<typeof fetch>().mockResolvedValue(new Response('{}', { status: 200 }));
    await postBackendEvent(event, config, fetchImpl);
    expect(fetchImpl).toHaveBeenCalledWith('http://127.0.0.1:8000/v1/events', expect.objectContaining({ method: 'POST' }));
    const body = JSON.parse(fetchImpl.mock.calls[0][1]?.body as string);
    expect(body).toEqual({
      participant_id: config.participantId,
      event_type: 'explanation_opened',
      platform: 'claude',
      answer_hash: hash,
      metadata: { modelVersion: 'reliability-fixture-v1', assessmentState: 'medium' },
    });
    expect(JSON.stringify(body)).not.toMatch(/Private (prompt|answer)/);
  });

  it('sends nothing in mock mode', async () => {
    const fetchImpl = vi.fn<typeof fetch>();
    await postBackendEvent(event, { ...config, mode: 'mock' }, fetchImpl);
    expect(fetchImpl).not.toHaveBeenCalled();
  });

  it('validates event messages', () => {
    expect(isOverlayEventMessage(event)).toBe(true);
    expect(isOverlayEventMessage({ ...event, eventType: 'answer_copied' })).toBe(false);
    expect(isOverlayEventMessage({ ...event, answerHash: 'not-a-hash' })).toBe(false);
  });

  it('is fire-and-forget: send failures never throw', () => {
    expect(() => sendOverlayEvent(event, () => Promise.reject(new Error('no receiver')))).not.toThrow();
    expect(() => sendOverlayEvent(event, () => { throw new Error('context invalidated'); })).not.toThrow();
  });

  it('emits signal_shown once, explanation_opened on open, and signal_dismissed', async () => {
    const container = document.createElement('article');
    document.body.append(container);
    const onEvent = vi.fn();
    let host!: HTMLElement;
    await act(async () => {
      host = mountOverlay(container, { status: 'checking', modelVersion: 'api' }, { answerHash: hash, onEvent });
    });
    expect(onEvent).not.toHaveBeenCalled();
    await act(async () => {
      mountOverlay(container, backendSignal, { answerHash: hash, onEvent });
    });
    await act(async () => {
      mountOverlay(container, backendSignal, { answerHash: hash, onEvent });
    });
    expect(onEvent.mock.calls).toEqual([['signal_shown']]);

    const button = (label: string) =>
      Array.from(host.shadowRoot!.querySelectorAll('button')).find((element) => element.textContent === label)!;
    await act(async () => button('Why?').click());
    await act(async () => button('Hide details').click());
    expect(onEvent.mock.calls).toEqual([['signal_shown'], ['explanation_opened']]);

    await act(async () => button('Dismiss').click());
    expect(onEvent.mock.calls.at(-1)).toEqual(['signal_dismissed']);
    expect(host.shadowRoot!.querySelector('.calibrai-overlay')).toBeNull();
  });
});

describe('bug 7: nullable score', () => {
  it('accepts a null score and still rejects out-of-range scores', () => {
    expect(isSignalResponse({ status: 'signal', assessmentState: 'insufficient_evidence', score: null, modelVersion: 'x' })).toBe(true);
    expect(isSignalResponse({ status: 'signal', score: 1.5, modelVersion: 'x' })).toBe(false);
  });

  it('renders insufficient evidence without a score', async () => {
    const container = document.createElement('article');
    document.body.append(container);
    let host!: HTMLElement;
    await act(async () => {
      host = mountOverlay(container, {
        status: 'signal',
        assessmentState: 'insufficient_evidence',
        score: null,
        explanation: 'No evidence.',
        modelVersion: 'reliability-fixture-v1',
      });
    });
    expect(host.shadowRoot!.textContent).toContain('Insufficient evidence');
  });
});

describe('item 6: mode version and popup site', () => {
  it('labels placeholder overlays with the active mode', () => {
    expect(modeModelVersion('mock')).toBe('mock-v1');
    expect(modeModelVersion('api')).toBe('api');
  });

  it('names the current supported site', () => {
    expect(activeSiteStatus('https://chatgpt.com/c/1')).toBe('Active on ChatGPT');
    expect(activeSiteStatus('https://claude.ai/chat/1')).toBe('Active on Claude');
    expect(activeSiteStatus('https://gemini.google.com/app')).toBe('Active on Gemini');
    expect(activeSiteStatus('https://example.com/')).toBe('Not active on this page');
    expect(activeSiteStatus(undefined)).toBe('Not active on this page');
  });
});
