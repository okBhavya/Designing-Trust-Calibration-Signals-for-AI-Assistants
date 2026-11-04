import { describe, expect, it } from 'vitest';
import { CompletionTracker } from '../src/core/completion';
import { DuplicateGuard } from '../src/core/duplicateGuard';
import { isSignalResponse } from '../src/signals/response';
import { mountOverlay } from '../src/overlay/mountOverlay';

describe('CompletionTracker', () => {
  it('requires two identical non-streaming samples', () => {
    const tracker = new CompletionTracker();
    const container = document.createElement('article');
    expect(tracker.isStable(container, { text: 'answer', streaming: true })).toBe(false);
    expect(tracker.isStable(container, { text: 'answer', streaming: false })).toBe(false);
    expect(tracker.isStable(container, { text: 'answer', streaming: false })).toBe(true);
  });
});

describe('DuplicateGuard', () => {
  it('allows a new hash and rejects the same hash', () => {
    const guard = new DuplicateGuard();
    const container = document.createElement('article');
    expect(guard.hasChanged(container, 'a')).toBe(true);
    expect(guard.hasChanged(container, 'a')).toBe(false);
    expect(guard.hasChanged(container, 'b')).toBe(true);
  });
});

describe('signal response validation', () => {
  it('accepts a versioned response and rejects malformed data', () => {
    expect(isSignalResponse({ status: 'signal', modelVersion: 'mock-v1', confidence: 'high' })).toBe(true);
    expect(isSignalResponse({ status: 'signal' })).toBe(false);
    expect(isSignalResponse(null)).toBe(false);
  });

  describe('overlay mounting', () => {
    it('keeps separate hosts for sibling answers and accepts a backend signal', async () => {
      const first = document.createElement('article');
      const second = document.createElement('article');
      document.body.append(first, second);
      const signal = {
        status: 'signal' as const,
        confidence: 'high' as const,
        explanation: 'Backend mock response.',
        modelVersion: 'mock-v1',
      };
      expect(mountOverlay(first, signal)).not.toBe(mountOverlay(second, signal));
      await new Promise((resolve) => setTimeout(resolve, 0));
      expect(mountOverlay(first, signal).shadowRoot?.textContent).toContain('High confidence');
    });
  });
});
