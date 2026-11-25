import { resolve } from 'node:path';
import react from '@vitejs/plugin-react';
import { defineConfig, loadEnv } from 'vite';

const repo = resolve(import.meta.dirname, '../..');

/**
 * Shared code comes from the repository through aliases, never copies:
 * - @calibrai/* -> src/* (the extension's overlay components and colour tokens)
 * - @study-data/* -> data/* (data/questions.json is bundled into the build)
 */
export const aliases = {
  '@calibrai': resolve(repo, 'src'),
  '@study-data': resolve(repo, 'data'),
  '@contracts': resolve(repo, 'contracts'),
};

export default defineConfig(({ command, mode }) => {
  const env = loadEnv(mode, process.cwd(), 'VITE_');
  if (command === 'build' && mode === 'production' && env.VITE_DEMO !== '1' && !env.VITE_API_BASE_URL) {
    // Allowed (local checks build without it), but a deployed harness would call 127.0.0.1.
    console.warn('VITE_API_BASE_URL is not set: this build will call the local API at http://127.0.0.1:8000.');
  }
  return {
  plugins: [react()],
  resolve: {
    alias: aliases,
    // The overlay sources live outside this package; make them use this package's React.
    dedupe: ['react', 'react-dom'],
  },
  server: { port: 5174, strictPort: true, fs: { allow: [repo] } },
  preview: { port: 4174, strictPort: true },
  };
});
