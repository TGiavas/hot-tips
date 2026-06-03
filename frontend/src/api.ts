import type { ArenaState, WhoAmI } from './types'

const getCookie = (name: string): string | null => {
  const match = document.cookie
    .split('; ')
    .find((row) => row.startsWith(`${name}=`))
  return match ? decodeURIComponent(match.slice(name.length + 1)) : null
}

const apiFetch = async (
  url: string,
  options: RequestInit = {},
): Promise<Response> => {
  const headers = new Headers(options.headers ?? {})
  headers.set('Accept', 'application/json')
  if (options.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  const csrf = getCookie('csrftoken')
  if (csrf && options.method && options.method.toUpperCase() !== 'GET') {
    headers.set('X-CSRFToken', csrf)
  }
  return fetch(url, {
    ...options,
    headers,
    credentials: 'include',
  })
}

export class ApiError extends Error {
  status: number
  body: unknown
  constructor(status: number, body: unknown) {
    super(`API error ${status}`)
    this.status = status
    this.body = body
  }
}

const parseOrThrow = async <T>(response: Response): Promise<T> => {
  if (response.status === 204) return undefined as T
  const text = await response.text()
  const body = text ? JSON.parse(text) : null
  if (!response.ok) {
    throw new ApiError(response.status, body)
  }
  return body as T
}

export const ensureCsrf = async (): Promise<void> => {
  await apiFetch('/api/auth/csrf/', { method: 'GET' })
}

export const fetchWhoAmI = async (): Promise<WhoAmI | null> => {
  const response = await apiFetch('/api/auth/whoami/', { method: 'GET' })
  if (response.status === 401) return null
  return parseOrThrow<WhoAmI>(response)
}

export const fetchArenaState = async (): Promise<ArenaState> => {
  const response = await apiFetch('/api/arena/state/', { method: 'GET' })
  return parseOrThrow<ArenaState>(response)
}

export const toggleTip = async (tipId: number): Promise<ArenaState> => {
  const response = await apiFetch('/api/arena/tips/toggle/', {
    method: 'POST',
    body: JSON.stringify({ tip_id: tipId }),
  })
  return parseOrThrow<ArenaState>(response)
}

/**
 * Force one community-spreadsheet sync cycle. Returns the new arena state
 * (including the updated ``sync_status`` block). Authenticated users only.
 */
export const triggerSync = async (): Promise<ArenaState> => {
  const response = await apiFetch('/api/arena/sync/', { method: 'POST' })
  return parseOrThrow<ArenaState>(response)
}
