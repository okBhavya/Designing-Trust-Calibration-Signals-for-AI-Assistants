import type { AssessmentState, SignalResponse } from '@calibrai/core/contracts';
import studyQuestions from '@study-data/questions.json';
import practiceQuestions from './practiceItems.json';

/** One pre-generated answer with its pre-computed signal (data/questions.json, built by validate.py). */
export interface StudyItem {
  id: string;
  domain: string;
  prompt: string;
  ai_answer: string;
  ground_truth: string;
  ai_is_correct: boolean;
  signal: {
    level: AssessmentState;
    score: number | null;
    flagged_sentence_indices: number[];
    reason: string;
    sentence_flags?: Array<{ sentenceIndex: number; label: string; explanation?: string; claimIds?: string[] }>;
    claim_assessments?: SignalResponse['claimAssessments'];
    model_version?: string;
  };
  difficulty: string;
}

export const MAIN_TRIAL_COUNT = 30;
export const MAIN_CORRECT_COUNT = 21;
const LEVELS: readonly string[] = ['high', 'medium', 'low', 'insufficient_evidence', 'abstained', 'unavailable'];

function isItem(value: unknown): value is StudyItem {
  const item = value as StudyItem;
  return (
    !!item &&
    typeof item.id === 'string' &&
    typeof item.prompt === 'string' &&
    typeof item.ai_answer === 'string' &&
    typeof item.ai_is_correct === 'boolean' &&
    !!item.signal &&
    LEVELS.includes(item.signal.level) &&
    (item.signal.score === null || typeof item.signal.score === 'number') &&
    Array.isArray(item.signal.flagged_sentence_indices) &&
    item.signal.flagged_sentence_indices.every((index) => Number.isInteger(index) && index >= 0) &&
    typeof item.signal.reason === 'string'
  );
}

/** Fails loudly when the study set is not what the protocol needs: 30 items, 21 correct (70%). */
export function validateStudyItems(value: unknown): StudyItem[] {
  if (!Array.isArray(value) || !value.every(isItem)) throw new Error('data/questions.json has an unexpected shape');
  const ids = new Set(value.map((item) => item.id));
  if (ids.size !== value.length) throw new Error('data/questions.json has duplicate ids');
  const correct = value.filter((item) => item.ai_is_correct).length;
  if (value.length !== MAIN_TRIAL_COUNT || correct !== MAIN_CORRECT_COUNT) {
    throw new Error(
      `data/questions.json must hold ${MAIN_TRIAL_COUNT} items with ${MAIN_CORRECT_COUNT} correct; it has ${value.length} with ${correct}`,
    );
  }
  return value;
}

export function loadStudyItems(): StudyItem[] {
  return validateStudyItems(studyQuestions);
}

/** Two real answers from the validation run that are not in the study set (see practiceItems.json). */
export function loadPracticeItems(): StudyItem[] {
  const value: unknown = practiceQuestions;
  if (!Array.isArray(value) || !value.every(isItem)) throw new Error('practiceItems.json is malformed');
  return value;
}

/** The item's stored signal in the shape the overlay renders. */
export function toSignalResponse(item: StudyItem): SignalResponse {
  const { level } = item.signal;
  return {
    status: 'signal',
    confidence: level === 'high' || level === 'medium' || level === 'low' ? level : null,
    assessmentState: level,
    score: item.signal.score,
    explanation: item.signal.reason,
    sentenceFlags: item.signal.sentence_flags ?? [],
    claimAssessments: item.signal.claim_assessments ?? [],
    modelVersion: item.signal.model_version ?? 'selfconsistency',
  };
}

/** What the tooltip on a flagged sentence says: that sentence's own flag explanation, else the overall reason. */
export function flagReason(item: StudyItem, sentenceIndex: number): string {
  const flag = item.signal.sentence_flags?.find((entry) => entry.sentenceIndex === sentenceIndex);
  return flag?.explanation?.trim() || item.signal.reason;
}
