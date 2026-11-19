import AppLayout from './components/layout/AppLayout.jsx'
import HomePage from './pages/HomePage.jsx'
import NotFoundPage from './pages/NotFoundPage.jsx'
import ProductPage from './pages/ProductPage.jsx'
import SearchPage from './pages/SearchPage.jsx'

/**
 * The route table, shared by the real browser router (main.jsx) and the in-memory
 * router used in tests, so tests exercise exactly the same routes.
 */
export const routes = [
  {
    path: '/',
    element: <AppLayout />,
    children: [
      { index: true, element: <HomePage /> },
      { path: 'search', element: <SearchPage /> },
      { path: 'products/:productId', element: <ProductPage /> },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]
