import { useCallback, useEffect, useRef, useState } from 'react'

import { fetchArenaState } from './api'
import type { ArenaState } from './types'

const POLL_INTERVAL_MS = 10_000

type State = {
  state: ArenaState | null
  loading: boolean
  error: string | null
}

export const usePolledArenaState = (enabled: boolean) => {
  const [{ state, loading, error }, setLocal] = useState<State>({
    state: null,
    loading: true,
    error: null,
  })
  const inFlight = useRef(false)

  const refresh = useCallback(async (): Promise<void> => {
    if (inFlight.current) return
    inFlight.current = true
    try {
      const next = await fetchArenaState()
      setLocal({ state: next, loading: false, error: null })
    } catch (err) {
      const message = err instanceof Error ? err.message : 'unknown error'
      setLocal((prev) => ({ ...prev, loading: false, error: message }))
    } finally {
      inFlight.current = false
    }
  }, [])

  const setState = useCallback((next: ArenaState) => {
    setLocal({ state: next, loading: false, error: null })
  }, [])

  useEffect(() => {
    if (!enabled) return
    void refresh()
    const tick = () => {
      if (document.visibilityState === 'visible') void refresh()
    }
    const intervalId = window.setInterval(tick, POLL_INTERVAL_MS)
    const onVisibility = () => {
      if (document.visibilityState === 'visible') void refresh()
    }
    document.addEventListener('visibilitychange', onVisibility)
    return () => {
      window.clearInterval(intervalId)
      document.removeEventListener('visibilitychange', onVisibility)
    }
  }, [enabled, refresh])

  return { state, loading, error, refresh, setState }
}
