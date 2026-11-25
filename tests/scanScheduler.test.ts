import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { CompletionTracker } from '../src/core/completion';
import { createScanScheduler, MUTATION_SCAN_DELAY_MS, SETTLE_SCAN_DELAY_MS } from '../src/core/scanScheduler';

describe('scan scheduler', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it('captures an answer even when the page stops changing as soon as streaming ends', async () => {
    // ChatGPT/Gemini case: the last mutation is the one that ends streaming; nothing changes afterwards.
    const container = document.createElement('div');
    const completion = new CompletionTracker();
    const captured: string[] = [];
    let streaming = true;
    const scan = vi.fn(async () => {
      // Same check as entrypoints/content.ts.
      const sample = { text: 'Paris.', streaming };
      if (streaming || !completion.isStable(container, sample)) return true;
      captured.push(sample.text);
      return false;
    });
    const scheduler = createScanScheduler(scan, { setTimeout: (cb, ms) => setTimeout(cb, ms) });

    scheduler.scanNow(); // start-up scan while streaming
    await vi.advanceTimersByTimeAsync(0);
    streaming = false;
    scheduler.onMutation(); // the mutation that ends streaming, and the last one
    await vi.advanceTimersByTimeAsync(MUTATION_SCAN_DELAY_MS);
    expect(captured).toEqual([]); // first stable-looking sample only

    await vi.advanceTimersByTimeAsync(SETTLE_SCAN_DELAY_MS);
    expect(captured).toEqual(['Paris.']);

    await vi.advanceTimersByTimeAsync(10 * SETTLE_SCAN_DELAY_MS);
    expect(captured).toEqual(['Paris.']); // no polling once nothing is settling
  });

  it('coalesces a burst of mutations into one scan', async () => {
    const scan = vi.fn(async () => false);
    const scheduler = createScanScheduler(scan, { setTimeout: (cb, ms) => setTimeout(cb, ms) });
    for (let i = 0; i < 20; i += 1) scheduler.onMutation();
    await vi.advanceTimersByTimeAsync(MUTATION_SCAN_DELAY_MS);
    expect(scan).toHaveBeenCalledTimes(1);
  });
});
