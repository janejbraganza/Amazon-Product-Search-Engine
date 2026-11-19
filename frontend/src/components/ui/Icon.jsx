/**
 * Inline SVG icons (no icon library). Decorative by default: pass `label` when the icon
 * carries meaning on its own, so screen readers announce it.
 */
const PATHS = {
  search: (
    <>
      <circle cx="11" cy="11" r="7" />
      <path d="m20 20-3.5-3.5" />
    </>
  ),
  logo: (
    <>
      <rect x="3" y="3" width="18" height="18" rx="5" />
      <circle cx="11" cy="11" r="3.5" />
      <path d="m16.5 16.5-3-3" />
    </>
  ),
  arrowLeft: <path d="M19 12H5m6-6-6 6 6 6" />,
  close: <path d="M18 6 6 18M6 6l12 12" />,
  filter: <path d="M4 6h16M7 12h10M10 18h4" />,
  chevronLeft: <path d="m15 18-6-6 6-6" />,
  chevronRight: <path d="m9 18 6-6-6-6" />,
  package: (
    <>
      <path d="M21 8 12 3 3 8v8l9 5 9-5z" />
      <path d="m3 8 9 5 9-5M12 13v8" />
    </>
  ),
  alert: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7.5v5.5m0 3.5v.01" />
    </>
  ),
  searchOff: (
    <>
      <circle cx="11" cy="11" r="7" />
      <path d="m20 20-3.5-3.5M8.5 8.5l5 5m0-5-5 5" />
    </>
  ),
  arrowRight: <path d="M5 12h14m-6-6 6 6-6 6" />,
  sun: (
    <>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2m0 16v2M4.9 4.9l1.4 1.4m11.4 11.4 1.4 1.4M2 12h2m16 0h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
    </>
  ),
  moon: <path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z" />,
  // Search capabilities (home page)
  ranking: <path d="M4 20h16M7 16V10m5 6V5m5 11v-4" />,
  autocomplete: (
    <>
      <path d="M4 7h10M4 12h7M4 17h5" />
      <path d="m15 13 5 5m0-5v5h-5" />
    </>
  ),
  bolt: <path d="M13 2 4 14h7l-1 8 9-12h-7z" />,
  sliders: (
    <>
      <path d="M4 6h9m4 0h3M4 12h3m4 0h9M4 18h11m4 0h1" />
      <circle cx="15" cy="6" r="2" />
      <circle cx="9" cy="12" r="2" />
      <circle cx="17" cy="18" r="2" />
    </>
  ),
  // Catalogue categories (see utils/categories.js)
  electronics: (
    <>
      <rect x="3" y="4" width="18" height="12" rx="2" />
      <path d="M8 20h8m-4-4v4" />
    </>
  ),
  home: (
    <>
      <path d="m3 11 9-7 9 7" />
      <path d="M5 10v10h14V10M10 20v-6h4v6" />
    </>
  ),
  book: (
    <>
      <path d="M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2z" />
      <path d="M4 21V5m4 2h7" />
    </>
  ),
  shirt: <path d="M8 3 3 6l2 5 3-1v11h8V10l3 1 2-5-5-3a4 4 0 0 1-8 0z" />,
  sparkle: (
    <>
      <path d="M12 3v4m0 10v4M3 12h4m10 0h4" />
      <path d="m12 8 1.5 2.5L16 12l-2.5 1.5L12 16l-1.5-2.5L8 12l2.5-1.5z" />
    </>
  ),
  basket: (
    <>
      <path d="M3 10h18l-2 10H5z" />
      <path d="m8 10 3-6m5 6-3-6M9 14v3m6-3v3" />
    </>
  ),
  car: (
    <>
      <path d="M5 16V11l2-5h10l2 5v5" />
      <path d="M3 16h18v3H3zM5 11h14" />
      <circle cx="7.5" cy="13.5" r=".5" />
      <circle cx="16.5" cy="13.5" r=".5" />
    </>
  ),
  paperclip: (
    <path d="m20 11.5-8 8a5 5 0 0 1-7-7l8.5-8.5a3.5 3.5 0 0 1 5 5L10 17.5a2 2 0 0 1-3-3L15 6.5" />
  ),
  ball: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18M3 12h18" />
    </>
  ),
  puzzle: (
    <path d="M10 4a2 2 0 0 1 4 0v2h4v4h-2a2 2 0 0 0 0 4h2v4h-4v-2a2 2 0 0 0-4 0v2H6v-4h2a2 2 0 0 0 0-4H6V6h4z" />
  ),
}

export default function Icon({ name, size = 20, label, className }) {
  return (
    <svg
      className={className}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      role={label ? 'img' : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
      focusable="false"
    >
      {PATHS[name]}
    </svg>
  )
}
