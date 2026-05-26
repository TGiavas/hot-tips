/**
 * Trigger a browser download of plain text content as a `.txt` file.
 *
 * Uses a transient `<a download>` + Blob URL — no DOM cleanup leftovers,
 * no external deps.
 */
export function downloadTxt(filename: string, content: string): void {
  const blob = new Blob([content], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

/**
 * Copy text to the system clipboard. Returns true on success.
 *
 * Uses the modern async API when available (requires a secure context,
 * which includes `localhost`) and falls back to a hidden `<textarea>` +
 * `execCommand` for production-over-HTTP and other oddities.
 */
export async function copyToClipboard(text: string): Promise<boolean> {
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text)
      return true
    }
  } catch {
    // Fall through to the textarea fallback.
  }
  try {
    const ta = document.createElement('textarea')
    ta.value = text
    ta.setAttribute('readonly', '')
    ta.style.position = 'fixed'
    ta.style.left = '-9999px'
    document.body.appendChild(ta)
    ta.select()
    const ok = document.execCommand('copy')
    document.body.removeChild(ta)
    return ok
  } catch {
    return false
  }
}
