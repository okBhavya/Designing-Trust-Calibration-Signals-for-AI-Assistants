import { describe, expect, it } from 'vitest';
import { hashAnswer } from '../src/core/hash';

describe('hashAnswer', () => {
  it('is deterministic and ignores surrounding whitespace', async () => {
    const first = await hashAnswer('  A reliable answer  ');
    const second = await hashAnswer('A reliable answer');
    expect(first).toBe(second);
    expect(first).toHaveLength(64);
  });
});
