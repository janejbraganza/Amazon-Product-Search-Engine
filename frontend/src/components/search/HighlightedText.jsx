import { highlightTerms } from '../../utils/highlight.js'

/** Text with words matching the search terms wrapped in <mark>. */
export default function HighlightedText({ text, terms }) {
  return highlightTerms(text, terms).map((part, i) =>
    part.match ? <mark key={i}>{part.text}</mark> : part.text,
  )
}
