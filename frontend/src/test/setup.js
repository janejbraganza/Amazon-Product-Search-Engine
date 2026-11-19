import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterAll, afterEach, beforeAll } from 'vitest'
import { server } from './server.js'

// Node 25+ defines its own global localStorage, which is undefined unless Node is started
// with --localstorage-file, and it hides jsdom's. Tests get a fresh in-memory one instead.
class MemoryStorage {
  #items = new Map()
  get length() {
    return this.#items.size
  }
  key(index) {
    return [...this.#items.keys()][index] ?? null
  }
  getItem(key) {
    return this.#items.has(String(key)) ? this.#items.get(String(key)) : null
  }
  setItem(key, value) {
    this.#items.set(String(key), String(value))
  }
  removeItem(key) {
    this.#items.delete(String(key))
  }
  clear() {
    this.#items.clear()
  }
}
if (typeof globalThis.localStorage?.getItem !== 'function') {
  Object.defineProperty(globalThis, 'localStorage', {
    value: new MemoryStorage(),
    configurable: true,
    writable: true,
  })
}

// jsdom has no real network: relative URLs need a base, and any request without a mock
// handler fails the test instead of silently reaching a real server.
beforeAll(() => {
  server.listen({ onUnhandledRequest: 'error' })
  // jsdom does not implement scrolling; the results page scrolls to the top on page change.
  window.scrollTo = () => {}
})
afterEach(() => {
  server.resetHandlers()
  cleanup()
  localStorage.clear()
})
afterAll(() => server.close())
