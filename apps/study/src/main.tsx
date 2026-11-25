import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import '@calibrai/overlay/tokens.css';
import './styles.css';
import { App } from './App';
import { createApi, env, readLinkParams } from './config';

/** Light/dark from the OS setting, through the overlay's shared colour tokens. */
function followColorScheme() {
  const root = document.documentElement;
  root.classList.add('calibrai-tokens');
  const media = window.matchMedia('(prefers-color-scheme: dark)');
  const apply = () => (root.dataset.theme = media.matches ? 'dark' : 'light');
  apply();
  media.addEventListener('change', apply);
}

followColorScheme();
createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App api={createApi()} enrollmentCode={readLinkParams().code} consentVersion={env.consentVersion} />
  </StrictMode>,
);
