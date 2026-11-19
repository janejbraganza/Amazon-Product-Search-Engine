import { act, renderHook } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { useDebouncedValue } from '../hooks/useDebouncedValue.js'
import { completeQuery, isSearchable, suggestionQuery } from './autocomplete.js'

describe('autocomplete helpers', () => {
  it.each([
    ['lap', true],
    ['  ear ', true],
    ['15.6', true],
    ['café', true],
    ['', false],
    ['   ', false],
    ['!!! -', false],
    ['___', false], // the backend tokenizer does not treat "_" as a word character
  ])('isSearchable(%j) is %s', (text, expected) => {
    expect(isSearchable(text)).toBe(expected)
  })

  it('suggestionQuery trims text and returns "" when nothing can be searched', () => {
    expect(suggestionQuery('  wireless ea ')).toBe('wireless ea')
    expect(suggestionQuery(' ?! ')).toBe('')
  })

  it.each([
    ['la', 'laptop', 'laptop'],
    ['wireless ea', 'earbud', 'wireless earbud'],
    ['wireless   ea', 'earbud', 'wireless   earbud'],
    ['wireless ', 'wireless', 'wireless'], // trailing space: the last word is still "wireless"
    ['USB-C', 'usbc', 'usbc'],
    ['', 'laptop', 'laptop'],
  ])('completeQuery(%j, %j) -> %j', (text, term, expected) => {
    expect(completeQuery(text, term)).toBe(expected)
  })
})

describe('useDebouncedValue', () => {
  afterEach(() => vi.useRealTimers())

  it('updates only after the value has been stable for the delay', () => {
    vi.useFakeTimers()
    const { result, rerender } = renderHook(({ value }) => useDebouncedValue(value, 175), {
      initialProps: { value: 'l' },
    })
    rerender({ value: 'la' })
    act(() => vi.advanceTimersByTime(100))
    rerender({ value: 'lap' }) // restarts the delay
    act(() => vi.advanceTimersByTime(174))
    expect(result.current).toBe('l')
    act(() => vi.advanceTimersByTime(1))
    expect(result.current).toBe('lap')
  })
})
