import { describe, expect, it } from 'vitest';
import contract from '@contracts/sentence_splits.json';
import { loadPracticeItems, loadStudyItems } from './items';
import { splitSentences } from './sentences';

describe('sentence splitting matches the backend', () => {
  it.each(contract.map((entry, index) => [index, entry] as const))('contract case %i', (_index, entry) => {
    const ours = splitSentences(entry.answer).map(({ index, text, isCode }) => ({ index, text, isCode }));
    expect(ours).toEqual(entry.sentences);
  });

  it('covers every study and practice answer', () => {
    const answers = new Set(contract.map((entry) => entry.answer));
    for (const item of [...loadStudyItems(), ...loadPracticeItems()]) expect(answers.has(item.ai_answer), item.id).toBe(true);
  });

  it('every flagged index points at a real sentence', () => {
    for (const item of [...loadStudyItems(), ...loadPracticeItems()]) {
      const count = splitSentences(item.ai_answer).length;
      for (const index of item.signal.flagged_sentence_indices) expect(index, item.id).toBeLessThan(count);
    }
  });

  it('keeps paragraphs apart for rendering', () => {
    const sentences = splitSentences('One. Two.\n\nThree.');
    expect(sentences.map((s) => [s.text, s.block])).toEqual([
      ['One.', 0],
      ['Two.', 0],
      ['Three.', 1],
    ]);
  });
});
