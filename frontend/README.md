# Frontend

React 19 + Vite single-page app for the Product Search Engine. It talks only to the FastAPI
backend (`/api/v1/...`) on its own origin: in development the Vite dev server forwards API
requests to `http://127.0.0.1:8000`; in Docker, nginx does the same. No CORS setup is needed.

See the [root README](../README.md) for the whole project, and
[docs/architecture.md](../docs/architecture.md#frontend) for how the frontend is organised.

## Commands

```powershell
npm ci                  # install exact versions from package-lock.json
npm run dev             # http://localhost:5173 (needs the backend on 127.0.0.1:8000)
npm run build           # production build in dist/
npm run preview         # serve the build on http://localhost:4173
npm run lint            # ESLint
npm run format          # Prettier (write); npm run format:check to only check
npm test                # unit/component tests (Vitest + Testing Library, API mocked with MSW)
npm run test:coverage   # the same with coverage (coverage/)
npm run test:live       # live tests against the running backend (see docs/testing.md)
```

Requires Node.js 24 LTS (or 22.22+). Point the dev proxy at another backend with
`API_PROXY_TARGET` in `frontend/.env.local` (git-ignored).

## Structure

```
src/
  api/          fetch wrapper (timeouts, cancellation, user-safe errors) and endpoints
  hooks/        data and UI hooks (search, suggestions, product, categories, theme)
  pages/        Home, Search, Product, Not found
  components/   layout, search, filters, product, states, ui
  utils/        URL search state, formatting, highlighting, catalogue helpers, theme
  styles/       design tokens (light/dark) and global styles
  test/         test setup, MSW handlers and fixtures
```

All search state (query, mode, sort, filters, page) lives in the URL, and every filter,
sort and count comes from the API; the frontend never filters or counts results itself.
