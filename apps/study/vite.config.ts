import { resolve } from 'node:path';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

const repo = resolve(__dirname, '../..');

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

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: aliases,
    // The overlay sources live outside this package; make them use this package's React.
    dedupe: ['react', 'react-dom'],
  },
  server: { port: 5174, strictPort: true, fs: { allow: [repo] } },
  preview: { port: 4174, strictPort: true },
});
