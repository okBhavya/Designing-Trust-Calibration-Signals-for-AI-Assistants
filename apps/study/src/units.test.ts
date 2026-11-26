import { describe, expect, it, vi } from 'vitest';
import { describeSignal } from '@calibrai/overlay/viewModel';
import { ApiError, createHttpApi, type Enrollment } from './api';
import { flagReason, loadPracticeItems, loadStudyItems, toSignalResponse, validateStudyItems } from './items';
import { isTransient, Outbox } from './outbox';
import { shuffle } from './random';

describe('study items', () => {
  it('bundles data/questions.json: 30 items, 21 correct', () => {
    const items = loadStudyItems();
    expect(items).toHaveLength(30);
    expect(items.filter((item) => item.ai_is_correct)).toHaveLength(21);
  });

  it('rejects a study set that does not fit the protocol', () => {
    const items = loadStudyItems();
    expect(() => validateStudyItems(items.slice(1))).toThrow(/30 items with 21 correct/);
    expect(() => validateStudyItems([{ ...items[0], signal: { ...items[0].signal, level: 'great' } }])).toThrow(/shape/);
    expect(() => validateStudyItems([...items.slice(1), items[1]])).toThrow(/duplicate/);
  });

  it('shows the real claim counts in the pill, as the extension would', () => {
    const item = loadStudyItems().find((entry) => entry.signal.level === 'high')!;
    const view = describeSignal(toSignalResponse(item));
    expect(view.kind).toBe('high');
    expect(view.reason).toMatch(/^\d\/\d checks agree$/);
    expect(view.claims.length).toBeGreaterThan(0);
  });

  it('gives a not-checkable pill for insufficient evidence', () => {
    const item = loadStudyItems().find((entry) => entry.signal.level === 'insufficient_evidence')!;
    expect(describeSignal(toSignalResponse(item)).kind).toBe('not-checkable');
  });

  it("uses each flagged sentence's own explanation for its tooltip", () => {
    const [, wrong] = loadPracticeItems();
    expect(flagReason(wrong, 0)).toBe(wrong.signal.sentence_flags![0].explanation);
    expect(flagReason({ ...wrong, signal: { ...wrong.signal, sentence_flags: [] } }, 0)).toBe(wrong.signal.reason);
  });
});

describe('shuffle', () => {
  it('returns a permutation and leaves the input alone', () => {
    const input = Array.from({ length: 30 }, (_, i) => i);
    const output = shuffle(input);
    expect([...output].sort((a, b) => a - b)).toEqual(input);
    expect(input[0]).toBe(0);
  });

  it('is driven by the random source', () => {
    let seed = 1;
    const seeded = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
    const first = shuffle([1, 2, 3, 4, 5], seeded);
    seed = 1;
    expect(shuffle([1, 2, 3, 4, 5], seeded)).toEqual(first);
  });
});

describe('outbox', () => {
  const instant = { wait: () => Promise.resolve(), baseDelayMs: 1 };
  const flush = () => new Promise((resolve) => setTimeout(resolve, 0));

  it('retries temporary failures in order until each record is sent', async () => {
    const outbox = new Outbox(instant);
    const sent: string[] = [];
    let failures = 2;
    outbox.enqueue('first', 1, async () => {
      if (failures-- > 0) throw new ApiError(503, 'busy');
      sent.push('first');
    });
    outbox.enqueue('second', 2, async () => {
      sent.push('second');
    });
    expect(outbox.getState().pending).toBe(2);
    await flush();
    await flush();
    expect(sent).toEqual(['first', 'second']);
    expect(outbox.getState()).toEqual({ pending: 0, retrying: false, failed: [] });
  });

  it('keeps records the server rejects for good, with the reason, and carries on', async () => {
    const outbox = new Outbox(instant);
    const sent: string[] = [];
    outbox.enqueue('bad trial', { question_id: 'x' }, async () => {
      throw new ApiError(422, 'invalid');
    });
    outbox.enqueue('good', 2, async () => {
      sent.push('good');
    });
    await flush();
    expect(sent).toEqual(['good']);
    expect(outbox.getState().failed).toEqual([{ label: 'bad trial', payload: { question_id: 'x' }, error: 'invalid (HTTP 422)' }]);
  });

  it('backs off exponentially up to the cap', async () => {
    const waits: number[] = [];
    const outbox = new Outbox({ baseDelayMs: 1000, maxDelayMs: 4000, wait: async (ms) => void waits.push(ms) });
    let failures = 4;
    outbox.enqueue('x', 1, async () => {
      if (failures-- > 0) throw new ApiError(0, 'offline');
    });
    await flush();
    expect(waits).toEqual([1000, 2000, 4000, 4000]);
  });

  it('classifies errors', () => {
    expect([0, 408, 429, 500, 503].map((status) => isTransient(new ApiError(status, '')))).toEqual([true, true, true, true, true]);
    expect([400, 401, 403, 404, 409, 422].map((status) => isTransient(new ApiError(status, '')))).toEqual([false, false, false, false, false, false]);
    expect(isTransient(new TypeError('fetch failed'))).toBe(true);
  });
});

describe('http api', () => {
  const enrollment: Enrollment = { participantId: 'p-1', token: 'tok', condition: 'C', consentVersion: 'v1' };

  it('enrolls and posts with the session token', async () => {
    const calls: Array<[string, RequestInit]> = [];
    const fetchImpl = vi.fn(async (url: string | URL | Request, init?: RequestInit) => {
      calls.push([String(url), init!]);
      const body = String(url).endsWith('/enroll')
        ? { participant_id: 'p-1', access_token: 'tok', condition: 'C', consent_version: 'v1' }
        : { id: 'x', created: true };
      return new Response(JSON.stringify(body), { status: 201 });
    });
    const api = createHttpApi('http://api.test/', fetchImpl as typeof fetch);
    expect(await api.enroll('CODE', 'v1')).toEqual(enrollment);
    expect(JSON.parse(String(calls[0][1].body))).toEqual({ enrollment_code: 'CODE', consent_version: 'v1', consent: true });
    await api.postEvent(enrollment, 'tooltip_opened', { sentence_index: '0' });
    expect(calls[1][0]).toBe('http://api.test/v1/events');
    expect((calls[1][1].headers as Record<string, string>).Authorization).toBe('Bearer tok');
    expect(JSON.parse(String(calls[1][1].body))).toEqual({
      participant_id: 'p-1',
      event_type: 'tooltip_opened',
      metadata: { sentence_index: '0' },
    });
  });

  it('turns HTTP and network failures into ApiError', async () => {
    const rejecting = createHttpApi('http://api.test', (async () =>
      new Response(JSON.stringify({ detail: 'Invalid study enrollment code' }), { status: 401 })) as typeof fetch);
    await expect(rejecting.enroll('bad', 'v1')).rejects.toMatchObject({ status: 401, message: 'Invalid study enrollment code' });
    const offline = createHttpApi('http://api.test', (async () => {
      throw new TypeError('Failed to fetch');
    }) as typeof fetch);
    await expect(offline.postTrial(enrollment, {} as never)).rejects.toMatchObject({ status: 0 });
  });
});
