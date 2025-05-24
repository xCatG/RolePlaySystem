import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 3000,
    cors: true,
    // Use 0.0.0.0 for dev server (works in containers and locally)
    // In production, this won't be used as the app will be built and served statically
    host: '0.0.0.0'
  }
})