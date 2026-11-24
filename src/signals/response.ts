import type { CaptureResponse, SignalResponse } from '../core/contracts';

function isSentenceFlag(value: unknown): boolean {
  if (!value || typeof value !== 'object') return false;
  const flag = value as Record<string, unknown>;
  return (
    Number.isInteger(flag.sentenceIndex) &&
    (flag.sentenceIndex as number) >= 0 &&
    typeof flag.label === 'string' &&
    (flag.explanation === undefined || flag.explanation === null || typeof flag.explanation === 'string') &&
    (flag.claimIds === undefined || (Array.isArray(flag.claimIds) && flag.claimIds.every((id) => typeof id === 'string')))
  );
}

export function isSignalResponse(value: unknown): value is SignalResponse {
  if (!value || typeof value !== 'object') return false;
  const response = value as Partial<SignalResponse>;
  const assessmentStateValid =
    response.assessmentState === undefined ||
    ['high', 'medium', 'low', 'insufficient_evidence', 'unavailable', 'abstained'].includes(response.assessmentState);
  const confidenceValid =
    response.confidence === undefined ||
    response.confidence === null ||
    ['high', 'medium', 'low'].includes(response.confidence);
  const scoreValid =
    response.score === undefined ||
    response.score === null ||
    (typeof response.score === 'number' && response.score >= 0 && response.score <= 1);
  const sentenceFlagsValid =
    response.sentenceFlags === undefined ||
    (Array.isArray(response.sentenceFlags) && response.sentenceFlags.every(isSentenceFlag));
  return (
    typeof response.modelVersion === 'string' &&
    assessmentStateValid &&
    typeof response.status === 'string' &&
    ['checking', 'signal', 'error', 'timeout', 'not-applicable'].includes(response.status) &&
    confidenceValid &&
    scoreValid &&
    sentenceFlagsValid
  );
}

export function isCaptureResponse(value: unknown): value is CaptureResponse {
  if (!value || typeof value !== 'object' || !('type' in value)) return false;
  const response = value as Partial<CaptureResponse>;
  return response.type === 'capture-result' && isSignalResponse(response.signal);
}
