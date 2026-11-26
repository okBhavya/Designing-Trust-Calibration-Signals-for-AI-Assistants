import { describe, expect, it } from 'vitest';
import { chatgptAdapter } from '../src/adapters/chatgpt';

describe('ChatGPT adapter', () => {
  it('extracts the prompt and answer while ignoring user turns', () => {
    document.body.innerHTML = `
      <article data-testid="conversation-turn-1" data-message-author-role="user">
        <div data-message-author-role="user">What is calibration?</div>
      </article>
      <article data-testid="conversation-turn-2" data-message-author-role="assistant">
        <div data-message-author-role="assistant"><div class="markdown">Calibration is measuring reliability.</div></div>
      </article>
    `;
    const answers = chatgptAdapter.findAnswers(document);
    expect(answers).toHaveLength(1);
    expect(answers[0].prompt).toBe('What is calibration?');
    expect(answers[0].answer).toBe('Calibration is measuring reliability.');
    expect(answers[0].answerNodes.length).toBeGreaterThan(0);
  });

  it('detects an active stop button as streaming', () => {
    document.body.innerHTML = '<article data-message-author-role="assistant"><button data-testid="stop-button"></button></article>';
    expect(chatgptAdapter.findAnswers(document)[0].isStreaming).toBe(true);
  });
});

/**
 * ChatGPT's current layout, recorded from chatgpt.com on 2026-11-26 (classes and ids trimmed):
 * one [data-turn-key] per exchange, a turn state, user/assistant search units, and the answer text
 * in [data-response-body] > … > [data-dil-response].
 */
const exchange = (key: string, question: string, answer: string, state = 'complete') => `
  <div data-virtualized-turn="">
    <div data-turn-key="${key}">
      <div data-content-search-turn-key="${key}-search">
        <div class="flex flex-col gap-1.5">
          <div data-talvt-turn-state="${state}" class="group flex flex-col">
            <div data-spacing="activity">
              <div class="block-BQZwFn">
                <div data-content-search-unit-key="${key}-search:0:user">
                  <h4 data-conversation-role="user" class="sr-only">You said:</h4>
                  <div data-user-message-bubble="true" data-user-message-has-prompt="true">${question}</div>
                </div>
              </div>
              <div class="block-BQZwFn">
                <span hidden data-chatgpt-agent-turn-start></span>
                <div data-content-search-unit-key="${key}-search:1:assistant" data-chatgpt-search-unit-key="${key}-search:1:assistant">
                  <h4 data-conversation-role="assistant" tabindex="-1" class="sr-only">ChatGPT said:</h4>
                  <div data-response-body="${key}-msg">
                    <div data-chatgpt-selection-message-id="${key}-msg" class="group flex min-w-0 flex-col">
                      <div data-markdown-text-style="assistant-message">
                        <div data-dil-source-message-id="${key}-msg" data-markdown-copy="contents">
                          <div><div data-theme="dark">
                            <div data-dil-response="" data-dil-message-id="${key}-msg">
                              <p class="TextBase-kDAqPL"><span data-d-stream-run="">${answer}</span></p>
                              <ol class="List-bYalj1"><li data-d-component="list-item">Location: Birla House.</li></ol>
                            </div>
                          </div></div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
            <div class="actionRow-nqqZbm turn-action-controls"><button aria-label="Copy"></button><button aria-label="Read aloud"></button></div>
          </div>
        </div>
      </div>
    </div>
  </div>`;

describe('ChatGPT adapter on the current layout', () => {
  it('finds each answer with its own question and only the answer text', () => {
    document.body.innerHTML = `<div data-rail-chat-transcript="true">
      ${exchange('t1', 'how did mahatma Gandhi die?', 'Mahatma Gandhi was assassinated on 30 January 1948.')}
      ${exchange('t2', 'who shot him?', 'Nathuram Godse.')}
    </div>`;
    const answers = chatgptAdapter.findAnswers(document);
    expect(answers).toHaveLength(2);
    expect(answers.map((answer) => answer.prompt)).toEqual(['how did mahatma Gandhi die?', 'who shot him?']);
    expect(answers[0].answer).toContain('Mahatma Gandhi was assassinated on 30 January 1948.');
    expect(answers[0].answer).toContain('Location: Birla House.');
    expect(answers[0].answer).not.toContain('ChatGPT said');
    expect(answers[0].container.getAttribute('data-content-search-unit-key')).toBe('t1-search:1:assistant');
    expect(answers.every((answer) => !answer.isStreaming)).toBe(true);
  });

  it('treats a turn that is not complete as still streaming', () => {
    document.body.innerHTML = exchange('t3', 'question?', 'Partial answ', 'streaming');
    expect(chatgptAdapter.findAnswers(document)[0].isStreaming).toBe(true);
  });

  it('reads the question from the unit when there is no bubble', () => {
    document.body.innerHTML = exchange('t4', 'q', 'An answer.').replace(
      '<div data-user-message-bubble="true" data-user-message-has-prompt="true">q</div>',
      '<p>What is calibration?</p>',
    );
    expect(chatgptAdapter.findAnswers(document)[0].prompt).toBe('What is calibration?');
  });
});
