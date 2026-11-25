import { act } from 'react';
import { expect, it, vi } from 'vitest';

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

it('popup shows the active tab site instead of a hardcoded one', async () => {
  document.body.innerHTML = '<div id="root"></div>';
  vi.stubGlobal('browser', {
    tabs: { query: vi.fn().mockResolvedValue([{ url: 'https://gemini.google.com/app/1' }]) },
    runtime: { getURL: (path: string) => `chrome-extension://test${path}` },
  });
  await act(async () => {
    await import('../entrypoints/popup/main');
  });
  expect(document.querySelector('.status')?.textContent).toContain('Active on Gemini');
  expect(document.body.textContent).not.toContain('Active on ChatGPT');
  vi.unstubAllGlobals();
});
