import type { CaptureRequest, CaptureResponse } from '../src/core/contracts';
import { defaultRuntimeConfig, type ExtensionRuntimeConfig } from '../src/core/runtimeConfig';
import { getMockSignal } from '../src/signals/mockProvider';
import { diagnostic } from '../src/core/diagnostics';
import { requestBackendSignal as requestConfiguredBackendSignal } from '../src/core/backendSignal';

export default defineBackground(() => {
  browser.runtime.onMessage.addListener(async (message: unknown): Promise<CaptureResponse | undefined> => {
    if (!isCaptureRequest(message)) return undefined;
    diagnostic('capture-received', { platform: message.platform });
    try {
      const config = await getRuntimeConfig();
      const signal = config.mode === 'mock'
        ? await getMockSignal(message.answer, message.platform)
        : await requestConfiguredBackendSignal(message, config);
      diagnostic('signal-request-succeeded', { platform: message.platform, status: signal.status });
      return { type: 'capture-result', signal };
    } catch (error) {
      console.error('CalibrAI signal request failed', error);
      diagnostic('signal-request-failed', { platform: message.platform, status: 'error' });
      return {
        type: 'capture-result',
        signal: { status: 'error', modelVersion: 'unavailable' },
      };
    }
  });
});

async function getRuntimeConfig(): Promise<ExtensionRuntimeConfig> {
  const stored = await browser.storage.local.get(Object.keys(defaultRuntimeConfig));
  return {
    mode: stored.mode === 'api' ? 'api' : 'mock',
    apiBaseUrl: typeof stored.apiBaseUrl === 'string' ? stored.apiBaseUrl : defaultRuntimeConfig.apiBaseUrl,
    participantId: typeof stored.participantId === 'string' ? stored.participantId : '',
    sessionToken: typeof stored.sessionToken === 'string' ? stored.sessionToken : '',
  };
}

function isCaptureRequest(message: unknown): message is CaptureRequest {
  if (!message || typeof message !== 'object') return false;
  const request = message as Partial<CaptureRequest>;
  return (
    request.type === 'capture-answer' &&
    (request.platform === 'chatgpt' || request.platform === 'claude' || request.platform === 'gemini') &&
    typeof request.prompt === 'string' &&
    typeof request.answer === 'string' &&
    typeof request.answerHash === 'string'
  );
}
