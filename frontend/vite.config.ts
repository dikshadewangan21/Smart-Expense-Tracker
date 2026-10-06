import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

const backend = process.env.VITE_BACKEND_URL ?? 'http://localhost:8000'

// Same-origin proxy in dev so the httpOnly refresh cookie works without CORS/SameSite tricks.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { proxy: { '/api': backend } },
})
