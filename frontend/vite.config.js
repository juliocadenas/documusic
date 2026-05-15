import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://100.103.141.33:8000',
        changeOrigin: true,
        secure: false,
        timeout: 120000, // 2min proxy timeout — CUDA inference can block backend for long periods
        proxyTimeout: 120000, // http-proxy timeout
        rewrite: (path) => path.replace(/^\/api/, '/api'), // Aseguramos que mantenga el prefijo /api
      },
    },
  },
})
