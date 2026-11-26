import type { DetectedAnswer, SiteAdapter } from '../core/contracts';
import { nearestPreviousText, readableText, textNodes } from './dom';

/*
 * ChatGPT ships two layouts.
 *
 * Current (recorded 2026-11-26): each exchange is a [data-turn-key] block whose
 * [data-talvt-turn-state] says whether it is still being written ("complete" when done). Inside it,
 * search units mark the question (…:user) and the answer (…:assistant); the answer's text lives in
 * [data-response-body] > … > [data-dil-response].
 *
 * Classic: <article data-testid="conversation-turn-N"> with [data-message-author-role] and .markdown.
 */

const unitSelector = '[data-content-search-unit-key], [data-chatgpt-search-unit-key]';
const userUnitSelector = '[data-content-search-unit-key$=":user"], [data-chatgpt-search-unit-key$=":user"]';
/** Turn states that mean the answer is still being produced. "complete" (and anything final) does not. */
const UNFINISHED_TURN_STATE = /stream|pend|progress|run|generat|start|load|think|active|typing|incomplete|partial|wait|queue/i;

function turnStillWriting(element: HTMLElement): boolean {
  const state = element.closest<HTMLElement>('[data-talvt-turn-state]')?.dataset.talvtTurnState;
  return Boolean(state && UNFINISHED_TURN_STATE.test(state));
}

export function isChatGPTStreaming(container: HTMLElement): boolean {
  return Boolean(
    turnStillWriting(container) ||
      container.querySelector('[data-testid="stop-button"], button[aria-label*="Stop" i]') ||
      container.matches('[data-is-streaming="true"]') ||
      container.querySelector('[data-is-streaming="true"]'),
  );
}

/** Answer text without the screen-reader heading: the rendered response, else the response body. */
function currentAnswerContent(body: HTMLElement): HTMLElement {
  const rendered = body.querySelectorAll<HTMLElement>('[data-dil-response]');
  if (rendered.length === 1) return rendered[0];
  return body.querySelector<HTMLElement>('[data-markdown-text-style="assistant-message"]') ?? body;
}

/** The question asked just before this answer in the current layout. */
function currentPrompt(container: HTMLElement, root: ParentNode): string {
  const units = Array.from(root.querySelectorAll<HTMLElement>(userUnitSelector))
    .filter((unit) => Boolean(unit.compareDocumentPosition(container) & Node.DOCUMENT_POSITION_FOLLOWING));
  const unit = units.at(-1);
  if (!unit) return '';
  const bubble = unit.querySelector<HTMLElement>('[data-user-message-bubble]');
  // Without a bubble, drop the screen-reader heading ("You said:") from the unit's text.
  const text = bubble ? readableText(bubble) : readableText(unit).replace(/^you said:?\s*/i, '');
  return text.trim();
}

function findCurrentAnswers(root: ParentNode): DetectedAnswer[] {
  const seen = new Set<HTMLElement>();
  return Array.from(root.querySelectorAll<HTMLElement>('[data-response-body]')).flatMap((body) => {
    const container = body.closest<HTMLElement>(unitSelector) ?? body;
    if (seen.has(container)) return [];
    seen.add(container);
    const content = currentAnswerContent(body);
    return [{
      answer: readableText(content),
      prompt: currentPrompt(container, root),
      container,
      answerNodes: textNodes(content),
      isStreaming: isChatGPTStreaming(container),
      platform: 'chatgpt' as const,
    }];
  });
}

const classicAssistantSelectors = [
  '[data-message-author-role="assistant"]',
  'article[data-testid^="conversation-turn"]',
];
const classicTurnSelectors = ['[data-message-author-role="user"]', '[data-message-author-role="assistant"]'];

function classicAnswerElement(container: HTMLElement): HTMLElement {
  return (
    container.querySelector<HTMLElement>('[data-message-author-role="assistant"]') ??
    container.querySelector<HTMLElement>('.markdown') ??
    container
  );
}

function findClassicAnswers(root: ParentNode): DetectedAnswer[] {
  const seen = new Set<HTMLElement>();
  return classicAssistantSelectors.flatMap((selector) =>
    Array.from(root.querySelectorAll<HTMLElement>(selector)).flatMap((candidate) => {
      const container = candidate.closest<HTMLElement>('article') ?? candidate;
      if (
        container.dataset.messageAuthorRole === 'user' ||
        (!container.querySelector('[data-message-author-role="assistant"]') &&
          container.getAttribute('data-message-author-role') !== 'assistant')
      ) return [];
      if (seen.has(container)) return [];
      seen.add(container);
      const content = classicAnswerElement(container);
      return [{
        answer: readableText(content),
        prompt: nearestPreviousText(container, root, classicTurnSelectors),
        container,
        answerNodes: textNodes(content),
        isStreaming: isChatGPTStreaming(container),
        platform: 'chatgpt' as const,
      }];
    }),
  );
}

export const chatgptAdapter: SiteAdapter = {
  platform: 'chatgpt',
  matchesPage: (url) => url.hostname === 'chatgpt.com',
  findAnswers(root) {
    const current = findCurrentAnswers(root);
    return current.length ? current : findClassicAnswers(root);
  },
  isStreaming: isChatGPTStreaming,
  getMountTarget: (container) => container,
};
