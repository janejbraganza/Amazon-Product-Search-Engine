import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'
import { makeProduct } from '../../test/fixtures.js'
import ProductCard from './ProductCard.jsx'

function renderCard(overrides = {}, terms = []) {
  const product = makeProduct(7, overrides)
  render(
    <MemoryRouter>
      <ProductCard product={product} terms={terms} fromSearch="/search?q=laptop" />
    </MemoryRouter>,
  )
  return product
}

describe('ProductCard', () => {
  it('shows the product fields returned by the API', () => {
    renderCard({
      product_name: 'Pulsewave Core Laptop, 14-inch',
      brand: 'Pulsewave',
      category: 'Electronics',
      price: 1226.99,
      rating: 4.5,
      review_count: 1234,
    })
    expect(screen.getByRole('heading', { name: 'Pulsewave Core Laptop, 14-inch' })).toBeVisible()
    expect(screen.getByText('Pulsewave')).toBeVisible()
    expect(screen.getByText('Electronics')).toBeVisible()
    expect(screen.getByText('$1,226.99')).toBeVisible()
    expect(screen.getByText('(1,234 reviews)')).toBeVisible()
    expect(screen.getByRole('img', { name: 'Rated 4.5 out of 5' })).toBeInTheDocument()
  })

  it('links to the product page', () => {
    renderCard()
    expect(screen.getByRole('link')).toHaveAttribute('href', '/products/7')
  })

  it.each([
    [0, 'Out of stock'],
    [3, 'Only 3 left'],
    [50, 'In stock'],
  ])('shows stock status for %i units', (quantity, label) => {
    renderCard({ stock_quantity: quantity })
    expect(screen.getByText(label)).toBeVisible()
  })

  it('highlights matching words in the name', () => {
    const { container } = render(
      <MemoryRouter>
        <ProductCard
          product={makeProduct(1, { product_name: 'Voltrix Wireless Earbuds' })}
          terms={['wireless', 'earbud']}
        />
      </MemoryRouter>,
    )
    expect([...container.querySelectorAll('mark')].map((m) => m.textContent)).toEqual([
      'Wireless',
      'Earbuds',
    ])
  })

  it('accepts price and rating as numeric strings', () => {
    renderCard({ price: '19.5', rating: '3.0' })
    expect(screen.getByText('$19.50')).toBeVisible()
    expect(screen.getByRole('img', { name: 'Rated 3.0 out of 5' })).toBeInTheDocument()
  })
})
