import type { SignalResponse } from '../core/contracts';

/** One signal per overlay state, for the dev preview page and the overlay tests. */
export interface PreviewFixture {
  id: string;
  title: string;
  signal: SignalResponse;
  /** The preview shows a retry button for this state. */
  retry?: boolean;
}

type Claim = NonNullable<SignalResponse['claimAssessments']>[number];

const VERSION = 'selfconsistency-v2:gpt-4o-mini';
const ids = (list: number[]) => list.map((n) => `sample-${n}`);

/** A self-consistency claim: which of the 5 samples supported or contradicted it. */
function claim(id: string, text: string | undefined, supported: number[], contradicted: number[]): Claim {
  const mentions = supported.length + contradicted.length;
  const rate = mentions ? supported.length / mentions : 0;
  const addressed = mentions >= 2;
  const level = rate >= 0.8 ? 'high' : rate >= 0.6 ? 'medium' : 'low';
  return {
    claimId: id,
    ...(text === undefined ? {} : { claim: text }),
    assessment: !addressed
      ? 'not_addressed'
      : { high: 'consistent', medium: 'partially_consistent', low: 'inconsistent' }[level],
    confidence: addressed ? level : 'low',
    evidenceStrength: addressed
      ? `${supported.length} of ${mentions} mentions supported (5 samples)`
      : `mentioned by ${mentions} of 5 samples`,
    supportingSourceIds: ids(supported),
    contradictingSourceIds: ids(contradicted),
  };
}

const highClaims = [
  claim('c1', 'The Eiffel Tower was completed in 1889 for the Exposition Universelle in Paris.', [1, 2, 3, 4, 5], []),
  claim('c2', 'It was the tallest man-made structure in the world until 1930.', [1, 2, 3, 5], []),
  claim('c3', 'Gustave Eiffel’s company designed and built it.', [1, 2, 3, 4, 5], []),
];

const mediumClaims = [
  claim('c1', 'Python 3.12 removed the distutils module from the standard library.', [1, 2, 3, 4, 5], []),
  claim('c2', 'The removal was first announced in PEP 632, accepted in 2020.', [1, 3, 4], [2, 5]),
  claim('c3', 'setuptools still ships a compatible distutils shim.', [2], []),
];

const lowClaims = [
  claim('c1', 'Ibuprofen and acetaminophen can usually be taken together for short periods.', [1, 2, 3, 4], [5]),
  claim('c2', 'The maximum adult dose of acetaminophen is 6 grams per day.', [3], [1, 2, 4, 5]),
  claim(
    'c3',
    'Taking them at staggered intervals every three hours gives smoother pain relief than taking either one alone, according to most guidance.',
    [1, 2],
    [4],
  ),
];

export const previewFixtures: PreviewFixture[] = [
  { id: 'checking', title: 'Checking', signal: { status: 'checking', modelVersion: 'api' } },
  {
    id: 'high',
    title: 'High',
    signal: {
      status: 'signal',
      confidence: 'high',
      assessmentState: 'high',
      score: 1,
      claimAssessments: highClaims,
      explanation: 'All 5 attempts agreed on "The Eiffel Tower was completed in 1889…"',
      modelVersion: VERSION,
    },
  },
  {
    id: 'medium',
    title: 'Medium',
    signal: {
      status: 'signal',
      confidence: 'medium',
      assessmentState: 'medium',
      score: 0.6,
      claimAssessments: mediumClaims,
      explanation: '3 of 5 attempts agreed on "The removal was first announced…"; 1 side detail not checked',
      modelVersion: VERSION,
    },
  },
  {
    id: 'low',
    title: 'Low',
    signal: {
      status: 'signal',
      confidence: 'low',
      assessmentState: 'low',
      score: 0.2,
      claimAssessments: lowClaims,
      explanation: '1 of 5 attempts agreed on "The maximum adult dose…"',
      modelVersion: VERSION,
    },
  },
  {
    id: 'replayed',
    title: 'Replayed (no claim text)',
    signal: {
      status: 'signal',
      confidence: 'medium',
      assessmentState: 'medium',
      score: 0.6,
      claimAssessments: mediumClaims.map(({ claim: _text, ...rest }) => rest),
      explanation: '3 of 5 attempts agreed on claim c2; 1 side detail not checked',
      modelVersion: VERSION,
    },
  },
  {
    id: 'insufficient',
    title: 'Insufficient evidence',
    signal: {
      status: 'signal',
      confidence: null,
      assessmentState: 'insufficient_evidence',
      score: null,
      claimAssessments: [
        claim('c1', 'The village has a population of about 1,200 people.', [3], []),
        claim('c2', 'Its church dates from the 14th century.', [], [2]),
      ],
      explanation: 'None of the 2 claims was mentioned by at least 2 of the 5 independent attempts, so none could be checked.',
      modelVersion: VERSION,
    },
  },
  {
    id: 'abstained',
    title: 'Abstained',
    signal: {
      status: 'signal',
      confidence: null,
      assessmentState: 'abstained',
      score: null,
      explanation: "The assistant didn't give a checkable answer.",
      modelVersion: VERSION,
    },
  },
  {
    id: 'unavailable',
    title: 'Unavailable',
    signal: {
      status: 'signal',
      confidence: null,
      assessmentState: 'unavailable',
      score: null,
      explanation: 'The checking model did not respond.',
      modelVersion: VERSION,
    },
  },
  { id: 'error', title: 'Error (with retry)', signal: { status: 'error', modelVersion: 'api' }, retry: true },
  {
    id: 'mock',
    title: 'Mock provider',
    signal: {
      status: 'signal',
      confidence: 'high',
      explanation: 'Mock signal for the extension foundation. This is not a factuality assessment.',
      modelVersion: 'mock-v1',
    },
  },
];
