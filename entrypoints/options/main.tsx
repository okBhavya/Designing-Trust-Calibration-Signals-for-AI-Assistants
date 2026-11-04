import { createRoot } from 'react-dom/client';
import { useState } from 'react';
import { useEffect } from 'react';
import { defaultRuntimeConfig, type RuntimeMode } from '../../src/core/runtimeConfig';
import './style.css';

function Options() {
  const [mode, setMode] = useState<RuntimeMode>(defaultRuntimeConfig.mode);
  const [apiBaseUrl, setApiBaseUrl] = useState(defaultRuntimeConfig.apiBaseUrl);
  const [participantId, setParticipantId] = useState('');
  const [sessionToken, setSessionToken] = useState('');
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    void browser.storage.local.get(Object.keys(defaultRuntimeConfig)).then((stored) => {
      setMode(stored.mode === 'api' ? 'api' : 'mock');
      setApiBaseUrl(typeof stored.apiBaseUrl === 'string' ? stored.apiBaseUrl : defaultRuntimeConfig.apiBaseUrl);
      setParticipantId(typeof stored.participantId === 'string' ? stored.participantId : '');
      setSessionToken(typeof stored.sessionToken === 'string' ? stored.sessionToken : '');
    });
  }, []);

  const save = () => {
    setSaved(false);
    void browser.storage.local.set({ mode, apiBaseUrl, participantId, sessionToken }).then(() => setSaved(true));
  };

  return (
    <main>
      <h1>CalibrAI settings</h1>
      <p>Backend consent is required before API mode can transmit conversation data. Local mock mode never sends data to the backend.</p>
      <label>Signal mode
        <select value={mode} onChange={(event) => setMode(event.target.value as RuntimeMode)}>
          <option value="mock">Local mock</option>
          <option value="api">Authenticated API</option>
        </select>
      </label>
      {mode === 'api' && (
        <>
          <label>API base URL<input value={apiBaseUrl} onChange={(event) => setApiBaseUrl(event.target.value)} /></label>
          <label>Participant ID<input value={participantId} onChange={(event) => setParticipantId(event.target.value)} /></label>
          <label>Session token<input type="password" value={sessionToken} onChange={(event) => setSessionToken(event.target.value)} /></label>
          <p>Tokens are stored in extension storage and are never bundled into source code.</p>
        </>
      )}
      <button type="button" onClick={save}>Save signal settings</button>
      {saved && <p role="status">Settings saved.</p>}
      <button type="button" onClick={() => void browser.storage.local.clear()}>Delete local extension data</button>
    </main>
  );
}

createRoot(document.getElementById('root')!).render(<Options />);
