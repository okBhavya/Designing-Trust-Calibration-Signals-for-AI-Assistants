import { defineConfig } from 'wxt';

export default defineConfig({
  modules: ['@wxt-dev/module-react'],
  hooks: {
    // The overlay preview page is a dev tool: built by `wxt` and `wxt build --mode development`,
    // never shipped in a production build.
    'entrypoints:found': (wxt, infos) => {
      if (wxt.config.mode !== 'production') return;
      const index = infos.findIndex((info) => info.name === 'overlay-preview');
      if (index >= 0) infos.splice(index, 1);
    },
  },
  manifest: {
    name: 'CalibrAI',
    description: 'Trust calibration signals for AI assistant answers.',
    permissions: ['storage'],
    host_permissions: [
      'https://chatgpt.com/*',
      'https://claude.ai/*',
      'https://gemini.google.com/*',
      'http://127.0.0.1:8000/*',
      // Alternative local port for when another dev server already holds 8000.
      'http://127.0.0.1:8010/*',
      'https://api.calibrai.example/*',
    ],
    action: {
      default_title: 'CalibrAI',
      default_popup: 'popup.html',
    },
    options_ui: {
      page: 'options.html',
      open_in_tab: true,
    },
  },
});
