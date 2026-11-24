import { createRoot } from 'react-dom/client';
import { useEffect, useState } from 'react';
import { activeSiteStatus } from '../../src/core/activeSite';
import './style.css';

function Popup() {
  const [status, setStatus] = useState('Checking current page');

  useEffect(() => {
    // tab.url is only visible for sites in host_permissions, which are exactly the supported ones.
    void browser.tabs
      .query({ active: true, currentWindow: true })
      .then(([tab]) => setStatus(activeSiteStatus(tab?.url)))
      .catch(() => setStatus(activeSiteStatus(undefined)));
  }, []);

  return (
    <main>
      <h1>CalibrAI</h1>
      <p>Trust calibration signals for AI answers.</p>
      <p className="status"><span /> {status}</p>
      <a href={browser.runtime.getURL('/options.html')}>Open settings</a>
    </main>
  );
}

createRoot(document.getElementById('root')!).render(<Popup />);
