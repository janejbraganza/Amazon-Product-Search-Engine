import { setupServer } from 'msw/node'
import { handlers } from './handlers.js'

/** Mock API server for tests: intercepts fetch() so no real backend is needed. */
export const server = setupServer(...handlers)
