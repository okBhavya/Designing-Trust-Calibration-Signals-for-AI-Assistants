/** Delay after a DOM mutation before scanning, so bursts of mutations cause one scan. */
export const MUTATION_SCAN_DELAY_MS = 250;
/**
 * Delay before re-checking an answer that is still streaming or not yet stable. Completion needs two
 * scans that see the same text; some sites stop mutating the page as soon as streaming ends, so
 * without this follow-up the second scan would never run and the answer would never be captured.
 */
export const SETTLE_SCAN_DELAY_MS = 1_000;

export interface ScanScheduler {
  /** Request a scan after a DOM mutation. */
  onMutation(): void;
  /** Run a scan now (used once at start-up). */
  scanNow(): void;
}

/**
 * Coalesces scan requests. `scan` resolves to true when some answer still needs another look
 * (streaming or not yet stable); a follow-up scan is then scheduled even if the page does not
 * change again.
 */
export function createScanScheduler(
  scan: () => Promise<boolean>,
  timers: { setTimeout: (callback: () => void, ms: number) => unknown } = window,
): ScanScheduler {
  // Independent timers: a pending follow-up must not delay the quicker scan a mutation asks for.
  const pending = { mutation: false, settle: false };

  const run = async () => {
    if (await scan()) schedule('settle', SETTLE_SCAN_DELAY_MS);
  };

  const schedule = (kind: keyof typeof pending, delay: number) => {
    if (pending[kind]) return;
    pending[kind] = true;
    timers.setTimeout(() => {
      pending[kind] = false;
      void run();
    }, delay);
  };

  return {
    onMutation: () => schedule('mutation', MUTATION_SCAN_DELAY_MS),
    scanNow: () => void run(),
  };
}
