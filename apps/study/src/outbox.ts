import { ApiError } from './api';

/**
 * Sends records in order and never drops one silently. A record that fails for a temporary reason
 * (offline, timeout, rate limit, server error) is retried with backoff until it is sent; a record
 * the server rejects for good (other 4xx) moves to `failed`, where the page shows it and offers a
 * download. Trial and questionnaire posts are idempotent on the server, so a retry after a lost
 * response cannot store a record twice.
 */

export interface FailedRecord {
  label: string;
  payload: unknown;
  error: string;
}

export interface OutboxState {
  /** Records not yet confirmed by the server (including the one being sent). */
  pending: number;
  /** The last attempt failed for a temporary reason and a retry is scheduled. */
  retrying: boolean;
  failed: FailedRecord[];
}

interface Job {
  label: string;
  payload: unknown;
  send: () => Promise<void>;
  attempts: number;
}

export function isTransient(error: unknown): boolean {
  if (!(error instanceof ApiError)) return true;
  return error.status === 0 || error.status === 408 || error.status === 425 || error.status === 429 || error.status >= 500;
}

export class Outbox {
  private queue: Job[] = [];
  private failed: FailedRecord[] = [];
  private retrying = false;
  private running = false;
  private state: OutboxState = { pending: 0, retrying: false, failed: [] };
  private readonly listeners = new Set<() => void>();

  constructor(
    private readonly options: {
      baseDelayMs?: number;
      maxDelayMs?: number;
      wait?: (ms: number) => Promise<void>;
    } = {},
  ) {}

  enqueue(label: string, payload: unknown, send: () => Promise<void>): void {
    this.queue.push({ label, payload, send, attempts: 0 });
    this.emit();
    void this.pump();
  }

  /** Stable snapshot, for useSyncExternalStore. */
  getState = (): OutboxState => this.state;

  subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  };

  /** Drops everything still queued (used when the participant stops and deletes their data). */
  clear(): void {
    this.queue = [];
    this.failed = [];
    this.retrying = false;
    this.emit();
  }

  private emit(): void {
    this.state = { pending: this.queue.length, retrying: this.retrying, failed: [...this.failed] };
    this.listeners.forEach((listener) => listener());
  }

  private delay(attempts: number): number {
    const base = this.options.baseDelayMs ?? 1_000;
    return Math.min(this.options.maxDelayMs ?? 30_000, base * 2 ** (attempts - 1));
  }

  private wait(ms: number): Promise<void> {
    return this.options.wait ? this.options.wait(ms) : new Promise((resolve) => setTimeout(resolve, ms));
  }

  private remove(job: Job): void {
    const index = this.queue.indexOf(job);
    if (index >= 0) this.queue.splice(index, 1);
  }

  private async pump(): Promise<void> {
    if (this.running) return;
    this.running = true;
    try {
      while (this.queue.length) {
        const job = this.queue[0];
        try {
          await job.send();
          this.remove(job);
          this.retrying = false;
          this.emit();
        } catch (error) {
          if (!this.queue.includes(job)) continue; // cleared while it was in flight
          if (isTransient(error)) {
            job.attempts += 1;
            this.retrying = true;
            this.emit();
            await this.wait(this.delay(job.attempts));
            continue;
          }
          this.remove(job);
          const message = error instanceof Error ? error.message : String(error);
          const status = error instanceof ApiError ? ` (HTTP ${error.status})` : '';
          this.failed.push({ label: job.label, payload: job.payload, error: `${message}${status}` });
          this.retrying = false;
          this.emit();
        }
      }
    } finally {
      this.running = false;
    }
  }
}
