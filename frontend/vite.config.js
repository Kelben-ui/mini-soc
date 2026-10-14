import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Local development: the dashboard calls the API on the same origin (relative
// base URL) and Vite proxies /api to the local backend, mirroring nginx in
// production. See deploy/nginx/mini-soc.conf.
export default defineConfig({
  plugins: [react()],
  // Vitest bundles its own Vite copy, which can compile JSX with the classic
  // runtime. Pin the automatic runtime explicitly so tests and the build agree.
  esbuild: {
    jsx: 'automatic',
    jsxImportSource: 'react',
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/test/setup.js',
  },
  server: {
    host: '127.0.0.1',
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  preview: {
    host: '127.0.0.1',
  },
})
