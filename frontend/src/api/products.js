import { apiGet } from './client.js'

/** GET /api/v1/products/{id} - one product (existing endpoint). */
export function getProduct(productId, { signal } = {}) {
  return apiGet(`/api/v1/products/${encodeURIComponent(productId)}`, { signal })
}

/** GET /api/v1/categories - every category with its product count (most products first). */
export function getCategories({ signal } = {}) {
  return apiGet('/api/v1/categories', { signal })
}

/** GET /api/v1/products - paginated catalogue listing (existing endpoint). */
export function listProducts({ limit, offset } = {}, { signal } = {}) {
  return apiGet('/api/v1/products', { params: { limit, offset }, signal })
}
