import { defineConfig } from 'wxt';
import { hostPermissions, parseApiOrigin } from './src/core/hostPermissions';

/*
 * Build-time settings, read from the shell or from .env.<mode>[.local] files (WXT loads them):
 * - WXT_API_ORIGIN: the deployed API, e.g. https://calibrai-api.onrender.com. It becomes a host
 *   permission and the options page's default API URL. Production builds without it can only run
 *   in mock mode.
 * - WXT_EXTENSION_KEY (optional): the manifest "key" (a base64 public key), which pins the
 *   extension ID across machines so the API's CORS allow-list can name it. See docs/DEPLOY.md.
 * Development builds (`wxt`, `wxt build --mode development`) also allow the local API on
 * 127.0.0.1:8000 and :8010.
 */
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
  manifest: ({ mode }) => {
    const apiOrigin = process.env.WXT_API_ORIGIN;
    if (mode === 'production' && !parseApiOrigin(apiOrigin)) {
      console.warn('WXT_API_ORIGIN is not set: this production build can only run in mock mode.');
    }
    const key = process.env.WXT_EXTENSION_KEY?.trim();
    return {
      name: 'CalibrAI',
      description: 'Trust calibration signals for AI assistant answers.',
      permissions: ['storage'],
      host_permissions: hostPermissions(apiOrigin, mode),
      ...(key ? { key } : {}),
      action: {
        default_title: 'CalibrAI',
        default_popup: 'popup.html',
      },
      options_ui: {
        page: 'options.html',
        open_in_tab: true,
      },
    };
  },
});
