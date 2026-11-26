import type { SiteAdapter } from '../core/contracts';
import { readableText, textNodes } from './dom';

/**
 * Gemini renders each turn as Angular custom elements: <user-query> for the question and
 * <model-response> for the answer, whose text sits in <message-content> (a `.markdown` panel that is
 * aria-busy="true" while streaming). The class-based selectors are older markup, kept as fallbacks.
 */
const answerSelectors = ['model-response', '.model-response', '[data-message-author-role="model"]'];
const promptSelectors = ['user-query', '.user-query', '[data-message-author-role="user"]'];

function contentElement(container: HTMLElement): HTMLElement {
  return (
    container.querySelector<HTMLElement>('message-content') ??
    container.querySelector<HTMLElement>('.model-response-text, .markdown') ??
    container
  );
}

/** Resolves any match to its outermost answer element so each answer is detected once. */
function answerContainer(candidate: HTMLElement): HTMLElement {
  const selector = answerSelectors.join(',');
  let outer = candidate;
  for (let parent = candidate.parentElement?.closest<HTMLElement>(selector); parent; parent = parent.parentElement?.closest<HTMLElement>(selector)) {
    outer = parent;
  }
  return outer;
}

/** Text of the question asked just before this answer ('' when none is on the page). */
function promptFor(container: HTMLElement, root: ParentNode): string {
  const queries = Array.from(root.querySelectorAll<HTMLElement>(promptSelectors.join(',')))
    // Nested matches (an element with both the tag and the class) count once: keep the outermost.
    .filter((query, _, all) => !all.some((other) => other !== query && other.contains(query)))
    .filter((query) => Boolean(query.compareDocumentPosition(container) & Node.DOCUMENT_POSITION_FOLLOWING));
  const query = queries.at(-1);
  if (!query) return '';
  const text = readableText(query.querySelector<HTMLElement>('.query-text') ?? query);
  // Gemini prefixes the question with a screen-reader label.
  return text.replace(/^you said:?\s*/i, '').trim();
}

export function isGeminiStreaming(container: HTMLElement): boolean {
  return Boolean(
    container.matches('[aria-busy="true"], [data-is-streaming="true"]') ||
      container.querySelector('[aria-busy="true"], [data-is-streaming="true"], button[aria-label*="Stop" i]'),
  );
}

export const geminiAdapter: SiteAdapter = {
  platform: 'gemini',
  matchesPage: (url) => url.hostname === 'gemini.google.com',
  findAnswers(root) {
    const seen = new Set<HTMLElement>();
    return Array.from(root.querySelectorAll<HTMLElement>(answerSelectors.join(','))).flatMap((candidate) => {
      const container = answerContainer(candidate);
      if (seen.has(container)) return [];
      seen.add(container);
      const content = contentElement(container);
      return [{
        answer: readableText(content),
        prompt: promptFor(container, root),
        container,
        answerNodes: textNodes(content),
        isStreaming: isGeminiStreaming(container),
        platform: 'gemini' as const,
      }];
    });
  },
  isStreaming: isGeminiStreaming,
  getMountTarget: (container) => container,
};
