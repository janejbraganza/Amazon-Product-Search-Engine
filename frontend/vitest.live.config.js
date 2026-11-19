import { defineConfig, mergeConfig } from 'vitest/config'
import viteConfig from './vite.config.js'

/**
 * Live tests: render real pages in jsdom with real fetch() calls (no mocks) to the Vite dev
 * server, which proxies /api to the real FastAPI backend. Start both first:
 *   backend:  python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
 *   frontend: npm run dev
 * then:       npm run test:live      (LIVE_BASE_URL overrides http://localhost:5173)
 */
export default defineConfig((env) =>
  mergeConfig(viteConfig(env), {
    test: {
      environment: 'jsdom',
      environmentOptions: {
        jsdom: { url: process.env.LIVE_BASE_URL || 'http://localhost:5173' },
      },
      setupFiles: ['./src/test/live-setup.js'],
      include: ['src/**/*.live.test.{js,jsx}'],
      testTimeout: 30_000,
      fileParallelism: false,
    },
  }),
)
