import type { SignalResponse } from '../core/contracts';
import type { PlatformId } from '../core/contracts';

export async function getMockSignal(answer: string, _platform: PlatformId): Promise<SignalResponse> {
  await new Promise((resolve) => setTimeout(resolve, 120));
  if (!answer.trim()) return { status: 'not-applicable', modelVersion: 'mock-v1' };
  const confidence = answer.length > 700 ? 'medium' : 'high';
  return {
    status: 'signal',
    confidence,
    explanation: 'Mock signal for the extension foundation. This is not a factuality assessment.',
    modelVersion: 'mock-v1',
  };
}
