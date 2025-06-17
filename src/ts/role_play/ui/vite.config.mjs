import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve, dirname } from 'path'
import { fileURLToPath } from 'url'

const __dirname = dirname(fileURLToPath(import.meta.url))

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src')
    }
  },
  server: {
    port: 3000,
    cors: true,
    // Use 0.0.0.0 for dev server (works in containers and locally)
    // In production, this won't be used as the app will be built and served statically
    host: '0.0.0.0',
    proxy: {
      '/api': 'http://localhost:8000'
    }
  },
  build: {
    target: 'esnext',
    rollupOptions: {
      external: [],
      output: {
        manualChunks: undefined
      }
    }
  }
})
