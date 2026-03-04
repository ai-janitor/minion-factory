import path from "path"
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    proxy: {
      // Network server (Python) — serves both /api/* compat routes and /projects/* routes
      "/api": "http://localhost:8377",
      "/projects": "http://localhost:8377",
    },
  },
})
