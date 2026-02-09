import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 7014,
    proxy: {
      '/api': {
        target: 'http://localhost:7021',
        changeOrigin: true,
        ws: true,
      },
      '/docs': {
        target: 'http://localhost:7021',
        changeOrigin: true,
      },
      '/openapi.json': {
        target: 'http://localhost:7021',
        changeOrigin: true,
      },
      '/redoc': {
        target: 'http://localhost:7021',
        changeOrigin: true,
      },
    },
  },
})
