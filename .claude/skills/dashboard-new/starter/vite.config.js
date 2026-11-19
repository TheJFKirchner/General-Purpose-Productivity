// Live dashboard config (npm run dev / build).
// Data comes from the Analysis server: Vite forwards /api to it. Tools/dev.mjs starts both and passes the port
// it actually used; on its own this file uses "server.port" from dashboard.config.json.
// @precomputed is an empty stub here; the export config points it at the report's precomputed results.
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { fileURLToPath } from 'node:url';
import { readJsonFile } from './Tools/py.mjs';

const here = (p) => fileURLToPath(new URL(p, import.meta.url));
const config = readJsonFile(here('./dashboard.config.json'));
const apiPort = config.server?.port || 8765;

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { '@precomputed': here('./Src/Lib/no-precomputed.js') } },
  server: {
    proxy: { '/api': `http://127.0.0.1:${apiPort}` },
    // Python, data and exports never reload the page (the Analysis server picks up its own edits)
    watch: { ignored: ['**/Exports/**', '**/.export/**', '**/Data/**', '**/Analysis/**', '**/Pipeline/**', '**/Reports/**', '**/__pycache__/**'] },
  },
  build: { outDir: 'Dist', chunkSizeWarningLimit: 5000 },
});
