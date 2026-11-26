import { useEffect, useId, useRef, useState } from 'react';
import { ShadowOverlay } from '@calibrai/overlay/ShadowOverlay';
import type { OverlayEventType } from '@calibrai/core/events';
import { AnswerText } from './AnswerText';
import type { Condition } from './api';
import { flagReason, toSignalResponse, type StudyItem } from './items';

export interface TrialResult {
  decision: 'accept' | 'reject';
  confidence: number;
  shownAt: Date;
  /** When the participant last chose Accept or Reject. */
  decidedAt: Date;
}

interface TrialProps {
  item: StudyItem;
  condition: Condition;
  /** e.g. "Question 4 of 30" or "Practice 1 of 2". */
  progress: string;
  onSignalEvent: (eventType: OverlayEventType | 'tooltip_opened', extra?: Record<string, string>) => void;
  onDone: (result: TrialResult) => void;
}

export const CONFIDENCE_LABELS = ['Not at all', 'Slightly', 'Moderately', 'Very', 'Completely'];

export function Trial({ item, condition, progress, onSignalEvent, onDone }: TrialProps) {
  const [decision, setDecision] = useState<'accept' | 'reject' | null>(null);
  const [confidence, setConfidence] = useState<number | null>(null);
  const shownAt = useRef<Date>(new Date());
  const decidedAt = useRef<Date | null>(null);
  const headingRef = useRef<HTMLHeadingElement>(null);
  const name = useId();

  useEffect(() => {
    shownAt.current = new Date(); // after the trial has painted
    window.scrollTo?.({ top: 0 });
    headingRef.current?.focus({ preventScroll: true });
  }, []);

  const showSignal = condition !== 'baseline';
  const flagged = condition === 'C' ? new Set(item.signal.flagged_sentence_indices) : undefined;
  const ready = decision !== null && confidence !== null;

  return (
    <section className="trial" aria-labelledby={`${name}-heading`}>
      <h1 id={`${name}-heading`} className="trial-progress" tabIndex={-1} ref={headingRef}>
        {progress}
      </h1>
      <div className="chat">
        <div className="msg user">
          <span className="sr-only">You asked:</span>
          <div className="bubble">{item.prompt}</div>
        </div>
        <div className="msg ai">
          <div className="avatar" aria-hidden="true">
            AI
          </div>
          <div className="ai-body">
            <span className="sr-only">The AI assistant answered:</span>
            <div className="answer">
              <AnswerText
                answer={item.ai_answer}
                flagged={flagged}
                reasonFor={(index) => flagReason(item, index)}
                onTooltipOpen={(index) => onSignalEvent('tooltip_opened', { sentence_index: String(index) })}
              />
            </div>
            {showSignal && <ShadowOverlay signal={toSignalResponse(item)} onEvent={(type) => onSignalEvent(type)} />}
          </div>
        </div>
      </div>

      <form
        className="decision"
        onSubmit={(event) => {
          event.preventDefault();
          if (!ready) return;
          onDone({ decision: decision!, confidence: confidence!, shownAt: shownAt.current, decidedAt: decidedAt.current! });
        }}
      >
        <fieldset>
          <legend>Do you accept the AI's answer?</legend>
          <div className="segmented two">
            {(['accept', 'reject'] as const).map((value) => (
              <label key={value} className="segment">
                <input
                  type="radio"
                  name={`${name}-decision`}
                  value={value}
                  checked={decision === value}
                  onChange={() => {
                    setDecision(value);
                    decidedAt.current = new Date();
                  }}
                />
                <span>{value === 'accept' ? 'Accept' : 'Reject'}</span>
              </label>
            ))}
          </div>
        </fieldset>
        <fieldset>
          <legend>How confident are you in your decision?</legend>
          <div className="segmented five">
            {CONFIDENCE_LABELS.map((label, index) => (
              <label key={label} className="segment">
                <input
                  type="radio"
                  name={`${name}-confidence`}
                  value={index + 1}
                  checked={confidence === index + 1}
                  onChange={() => setConfidence(index + 1)}
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
          <button type="submit" className="primary" disabled={!ready}>
            Next
          </button>
        </div>
      </form>
    </section>
  );
}
