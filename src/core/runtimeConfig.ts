export type RuntimeMode = 'mock' | 'api';

export interface ExtensionRuntimeConfig {
  mode: RuntimeMode;
  apiBaseUrl: string;
  participantId: string;
  sessionToken: string;
}

/** The deployed API (WXT_API_ORIGIN at build time), else the local development API. */
export const DEFAULT_API_BASE_URL: string = import.meta.env.WXT_API_ORIGIN?.trim() || 'http://127.0.0.1:8000';

export const defaultRuntimeConfig: ExtensionRuntimeConfig = {
  mode: 'mock',
  apiBaseUrl: DEFAULT_API_BASE_URL,
  participantId: '',
  sessionToken: '',
};

/** Version label for overlays shown before (or instead of) a provider response. */
export function modeModelVersion(mode: RuntimeMode): string {
  return mode === 'api' ? 'api' : 'mock-v1';
}
