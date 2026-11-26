import { describe, expect, it } from 'vitest';
import { geminiAdapter } from '../src/adapters/gemini';

/**
 * Markup recorded from gemini.google.com on 2026-11-26 (Angular attributes trimmed). Turns are
 * custom elements, not classes: <user-query> and <model-response>, with the answer text in
 * <message-content> and an aria-busy markdown panel.
 */
const turn = (id: string, question: string, answer: string, busy = 'false') => `
  <div class="conversation-container message-actions-hover-boundary" id="${id}">
    <user-query>
      <span class="cdk-visually-hidden">You said</span>
      <div class="query-text"><p class="query-text-line">${question}</p></div>
    </user-query>
    <model-response class="enable-lr26-response-chrome-updates">
      <div>
        <response-container>
          <div class="response-container response-container-with-gpi">
            <model-thoughts><button>Show thinking</button></model-thoughts>
            <div class="model-response-label-announcer" aria-busy="false" aria-live="polite"></div>
            <message-content>
              <div class="markdown markdown-main-panel" id="model-response-message-contentr_${id}" aria-busy="${busy}" aria-live="polite">
                <p>${answer}</p>
              </div>
            </message-content>
            <button aria-label="Good response"></button><button aria-label="Copy"></button>
          </div>
        </response-container>
        <freemium-rag-disclaimer></freemium-rag-disclaimer>
      </div>
    </model-response>
  </div>`;

describe('Gemini adapter on the live markup', () => {
  it('finds each answer with its own question and only the answer text', () => {
    document.body.innerHTML = `<infinite-scroller data-test-id="chat-history-container">
      ${turn('a1', 'How did Mahatma Gandhi die?', 'He was assassinated on 30 January 1948.')}
      ${turn('a2', 'Who shot him?', 'Nathuram Godse.')}
    </infinite-scroller>`;
    const answers = geminiAdapter.findAnswers(document);
    expect(answers).toHaveLength(2);
    expect(answers.map((answer) => answer.prompt)).toEqual(['How did Mahatma Gandhi die?', 'Who shot him?']);
    expect(answers[0].answer).toBe('He was assassinated on 30 January 1948.');
    expect(answers[0].answer).not.toContain('Show thinking');
    expect(answers[0].container.tagName).toBe('MODEL-RESPONSE');
    expect(answers.every((answer) => !answer.isStreaming)).toBe(true);
  });

  it('treats a busy markdown panel as streaming', () => {
    document.body.innerHTML = turn('b1', 'Question?', 'Partial answ', 'true');
    expect(geminiAdapter.findAnswers(document)[0].isStreaming).toBe(true);
  });
});
