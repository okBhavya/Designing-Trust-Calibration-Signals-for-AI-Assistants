export type RuntimeMode = 'mock' | 'api';

export interface ExtensionRuntimeConfig {
  mode: RuntimeMode;
  apiBaseUrl: string;
  participantId: string;
  sessionToken: string;
}

export const defaultRuntimeConfig: ExtensionRuntimeConfig = {
  mode: 'mock',
  apiBaseUrl: 'http://127.0.0.1:8000',
  participantId: '',
  sessionToken: '',
};
