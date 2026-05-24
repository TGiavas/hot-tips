import type { WhoAmI } from '../types'

type Props = {
  gameDay: string
  knownTipCount: number
  maxTips: number
  whoami: WhoAmI | null
}

export const Header = ({ gameDay, knownTipCount, maxTips, whoami }: Props) => {
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
        {whoami ? (
          <>
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
              Sign in with Discord / Google
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
