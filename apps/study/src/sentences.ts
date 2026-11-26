/**
 * Port of normalize_answer in apps/api/app/services/reliability_service.py. Sentence flags index
 * into this list, so it must split exactly as the backend does, quirks included ("Dr." ends a
 * sentence; a "#" line swallows the text joined to it). contracts/sentence_splits.json holds the
 * backend's output for every study answer plus edge cases; sentences.test.ts checks this port
 * against it.
 */

export interface Sentence {
  index: number;
  text: string;
  isCode: boolean;
  /** Paragraph (or code block) the sentence came from, for rendering. Not part of the contract. */
  block: number;
}

const LIST_MARKER = /^\s*(?:[-*+]|\d+[.)])\s+/;
const SENTENCE_BREAK = /(?<=[.!?])\s+(?=[A-Z0-9"'])/;

export function splitSentences(answer: string): Sentence[] {
  const text = answer.replace(/\r\n/g, '\n').replace(/\r/g, '\n').trim();
  const blocks: Array<{ text: string; isCode: boolean }> = [];
  let inCode = false;
  let buffer: string[] = [];
  for (const line of text.split('\n')) {
    if (line.trim().startsWith('```')) {
      if (buffer.length) {
        blocks.push({ text: buffer.join(' ').trim(), isCode: inCode });
        buffer = [];
      }
      inCode = !inCode;
      continue;
    }
    if (!line.trim() && buffer.length && !inCode) {
      blocks.push({ text: buffer.join(' ').trim(), isCode: false });
      buffer = [];
      continue;
    }
    if (inCode) {
      buffer.push(line);
      continue;
    }
    buffer.push(line.replace(LIST_MARKER, '').trim());
  }
  if (buffer.length) blocks.push({ text: buffer.join(' ').trim(), isCode: inCode });

  const sentences: Sentence[] = [];
  blocks.forEach((block, blockIndex) => {
    if (block.isCode) {
      sentences.push({ index: sentences.length, text: block.text, isCode: true, block: blockIndex });
      return;
    }
    for (const part of block.text.split(SENTENCE_BREAK)) {
      if (part.trim() && !part.trimStart().startsWith('#')) {
        sentences.push({ index: sentences.length, text: part.trim(), isCode: false, block: blockIndex });
      }
    }
  });
  return sentences;
}
