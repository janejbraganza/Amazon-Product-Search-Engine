import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

// The browser only ever talks to its own origin. In development, Vite forwards API calls
// to FastAPI (so no CORS setup is needed); in Docker, nginx does the same job.
// Override the target with API_PROXY_TARGET (e.g. in frontend/.env.local).
const DEFAULT_API_TARGET = 'http://127.0.0.1:8000'
const PROXIED_PATHS = ['/api', '/health', '/docs', '/openapi.json']

export default defineConfig(({ mode }) => {
  // Empty prefix = read API_PROXY_TARGET without exposing it to browser code (no VITE_ prefix).
  const env = loadEnv(mode, process.cwd(), '')
  const target = env.API_PROXY_TARGET || DEFAULT_API_TARGET
  const proxy = Object.fromEntries(
    PROXIED_PATHS.map((path) => [path, { target, changeOrigin: true }]),
  )

  return {
    plugins: [react()],
    server: { port: 5173, strictPort: true, proxy },
    preview: { port: 4173, strictPort: true, proxy },
  }
})
