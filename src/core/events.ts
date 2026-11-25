import type { AssessmentState, PlatformId } from './contracts';
import type { ExtensionRuntimeConfig } from './runtimeConfig';
import { resolveApiEndpoint } from './backendSignal';

export type OverlayEventType = 'signal_shown' | 'explanation_opened' | 'signal_dismissed';

/** Sent from the content script to the background worker. Carries no prompt or answer text. */
export interface OverlayEventMessage {
  type: 'overlay-event';
  eventType: OverlayEventType;
  platform: PlatformId;
  answerHash: string;
  modelVersion: string;
  assessmentState?: AssessmentState;
}

const eventTypes: readonly OverlayEventType[] = ['signal_shown', 'explanation_opened', 'signal_dismissed'];

export function isOverlayEventMessage(value: unknown): value is OverlayEventMessage {
  if (!value || typeof value !== 'object') return false;
  const message = value as Partial<OverlayEventMessage>;
  return (
    message.type === 'overlay-event' &&
    eventTypes.includes(message.eventType as OverlayEventType) &&
    (message.platform === 'chatgpt' || message.platform === 'claude' || message.platform === 'gemini') &&
    typeof message.answerHash === 'string' &&
    /^[a-f0-9]{64}$/.test(message.answerHash) &&
    typeof message.modelVersion === 'string'
  );
}

/** Fire-and-forget: never throws and never makes the caller wait. */
export function sendOverlayEvent(
  message: OverlayEventMessage,
  send: (message: OverlayEventMessage) => Promise<unknown>,
): void {
  try {
    void send(message).catch(() => undefined);
  } catch {
    // The extension context can be invalidated mid-page; events are best effort.
  }
}

export async function postBackendEvent(
  event: OverlayEventMessage,
  config: ExtensionRuntimeConfig,
  fetchImpl: typeof fetch = fetch,
): Promise<void> {
  if (config.mode !== 'api') return;
  const base = resolveApiEndpoint(config);
  const metadata: Record<string, string> = { modelVersion: event.modelVersion };
  if (event.assessmentState) metadata.assessmentState = event.assessmentState;
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 8_000);
  try {
    const response = await fetchImpl(`${base}/v1/events`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${config.sessionToken}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        participant_id: config.participantId,
        event_type: event.eventType,
        platform: event.platform,
        answer_hash: event.answerHash,
        metadata,
      }),
      signal: controller.signal,
    });
    if (!response.ok) throw new Error(`Backend returned ${response.status}`);
  } finally {
    clearTimeout(timeout);
  }
}
