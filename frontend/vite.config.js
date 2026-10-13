import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Local development: the dashboard calls the API on the same origin (relative
// base URL) and Vite proxies /api to the local backend, mirroring nginx in
// production. See deploy/nginx/mini-soc.conf.
export default defineConfig({
  plugins: [react()],
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
