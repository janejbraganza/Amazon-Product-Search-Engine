import { render } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { routes } from '../routes.jsx'

/**
 * Render the real app routes at ``path`` with an in-memory router.
 * Returns the router too, so tests can assert the current location.
 */
export function renderRoute(path = '/') {
  const router = createMemoryRouter(routes, { initialEntries: [path] })
  const utils = render(<RouterProvider router={router} />)
  return { router, ...utils }
}
