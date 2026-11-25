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
  /** null when the backend gives no confidence (insufficient evidence, unavailable, abstained). */
  confidence?: ConfidenceLevel | null;
  assessmentState?: AssessmentState;
  /** null when no score is meaningful (insufficient evidence, unavailable). */
  score?: number | null;
  sentenceFlags?: Array<{
    sentenceIndex: number;
    label: string;
    explanation?: string;
    claimIds?: string[];
  }>;
  claimAssessments?: Array<{
    claimId?: string;
    /** Omitted when the backend replays a stored response. */
    claim?: string;
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
