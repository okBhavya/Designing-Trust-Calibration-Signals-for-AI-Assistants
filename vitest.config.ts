import { configDefaults, defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    environment: 'jsdom',
    // apps/* have their own vitest configs (aliases, includes).
    exclude: [...configDefaults.exclude, 'apps/**'],
  },
});
