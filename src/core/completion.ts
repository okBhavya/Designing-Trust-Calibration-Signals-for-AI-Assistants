export interface CompletionSample {
  text: string;
  streaming: boolean;
}

export class CompletionTracker {
  private readonly samples = new WeakMap<HTMLElement, CompletionSample>();

  record(container: HTMLElement, sample: CompletionSample): void {
    this.samples.set(container, sample);
  }

  isStable(container: HTMLElement, sample: CompletionSample): boolean {
    const previous = this.samples.get(container);
    this.record(container, sample);
    return Boolean(previous && !previous.streaming && !sample.streaming && previous.text === sample.text);
  }
}
