import { createRoot } from 'react-dom/client';
import './style.css';

function Popup() {
  return (
    <main>
      <h1>CalibrAI</h1>
      <p>Trust calibration signals for AI answers.</p>
      <p className="status"><span /> Active on ChatGPT</p>
      <a href={browser.runtime.getURL('/options.html')}>Open settings</a>
    </main>
  );
}

createRoot(document.getElementById('root')!).render(<Popup />);
