import { useEffect, useRef, useState } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import type { SignalResponse } from '../../src/core/contracts';
import { Overlay } from '../../src/overlay/Overlay';
import overlayStyles from '../../src/overlay/overlay.css?inline';
import { previewFixtures, type PreviewFixture } from '../../src/overlay/previewFixtures';
import './style.css';

/** Host page palettes, so the overlay can be judged against each site's real background. */
const hosts = {
  chatgpt: {
    name: 'ChatGPT',
    font: 'ui-sans-serif, -apple-system, system-ui, "Segoe UI", Helvetica, Arial, sans-serif',
    light: { bg: '#ffffff', fg: '#0d0d0d' },
    dark: { bg: '#212121', fg: '#ececec' },
  },
  claude: {
    name: 'Claude',
    font: 'ui-sans-serif, system-ui, "Segoe UI", sans-serif',
    light: { bg: '#faf9f5', fg: '#141413' },
    dark: { bg: '#262624', fg: '#f5f4ef' },
  },
  gemini: {
    name: 'Gemini',
    font: '"Google Sans", Roboto, Arial, sans-serif',
    light: { bg: '#ffffff', fg: '#1b1c1d' },
    dark: { bg: '#1b1c1d', fg: '#e3e3e3' },
  },
} as const;
type HostId = keyof typeof hosts;
type Mode = 'light' | 'dark';
type Log = (line: string) => void;

/**
 * Mounts an overlay the way mountOverlay does (a Shadow DOM host right after the answer), so
 * theme detection and column alignment run against the surrounding page, not a forced prop.
 */
function ShadowOverlay({ signal, expanded, retry, log }: { signal: SignalResponse; expanded: boolean; retry: boolean; log: Log }) {
  const hostRef = useRef<HTMLDivElement>(null);
  const rootRef = useRef<Root>();
  useEffect(() => {
    const host = hostRef.current!;
    if (!rootRef.current) {
      const shadow = host.shadowRoot ?? host.attachShadow({ mode: 'open' });
      const style = document.createElement('style');
      style.textContent = overlayStyles;
      shadow.append(style);
      rootRef.current = createRoot(shadow);
    }
    rootRef.current.render(
      <Overlay
        signal={signal}
        defaultExpanded={expanded}
        onEvent={log}
        onRetry={retry ? () => log('retry clicked') : undefined}
      />,
    );
  });
  useEffect(() => () => rootRef.current?.unmount(), []);
  return <div ref={hostRef} data-calibrai-overlay="true" />;
}

function Cell({ fixture, host, mode, log }: { fixture: PreviewFixture; host: HostId; mode: Mode; log: Log }) {
  const palette = hosts[host][mode];
  const canExpand = fixture.signal.status === 'signal' && fixture.signal.assessmentState !== 'unavailable';
  return (
    <div className="cell" style={{ background: palette.bg, color: palette.fg, fontFamily: hosts[host].font }}>
      {(canExpand ? [false, true] : [false]).map((expanded) => (
        <div className="variant" key={String(expanded)}>
          {canExpand && <div className="variant-label">{expanded ? 'Expanded' : 'Collapsed'}</div>}
          <p className="answer">An answer from the assistant would appear here, ending with this sentence.</p>
          <ShadowOverlay
            signal={fixture.signal}
            expanded={expanded}
            retry={Boolean(fixture.retry)}
            log={(event) => log(`${fixture.id} / ${mode}${expanded ? ' / expanded' : ''}: ${event}`)}
          />
        </div>
      ))}
    </div>
  );
}

function Row({ fixture, host, log }: { fixture: PreviewFixture; host: HostId; log: Log }) {
  const { signal } = fixture;
  return (
    <>
      <div className="state">
        {fixture.title}
        <small>{signal.status === 'signal' ? signal.assessmentState ?? signal.confidence : signal.status}</small>
      </div>
      <Cell fixture={fixture} host={host} mode="light" log={log} />
      <Cell fixture={fixture} host={host} mode="dark" log={log} />
    </>
  );
}

function Preview() {
  const [host, setHost] = useState<HostId>('chatgpt');
  const [events, setEvents] = useState<string[]>([]);
  const [epoch, setEpoch] = useState(0);
  const log: Log = (line) =>
    setEvents((list) => [`${new Date().toLocaleTimeString()}  ${line}`, ...list].slice(0, 50));

  // Overlays re-read the page background when <body> attributes change, as on a real theme switch.
  useEffect(() => {
    document.body.dataset.theme = host;
  }, [host]);

  return (
    <>
      <header>
        <h1>CalibrAI overlay preview</h1>
        <label>
          Host page
          <select value={host} onChange={(event) => setHost(event.target.value as HostId)}>
            {Object.entries(hosts).map(([id, value]) => (
              <option key={id} value={id}>
                {value.name}
              </option>
            ))}
          </select>
        </label>
        <button type="button" onClick={() => setEpoch(epoch + 1)}>
          Reset (restore dismissed)
        </button>
        <p className="hint">
          Each overlay detects light or dark from its cell's background, as it does on the real sites. Tab through to
          check focus rings; Escape closes a panel. Turn on "reduce motion" in your OS settings to check the static
          variants.
        </p>
      </header>
      <div className="grid" key={`${epoch}-${host}`}>
        <div />
        <div className="col-head">Light</div>
        <div className="col-head">Dark</div>
        {previewFixtures.map((fixture) => (
          <Row key={fixture.id} fixture={fixture} host={host} log={log} />
        ))}
      </div>
      <div className="log" aria-label="Emitted events">
        {events.length ? events.map((line, index) => <div key={index}>{line}</div>) : 'Emitted events appear here.'}
      </div>
    </>
  );
}

createRoot(document.getElementById('root')!).render(<Preview />);
