import { useState } from 'react'

import { ApiError, triggerSync } from '../api'
import type { ArenaState, SyncStatus, WhoAmI } from '../types'

type Props = {
  gameDay: string
  knownTipCount: number
  maxTips: number
  whoami: WhoAmI | null
  syncStatus: SyncStatus | null
  onSyncComplete: (next: ArenaState) => void
}

export const Header = ({
  gameDay,
  knownTipCount,
  maxTips,
  whoami,
  syncStatus,
  onSyncComplete,
}: Props) => {
  const full = knownTipCount >= maxTips
  return (
    <header className="header">
      <div className="brand">
        <span className="sigil">⚔</span>
        <span className="brand-text">Hot Tips</span>
      </div>
      <div className="meta">
        <div>
          Day <b>{gameDay}</b>
        </div>
        <div>
          Tips{' '}
          <b className={full ? 'pool-warning' : undefined}>
            {knownTipCount} / {maxTips}
          </b>
        </div>
        <div className="muted">Resets at midnight, New York</div>
      </div>
      <div className="right">
        <SyncIndicator status={syncStatus} />
        {whoami ? (
          <>
            <SyncNowButton onSyncComplete={onSyncComplete} />
            <span>
              Signed in as <b>{whoami.display_name}</b>
            </span>
            {whoami.is_staff ? (
              <a href="/admin/" target="_blank" rel="noopener noreferrer">
                Admin
              </a>
            ) : null}
            <form
              method="post"
              action="/accounts/logout/"
              style={{ display: 'inline' }}
            >
              <CsrfHidden />
              <button type="submit">Log out</button>
            </form>
          </>
        ) : (
          <>
            <span className="muted">Read-only — sign in to edit</span>
            <button
              type="button"
              onClick={() => {
                window.location.href = '/accounts/login/?next=/'
              }}
            >
              Sign in with Discord
            </button>
          </>
        )}
      </div>
    </header>
  )
}

const CsrfHidden = () => {
  const cookie = document.cookie
    .split('; ')
    .find((c) => c.startsWith('csrftoken='))
  const token = cookie
    ? decodeURIComponent(cookie.slice('csrftoken='.length))
    : ''
  return <input type="hidden" name="csrfmiddlewaretoken" value={token} />
}

/**
 * Coloured dot + short text describing the last spreadsheet-sync run.
 * Hover for the verbose error / message. Anonymous users see it too —
 * it's just observability.
 */
const SyncIndicator = ({ status }: { status: SyncStatus | null }) => {
  if (!status) return null

  let dotClass = 'sync-dot sync-dot-amber'
  let label = 'Sync: not configured'
  let title = status.message || 'No sync runs yet.'

  if (!status.configured) {
    dotClass = 'sync-dot sync-dot-amber'
    label = 'Sync: not configured'
    title = 'Admin needs to paste the spreadsheet URL in /admin/.'
  } else if (!status.enabled) {
    dotClass = 'sync-dot sync-dot-grey'
    label = 'Sync: paused'
    title = 'Disabled by admin.'
  } else if (status.status === 'error') {
    dotClass = 'sync-dot sync-dot-red'
    label = 'Sync: failed'
    title = status.message || 'Sync failed (no detail).'
  } else if (status.status === 'ok') {
    dotClass = 'sync-dot sync-dot-green'
    label = `Synced ${formatRelative(status.last_run_at)}`
    title =
      `${status.message || 'ok'}\n` +
      `Last run: ${status.last_run_at ?? 'never'}\n` +
      `Sheet date: ${status.last_sheet_date ?? '-'}`
  } else if (status.status === 'skipped') {
    dotClass = 'sync-dot sync-dot-amber'
    label = `Sync: skipped`
    title = status.message || 'Last sync skipped.'
  } else {
    dotClass = 'sync-dot sync-dot-amber'
    label = 'Sync: never run'
    title = 'No sync runs yet.'
  }

  return (
    <span className="sync-indicator" title={title}>
      <span className={dotClass} aria-hidden="true" />
      <span className="muted small">{label}</span>
    </span>
  )
}

const SyncNowButton = ({
  onSyncComplete,
}: {
  onSyncComplete: (next: ArenaState) => void
}) => {
  const [pending, setPending] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const click = async () => {
    setPending(true)
    setErr(null)
    try {
      const next = await triggerSync()
      onSyncComplete(next)
    } catch (e) {
      const msg =
        e instanceof ApiError
          ? `Sync request failed (${e.status})`
          : 'Sync request failed (network error)'
      setErr(msg)
    } finally {
      setPending(false)
    }
  }
  return (
    <button
      type="button"
      onClick={click}
      disabled={pending}
      title={err ?? 'Fetch the community spreadsheet and apply new tips.'}
    >
      {pending ? 'Syncing…' : 'Sync now'}
    </button>
  )
}

/** Compact "5 min ago" / "just now" formatter for the indicator. */
const formatRelative = (iso: string | null): string => {
  if (!iso) return 'never'
  const t = Date.parse(iso)
  if (Number.isNaN(t)) return iso
  const seconds = Math.max(0, Math.floor((Date.now() - t) / 1000))
  if (seconds < 30) return 'just now'
  if (seconds < 60) return `${seconds}s ago`
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes} min ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}
