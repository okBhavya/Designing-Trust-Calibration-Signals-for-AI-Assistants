import type { PlatformId } from './contracts';
import { getAdapterForPage } from '../adapters';

const platformNames: Record<PlatformId, string> = {
  chatgpt: 'ChatGPT',
  claude: 'Claude',
  gemini: 'Gemini',
};

/** Popup status line for the active tab's URL (undefined when the tab URL is not visible). */
export function activeSiteStatus(url: string | undefined): string {
  if (!url) return 'Not active on this page';
  try {
    const adapter = getAdapterForPage(new URL(url));
    return adapter ? `Active on ${platformNames[adapter.platform]}` : 'Not active on this page';
  } catch {
    return 'Not active on this page';
  }
}
