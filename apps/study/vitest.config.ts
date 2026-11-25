import { defineConfig } from 'vitest/config';
import { aliases } from './vite.config';

export default defineConfig({
  resolve: { alias: aliases, dedupe: ['react', 'react-dom'] },
  test: { environment: 'jsdom', include: ['src/**/*.test.{ts,tsx}'] },
});
