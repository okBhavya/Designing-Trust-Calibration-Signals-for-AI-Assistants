import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { SignalResponse } from '../src/core/contracts';
import { Overlay, type OverlayProps } from '../src/overlay/Overlay';
import { previewFixtures } from '../src/overlay/previewFixtures';
import { detectHostTheme, parseCssColor, relativeLuminance } from '../src/overlay/theme';
import { describeSignal, pillAriaLabel } from '../src/overlay/viewModel';

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const fixture = (id: string): SignalResponse => previewFixtures.find((item) => item.id === id)!.signal;

describe('overlay view model', () => {
  it.each([
    ['high', 'high', 'Likely reliable', '5/5 checks agree'],
    ['medium', 'medium', 'Partly consistent', '3/5 checks agree'],
    ['low', 'low', 'Check before relying on it', '1/5 checks agree'],
    ['replayed', 'medium', 'Partly consistent', '3/5 checks agree'],
    ['insufficient', 'not-checkable', 'Not checkable', undefined],
    ['abstained', 'not-checkable', 'Not checkable', undefined],
    ['unavailable', 'unavailable', "Couldn't check this answer", undefined],
    ['error', 'unavailable', "Couldn't check this answer", undefined],
    ['checking', 'checking', 'Checking answer…', undefined],
  ])('%s → %s "%s"', (id, kind, label, reason) => {
    const view = describeSignal(fixture(id));
    expect(view.kind).toBe(kind);
    expect(view.label).toBe(label);
    expect(view.reason).toBe(reason);
  });

  it('counts the weakest scored claim and lists it first', () => {
    const view = describeSignal(fixture('low'));
    expect(view.claims.map((claim) => claim.key)).toEqual(['c2', 'c3', 'c1']);
    expect(view.claims[0].verdicts).toEqual(['contradicted', 'contradicted', 'supported', 'contradicted', 'contradicted']);
    expect(view.claims.map((claim) => claim.state)).toEqual(['disputed', 'disputed', 'agreed']);
  });

  it('puts claims no sample checked last, tagged Not checked', () => {
    const view = describeSignal(fixture('medium'));
    expect(view.claims.map((claim) => [claim.key, claim.state])).toEqual([
      ['c2', 'disputed'],
      ['c1', 'agreed'],
      ['c3', 'not-checked'],
    ]);
  });

  it('names claims "Claim N" when a replayed response has no claim text', () => {
    const view = describeSignal(fixture('replayed'));
    expect(view.claims.map((claim) => claim.text)).toEqual(['Claim 2', 'Claim 1', 'Claim 3']);
    expect(view.claims.every((claim) => !claim.hasText)).toBe(true);
  });

  it('reads the pill aloud as a sentence', () => {
    expect(pillAriaLabel(describeSignal(fixture('high')), false)).toBe(
      'Confidence: likely reliable. 5 of 5 checks agree. Expand for details.',
    );
    expect(pillAriaLabel(describeSignal(fixture('low')), true)).toBe(
      'Confidence: check before relying on it. 1 of 5 checks agree. Collapse details.',
    );
  });

  it('never says "wrong" about the answer and never shows the raw score', () => {
    for (const { signal } of previewFixtures) {
      const view = describeSignal(signal);
      expect(`${view.label} ${view.reason ?? ''}`).not.toMatch(/wrong/i);
      if (typeof signal.score === 'number' && signal.score % 1 !== 0) {
        expect(JSON.stringify(view)).not.toContain(String(signal.score));
      }
    }
  });

  it('keeps the pre-existing mock behaviour of showing confidence despite assessmentState', () => {
    const view = describeSignal({ status: 'signal', confidence: 'medium', assessmentState: 'abstained', modelVersion: 'mock-v1' });
    expect(view.kind).toBe('medium');
  });
});

