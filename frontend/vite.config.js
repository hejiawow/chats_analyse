import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  server: {
    host: '0.0.0.0',  // 允许内网访问
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://192.168.23.26:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: resolve(__dirname, 'dist'),
    assetsDir: 'assets',
    emptyOutDir: true,
  },
})
