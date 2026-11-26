import { getAdapterForPage } from '../src/adapters';
import { isCaptureResponse } from '../src/signals/response';
import type { CaptureRequest } from '../src/core/contracts';
import { CompletionTracker } from '../src/core/completion';
import { DuplicateGuard } from '../src/core/duplicateGuard';
import { hashAnswer } from '../src/core/hash';
import { mountOverlay } from '../src/overlay/mountOverlay';
import { diagnostic } from '../src/core/diagnostics';
import { modeModelVersion, type RuntimeMode } from '../src/core/runtimeConfig';
import { sendOverlayEvent } from '../src/core/events';
import { createScanScheduler } from '../src/core/scanScheduler';

export default defineContentScript({
  matches: ['https://chatgpt.com/*', 'https://claude.ai/*', 'https://gemini.google.com/*'],
  runAt: 'document_idle',
  main() {
    const completion = new CompletionTracker();
    const duplicates = new DuplicateGuard();

    const adapter = getAdapterForPage(new URL(location.href));
    if (!adapter) return;
    diagnostic('adapter-selected', { platform: adapter.platform });

    /** Resolves to true when an answer is still streaming or settling and needs another scan. */
    const scan = async (): Promise<boolean> => {
      let settling = false;
      const detectedAnswers = adapter.findAnswers(document);
      diagnostic('assistant-scan', { platform: adapter.platform, count: detectedAnswers.length });
      for (const detected of detectedAnswers) {
        const sample = { text: detected.answer, streaming: detected.isStreaming };
        diagnostic('answer-state', { platform: detected.platform, streaming: detected.isStreaming });
        // An empty answer is a placeholder the site has not filled yet (Gemini adds the element first).
        if (!detected.answer || detected.isStreaming || !completion.isStable(detected.container, sample)) {
          settling = true;
          continue;
        }
        const answerHash = await hashAnswer(detected.answer);
        if (!duplicates.hasChanged(detected.container, answerHash)) {
          diagnostic('duplicate-capture-prevented', { platform: detected.platform });
          continue;
        }
        const target = adapter.getMountTarget(detected.container);
        const placeholderVersion = modeModelVersion(await readRuntimeMode());
        const host = mountOverlay(target, { status: 'checking', modelVersion: placeholderVersion });
        try {
          const request: CaptureRequest = {
            type: 'capture-answer',
            platform: detected.platform,
            prompt: detected.prompt,
            answer: detected.answer,
            answerHash,
          };
          const response: unknown = await browser.runtime.sendMessage(request);
          if (!isCaptureResponse(response)) {
            throw new Error('Invalid signal response from the background service worker');
          }
          if (response.signal.status === 'error' || response.signal.status === 'timeout') {
            throw new Error('Signal service could not process the answer');
          }
          const signal = response.signal;
          const platform = detected.platform;
          mountOverlay(target, signal, {
            answerHash,
            onEvent: (eventType) =>
              sendOverlayEvent(
                {
                  type: 'overlay-event',
                  eventType,
                  platform,
                  answerHash,
                  modelVersion: signal.modelVersion,
                  assessmentState: signal.assessmentState,
                },
                (message) => browser.runtime.sendMessage(message),
              ),
          });
          diagnostic('signal-delivered', { platform: detected.platform, status: response.signal.status });
        } catch (error) {
          console.error('CalibrAI signal processing failed', error);
          diagnostic('signal-failed', { platform: detected.platform });
          duplicates.forget(detected.container);
          // The answer is forgotten above, so a fresh scan captures and checks it again.
          mountOverlay(target, { status: 'error', modelVersion: placeholderVersion }, {
            answerHash,
            onRetry: () => scheduler.scanNow(),
          });
        }
        host.dataset.answerHash = answerHash;
      }
      return settling;
    };
    const scheduler = createScanScheduler(scan);
    const observer = new MutationObserver(() => scheduler.onMutation());
    observer.observe(document.body, { childList: true, subtree: true, characterData: true });
    scheduler.scanNow();
  },
});

async function readRuntimeMode(): Promise<RuntimeMode> {
  try {
    const stored = await browser.storage.local.get('mode');
    return stored.mode === 'api' ? 'api' : 'mock';
  } catch {
    return 'mock';
  }
}
