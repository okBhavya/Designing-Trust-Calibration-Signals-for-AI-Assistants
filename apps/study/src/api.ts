export type Condition = 'baseline' | 'A' | 'C';
export const CONDITIONS: readonly Condition[] = ['baseline', 'A', 'C'];
export type StudyEventType = 'signal_shown' | 'explanation_opened' | 'signal_dismissed' | 'tooltip_opened';

export interface Enrollment {
  participantId: string;
  token: string;
  condition: Condition;
  consentVersion: string;
}

/** Body of POST /v1/study/trials, minus participant_id. */
export interface TrialRecord {
  question_id: string;
  position: number;
  condition: Condition;
  ai_correct: boolean;
  signal_level: string | null;
  signal_score: number | null;
  shown_at: string;
  decided_at: string;
  decision: 'accept' | 'reject';
  self_confidence: number;
  final_correct: boolean;
}

export type Instrument = 'demographics' | 'trust';

export interface StudyApi {
  readonly demo: boolean;
  enroll(code: string, consentVersion: string): Promise<Enrollment>;
  postTrial(enrollment: Enrollment, trial: TrialRecord): Promise<void>;
  postQuestionnaire(enrollment: Enrollment, instrument: Instrument, responses: Record<string, number | string>): Promise<void>;
  postEvent(enrollment: Enrollment, eventType: StudyEventType, metadata: Record<string, string>): Promise<void>;
  deleteParticipant(enrollment: Enrollment): Promise<void>;
}

/** status 0 = the request never got an HTTP response (offline, timeout, CORS). */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

const REQUEST_TIMEOUT_MS = 15_000;

export function createHttpApi(baseUrl: string, fetchImpl: typeof fetch = (...args) => fetch(...args)): StudyApi {
  const base = baseUrl.replace(/\/+$/, '');

  async function request(path: string, init: RequestInit & { token?: string } = {}): Promise<unknown> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
    let response: Response;
    try {
      response = await fetchImpl(`${base}${path}`, {
        ...init,
        signal: controller.signal,
        headers: {
          'Content-Type': 'application/json',
          ...(init.token ? { Authorization: `Bearer ${init.token}` } : {}),
        },
      });
    } catch (error) {
      throw new ApiError(0, error instanceof Error && error.name === 'AbortError' ? 'Request timed out' : 'Network error');
    } finally {
      clearTimeout(timer);
    }
    if (!response.ok) {
      let detail = response.statusText;
      try {
        const body = (await response.json()) as { detail?: unknown };
        if (typeof body.detail === 'string') detail = body.detail;
      } catch {
        // keep the status text
      }
      throw new ApiError(response.status, detail || `HTTP ${response.status}`);
    }
    return response.status === 204 ? null : response.json();
  }

  const post = (path: string, enrollment: Enrollment, body: object) =>
    request(path, {
      method: 'POST',
      token: enrollment.token,
      body: JSON.stringify({ participant_id: enrollment.participantId, ...body }),
    });

  return {
    demo: false,
    async enroll(code, consentVersion) {
      const body = (await request('/v1/study/enroll', {
        method: 'POST',
        body: JSON.stringify({ enrollment_code: code, consent_version: consentVersion, consent: true }),
      })) as { participant_id: string; access_token: string; condition: Condition; consent_version: string };
      return {
        participantId: body.participant_id,
        token: body.access_token,
        condition: body.condition,
        consentVersion: body.consent_version,
      };
    },
    async postTrial(enrollment, trial) {
      await post('/v1/study/trials', enrollment, trial);
    },
    async postQuestionnaire(enrollment, instrument, responses) {
      await post('/v1/study/questionnaire', enrollment, { instrument, responses });
    },
    async postEvent(enrollment, eventType, metadata) {
      await post('/v1/events', enrollment, { event_type: eventType, metadata });
    },
    async deleteParticipant(enrollment) {
      await request(`/v1/participant/${enrollment.participantId}`, { method: 'DELETE', token: enrollment.token });
    },
  };
}

/** VITE_DEMO=1: the whole flow with no backend. Records are only logged to the console. */
export function createDemoApi(condition?: Condition, log: (...args: unknown[]) => void = console.info): StudyApi {
  const pause = () => new Promise((resolve) => setTimeout(resolve, 120));
  const record = async (...args: unknown[]) => {
    await pause();
    log('[demo, not saved]', ...args);
  };
  return {
    demo: true,
    async enroll(_code, consentVersion) {
      await pause();
      const assigned = condition ?? CONDITIONS[Math.floor(Math.random() * CONDITIONS.length)];
      return { participantId: crypto.randomUUID(), token: 'demo', condition: assigned, consentVersion };
    },
    postTrial: (_enrollment, trial) => record('trial', trial),
    postQuestionnaire: (_enrollment, instrument, responses) => record('questionnaire', instrument, responses),
    postEvent: (_enrollment, eventType, metadata) => record('event', eventType, metadata),
    deleteParticipant: () => record('delete participant'),
  };
}

export function parseCondition(value: string | null | undefined): Condition | undefined {
  return CONDITIONS.find((condition) => condition === value);
}
