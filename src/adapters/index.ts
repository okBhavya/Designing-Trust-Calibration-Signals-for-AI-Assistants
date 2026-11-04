import type { SiteAdapter } from '../core/contracts';
import { chatgptAdapter } from './chatgpt';
import { claudeAdapter } from './claude';
import { geminiAdapter } from './gemini';

export const siteAdapters: readonly SiteAdapter[] = [chatgptAdapter, claudeAdapter, geminiAdapter];

export function getAdapterForPage(url: URL): SiteAdapter | undefined {
  return siteAdapters.find((adapter) => adapter.matchesPage(url));
}
