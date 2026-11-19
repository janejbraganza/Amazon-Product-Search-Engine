/**
 * Split ``text`` into parts, marking words that match the search terms.
 *
 * The API's terms are processed forms ("earbud" for "Earbuds", "battery" for "Batteries"),
 * so a word matches when it starts with a term. This is a visual aid only and is
 * deliberately approximate. Terms shorter than 3 characters (e.g. "c" from "USB-C") must
 * match a whole word, so that they don't highlight every word starting with that letter.
 *
 * @returns {{text: string, match: boolean}[]}
 */
export function highlightTerms(text, terms) {
  const needles = [...new Set(terms.map((term) => term.toLowerCase()).filter(Boolean))]
  if (!text || needles.length === 0) return [{ text, match: false }]

  const parts = []
  // Keep separators so the original text is reproduced exactly.
  for (const piece of text.split(/([^\p{L}\p{N}]+)/u)) {
    if (!piece) continue
    const word = piece.toLowerCase()
    const match = needles.some((term) => (term.length < 3 ? word === term : word.startsWith(term)))
    const last = parts[parts.length - 1]
    if (last && last.match === match && !match) last.text += piece
    else parts.push({ text: piece, match })
  }
  return parts
}
