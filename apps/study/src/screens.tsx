import { useEffect, useId, useRef, useState, type ReactNode } from 'react';
import type { Condition } from './api';
import { MAIN_CORRECT_COUNT, MAIN_TRIAL_COUNT } from './items';
import type { FailedRecord, OutboxState } from './outbox';

/** A screen with a heading that takes focus when it appears, so keyboard and screen-reader users start at the top. */
export function Screen({ title, children }: { title: string; children: ReactNode }) {
  const headingRef = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    window.scrollTo?.({ top: 0 });
    headingRef.current?.focus({ preventScroll: true });
  }, []);
  return (
    <section className="screen">
      <h1 tabIndex={-1} ref={headingRef}>
        {title}
      </h1>
      {children}
    </section>
  );
}

export function ConsentScreen({
  consentVersion,
  missingCode,
  error,
  busy,
  onAgree,
}: {
  consentVersion: string;
  missingCode: boolean;
  error: string | null;
  busy: boolean;
  onAgree: () => void;
}) {
  const [agreed, setAgreed] = useState(false);
  return (
    <Screen title="Judging AI answers: a short study">
      <p className="lead">
        You will read {MAIN_TRIAL_COUNT} questions answered by an AI assistant and decide whether to accept each answer.
        It takes about 15 to 20 minutes.
      </p>
      <h2>What to know before you start</h2>
      <ul className="plain-list">
        <li>
          <strong>The answers are pre-generated.</strong> You are not chatting with a live AI, and nothing you type is
          sent to one.
        </li>
        <li>
          <strong>Your data is pseudonymous.</strong> We record your choices, how long they take, which explanations you
          open and your questionnaire answers, under a random ID. We don't ask for your name, email or anything else
          that identifies you.
        </li>
        <li>
          <strong>You can stop at any time.</strong> Close the tab or use <em>Stop</em> at the top of the page. You can
          also ask for everything you've answered to be deleted, without giving a reason.
        </li>
      </ul>
      {missingCode && (
        <p className="notice error" role="alert">
          This study link is missing its access code. Please use the link you were given.
        </p>
      )}
      {error && (
        <p className="notice error" role="alert">
          {error}
        </p>
      )}
      <form
        onSubmit={(event) => {
          event.preventDefault();
          if (agreed && !busy && !missingCode) onAgree();
        }}
      >
        <label className="check">
          <input type="checkbox" checked={agreed} onChange={(event) => setAgreed(event.target.checked)} />
          <span>I have read this and agree to take part.</span>
        </label>
        <div className="actions">
          <button type="submit" className="primary" disabled={!agreed || busy || missingCode}>
            {busy ? 'Starting…' : 'Start'}
          </button>
        </div>
      </form>
      <p className="fine-print">Consent version {consentVersion}</p>
    </Screen>
  );
}

export const AGE_BANDS: Array<[string, string]> = [
  ['18-24', '18–24'],
  ['25-34', '25–34'],
  ['35-44', '35–44'],
  ['45-54', '45–54'],
  ['55-64', '55–64'],
  ['65+', '65 or older'],
  ['prefer_not_to_say', 'Prefer not to say'],
];
export const EXPERIENCE_LABELS = ['None', 'A little', 'Some', 'A lot', 'Daily use'];

export function DemographicsScreen({ onSubmit }: { onSubmit: (responses: { age_band: string; ai_experience: number }) => void }) {
  const [age, setAge] = useState<string | null>(null);
  const [experience, setExperience] = useState<number | null>(null);
  const name = useId();
  return (
    <Screen title="About you">
      <p className="lead">Two quick questions before the practice.</p>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          if (age && experience) onSubmit({ age_band: age, ai_experience: experience });
        }}
      >
        <fieldset>
          <legend>Your age</legend>
          <div className="options">
            {AGE_BANDS.map(([value, label]) => (
              <label key={value} className="option">
                <input type="radio" name={`${name}-age`} value={value} checked={age === value} onChange={() => setAge(value)} />
                <span>{label}</span>
              </label>
            ))}
          </div>
        </fieldset>
        <fieldset>
          <legend>How much experience do you have with AI chat assistants such as ChatGPT, Claude or Gemini?</legend>
          <div className="segmented five">
            {EXPERIENCE_LABELS.map((label, index) => (
              <label key={label} className="segment">
                <input
                  type="radio"
                  name={`${name}-experience`}
                  value={index + 1}
                  checked={experience === index + 1}
                  onChange={() => setExperience(index + 1)}
                />
                <span>
                  <strong>{index + 1}</strong>
                  <small>{label}</small>
                </span>
              </label>
            ))}
          </div>
        </fieldset>
        <div className="actions">
          <button type="submit" className="primary" disabled={!age || !experience}>
            Continue
          </button>
        </div>
      </form>
    </Screen>
  );
}

