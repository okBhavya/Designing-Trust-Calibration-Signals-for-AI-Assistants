import type { ReactNode } from 'react';
import type { OverlayKind, SampleVerdict } from './viewModel';

/** Inline 16px icons drawn in currentColor. Decorative: the adjacent text carries meaning. */
function Svg({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <svg
      className={className}
      width="16"
      height="16"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {children}
    </svg>
  );
}

export function LevelIcon({ kind }: { kind: OverlayKind }) {
  switch (kind) {
    case 'high':
      return (
        <Svg>
          <circle cx="8" cy="8" r="6.25" />
          <path d="m5.5 8.2 1.7 1.7 3.3-3.6" />
        </Svg>
      );
    case 'medium':
      return (
        <Svg>
          <circle cx="8" cy="8" r="6.25" />
          <path d="M8 1.75a6.25 6.25 0 0 0 0 12.5z" fill="currentColor" stroke="none" />
        </Svg>
      );
    case 'low':
      return (
        <Svg>
          <path d="M7.13 2.4a1 1 0 0 1 1.74 0l5.5 9.6a1 1 0 0 1-.87 1.5H2.5a1 1 0 0 1-.87-1.5z" />
          <path d="M8 6.2v3" />
          <circle cx="8" cy="11.1" r=".35" fill="currentColor" />
        </Svg>
      );
    case 'not-checkable':
      return (
        <Svg>
          <circle cx="8" cy="8" r="6.25" strokeDasharray="2.4 2.2" />
        </Svg>
      );
    case 'unavailable':
      return (
        <Svg>
          <circle cx="8" cy="8" r="6.25" />
          <path d="m3.6 12.4 8.8-8.8" />
        </Svg>
      );
    case 'checking':
      return (
        <Svg className="calibrai-spin">
          <circle cx="8" cy="8" r="6.25" opacity=".3" />
          <path d="M8 1.75a6.25 6.25 0 0 1 6.25 6.25" />
        </Svg>
      );
  }
}

export const ChevronIcon = () => (
  <Svg>
    <path d="m4.5 6.25 3.5 3.5 3.5-3.5" />
  </Svg>
);

export const CloseIcon = () => (
  <Svg>
    <path d="m4.75 4.75 6.5 6.5m0-6.5-6.5 6.5" />
  </Svg>
);

export const RetryIcon = () => (
  <Svg>
    <path d="M2.75 8a5.25 5.25 0 1 0 1.6-3.77" />
    <path d="M2.75 2.75v2.5h2.5" />
  </Svg>
);

/**
 * One mark per independent answer. Shape differs as well as colour: filled dot = agreed,
 * cross = disagreed, hollow ring = didn't mention the claim.
 */
export function VerdictMark({ verdict }: { verdict: SampleVerdict }) {
  return (
    <svg className={`calibrai-mark ${verdict}`} width="8" height="8" viewBox="0 0 8 8" aria-hidden="true" focusable="false">
      {verdict === 'supported' && <circle cx="4" cy="4" r="3.5" fill="currentColor" />}
      {verdict === 'contradicted' && (
        <path d="m1.2 1.2 5.6 5.6m0-5.6-5.6 5.6" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
      )}
      {verdict === 'not_mentioned' && <circle cx="4" cy="4" r="3" fill="none" stroke="currentColor" strokeWidth="1" />}
    </svg>
  );
}
