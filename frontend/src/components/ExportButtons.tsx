import { useState } from 'react'

import { copyToClipboard, downloadTxt } from '../download'

type Props = {
  /**
   * Lazily compute the export text. Lazy so we always use the *current*
   * (filtered / sorted) state of the table, not whatever it was at mount.
   */
  getText: () => string
  filename: string
  className?: string
}

export const ExportButtons = ({ getText, filename, className }: Props) => {
  const [copied, setCopied] = useState<'idle' | 'ok' | 'fail'>('idle')

  const handleExport = () => {
    downloadTxt(filename, getText())
  }

  const handleCopy = async () => {
    const ok = await copyToClipboard(getText())
    setCopied(ok ? 'ok' : 'fail')
    window.setTimeout(() => setCopied('idle'), 1500)
  }

  const copyLabel =
    copied === 'ok' ? 'Copied!' : copied === 'fail' ? 'Copy failed' : 'Copy'

  return (
    <div className={`export-group${className ? ` ${className}` : ''}`}>
      <button type="button" className="ghost-btn" onClick={handleExport}>
        Export to TXT
      </button>
      <button
        type="button"
        className="ghost-btn"
        onClick={handleCopy}
        aria-live="polite"
      >
        {copyLabel}
      </button>
    </div>
  )
}
