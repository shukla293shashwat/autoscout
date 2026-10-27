import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Vite config for AutoScout frontend.
// - Tailwind is loaded via PostCSS (tailwind.config.js).
// - /api requests are proxied to the FastAPI backend during development.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
    },
  },
})
