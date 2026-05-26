import { useCallback, useEffect, useMemo, useState } from 'react'

import { ApiError, ensureCsrf, fetchWhoAmI, toggleTip } from './api'
import { ExportButtons } from './components/ExportButtons'
import { Header } from './components/Header'
import { FighterTipsTab } from './components/FighterTipsTab'
import { MatchResultsTable } from './components/MatchResultsTable'
import { MatchupTipsTab } from './components/MatchupTipsTab'
import { buildTipsExportText } from './exportText'
import { usePolledArenaState } from './usePolledArenaState'
import type { ActiveTip, WhoAmI } from './types'

type AuthStatus =
  | { kind: 'loading' }
  | { kind: 'anonymous' }
  | { kind: 'signed-in'; whoami: WhoAmI }

type Tab = 'fighter' | 'matchup'

export const App = () => {
  const [auth, setAuth] = useState<AuthStatus>({ kind: 'loading' })

  useEffect(() => {
    let cancelled = false
    const bootstrap = async () => {
      try {
        await ensureCsrf()
        const whoami = await fetchWhoAmI()
        if (cancelled) return
        setAuth(whoami ? { kind: 'signed-in', whoami } : { kind: 'anonymous' })
      } catch {
        if (!cancelled) setAuth({ kind: 'anonymous' })
      }
    }
    void bootstrap()
    return () => {
      cancelled = true
    }
  }, [])

  if (auth.kind === 'loading') {
    return (
      <div className="app">
        <div className="center">Loading…</div>
      </div>
    )
  }

  const whoami = auth.kind === 'signed-in' ? auth.whoami : null
  return <Main whoami={whoami} />
}

type MainProps = { whoami: WhoAmI | null }

const Main = ({ whoami }: MainProps) => {
  const { state, loading, error, refresh, setState } = usePolledArenaState(true)
  const [tab, setTab] = useState<Tab>('fighter')
  const [pending, setPending] = useState<Set<number>>(new Set())
  const [toggleError, setToggleError] = useState<string | null>(null)

  const activeByTipId = useMemo(() => {
    const map = new Map<number, ActiveTip>()
    if (!state) return map
    for (const at of state.active_tips) map.set(at.tip_id, at)
    return map
  }, [state])

  const canEdit = whoami !== null

  const onToggle = useCallback(
    async (tipId: number) => {
      if (!canEdit) return
      setPending((prev) => {
        const next = new Set(prev)
        next.add(tipId)
        return next
      })
      setToggleError(null)
      try {
        const next = await toggleTip(tipId)
        setState(next)
      } catch (err) {
        if (err instanceof ApiError) {
          if (err.status === 409) {
            setToggleError(
              'The shared daily pool is full (15 tips). Remove one to add another.',
            )
          } else if (err.status === 401 || err.status === 403) {
            setToggleError(
              'Your session expired. Sign in again to keep editing.',
            )
          } else {
            const body = err.body as { detail?: string } | null
            setToggleError(body?.detail ?? `Request failed (${err.status}).`)
          }
        } else {
          setToggleError('Network error. The polling tick will retry.')
        }
        // Re-sync from the server so optimistic UI doesn't drift.
        void refresh()
      } finally {
        setPending((prev) => {
          const next = new Set(prev)
          next.delete(tipId)
          return next
        })
      }
    },
    [canEdit, refresh, setState],
  )

  if (!state) {
    return (
      <div className="app">
        <div className="center">
          {error ? `Failed to load: ${error}` : loading ? 'Loading…' : 'No data.'}
        </div>
      </div>
    )
  }

  return (
    <div className="app">
      <Header
        gameDay={state.game_day}
        knownTipCount={state.known_tip_count}
        maxTips={state.max_tips}
        whoami={whoami}
      />
      {toggleError ? (
        <div className="error-banner">{toggleError}</div>
      ) : null}
      <main className="workspace">
        <section className="panel panel-results">
          <h2>Match Results</h2>
          <MatchResultsTable
            results={state.match_results}
            gameDay={state.game_day}
          />
        </section>
        <section className="panel">
          <h2>Tip Selection</h2>
          <div className="tabs">
            <button
              type="button"
              className={tab === 'fighter' ? 'active' : ''}
              onClick={() => setTab('fighter')}
            >
              Fighter Tips
            </button>
            <button
              type="button"
              className={tab === 'matchup' ? 'active' : ''}
              onClick={() => setTab('matchup')}
            >
              Matchup Tips
            </button>
            <ExportButtons
              getText={() => buildTipsExportText(state, activeByTipId)}
              filename={`hot-tips-${state.game_day}.txt`}
            />
          </div>
          {tab === 'fighter' ? (
            <FighterTipsTab
              state={state}
              activeByTipId={activeByTipId}
              pendingTipIds={pending}
              canEdit={canEdit}
              onToggle={onToggle}
            />
          ) : (
            <MatchupTipsTab
              state={state}
              activeByTipId={activeByTipId}
              pendingTipIds={pending}
              canEdit={canEdit}
              onToggle={onToggle}
            />
          )}
        </section>
      </main>
    </div>
  )
}
