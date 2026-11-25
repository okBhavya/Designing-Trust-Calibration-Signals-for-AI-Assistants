import type { ConfidenceLevel, SignalResponse } from '../core/contracts';

/**
 * Turns a SignalResponse into what the overlay shows. Pure and DOM-free so every state can be
 * unit tested and previewed. The raw score is never surfaced; counts come from per-sample
 * verdicts (`sample-N` source ids) on the claim assessments.
 */

export type OverlayKind = 'checking' | 'high' | 'medium' | 'low' | 'not-checkable' | 'unavailable';
export type OverlayTone = 'high' | 'medium' | 'low' | 'neutral';
export type SampleVerdict = 'supported' | 'contradicted' | 'not_mentioned';
export type ClaimState = 'agreed' | 'disputed' | 'not-checked';

export interface ClaimRow {
  key: string;
  /** Claim text, or "Claim N" when a replayed response carries no text. */
  text: string;
  hasText: boolean;
  state: ClaimState;
  tone: OverlayTone;
  /** One entry per independent answer; empty when the method is not sample based. */
  verdicts: SampleVerdict[];
  supported: number;
  contradicted: number;
}

export interface OverlayView {
  kind: OverlayKind;
  tone: OverlayTone;
  label: string;
  /** Short pill reason such as "5/5 checks agree". */
  reason?: string;
  /** The reason as read aloud: "5 of 5 checks agree". */
  spokenReason?: string;
  /** One plain sentence explaining the level, for the expanded panel. */
  sentence?: string;
  claims: ClaimRow[];
  /** Number of independent answers compared, when the method is sample based. */
  sampleCount?: number;
  expandable: boolean;
  dismissible: boolean;
}

export const LEVEL_LABELS: Record<ConfidenceLevel, string> = {
  high: 'Likely reliable',
  medium: 'Partly consistent',
  low: 'Check before relying on it',
};

export const CLAIM_STATE_LABELS: Record<ClaimState, string> = {
  agreed: 'Agreed',
  disputed: 'Disputed',
  'not-checked': 'Not checked',
};

const LEVEL_SENTENCES: Record<ConfidenceLevel, string> = {
  high: 'Independent answers to the same question agreed with what this answer says.',
  medium:
    'Independent answers agreed with most of this answer but disagreed on at least one point, so check the disputed claim.',
  low: 'Independent answers often disagreed with at least one claim here, so verify it before relying on this answer.',
};

const SAMPLE_ID = /^sample-(\d+)$/;
const AGREED = new Set(['consistent', 'supported']);
const DISPUTED = new Set(['partially_consistent', 'inconsistent', 'contradicted']);
const NOT_CHECKED = new Set(['not_addressed', 'insufficient_evidence']);

type Assessment = NonNullable<SignalResponse['claimAssessments']>[number];

function sampleIndices(ids: string[] | undefined): number[] {
  return (ids ?? []).flatMap((id) => {
    const match = SAMPLE_ID.exec(id);
    return match ? [Number(match[1])] : [];
  });
}

/** Number of independent answers, from sample ids or "(N samples)" in evidenceStrength. */
function countSamples(assessments: Assessment[]): number | undefined {
  let count = 0;
  for (const item of assessments) {
    for (const index of [...sampleIndices(item.supportingSourceIds), ...sampleIndices(item.contradictingSourceIds)]) {
      count = Math.max(count, index);
    }
    const stated = /(\d+) samples/.exec(item.evidenceStrength ?? '');
    if (stated) count = Math.max(count, Number(stated[1]));
  }
  return count > 0 ? count : undefined;
}

function claimState(item: Assessment): ClaimState {
  if (NOT_CHECKED.has(item.assessment)) return 'not-checked';
  if (AGREED.has(item.assessment)) return 'agreed';
  if (DISPUTED.has(item.assessment)) return 'disputed';
  return item.confidence === 'high' ? 'agreed' : 'disputed';
}

function toRow(item: Assessment, index: number, sampleCount: number | undefined): ClaimRow {
  const supported = new Set(sampleIndices(item.supportingSourceIds));
  const contradicted = new Set(sampleIndices(item.contradictingSourceIds));
  const verdicts: SampleVerdict[] = sampleCount
    ? Array.from({ length: sampleCount }, (_, i) =>
        supported.has(i + 1) ? 'supported' : contradicted.has(i + 1) ? 'contradicted' : 'not_mentioned',
      )
    : [];
  const state = claimState(item);
  const text = item.claim?.trim();
  return {
    key: item.claimId ?? `claim-${index}`,
    text: text || `Claim ${index + 1}`,
    hasText: Boolean(text),
    state,
    tone: state === 'not-checked' ? 'neutral' : item.confidence,
    verdicts,
    supported: supported.size,
    contradicted: contradicted.size,
  };
}

const supportRate = (row: ClaimRow) => row.supported / (row.supported + row.contradicted);
const isScored = (row: ClaimRow) => row.state !== 'not-checked' && row.supported + row.contradicted > 0;

