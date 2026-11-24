import { describe, expect, it } from 'vitest';
import raw from '../contracts/signal_responses.json?raw';
import { isSignalResponse } from '../src/signals/response';

// Extension half of the signal-response contract. apps/api/tests/test_contract.py checks that the
// backend still produces exactly these responses; here the extension's validator must accept them.
const { responses } = JSON.parse(raw) as { responses: Record<string, Record<string, unknown>> };

describe('backend signal responses satisfy the extension contract', () => {
  it.each(Object.entries(responses))('%s', (_name, response) => {
    expect(isSignalResponse(response)).toBe(true);
    for (const flag of (response.sentenceFlags as Array<Record<string, unknown>>) ?? []) {
      expect(Number.isInteger(flag.sentenceIndex)).toBe(true);
      expect(flag).not.toHaveProperty('sentence_index');
    }
  });

  it('rejects the old snake_case sentence flag field', () => {
    const response = { ...responses.selfconsistency_with_flags };
    response.sentenceFlags = [{ sentence_index: 1, label: 'low_agreement' }];
    expect(isSignalResponse(response)).toBe(false);
  });
});
