import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    // em desenvolvimento, as chamadas /api vão para o backend Python
    proxy: { '/api': 'http://localhost:8000' }
  }
})
