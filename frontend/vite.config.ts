import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Vite config for AutoScout frontend.
// - Tailwind is loaded via PostCSS (tailwind.config.js).
// - /api and /health requests are proxied to the FastAPI backend during dev.
//   Override the backend URL with the API_TARGET env var (defaults to :8000).
const API_TARGET = process.env.API_TARGET || 'http://localhost:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': API_TARGET,
      '/health': API_TARGET,
    },
  },
})
