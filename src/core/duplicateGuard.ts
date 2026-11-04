export class DuplicateGuard {
  private readonly processed = new WeakMap<HTMLElement, string>();

  hasChanged(container: HTMLElement, answerHash: string): boolean {
    if (this.processed.get(container) === answerHash) {
      return false;
    }
    this.processed.set(container, answerHash);
    return true;
  }

  forget(container: HTMLElement): void {
    this.processed.delete(container);
  }
}