describe('overlay rendering', () => {
  let root: Root | undefined;
  let container: HTMLElement | undefined;

  afterEach(() => {
    act(() => root?.unmount());
    container?.remove();
    root = container = undefined;
  });

  async function render(props: OverlayProps) {
    container = document.createElement('div');
    document.body.append(container);
    root = createRoot(container);
    await act(async () => root!.render(<Overlay {...props} />));
    return container;
  }

  it.each(previewFixtures.flatMap((item) => (['light', 'dark'] as const).map((theme) => [item.id, theme] as const)))(
    'renders %s in %s, collapsed and expanded',
    async (id, theme) => {
      const signal = fixture(id);
      const collapsed = await render({ signal, theme });
      const overlay = collapsed.querySelector('.calibrai-overlay')!;
      expect(overlay.getAttribute('data-theme')).toBe(theme);
      expect(overlay.querySelector('.calibrai-pill')).not.toBeNull();
      // The model version only ever appears in the expanded footer.
      expect(collapsed.textContent).not.toContain(signal.modelVersion);
      act(() => root!.unmount());

      const expanded = await render({ signal, theme, defaultExpanded: true });
      const view = describeSignal(signal);
      if (view.expandable) {
        expect(expanded.querySelector('.calibrai-footer')!.textContent).toContain(signal.modelVersion);
        expect(expanded.querySelectorAll('.calibrai-claim')).toHaveLength(view.claims.length);
      } else {
        expect(expanded.querySelector('.calibrai-panel')).toBeNull();
      }
    },
  );

  it('shows five marks per claim and the sample count in the footer', async () => {
    const view = await render({ signal: fixture('high'), defaultExpanded: true });
    const marks = view.querySelectorAll('.calibrai-claim')[0].querySelectorAll('.calibrai-mark');
    expect(marks).toHaveLength(5);
    expect(view.querySelector('.calibrai-footer')!.textContent).toContain(
      'Checked by comparing 5 independent AI answers. This can be wrong.',
    );
    const text = view.querySelector('.calibrai-claim-text')!;
    expect(text.getAttribute('title')).toBe(text.textContent);
  });

  it('tabs pill → dismiss, and Escape collapses back to the pill', async () => {
    const onEvent = vi.fn();
    const view = await render({ signal: fixture('medium'), onEvent });
    const buttons = Array.from(view.querySelectorAll('button'));
    expect(buttons.map((button) => button.getAttribute('aria-label'))).toEqual([
      'Confidence: partly consistent. 3 of 5 checks agree. Expand for details.',
      'Dismiss confidence signal',
    ]);
    const pill = buttons[0];
    await act(async () => pill.click());
    expect(pill.getAttribute('aria-expanded')).toBe('true');
    expect(view.querySelector('.calibrai-panel')).not.toBeNull();

    const inside = view.querySelector('.calibrai-panel')!;
    await act(async () => inside.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true })));
    expect(pill.getAttribute('aria-expanded')).toBe('false');
    expect(view.querySelector('.calibrai-panel')).toBeNull();
    expect(document.activeElement).toBe(pill);
    expect(onEvent.mock.calls).toEqual([['signal_shown'], ['explanation_opened']]);
  });

  it('offers retry only on the could-not-check state when a handler is given', async () => {
    const onRetry = vi.fn();
    const view = await render({ signal: fixture('error'), onRetry });
    const retry = view.querySelector<HTMLButtonElement>('button[aria-label="Try checking this answer again"]')!;
    await act(async () => retry.click());
    expect(onRetry).toHaveBeenCalledOnce();
    act(() => root!.unmount());

    const high = await render({ signal: fixture('high'), onRetry });
    expect(high.querySelector('button[aria-label="Try checking this answer again"]')).toBeNull();
  });

  it('announces state changes through a polite live region', async () => {
    const view = await render({ signal: fixture('low') });
    const status = view.querySelector('[role="status"]')!;
    expect(status.getAttribute('aria-live')).toBe('polite');
    expect(status.textContent).toBe('Confidence: check before relying on it. 1 of 5 checks agree.');
  });

  it('has no dismiss button while checking', async () => {
    const view = await render({ signal: fixture('checking') });
    expect(view.querySelectorAll('button')).toHaveLength(0);
    expect(view.textContent).toContain('Checking answer…');
  });
});

describe('host theme detection', () => {
  it('parses computed colours', () => {
    expect(parseCssColor('rgb(33, 33, 33)')).toEqual([33, 33, 33, 1]);
    expect(parseCssColor('rgba(0, 0, 0, 0)')).toEqual([0, 0, 0, 0]);
    expect(parseCssColor('rgb(250 249 245 / 50%)')).toEqual([250, 249, 245, 0.5]);
    expect(parseCssColor('transparent')).toBeNull();
  });

  it('uses the nearest painted ancestor background', () => {
    const page = document.createElement('div');
    const wrapper = document.createElement('div');
    const host = document.createElement('div');
    page.append(wrapper);
    wrapper.append(host);
    document.body.append(page);
    try {
      page.style.backgroundColor = 'rgb(33, 33, 33)';
      expect(detectHostTheme(host)).toBe('dark');
      wrapper.style.backgroundColor = 'rgb(250, 249, 245)';
      expect(detectHostTheme(host)).toBe('light');
      wrapper.style.backgroundColor = 'rgba(255, 255, 255, 0.1)';
      expect(detectHostTheme(host)).toBe('dark');
    } finally {
      page.remove();
    }
  });
});

describe('overlay colour tokens', () => {
  it('overlay.css takes its tokens from tokens.css', () => {
    const overlayCss = readFileSync(resolve(process.cwd(), 'src/overlay/overlay.css'), 'utf8');
    expect(overlayCss).toContain("@import './tokens.css';");
    expect(overlayCss).not.toMatch(/--c-text:/);
  });

  // Read from disk: vitest stubs CSS imports, even ?raw ones.
  const css = readFileSync(resolve(process.cwd(), 'src/overlay/tokens.css'), 'utf8');
  const block = (selector: string) => {
    const start = css.indexOf(`${selector} {`);
    return css.slice(start, css.indexOf('}', start));
  };
  const tokens = (text: string) =>
    Object.fromEntries(Array.from(text.matchAll(/--(c-[a-z-]+):\s*(#[0-9a-f]{6})/g), (match) => [match[1], match[2]]));
  const hex = (value: string) => [1, 3, 5].map((i) => parseInt(value.slice(i, i + 2), 16)) as [number, number, number];
  const contrast = (a: string, b: string) => {
    const [x, y] = [relativeLuminance(...hex(a)), relativeLuminance(...hex(b))].sort((p, q) => q - p);
    return (x + 0.05) / (y + 0.05);
  };

  it.each([
    ['light', '.calibrai-tokens', ['#ffffff', '#faf9f5']],
    ['dark', ".calibrai-tokens[data-theme='dark']", ['#212121', '#262624', '#1b1c1d']],
  ])('keeps every %s text token at 4.5:1 or more', (_name, selector, hostBackgrounds) => {
    const theme = tokens(block(selector));
    const backgrounds = [theme['c-surface'], theme['c-surface-hover'], ...hostBackgrounds];
    for (const name of ['c-text', 'c-muted', 'c-high', 'c-medium', 'c-low', 'c-neutral']) {
      for (const background of backgrounds) {
        expect(contrast(theme[name], background), `${name} on ${background}`).toBeGreaterThanOrEqual(4.5);
      }
    }
  });
});
