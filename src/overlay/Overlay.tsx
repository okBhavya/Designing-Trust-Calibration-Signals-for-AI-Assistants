import {
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
  useState,
  type CSSProperties,
  type KeyboardEvent,
  type RefObject,
} from 'react';
import type { SignalResponse } from '../core/contracts';
import type { OverlayEventType } from '../core/events';
import { ChevronIcon, CloseIcon, LevelIcon, RetryIcon, VerdictMark } from './icons';
import { detectHostTheme, measureAnswerColumn, watchHostTheme, type OverlayTheme } from './theme';
import {
  CLAIM_STATE_LABELS,
  describeSignal,
  pillAriaLabel,
  statusText,
  verdictSummary,
  type OverlayView,
} from './viewModel';

export interface OverlayProps {
  signal: SignalResponse;
  onEvent?: (eventType: OverlayEventType) => void;
  /** Forces a theme instead of reading the host page background (previews, study harness). */
  theme?: OverlayTheme;
  /** When set, the "couldn't check" state offers a retry button that calls it. */
  onRetry?: () => void;
  /** Starts with the details panel open (previews only; emits no event). */
  defaultExpanded?: boolean;
}

type Column = { inset: number; width: number } | null;

/** Light/dark from the page behind the overlay, plus the answer column it should line up with. */
function useHostLayout(rootRef: RefObject<HTMLElement>, forcedTheme?: OverlayTheme) {
  const [theme, setTheme] = useState<OverlayTheme>(forcedTheme ?? 'light');
  const [column, setColumn] = useState<Column>(null);
  const [ready, setReady] = useState(false);

  // Enable transitions one frame after the first detected theme has painted.
  useEffect(() => {
    if (typeof requestAnimationFrame !== 'function') return setReady(true);
    const frame = requestAnimationFrame(() => setReady(true));
    return () => cancelAnimationFrame(frame);
  }, []);

  useLayoutEffect(() => {
    if (forcedTheme) {
      setTheme(forcedTheme);
      return;
    }
    const root = rootRef.current;
    const host = root?.getRootNode() instanceof ShadowRoot ? (root.getRootNode() as ShadowRoot).host : root;
    const update = () => setTheme(detectHostTheme(host ?? null));
    update();
    return watchHostTheme(update);
  }, [forcedTheme]);

  useLayoutEffect(() => {
    const root = rootRef.current;
    const rootNode = root?.getRootNode();
    // mountOverlay inserts the host right after the answer container.
    const answer = rootNode instanceof ShadowRoot ? rootNode.host.previousElementSibling : null;
    if (!answer) return;
    const update = () => setColumn(measureAnswerColumn(answer));
    update();
    if (typeof ResizeObserver !== 'function') return;
    const observer = new ResizeObserver(update);
    observer.observe(answer);
    return () => observer.disconnect();
  }, []);

  return { theme, column, ready };
}

