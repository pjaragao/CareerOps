import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { existsSync } from 'node:fs'

// Inside the compose stack the backend is the `backend` service; on the host it is published on :8005.
const apiTarget = process.env.API_TARGET ?? (existsSync('/.dockerenv') ? 'http://backend:8000' : 'http://127.0.0.1:8005')

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    allowedHosts: true,
    proxy: {
      '/api': {
        target: apiTarget,
        changeOrigin: true
      }
    }
  }
})
