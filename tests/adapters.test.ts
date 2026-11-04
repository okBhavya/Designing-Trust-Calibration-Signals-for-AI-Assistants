import { describe, expect, it } from 'vitest';
import { claudeAdapter } from '../src/adapters/claude';
import { geminiAdapter } from '../src/adapters/gemini';
import { getAdapterForPage } from '../src/adapters';

describe.each([
  {
    name: 'Claude',
    adapter: claudeAdapter,
    html: `
      <div data-testid="user-message">Explain calibration.</div>
      <div data-testid="assistant-message">Calibration measures whether confidence matches accuracy.</div>
    `,
    url: 'https://claude.ai/new',
  },
  {
    name: 'Gemini',
    adapter: geminiAdapter,
    html: `
      <div class="user-query">Explain calibration.</div>
      <div class="model-response"><div class="model-response-text">Calibration measures whether confidence matches accuracy.</div></div>
    `,
    url: 'https://gemini.google.com/app',
  },
])('$name adapter', ({ adapter, html, url }) => {
  it('extracts a non-empty prompt and answer', () => {
    document.body.innerHTML = html;
    const answers = adapter.findAnswers(document);
    expect(answers).toHaveLength(1);
    expect(answers[0].platform).toBe(adapter.platform);
    expect(answers[0].prompt).toBe('Explain calibration.');
    expect(answers[0].answer).toContain('Calibration measures');
  });

  it('identifies its own page and ignores another platform', () => {
    expect(adapter.matchesPage(new URL(url))).toBe(true);
    expect(adapter.matchesPage(new URL('https://chatgpt.com/'))).toBe(false);
  });

  it('detects an in-progress response', () => {
    document.body.innerHTML =
      adapter.platform === 'claude'
        ? '<div data-testid="assistant-message" data-is-streaming="true">Working</div>'
        : adapter.platform === 'gemini'
          ? '<div class="model-response" aria-busy="true">Working</div>'
          : '<div data-message-author-role="assistant" data-is-streaming="true">Working</div>';
    expect(adapter.findAnswers(document)[0].isStreaming).toBe(true);
  });
});

it('selects the adapter independently from the page URL', () => {
  expect(getAdapterForPage(new URL('https://chatgpt.com/'))?.platform).toBe('chatgpt');
  expect(getAdapterForPage(new URL('https://claude.ai/'))?.platform).toBe('claude');
  expect(getAdapterForPage(new URL('https://gemini.google.com/'))?.platform).toBe('gemini');
  expect(getAdapterForPage(new URL('https://example.com/'))).toBeUndefined();
});
