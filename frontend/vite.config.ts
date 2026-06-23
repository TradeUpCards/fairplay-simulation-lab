import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/  ·  https://vitest.dev/config/
export default defineConfig({
  plugins: [react()],
  // Relative base so the static bundle works from any host path (no API server).
  base: './',
  resolve: {
    // `@data` → the repo-root data/ dir (frozen Contract-2 JSON + derived scores),
    // so the data layer imports `@data/derived/...` instead of `../../../data`.
    alias: { '@data': fileURLToPath(new URL('../data', import.meta.url)) },
  },
  server: {
    // The frozen Contract-2 JSON lives at the repo root (../data); allow the dev
    // server to read it. Production `vite build` inlines it into the bundle.
    fs: { allow: ['..'] },
  },
  test: {
    environment: 'node',
    include: ['tests/**/*.{test,spec}.{ts,tsx}'],
  },
})
