import { useEffect, useMemo, useState, useSyncExternalStore } from 'react';
import type { OverlayEventType } from '@calibrai/core/events';
import { ApiError, type Enrollment, type StudyApi, type TrialRecord } from './api';
import { loadPracticeItems, loadStudyItems, type StudyItem } from './items';
import { Outbox } from './outbox';
import { shuffle } from './random';
import {
  ConsentScreen,
  DebriefScreen,
  DemographicsScreen,
  MainIntroScreen,
  PracticeIntroScreen,
  QuestionnaireScreen,
  StopScreen,
  StoppedScreen,
} from './screens';
import { Trial, type TrialResult } from './Trial';

type Step =
  | { kind: 'consent' }
  | { kind: 'demographics' }
  | { kind: 'practice-intro' }
  | { kind: 'practice'; index: number }
  | { kind: 'main-intro' }
  | { kind: 'trial'; index: number }
  | { kind: 'questionnaire' }
  | { kind: 'debrief' }
  | { kind: 'stopped'; deleted: boolean };

export interface AppProps {
  api: StudyApi;
  enrollmentCode: string;
  consentVersion: string;
  /** Injected in tests; defaults to the bundled data/questions.json and practice items. */
  items?: StudyItem[];
  practiceItems?: StudyItem[];
  outbox?: Outbox;
  random?: () => number;
}

function enrollError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 401) return 'This study link has an invalid access code. Please use the link you were given.';
    if (error.status === 409) return 'This page is out of date. Please reload it and try again.';
    if (error.status === 503) return 'The study is not open at the moment.';
    if (error.status === 0) return "We couldn't reach the study server. Check your connection and try again.";
  }
  return 'Something went wrong while starting the study. Please try again.';
}

