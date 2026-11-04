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
