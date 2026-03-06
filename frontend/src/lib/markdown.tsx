export function MarkdownLine({ line }: { line: string }) {
  const trimmed = line.trim()
  if (!trimmed) return <div className="h-3" />

  if (trimmed.startsWith('### '))
    return <h3 className="text-sm font-semibold text-text-100 mt-4 mb-1.5">{renderInline(trimmed.slice(4))}</h3>
  if (trimmed.startsWith('## '))
    return <h2 className="text-base font-semibold text-text-100 mt-5 mb-2">{renderInline(trimmed.slice(3))}</h2>
  if (trimmed.startsWith('# '))
    return <h1 className="text-lg font-bold text-text-100 mt-5 mb-2">{renderInline(trimmed.slice(2))}</h1>
  if (trimmed.startsWith('- ') || trimmed.startsWith('* '))
    return <li className="text-sm text-text-200 ml-4 mb-1 list-disc">{renderInline(trimmed.slice(2))}</li>
  if (/^\d+\.\s/.test(trimmed)) {
    const text = trimmed.replace(/^\d+\.\s/, '')
    return <li className="text-sm text-text-200 ml-4 mb-1 list-decimal">{renderInline(text)}</li>
  }
  if (trimmed.startsWith('```'))
    return <div className="font-mono text-xs bg-bg-200 px-3 py-1 rounded text-text-300">{trimmed.slice(3)}</div>

  return <p className="text-sm text-text-200 mb-2 leading-relaxed">{renderInline(trimmed)}</p>
}
export function renderInline(text: string): (string | JSX.Element)[] {
  const parts: (string | JSX.Element)[] = []
  let remaining = text
  let key = 0
  while (remaining) {
    const boldMatch = remaining.match(/\*\*(.+?)\*\*/)
    const codeMatch = remaining.match(/`(.+?)`/)

    // Pick whichever comes first
    const boldIdx = boldMatch?.index ?? Infinity
    const codeIdx = codeMatch?.index ?? Infinity

    if (boldIdx === Infinity && codeIdx === Infinity) {
      parts.push(remaining)
      break
    }

    if (boldIdx <= codeIdx && boldMatch) {
      parts.push(remaining.slice(0, boldIdx))
      parts.push(<strong key={key++} className="font-semibold text-text-100">{boldMatch[1]}</strong>)
      remaining = remaining.slice(boldIdx + boldMatch[0].length)
    } else if (codeMatch) {
      parts.push(remaining.slice(0, codeIdx))
      parts.push(
        <code key={key++} className="px-1 py-0.5 rounded bg-bg-200 text-xs font-mono text-accent">{codeMatch[1]}</code>
      )
      remaining = remaining.slice(codeIdx + codeMatch[0].length)
    }
  }
  return parts
}