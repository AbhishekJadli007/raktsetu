import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// During development the API runs on :8000 (uvicorn api.main:app --port 8000).
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: { '/api': 'http://localhost:8000' },
  },
  build: {
    chunkSizeWarningLimit: 1500,
  },
})
