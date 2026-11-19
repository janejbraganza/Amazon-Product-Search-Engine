import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach, beforeAll } from 'vitest'

// Live tests use the real network (no MSW). Fail fast with a clear message if the dev
// server/backend is not running, instead of a wall of timeouts.
beforeAll(async () => {
  window.scrollTo = () => {}
  const url = `${window.location.origin}/health`
  const response = await fetch(url).catch(() => null)
  if (!response?.ok) {
    throw new Error(
      `Live tests need the Vite dev server and backend running (${url} not reachable). ` +
        'Start the backend on 127.0.0.1:8000 and `npm run dev`, then retry.',
    )
  }
})

afterEach(() => cleanup())
