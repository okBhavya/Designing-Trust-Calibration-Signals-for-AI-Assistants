import { useEffect, useState } from 'react';
import type { SignalResponse } from '../core/contracts';

interface OverlayProps {
  signal: SignalResponse;
}

const labels = { high: 'High confidence', medium: 'Medium confidence', low: 'Low confidence' };
const prefersDark = () =>
  typeof window.matchMedia === 'function' && window.matchMedia('(prefers-color-scheme: dark)').matches;

export function Overlay({ signal }: OverlayProps) {
  const [expanded, setExpanded] = useState(false);
  const [dark, setDark] = useState(prefersDark);
  const isMockSignal = signal.modelVersion.startsWith('mock-');

  useEffect(() => {
    if (typeof window.matchMedia !== 'function') return;
    const media = window.matchMedia('(prefers-color-scheme: dark)');
    const listener = () => setDark(media.matches);
    media.addEventListener('change', listener);
    return () => media.removeEventListener('change', listener);
  }, []);

  const title =
    signal.status === 'checking'
      ? 'Checking answer'
      : signal.status === 'not-applicable'
        ? 'No signal available'
        : signal.status === 'error' || signal.status === 'timeout'
          ? 'Could not check this answer'
        : !isMockSignal && signal.assessmentState === 'insufficient_evidence'
          ? 'Insufficient evidence'
          : !isMockSignal && signal.assessmentState === 'unavailable'
            ? 'Evaluation unavailable'
            : !isMockSignal && signal.assessmentState === 'abstained'
              ? 'Evaluation not provided'
              : signal.status === 'signal' && signal.confidence
                ? labels[signal.confidence]
          : 'Signal unavailable';

  return (
    <div className={`calibrai-overlay ${dark ? 'dark' : ''}`} role="status" aria-live="polite">
      <div className="calibrai-row">
        <span className={`calibrai-dot ${signal.confidence ?? signal.status}`} aria-hidden="true" />
        <span className="calibrai-title">{title}</span>
        {signal.status === 'signal' && (isMockSignal || signal.assessmentState !== 'unavailable') && (
          <button
            type="button"
            className="calibrai-button"
            aria-expanded={expanded}
            onClick={() => setExpanded((value) => !value)}
          >
            {expanded ? 'Hide details' : 'Why?'}
          </button>
        )}
      </div>
      {expanded && signal.explanation && <p className="calibrai-explanation">{signal.explanation}</p>}
      <span className="calibrai-meta">CalibrAI {signal.modelVersion}</span>
    </div>
  );
}
