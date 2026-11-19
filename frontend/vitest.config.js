import { configDefaults, defineConfig, mergeConfig } from 'vitest/config'
import viteConfig from './vite.config.js'

// Unit/component tests: the backend is replaced by MSW mocks, so no server is needed.
// Live tests against the real backend (*.live.test.jsx) run separately: npm run test:live
export default defineConfig((env) =>
  mergeConfig(viteConfig(env), {
    test: {
      environment: 'jsdom',
      setupFiles: ['./src/test/setup.js'],
      include: ['src/**/*.test.{js,jsx}'],
      exclude: [...configDefaults.exclude, 'src/**/*.live.test.{js,jsx}'],
      restoreMocks: true,
      coverage: {
        provider: 'v8',
        include: ['src/**/*.{js,jsx}'],
        exclude: ['src/main.jsx', 'src/test/**', 'src/**/*.test.{js,jsx}'],
        reporter: ['text', 'html'],
      },
    },
  }),
)
