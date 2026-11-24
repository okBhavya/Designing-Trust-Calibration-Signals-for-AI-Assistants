import type { SiteAdapter } from '../core/contracts';
import { nearestPreviousText, readableText, textNodes } from './dom';

const assistantSelectors = [
  '[data-message-author-role="model"]',
  '.model-response',
  'message-content.model-response-text',
];
const turnSelectors = ['[data-message-author-role="user"]', '.user-query', '[data-message-author-role="model"]'];

function contentElement(container: HTMLElement): HTMLElement {
  return container.querySelector<HTMLElement>('.model-response-text, message-content') ?? container;
}

/** Resolves any match to the outermost .model-response so each answer is detected once. */
function answerContainer(candidate: HTMLElement): HTMLElement {
  let outer = candidate.closest<HTMLElement>('.model-response');
  let parent = outer?.parentElement?.closest<HTMLElement>('.model-response');
  while (parent) {
    outer = parent;
    parent = parent.parentElement?.closest<HTMLElement>('.model-response');
  }
  return outer ?? candidate.closest<HTMLElement>('message-content') ?? candidate;
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
    return assistantSelectors.flatMap((selector) =>
      Array.from(root.querySelectorAll<HTMLElement>(selector)).flatMap((candidate) => {
        const container = answerContainer(candidate);
        if (seen.has(container)) return [];
        seen.add(container);
        const content = contentElement(container);
        return [{
          answer: readableText(content),
          prompt: nearestPreviousText(container, root, turnSelectors),
          container,
          answerNodes: textNodes(content),
          isStreaming: isGeminiStreaming(container),
          platform: 'gemini' as const,
        }];
      }),
    );
  },
  isStreaming: isGeminiStreaming,
  getMountTarget: (container) => container,
};