export function Overlay({ signal, onEvent, theme: forcedTheme, onRetry, defaultExpanded = false }: OverlayProps) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const [dismissed, setDismissed] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const pillRef = useRef<HTMLButtonElement>(null);
  const panelId = useId();
  const { theme, column, ready } = useHostLayout(rootRef, forcedTheme);
  const view = describeSignal(signal);

  useEffect(() => {
    if (signal.status === 'signal') onEvent?.('signal_shown');
  }, [signal.status, signal.modelVersion]);

  if (dismissed) return null;

  const isOpen = expanded && view.expandable;
  const toggle = () => {
    if (!isOpen) onEvent?.('explanation_opened');
    setExpanded(!isOpen);
  };
  const onKeyDown = (event: KeyboardEvent) => {
    if (event.key === 'Escape' && isOpen) {
      event.stopPropagation();
      setExpanded(false);
      pillRef.current?.focus();
    }
  };
  const style = column
    ? ({ '--calibrai-inset': `${column.inset}px`, '--calibrai-column': `${column.width}px` } as CSSProperties)
    : undefined;

  const pillContent = (
    <>
      <span className="calibrai-icon">
        <LevelIcon kind={view.kind} />
      </span>
      <span className="calibrai-label">{view.label}</span>
      {view.reason && (
        <>
          <span className="calibrai-sep" aria-hidden="true">
            ·
          </span>
          <span className="calibrai-reason">{view.reason}</span>
        </>
      )}
    </>
  );

  return (
    <div
      ref={rootRef}
      className="calibrai-overlay"
      data-theme={theme}
      data-kind={view.kind}
      data-tone={view.tone}
      data-expanded={isOpen || undefined}
      data-ready={ready || undefined}
      style={style}
      onKeyDown={onKeyDown}
    >
      <span className="calibrai-sr" role="status" aria-live="polite">
        {statusText(view)}
      </span>
      <div className="calibrai-bar">
        {view.expandable ? (
          <button
            ref={pillRef}
            type="button"
            className="calibrai-pill"
            aria-expanded={isOpen}
            aria-controls={isOpen ? panelId : undefined}
            aria-label={pillAriaLabel(view, isOpen)}
            onClick={toggle}
          >
            {pillContent}
            <span className="calibrai-chevron" aria-hidden="true">
              <ChevronIcon />
            </span>
          </button>
        ) : (
          <div className="calibrai-pill" aria-hidden="true">
            {pillContent}
          </div>
        )}
        {view.kind === 'unavailable' && onRetry && (
          <button type="button" className="calibrai-icon-button" aria-label="Try checking this answer again" title="Try again" onClick={onRetry}>
            <RetryIcon />
          </button>
        )}
        {view.dismissible && (
          <button
            type="button"
            className="calibrai-icon-button"
            aria-label="Dismiss confidence signal"
            title="Dismiss"
            onClick={() => {
              onEvent?.('signal_dismissed');
              setDismissed(true);
            }}
          >
            <CloseIcon />
          </button>
        )}
      </div>
      {isOpen && <Panel id={panelId} view={view} modelVersion={signal.modelVersion} />}
    </div>
  );
}

function Panel({ id, view, modelVersion }: { id: string; view: OverlayView; modelVersion: string }) {
  const samples = view.sampleCount;
  return (
    <div id={id} className="calibrai-panel" role="region" aria-label="Confidence details">
      {/* The clip collapses to zero height for the reveal animation; the card holds the chrome. */}
      <div className="calibrai-panel-clip">
        <div className="calibrai-card">
          {view.sentence && <p className="calibrai-sentence">{view.sentence}</p>}
          {view.claims.length > 0 && (
            <ul className="calibrai-claims" aria-label="Checked claims, weakest first">
              {view.claims.map((claim) => (
                <li key={claim.key} className="calibrai-claim" data-tone={claim.tone}>
                  <span className={`calibrai-claim-text${claim.hasText ? '' : ' placeholder'}`} title={claim.text}>
                    {claim.text}
                  </span>
                  {claim.verdicts.length > 0 && (
                    <span className="calibrai-marks" role="img" aria-label={verdictSummary(claim)} title={verdictSummary(claim)}>
                      {claim.verdicts.map((verdict, index) => (
                        <VerdictMark key={index} verdict={verdict} />
                      ))}
                    </span>
                  )}
                  <span className="calibrai-tag">{CLAIM_STATE_LABELS[claim.state]}</span>
                </li>
              ))}
            </ul>
          )}
          <div className="calibrai-footer">
            {samples ? (
              <div className="calibrai-legend" aria-hidden="true">
                <span>
                  <VerdictMark verdict="supported" /> agreed
                </span>
                <span>
                  <VerdictMark verdict="contradicted" /> disagreed
                </span>
                <span>
                  <VerdictMark verdict="not_mentioned" /> didn't mention it
                </span>
              </div>
            ) : null}
            <p>
              {samples
                ? `Checked by comparing ${samples} independent AI answers. This can be wrong.`
                : 'This signal can be wrong.'}
            </p>
            <p className="calibrai-version">Model: {modelVersion}</p>
          </div>
        </div>
      </div>
    </div>
  );
}
