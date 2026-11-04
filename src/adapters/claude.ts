import type { SiteAdapter } from '../core/contracts';
import { nearestPreviousText, readableText, textNodes } from './dom';

const assistantSelectors = [
  '[data-testid="assistant-message"]',
  '[data-is-streaming="true"][data-testid*="message" i]',
  'div.font-claude-message',
];
const turnSelectors = ['[data-testid="user-message"]', '[data-testid="assistant-message"]'];

function contentElement(container: HTMLElement): HTMLElement {
  return container.querySelector<HTMLElement>('[data-testid="assistant-message"]') ?? container;
}

export function isClaudeStreaming(container: HTMLElement): boolean {
  return Boolean(
    container.matches('[data-is-streaming="true"]') ||
      container.querySelector('[data-is-streaming="true"], button[aria-label*="Stop" i]'),
  );
}

export const claudeAdapter: SiteAdapter = {
  platform: 'claude',
  matchesPage: (url) => url.hostname === 'claude.ai',
  findAnswers(root) {
    const seen = new Set<HTMLElement>();
    return assistantSelectors.flatMap((selector) =>
      Array.from(root.querySelectorAll<HTMLElement>(selector)).flatMap((candidate) => {
        const container = candidate.closest<HTMLElement>('[data-testid="assistant-message"]') ?? candidate;
        if (seen.has(container)) return [];
        seen.add(container);
        const content = contentElement(container);
        return [{
          answer: readableText(content),
          prompt: nearestPreviousText(container, root, turnSelectors),
          container,
          answerNodes: textNodes(content),
          isStreaming: isClaudeStreaming(container),
          platform: 'claude' as const,
        }];
      }),
    );
  },
  isStreaming: isClaudeStreaming,
  getMountTarget: (container) => container,
};
