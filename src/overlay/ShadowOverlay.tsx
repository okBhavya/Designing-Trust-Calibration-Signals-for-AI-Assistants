import { useEffect, useRef } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { Overlay, type OverlayProps } from './Overlay';
import styles from './overlay.css?inline';

/**
 * The overlay inside its own Shadow DOM host, as the extension mounts it, for use in a React page
 * (the study harness). Render it directly after the answer element: the overlay lines its pill up
 * with that element's text column and reads its theme from the page behind it.
 */
export function ShadowOverlay(props: OverlayProps) {
  const hostRef = useRef<HTMLDivElement>(null);
  const rootRef = useRef<Root | null>(null);

  useEffect(() => {
    const host = hostRef.current!;
    if (!rootRef.current) {
      const shadow = host.shadowRoot ?? host.attachShadow({ mode: 'open' });
      const style = document.createElement('style');
      style.textContent = styles;
      shadow.append(style);
      rootRef.current = createRoot(shadow);
    }
    return () => {
      // Deferred: unmounting a nested root while the parent tree commits warns, and StrictMode
      // re-runs this effect on a host that stays in the page, which must keep its root.
      setTimeout(() => {
        if (host.isConnected || !rootRef.current) return;
        rootRef.current.unmount();
        rootRef.current = null;
      }, 0);
    };
  }, []);

  useEffect(() => {
    rootRef.current?.render(<Overlay {...props} />);
  });

  return <div ref={hostRef} data-calibrai-overlay="true" />;
}
