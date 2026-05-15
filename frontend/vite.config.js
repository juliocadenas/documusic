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
        timeout: 30000, // 30s proxy timeout — Stage2 inference can cause slow responses
        rewrite: (path) => path.replace(/^\/api/, '/api'), // Aseguramos que mantenga el prefijo /api
      },
    },
  },
})
