import type { CaptureResponse, SignalResponse } from '../core/contracts';

export function isSignalResponse(value: unknown): value is SignalResponse {
  if (!value || typeof value !== 'object') return false;
  const response = value as Partial<SignalResponse>;
  const confidenceValid =
    response.confidence === undefined || ['high', 'medium', 'low'].includes(response.confidence);
  const scoreValid =
    response.score === undefined || (typeof response.score === 'number' && response.score >= 0 && response.score <= 1);
  return (
    typeof response.modelVersion === 'string' &&
    typeof response.status === 'string' &&
    ['checking', 'signal', 'error', 'timeout', 'not-applicable'].includes(response.status) &&
    confidenceValid &&
    scoreValid
  );
}

export function isCaptureResponse(value: unknown): value is CaptureResponse {
  if (!value || typeof value !== 'object' || !('type' in value)) return false;
  const response = value as Partial<CaptureResponse>;
  return response.type === 'capture-result' && isSignalResponse(response.signal);
}
