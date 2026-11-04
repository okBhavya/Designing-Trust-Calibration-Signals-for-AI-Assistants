import { getAdapterForPage } from '../src/adapters';
import { isCaptureResponse } from '../src/signals/response';
import type { CaptureRequest } from '../src/core/contracts';
import { CompletionTracker } from '../src/core/completion';
import { DuplicateGuard } from '../src/core/duplicateGuard';
import { hashAnswer } from '../src/core/hash';
import { mountOverlay } from '../src/overlay/mountOverlay';
import { diagnostic } from '../src/core/diagnostics';

export default defineContentScript({
  matches: ['https://chatgpt.com/*', 'https://claude.ai/*', 'https://gemini.google.com/*'],
  runAt: 'document_idle',
  main() {
    const completion = new CompletionTracker();
    const duplicates = new DuplicateGuard();
    let scheduled = false;

    const adapter = getAdapterForPage(new URL(location.href));
    if (!adapter) return;
    diagnostic('adapter-selected', { platform: adapter.platform });

    const scan = async () => {
      scheduled = false;
      const detectedAnswers = adapter.findAnswers(document);
      diagnostic('assistant-scan', { platform: adapter.platform, count: detectedAnswers.length });
      for (const detected of detectedAnswers) {
        const sample = { text: detected.answer, streaming: detected.isStreaming };
        diagnostic('answer-state', { platform: detected.platform, streaming: detected.isStreaming });
        if (detected.isStreaming || !completion.isStable(detected.container, sample)) continue;
        const answerHash = await hashAnswer(detected.answer);
        if (!duplicates.hasChanged(detected.container, answerHash)) {
          diagnostic('duplicate-capture-prevented', { platform: detected.platform });
          continue;
        }
        const target = adapter.getMountTarget(detected.container);
        const host = mountOverlay(target, { status: 'checking', modelVersion: 'mock-v1' });
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
          mountOverlay(target, response.signal);
          diagnostic('signal-delivered', { platform: detected.platform, status: response.signal.status });
        } catch (error) {
          console.error('CalibrAI signal processing failed', error);
          diagnostic('signal-failed', { platform: detected.platform });
          duplicates.forget(detected.container);
          mountOverlay(target, { status: 'error', modelVersion: 'mock-v1' });
        }
        host.dataset.answerHash = answerHash;
      }
    };
    const observer = new MutationObserver(() => {
      if (scheduled) return;
      scheduled = true;
      window.setTimeout(() => void scan(), 250);
    });
    observer.observe(document.body, { childList: true, subtree: true, characterData: true });
    void scan();
  },
});
