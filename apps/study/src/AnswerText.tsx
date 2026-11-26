import { Fragment, useEffect, useId, useLayoutEffect, useRef, useState, type CSSProperties, type ReactNode } from 'react';
import { splitSentences } from './sentences';

const EMPHASIS = /(\*\*[^*\n]+\*\*|\*[^*\s][^*\n]*\*)/g;

/** Renders the **bold** and *italic* Markdown the assistant answers contain; everything else stays text. */
export function renderInline(text: string): ReactNode[] {
  return text.split(EMPHASIS).map((part, index) => {
    if (part.startsWith('**') && part.endsWith('**') && part.length > 4) return <strong key={index}>{part.slice(2, -2)}</strong>;
    if (part.startsWith('*') && part.endsWith('*') && part.length > 2) return <em key={index}>{part.slice(1, -1)}</em>;
    return part;
  });
}

interface AnswerTextProps {
  answer: string;
  /** Sentence indices to underline (condition C); empty for the other conditions. */
  flagged?: ReadonlySet<number>;
  reasonFor?: (sentenceIndex: number) => string;
  onTooltipOpen?: (sentenceIndex: number) => void;
}

/** The answer split into the backend's sentences, so flag indices land on the right sentence. */
export function AnswerText({ answer, flagged, reasonFor, onTooltipOpen }: AnswerTextProps) {
  const sentences = splitSentences(answer);
  const blocks = new Map<number, typeof sentences>();
  for (const sentence of sentences) blocks.set(sentence.block, [...(blocks.get(sentence.block) ?? []), sentence]);
  return (
    <>
      {[...blocks.entries()].map(([block, items]) =>
        items[0].isCode ? (
          <pre key={block}>
            <code>{items[0].text}</code>
          </pre>
        ) : (
          <p key={block}>
            {items.map((sentence, position) => (
              <Fragment key={sentence.index}>
                {position > 0 && ' '}
                {flagged?.has(sentence.index) ? (
                  <FlaggedSentence
                    text={sentence.text}
                    reason={reasonFor?.(sentence.index) ?? ''}
                    onOpen={() => onTooltipOpen?.(sentence.index)}
                  />
                ) : (
                  renderInline(sentence.text)
                )}
              </Fragment>
            ))}
          </p>
        ),
      )}
    </>
  );
}

const TIP_MAX_WIDTH = 320;
const GAP = 6;

/**
 * A dotted underline with a tooltip giving the checker's reason. Opens on hover, keyboard focus or
 * tap; Escape closes it until the pointer or focus leaves. The reason is also the sentence's
 * accessible description, so screen readers hear it without opening the tooltip.
 */
function FlaggedSentence({ text, reason, onOpen }: { text: string; reason: string; onOpen: () => void }) {
  const [open, setOpen] = useState(false);
  const [suppressed, setSuppressed] = useState(false);
  const [style, setStyle] = useState<CSSProperties>({});
  const anchorRef = useRef<HTMLSpanElement>(null);
  const id = useId();

  const show = () => {
    if (suppressed || open) return;
    setOpen(true);
    onOpen();
  };
  const reset = () => {
    setOpen(false);
    setSuppressed(false);
  };

  useLayoutEffect(() => {
    if (!open || !anchorRef.current) return;
    const place = () => {
      const rects = anchorRef.current!.getClientRects();
      const rect = rects[rects.length - 1] ?? anchorRef.current!.getBoundingClientRect();
      const width = Math.min(TIP_MAX_WIDTH, window.innerWidth - 16);
      const left = Math.max(8, Math.min(rect.left, window.innerWidth - width - 8));
      const below = rect.bottom + GAP + 96 < window.innerHeight;
      setStyle(
        below
          ? { left, top: rect.bottom + GAP, maxWidth: width }
          : { left, bottom: window.innerHeight - rect.top + GAP, maxWidth: width },
      );
    };
    place();
    window.addEventListener('scroll', place, true);
    window.addEventListener('resize', place);
    return () => {
      window.removeEventListener('scroll', place, true);
      window.removeEventListener('resize', place);
    };
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setOpen(false);
        setSuppressed(true);
      }
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open]);

  return (
    <span
      ref={anchorRef}
      className="flagged"
      tabIndex={0}
      aria-describedby={id}
      data-open={open || undefined}
      onMouseEnter={show}
      onMouseLeave={reset}
      onFocus={show}
      onBlur={reset}
      onClick={show}
    >
      {renderInline(text)}
      <span role="tooltip" id={id} className="flag-tip" hidden={!open} style={style}>
        <span className="flag-tip-title">Flagged by the checker</span>
        {reason}
      </span>
    </span>
  );
}
