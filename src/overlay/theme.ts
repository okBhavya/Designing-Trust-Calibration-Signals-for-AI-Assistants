export type OverlayTheme = 'light' | 'dark';

/** Parses `rgb()`/`rgba()` in comma or space syntax. Returns [r, g, b, alpha] or null. */
export function parseCssColor(value: string): [number, number, number, number] | null {
  const match = /^rgba?\(([^)]+)\)$/i.exec(value.trim());
  if (!match) return null;
  const parts = match[1].split(/[\s,/]+/).filter(Boolean);
  if (parts.length < 3) return null;
  const [r, g, b] = parts.slice(0, 3).map(Number);
  const alphaPart = parts[3];
  const alpha = alphaPart === undefined ? 1 : alphaPart.endsWith('%') ? parseFloat(alphaPart) / 100 : Number(alphaPart);
  if ([r, g, b, alpha].some((n) => Number.isNaN(n))) return null;
  return [r, g, b, alpha];
}

/** WCAG relative luminance of an sRGB colour (0–255 channels). */
export function relativeLuminance(r: number, g: number, b: number): number {
  const channel = (c: number) => {
    const s = c / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
}

const prefersDark = () =>
  typeof window !== 'undefined' &&
  typeof window.matchMedia === 'function' &&
  window.matchMedia('(prefers-color-scheme: dark)').matches;

/**
 * Reads the effective background behind `element` by walking up to the first ancestor with a
 * mostly opaque background. Falls back to the OS colour scheme when nothing is painted.
 */
export function detectHostTheme(element: Element | null): OverlayTheme {
  for (let node = element; node; node = node.parentElement) {
    const color = parseCssColor(getComputedStyle(node).backgroundColor);
    if (color && color[3] >= 0.5) return relativeLuminance(color[0], color[1], color[2]) < 0.2 ? 'dark' : 'light';
  }
  return prefersDark() ? 'dark' : 'light';
}

/**
 * Calls `onChange` when the host page may have switched theme: the OS scheme changes, or the
 * page toggles a class/style/theme attribute on <html> or <body> (how ChatGPT, Claude and
 * Gemini switch). Returns a cleanup function.
 */
export function watchHostTheme(onChange: () => void): () => void {
  const cleanups: Array<() => void> = [];
  if (typeof window.matchMedia === 'function') {
    const media = window.matchMedia('(prefers-color-scheme: dark)');
    media.addEventListener('change', onChange);
    cleanups.push(() => media.removeEventListener('change', onChange));
  }
  if (typeof MutationObserver === 'function') {
    const observer = new MutationObserver(onChange);
    const attributeFilter = ['class', 'style', 'data-theme', 'data-mode', 'data-color-scheme'];
    for (const target of [document.documentElement, document.body]) {
      if (target) observer.observe(target, { attributes: true, attributeFilter });
    }
    cleanups.push(() => observer.disconnect());
  }
  return () => cleanups.forEach((cleanup) => cleanup());
}

/**
 * Where the answer's text starts and how wide its column is, so the pill lines up with the
 * text's left edge and the panel never outgrows the answer. `answer` is the element the
 * overlay host was inserted after.
 */
export function measureAnswerColumn(answer: Element | null): { inset: number; width: number } | null {
  if (!answer) return null;
  const style = getComputedStyle(answer);
  const inset = (parseFloat(style.paddingLeft) || 0) + (parseFloat(style.borderLeftWidth) || 0);
  const right = (parseFloat(style.paddingRight) || 0) + (parseFloat(style.borderRightWidth) || 0);
  const width = answer.getBoundingClientRect().width - inset - right;
  return { inset, width: width > 0 ? width : 0 };
}