/** What the participant is told about the signal. Baseline participants are not told about signals at all. */
function signalInstructions(condition: Condition): ReactNode {
  if (condition === 'baseline') return null;
  return (
    <>
      <li>
        Below each answer, a label from an automated checker says how consistent the answer looked. Select the label to
        see which claims it checked.
      </li>
      {condition === 'C' && (
        <li>
          Sentences the checker flagged have a dotted underline. Point at one, tap it or move to it with the Tab key to
          see why.
        </li>
      )}
    </>
  );
}

export function PracticeIntroScreen({ condition, onStart }: { condition: Condition; onStart: () => void }) {
  return (
    <Screen title="How it works">
      <ul className="plain-list">
        <li>Each screen shows a question and the AI assistant's answer.</li>
        {signalInstructions(condition)}
        <li>
          Decide whether you would <strong>accept</strong> the answer as correct or <strong>reject</strong> it, then say
          how confident you are in that decision.
        </li>
        <li>Answer on your own, without looking anything up.</li>
      </ul>
      <p>We start with 2 practice questions. They don't count.</p>
      <div className="actions">
        <button type="button" className="primary" onClick={onStart}>
          Start the practice
        </button>
      </div>
    </Screen>
  );
}

export function MainIntroScreen({ onStart }: { onStart: () => void }) {
  return (
    <Screen title="Practice done">
      <p className="lead">
        Now the {MAIN_TRIAL_COUNT} real questions. Take each one at your own pace; there's no time limit.
      </p>
      <div className="actions">
        <button type="button" className="primary" onClick={onStart}>
          Start
        </button>
      </div>
    </Screen>
  );
}

export const TRUST_ITEMS: Array<[string, string]> = [
  ['trust_1', "I trusted the AI assistant's answers."],
  ['trust_2', "I could tell when the AI assistant's answers were wrong."],
  ['trust_3', 'I felt confident in my accept and reject decisions.'],
  ['trust_4', 'I would rely on this AI assistant for factual questions.'],
  ['trust_5', "I was cautious about the AI assistant's answers."],
];
const LIKERT_ANCHORS: Record<number, string> = { 1: 'Strongly disagree', 4: 'Neutral', 7: 'Strongly agree' };

export function QuestionnaireScreen({ onSubmit }: { onSubmit: (responses: Record<string, number>) => void }) {
  const [answers, setAnswers] = useState<Record<string, number>>({});
  const name = useId();
  const complete = TRUST_ITEMS.every(([key]) => answers[key]);
  return (
    <Screen title="Almost done">
      <p className="lead">How much do you agree with each statement about the AI assistant you just worked with?</p>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          if (complete) onSubmit(answers);
        }}
      >
        {TRUST_ITEMS.map(([key, statement]) => (
          <fieldset key={key} className="likert">
            <legend>{statement}</legend>
            <div className="segmented seven">
              {[1, 2, 3, 4, 5, 6, 7].map((value) => (
                <label key={value} className="segment">
                  <input
                    type="radio"
                    name={`${name}-${key}`}
                    value={value}
                    checked={answers[key] === value}
                    onChange={() => setAnswers((current) => ({ ...current, [key]: value }))}
                    aria-label={LIKERT_ANCHORS[value] ? `${value}, ${LIKERT_ANCHORS[value]}` : String(value)}
                  />
                  <span>
                    <strong>{value}</strong>
                  </span>
                </label>
              ))}
            </div>
            <div className="anchors" aria-hidden="true">
              <span>Strongly disagree</span>
              <span>Strongly agree</span>
            </div>
          </fieldset>
        ))}
        <div className="actions">
          <button type="submit" className="primary" disabled={!complete}>
            Finish
          </button>
        </div>
      </form>
    </Screen>
  );
}

