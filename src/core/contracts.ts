export type ConfidenceLevel = 'high' | 'medium' | 'low';
export type AssessmentState =
  | ConfidenceLevel
  | 'insufficient_evidence'
  | 'unavailable'
  | 'abstained';
export type SignalStatus =
  | 'checking'
  | 'signal'
  | 'error'
  | 'timeout'
  | 'not-applicable';

export interface DetectedAnswer {
  answer: string;
  prompt: string;
  container: HTMLElement;
  answerNodes: Text[];
  isStreaming: boolean;
  platform: PlatformId;
  answerHash?: string;
}

export type PlatformId = 'chatgpt' | 'claude' | 'gemini';

export interface SignalResponse {
  status: SignalStatus;
  confidence?: ConfidenceLevel;
  assessmentState?: AssessmentState;
  score?: number;
  sentenceFlags?: Array<{
    sentenceIndex: number;
    label: string;
    explanation?: string;
    claimIds?: string[];
  }>;
  claimAssessments?: Array<{
    claimId?: string;
    claim: string;
    assessment: string;
    confidence: ConfidenceLevel;
    evidenceStrength?: string;
    uncertainty?: number;
    supportingSourceIds?: string[];
    contradictingSourceIds?: string[];
  }>;
  explanation?: string;
  modelVersion: string;
  processingLatencyMs?: number;
}

export interface SiteAdapter {
  readonly platform: PlatformId;
  matchesPage(url: URL): boolean;
  findAnswers(root: ParentNode): DetectedAnswer[];
  isStreaming(container: HTMLElement): boolean;
  getMountTarget(container: HTMLElement): HTMLElement;
}

export interface CaptureRequest {
  type: 'capture-answer';
  platform: PlatformId;
  prompt: string;
  answer: string;
  answerHash: string;
}

export interface CaptureResponse {
  type: 'capture-result';
  signal: SignalResponse;
}
