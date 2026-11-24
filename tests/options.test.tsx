import { act } from 'react';
import { expect, it, vi } from 'vitest';

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

it('options form resets to defaults after deleting local data', async () => {
  document.body.innerHTML = '<div id="root"></div>';
  const local = {
    get: vi.fn().mockResolvedValue({
      mode: 'api',
      apiBaseUrl: 'https://study.example.test',
      participantId: 'participant-1',
      sessionToken: 'token-1',
    }),
    set: vi.fn().mockResolvedValue(undefined),
    clear: vi.fn().mockResolvedValue(undefined),
  };
  vi.stubGlobal('browser', { storage: { local } });
  await act(async () => {
    await import('../entrypoints/options/main');
  });
  const inputs = () => Array.from(document.querySelectorAll('input')).map((input) => input.value);
  expect(inputs()).toEqual(['https://study.example.test', 'participant-1', 'token-1']);

  const deleteButton = Array.from(document.querySelectorAll('button')).find((button) =>
    button.textContent?.includes('Delete local extension data'),
  )!;
  await act(async () => deleteButton.click());
  expect(local.clear).toHaveBeenCalledTimes(1);
  const select = document.querySelector('select')!;
  expect(select.value).toBe('mock');
  expect(document.querySelectorAll('input')).toHaveLength(0);

  // Switching back to API mode must show empty credentials, not the deleted ones.
  await act(async () => {
    select.value = 'api';
    select.dispatchEvent(new Event('change', { bubbles: true }));
  });
  expect(inputs()).toEqual(['http://127.0.0.1:8000', '', '']);

  // Saving now must not write the deleted credentials back.
  const saveButton = Array.from(document.querySelectorAll('button')).find((button) =>
    button.textContent?.includes('Save'),
  )!;
  await act(async () => saveButton.click());
  expect(local.set).toHaveBeenCalledWith({
    mode: 'api',
    apiBaseUrl: 'http://127.0.0.1:8000',
    participantId: '',
    sessionToken: '',
  });
  vi.unstubAllGlobals();
});