/**
 * The claim the headline level rests on: the scored claim whose support rate equals the
 * backend score (the backend scores the weakest material claim), else the lowest rate.
 */
function weakestScored(rows: ClaimRow[], score: number | null | undefined): ClaimRow | undefined {
  const scored = rows.filter(isScored);
  if (typeof score === 'number') {
    const match = scored.find((row) => Math.abs(supportRate(row) - score) < 1e-3);
    if (match) return match;
  }
  return scored.reduce<ClaimRow | undefined>(
    (weakest, row) => (!weakest || supportRate(row) < supportRate(weakest) ? row : weakest),
    undefined,
  );
}

/** Weakest first: the headline claim, then scored claims by support, then unchecked ones. */
function orderClaims(rows: ClaimRow[], headline: ClaimRow | undefined): ClaimRow[] {
  const rank = (row: ClaimRow) => (row === headline ? -1 : isScored(row) ? supportRate(row) : 2);
  return rows
    .map((row, index) => ({ row, index }))
    .sort((a, b) => rank(a.row) - rank(b.row) || a.index - b.index)
    .map(({ row }) => row);
}

function levelOf(signal: SignalResponse, isMock: boolean): ConfidenceLevel | 'not-checkable' | 'unavailable' {
  if (!isMock) {
    if (signal.assessmentState === 'unavailable') return 'unavailable';
    if (signal.assessmentState === 'insufficient_evidence' || signal.assessmentState === 'abstained') {
      return 'not-checkable';
    }
  }
  return signal.confidence ?? 'not-checkable';
}

export function describeSignal(signal: SignalResponse): OverlayView {
  const base = { claims: [] as ClaimRow[], expandable: false, dismissible: signal.status !== 'checking' };

  if (signal.status === 'checking') {
    return { ...base, kind: 'checking', tone: 'neutral', label: 'Checking answer…' };
  }
  if (signal.status === 'error' || signal.status === 'timeout') {
    return {
      ...base,
      kind: 'unavailable',
      tone: 'neutral',
      label: "Couldn't check this answer",
      sentence: "The checking service didn't respond in time.",
    };
  }
  if (signal.status === 'not-applicable') {
    return { ...base, kind: 'not-checkable', tone: 'neutral', label: 'Not checkable' };
  }

  const isMock = signal.modelVersion.startsWith('mock-');
  const level = levelOf(signal, isMock);
  const assessments = signal.claimAssessments ?? [];
  const sampleCount = countSamples(assessments);
  const rows = assessments.map((item, index) => toRow(item, index, sampleCount));
  const headline = weakestScored(rows, signal.score);
  const claims = orderClaims(rows, headline);
  const explanation = signal.explanation?.trim() || undefined;

  if (level === 'unavailable') {
    return {
      ...base,
      kind: 'unavailable',
      tone: 'neutral',
      label: "Couldn't check this answer",
      sentence: explanation,
    };
  }

  if (level === 'not-checkable') {
    const sentence =
      signal.assessmentState === 'insufficient_evidence' && sampleCount
        ? 'Too few of the independent answers mentioned these claims to compare them, so no level is given.'
        : explanation ?? "This answer didn't contain a claim that could be checked.";
    return {
      ...base,
      kind: 'not-checkable',
      tone: 'neutral',
      label: 'Not checkable',
      sentence,
      claims,
      sampleCount,
      expandable: true,
    };
  }

  const counted = headline && sampleCount ? headline : undefined;
  const mentions = counted ? counted.supported + counted.contradicted : 0;
  return {
    ...base,
    kind: level,
    tone: level,
    label: LEVEL_LABELS[level],
    reason: counted ? `${counted.supported}/${mentions} checks agree` : isMock ? 'demo signal' : undefined,
    spokenReason: counted ? `${counted.supported} of ${mentions} checks agree` : isMock ? 'Demo signal' : undefined,
    // Sample-based results get a plain sentence; other methods keep their own explanation.
    sentence: sampleCount ? LEVEL_SENTENCES[level] : explanation ?? LEVEL_SENTENCES[level],
    claims,
    sampleCount,
    expandable: true,
  };
}

/** What a screen reader hears when the state changes: "Confidence: likely reliable. 5 of 5 checks agree." */
export function statusText(view: OverlayView): string {
  const label = `Confidence: ${view.label.toLowerCase().replace(/…$/, '')}.`;
  return view.spokenReason ? `${label} ${view.spokenReason}.` : label;
}

export function pillAriaLabel(view: OverlayView, expanded: boolean): string {
  if (!view.expandable) return statusText(view);
  return `${statusText(view)} ${expanded ? 'Collapse details.' : 'Expand for details.'}`;
}

export function verdictSummary(row: ClaimRow): string {
  const missing = row.verdicts.length - row.supported - row.contradicted;
  return `${row.supported} agreed, ${row.contradicted} disagreed, ${missing} didn't mention it`;
}
