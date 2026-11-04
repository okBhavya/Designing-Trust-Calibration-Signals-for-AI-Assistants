import type { DetectedAnswer, SiteAdapter } from '../core/contracts';
import { nearestPreviousText, readableText, textNodes } from './dom';

const assistantSelectors = [
  '[data-message-author-role="assistant"]',
  'article[data-testid^="conversation-turn"]',
];
const turnSelectors = ['[data-message-author-role="user"]', '[data-message-author-role="assistant"]'];

function answerElement(container: HTMLElement): HTMLElement {
  return (
    container.querySelector<HTMLElement>('[data-message-author-role="assistant"]') ??
    container.querySelector<HTMLElement>('.markdown') ??
    container
  );
}

export function isChatGPTStreaming(container: HTMLElement): boolean {
  return Boolean(
    container.querySelector('[data-testid="stop-button"], button[aria-label*="Stop" i]') ||
      container.matches('[data-is-streaming="true"]') ||
      container.querySelector('[data-is-streaming="true"]'),
  );
}

export const chatgptAdapter: SiteAdapter = {
  platform: 'chatgpt',
  matchesPage: (url) => url.hostname === 'chatgpt.com',
  findAnswers(root) {
    const seen = new Set<HTMLElement>();
    return assistantSelectors.flatMap((selector) =>
      Array.from(root.querySelectorAll<HTMLElement>(selector)).flatMap((candidate) => {
        const container = candidate.closest<HTMLElement>('article') ?? candidate;
        if (
          container.dataset.messageAuthorRole === 'user' ||
          (!container.querySelector('[data-message-author-role="assistant"]') &&
            container.getAttribute('data-message-author-role') !== 'assistant')
        ) return [];
        if (seen.has(container)) return [];
        seen.add(container);
        const content = answerElement(container);
        return [{
          answer: readableText(content),
          prompt: nearestPreviousText(container, root, turnSelectors),
          container,
          answerNodes: textNodes(content),
          isStreaming: isChatGPTStreaming(container),
          platform: 'chatgpt' as const,
        }];
      }),
    );
  },
  isStreaming: isChatGPTStreaming,
  getMountTarget: (container) => container,
};