function downloadUnsaved(failed: FailedRecord[]) {
  const blob = new Blob([JSON.stringify(failed, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = 'unsaved-study-answers.json';
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1_000);
}

/** Shown wherever saving status matters at the end: never let a lost record go unnoticed. */
export function SaveStatus({ state, demo }: { state: OutboxState; demo: boolean }) {
  if (state.failed.length) {
    return (
      <div className="notice error" role="alert">
        <p>
          {state.failed.length === 1 ? '1 answer' : `${state.failed.length} answers`} couldn't be saved. Please download
          them and send the file to the research team, so nothing is lost.
        </p>
        <button type="button" className="secondary" onClick={() => downloadUnsaved(state.failed)}>
          Download unsaved answers
        </button>
      </div>
    );
  }
  if (state.pending) {
    return (
      <p className="notice" role="status">
        Saving your last answers… Please keep this tab open.
      </p>
    );
  }
  return (
    <p className="notice ok" role="status">
      {demo ? 'Demo mode: nothing was saved.' : 'All your answers are saved. You can close this tab.'}
    </p>
  );
}

export function DebriefScreen({ state, demo }: { state: OutboxState; demo: boolean }) {
  const percent = Math.round((MAIN_CORRECT_COUNT / MAIN_TRIAL_COUNT) * 100);
  return (
    <Screen title="Thank you">
      <SaveStatus state={state} demo={demo} />
      <h2>About this study</h2>
      <ul className="plain-list">
        <li>
          The AI answers were generated in advance. We chose them so that the AI was right exactly {percent}% of the
          time: {MAIN_CORRECT_COUNT} of the {MAIN_TRIAL_COUNT} answers were correct and {MAIN_TRIAL_COUNT - MAIN_CORRECT_COUNT}{' '}
          were wrong.
        </li>
        <li>
          If you saw confidence labels or underlined sentences, they came from an automated checker that compares several
          AI answers to the same question. It can be wrong: a confidently repeated mistake can look consistent.
        </li>
        <li>Participants saw different versions of the page; we compare how people decide with and without the checker.</li>
      </ul>
      <p>If you have questions or want your answers deleted later, contact the research team with the study name.</p>
    </Screen>
  );
}

export function StopScreen({
  busy,
  error,
  onContinue,
  onStop,
}: {
  busy: boolean;
  error: string | null;
  onContinue: () => void;
  onStop: (deleteData: boolean) => void;
}) {
  return (
    <Screen title="Stop the study?">
      <p className="lead">You can stop now. Nothing bad happens if you do.</p>
      {error && (
        <p className="notice error" role="alert">
          {error}
        </p>
      )}
      <div className="actions stacked">
        <button type="button" className="primary" onClick={onContinue} disabled={busy}>
          Continue the study
        </button>
        <button type="button" className="secondary" onClick={() => onStop(false)} disabled={busy}>
          Stop and keep my answers
        </button>
        <button type="button" className="secondary danger" onClick={() => onStop(true)} disabled={busy}>
          {busy ? 'Deleting…' : 'Stop and delete my answers'}
        </button>
      </div>
    </Screen>
  );
}

export function StoppedScreen({ deleted, state, demo }: { deleted: boolean; state: OutboxState; demo: boolean }) {
  return (
    <Screen title="You've stopped the study">
      {deleted ? (
        <p className="notice ok" role="status">
          Everything you answered has been deleted. You can close this tab.
        </p>
      ) : (
        <SaveStatus state={state} demo={demo} />
      )}
      <p>Thank you for your time.</p>
    </Screen>
  );
}
