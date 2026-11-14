/// <reference types="vitest/config" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Built files go to frontend/dist and are served by app/server.py from the same origin:
// GET / -> dist/index.html, GET /assets/<file> -> dist/assets/<file>. base './' keeps asset URLs relative.
// Nothing is fetched from the internet at run time: every library is bundled here.
export default defineConfig({
  base: './',
  plugins: [react()],
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
    emptyOutDir: true,
    sourcemap: false,
    chunkSizeWarningLimit: 700,   // one bundle on purpose: a local app served from disk, no network cost
  },
  server: { port: 5173, strictPort: false },
  test: {
    environment: 'node',
    include: ['src/**/*.test.{ts,tsx}'],
  },
});