export function App({ api, enrollmentCode, consentVersion, items, practiceItems, outbox: injected, random }: AppProps) {
  const outbox = useMemo(() => injected ?? new Outbox(), [injected]);
  const saving = useSyncExternalStore(outbox.subscribe, outbox.getState);
  const mainItems = useMemo(() => items ?? loadStudyItems(), [items]);
  const practice = useMemo(() => practiceItems ?? loadPracticeItems(), [practiceItems]);

  const [step, setStep] = useState<Step>({ kind: 'consent' });
  const [enrollment, setEnrollment] = useState<Enrollment | null>(null);
  const [order, setOrder] = useState<StudyItem[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [stopping, setStopping] = useState(false);

  // Warn before closing the tab while answers are still being saved.
  useEffect(() => {
    if (!saving.pending) return;
    const warn = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = '';
    };
    window.addEventListener('beforeunload', warn);
    return () => window.removeEventListener('beforeunload', warn);
  }, [saving.pending]);

  const condition = enrollment?.condition ?? 'baseline';
  const inProgress = enrollment !== null && step.kind !== 'debrief' && step.kind !== 'stopped';

  async function start() {
    setBusy(true);
    setError(null);
    try {
      const enrolled = await api.enroll(enrollmentCode, consentVersion);
      setEnrollment(enrolled);
      setOrder(shuffle(mainItems, random));
      setStep({ kind: 'demographics' });
    } catch (caught) {
      setError(enrollError(caught));
    } finally {
      setBusy(false);
    }
  }

  function save(label: string, payload: unknown, send: (enrolled: Enrollment) => Promise<void>) {
    const enrolled = enrollment!;
    outbox.enqueue(label, payload, () => send(enrolled));
  }

  function logSignalEvent(item: StudyItem, position: number, eventType: OverlayEventType | 'tooltip_opened', extra: Record<string, string> = {}) {
    const metadata = { question_id: item.id, condition, phase: 'main', position: String(position), ...extra };
    save(`event ${eventType}`, { eventType, metadata }, (enrolled) => api.postEvent(enrolled, eventType, metadata));
  }

  function finishTrial(item: StudyItem, position: number, result: TrialResult) {
    const record: TrialRecord = {
      question_id: item.id,
      position,
      condition,
      ai_correct: item.ai_is_correct,
      signal_level: item.signal.level,
      signal_score: item.signal.score,
      shown_at: result.shownAt.toISOString(),
      decided_at: result.decidedAt.toISOString(),
      decision: result.decision,
      self_confidence: result.confidence,
      final_correct: (result.decision === 'accept') === item.ai_is_correct,
    };
    save(`trial ${item.id}`, record, (enrolled) => api.postTrial(enrolled, record));
    setStep(position + 1 < order.length ? { kind: 'trial', index: position + 1 } : { kind: 'questionnaire' });
  }

  async function stop(deleteData: boolean) {
    if (!deleteData || !enrollment) {
      setStopping(false);
      setStep({ kind: 'stopped', deleted: false });
      return;
    }
    setBusy(true);
    setError(null);
    outbox.clear();
    try {
      await api.deleteParticipant(enrollment);
      setStopping(false);
      setStep({ kind: 'stopped', deleted: true });
    } catch {
      setError("We couldn't delete your answers just now. Please try again, or contact the research team.");
    } finally {
      setBusy(false);
    }
  }

  let body;
  if (stopping) {
    body = <StopScreen busy={busy} error={error} onContinue={() => setStopping(false)} onStop={(deleteData) => void stop(deleteData)} />;
  } else {
    switch (step.kind) {
      case 'consent':
        body = (
          <ConsentScreen
            consentVersion={consentVersion}
            missingCode={!api.demo && !enrollmentCode}
            error={error}
            busy={busy}
            onAgree={() => void start()}
          />
        );
        break;
      case 'demographics':
        body = (
          <DemographicsScreen
            onSubmit={(responses) => {
              save('demographics', responses, (enrolled) => api.postQuestionnaire(enrolled, 'demographics', responses));
              setStep({ kind: 'practice-intro' });
            }}
          />
        );
        break;
      case 'practice-intro':
        body = <PracticeIntroScreen condition={condition} onStart={() => setStep({ kind: 'practice', index: 0 })} />;
        break;
      case 'practice': {
        const item = practice[step.index];
        body = (
          <Trial
            key={item.id}
            item={item}
            condition={condition}
            progress={`Practice ${step.index + 1} of ${practice.length}`}
            onSignalEvent={() => {}} // practice is not logged
            onDone={() =>
              setStep(step.index + 1 < practice.length ? { kind: 'practice', index: step.index + 1 } : { kind: 'main-intro' })
            }
          />
        );
        break;
      }
      case 'main-intro':
        body = <MainIntroScreen onStart={() => setStep({ kind: 'trial', index: 0 })} />;
        break;
      case 'trial': {
        const item = order[step.index];
        const position = step.index;
        body = (
          <Trial
            key={item.id}
            item={item}
            condition={condition}
            progress={`Question ${position + 1} of ${order.length}`}
            onSignalEvent={(eventType, extra) => logSignalEvent(item, position, eventType, extra)}
            onDone={(result) => finishTrial(item, position, result)}
          />
        );
        break;
      }
      case 'questionnaire':
        body = (
          <QuestionnaireScreen
            onSubmit={(responses) => {
              save('trust questionnaire', responses, (enrolled) => api.postQuestionnaire(enrolled, 'trust', responses));
              setStep({ kind: 'debrief' });
            }}
          />
        );
        break;
      case 'debrief':
        body = <DebriefScreen state={saving} demo={api.demo} />;
        break;
      case 'stopped':
        body = <StoppedScreen deleted={step.deleted} state={saving} demo={api.demo} />;
        break;
    }
  }

  const savingLabel = saving.failed.length
    ? "Some answers couldn't be saved"
    : saving.pending
      ? saving.retrying
        ? 'Saving… (connection problem, retrying)'
        : 'Saving…'
      : '';

  return (
    <div className="app">
      <header className="topbar">
        <span className="brand">AI answer study</span>
        {api.demo && <span className="tag">Demo: nothing is saved</span>}
        <span className="saving" role="status" aria-live="polite" data-problem={saving.failed.length > 0 || saving.retrying || undefined}>
          {savingLabel}
        </span>
        {inProgress && !stopping && (
          <button type="button" className="link" onClick={() => setStopping(true)}>
            Stop
          </button>
        )}
      </header>
      <main>{body}</main>
    </div>
  );
}
