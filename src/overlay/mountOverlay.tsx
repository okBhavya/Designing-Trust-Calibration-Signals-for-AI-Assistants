import { createRoot, type Root } from 'react-dom/client';
import type { SignalResponse } from '../core/contracts';
import { Overlay } from './Overlay';
import styles from './overlay.css?inline';

const overlayRoots = new WeakMap<HTMLElement, Root>();
const overlayHosts = new WeakMap<HTMLElement, HTMLElement>();

export function mountOverlay(answerContainer: HTMLElement, signal: SignalResponse): HTMLElement {
  let host = overlayHosts.get(answerContainer);
  if (!host) {
    host = document.createElement('div');
    host.dataset.calibraiOverlay = 'true';
    host.setAttribute('aria-label', 'CalibrAI confidence signal');
    answerContainer.insertAdjacentElement('afterend', host);
    overlayHosts.set(answerContainer, host);
  }
  let shadow = host.shadowRoot;
  if (!shadow) {
    shadow = host.attachShadow({ mode: 'open' });
    const style = document.createElement('style');
    style.textContent = styles;
    shadow.append(style);
  }
  let root = overlayRoots.get(host);
  if (!root) {
    root = createRoot(shadow);
    overlayRoots.set(host, root);
  }
  root.render(<Overlay signal={signal} />);
  return host;
}
