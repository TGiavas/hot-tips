import { useMemo, useState } from 'react'
import type { CSSProperties } from 'react'

import type { MatchResult } from '../types'
import { ExportButtons } from './ExportButtons'

type Props = {
  results: MatchResult[]
  gameDay: string
}

type SortKey = 'fighter_a' | 'a_pct' | 'fighter_b' | 'b_pct'
type SortDir = 'asc' | 'desc'

type Column = {
  key: SortKey
  label: string
  numeric: boolean
}

const COLUMNS: Column[] = [
  { key: 'fighter_a', label: 'Fighter A', numeric: false },
  { key: 'a_pct', label: 'A %', numeric: true },
  { key: 'fighter_b', label: 'Fighter B', numeric: false },
  { key: 'b_pct', label: 'B %', numeric: true },
]

// `0` means "no threshold" — labeled as "All" in the UI. Listed first so
// it reads as the broadest-to-narrowest filter from top to bottom.
const THRESHOLD_OPTIONS = [0, 50, 55, 60, 65, 70] as const

// Per-cell green/red tint that scales with distance from 50%.
//
// We deliberately use the theme's existing `moss` (#4d6b2b) and `oxblood`
// (#6b1818) so the highlight reads as parchment+ink rather than fighting
// the aesthetic. Alpha tops out at 0.4 so dark ink text stays legible.
// Tip-driven percentages currently fall in roughly 25..75, so we divide
// by 25 to get 0..1 across that range.
const tintStyle = (pct: number): CSSProperties => {
  if (pct === 50) return {}
  const intensity = Math.min(1, Math.abs(pct - 50) / 25)
  const alpha = intensity * 0.4
  const rgb = pct > 50 ? '77, 107, 43' : '107, 24, 24'
  return { backgroundColor: `rgba(${rgb}, ${alpha})` }
}

// Each backend match shows up TWICE in the table (cartesian product) so
// the user can always read every matchup for a given fighter off the left
// column. The TXT/Copy export deduplicates by matchup_id and always orients
// the leading fighter on the left, so chat doesn't get spammed.
type Row = MatchResult & { direction: 'forward' | 'reversed' }

export const MatchResultsTable = ({ results, gameDay }: Props) => {
  const [sortKey, setSortKey] = useState<SortKey>('a_pct')
  const [sortDir, setSortDir] = useState<SortDir>('desc')
  // 55% is the first "real" favorite tier (a single +5% fighter tip nudges
  // a match here), so it's a sensible default that hides 50/50 noise without
  // hiding modest favorites.
  const [minPercent, setMinPercent] = useState<number>(55)
  const [search, setSearch] = useState<string>('')

  const expanded: Row[] = useMemo(
    () =>
      results.flatMap((r): Row[] => [
        { ...r, direction: 'forward' },
        {
          ...r,
          fighter_a: r.fighter_b,
          fighter_b: r.fighter_a,
          fighter_a_percent: r.fighter_b_percent,
          fighter_b_percent: r.fighter_a_percent,
          direction: 'reversed',
        },
      ]),
    [results],
  )

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    return expanded.filter((r) => {
      if (r.fighter_a_percent < minPercent) return false
      if (q.length === 0) return true
      // Match only the LEFT column. The cartesian product guarantees every
      // fighter appears in the left column for each of their matchups, so
      // searching "Corrrak" surfaces exactly Corrrak's 6 rows — no doubled
      // hits from matching the opponent column.
      return r.fighter_a.toLowerCase().includes(q)
    })
  }, [expanded, minPercent, search])

  const sorted = useMemo(() => {
    const factor = sortDir === 'asc' ? 1 : -1
    return [...filtered].sort((a, b) => {
      switch (sortKey) {
        case 'fighter_a':
          return a.fighter_a.localeCompare(b.fighter_a) * factor
        case 'fighter_b':
          return a.fighter_b.localeCompare(b.fighter_b) * factor
        case 'a_pct':
          return (a.fighter_a_percent - b.fighter_a_percent) * factor
        case 'b_pct':
          return (a.fighter_b_percent - b.fighter_b_percent) * factor
      }
    })
  }, [filtered, sortKey, sortDir])

  const onHeaderClick = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortKey(key)
      // Numeric columns default to descending (biggest first feels right);
      // string columns default to ascending (A-Z).
      setSortDir(COLUMNS.find((c) => c.key === key)?.numeric ? 'desc' : 'asc')
    }
  }

  const indicator = (key: SortKey): string => {
    if (sortKey !== key) return '⇅'
    return sortDir === 'asc' ? '▲' : '▼'
  }

  // Lazy: rebuild on click so the export always reflects current filter/sort.
  // The on-screen table is a cartesian product, but the export deduplicates
  // by matchup_id and always puts the leading fighter on the left, so chat
  // gets one clean line per matchup. Example: "Corrrak > Gloz (60%)"
  const buildExportText = (): string => {
    const seen = new Set<number>()
    const lines: string[] = []
    for (const r of sorted) {
      if (seen.has(r.matchup_id)) continue
      seen.add(r.matchup_id)
      const leadingFirst = r.fighter_a_percent >= r.fighter_b_percent
      const left = leadingFirst ? r.fighter_a : r.fighter_b
      const right = leadingFirst ? r.fighter_b : r.fighter_a
      const pct = leadingFirst ? r.fighter_a_percent : r.fighter_b_percent
      lines.push(`${left} > ${right} (${pct}%)`)
    }
    return lines.join('\n')
  }

  return (
    <>
      <div className="table-toolbar">
        <input
          type="search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search fighter…"
          className="search-input"
          aria-label="Search by fighter name"
        />
        <label className="filter-label">
          <span>Show matches with leading fighter at least</span>
          <select
            value={minPercent}
            onChange={(e) => setMinPercent(Number(e.target.value))}
            className="select-input"
            aria-label="Minimum leading-fighter percentage"
          >
            {THRESHOLD_OPTIONS.map((p) => (
              <option key={p} value={p}>
                {p === 0 ? 'All' : `${p}%`}
              </option>
            ))}
          </select>
        </label>
        <span className="muted small">
          Showing {sorted.length} of {expanded.length} rows
        </span>
        <ExportButtons
          getText={buildExportText}
          filename={`hot-tips-results-${gameDay}.txt`}
        />
      </div>
      <table>
        <thead>
          <tr>
            {COLUMNS.map((col) => (
              <th
                key={col.key}
                className={`sortable${col.numeric ? ' num' : ''}${
                  sortKey === col.key ? ' sorted' : ''
                }`}
                onClick={() => onHeaderClick(col.key)}
                aria-sort={
                  sortKey === col.key
                    ? sortDir === 'asc'
                      ? 'ascending'
                      : 'descending'
                    : 'none'
                }
              >
                <span className="th-label">{col.label}</span>
                <span className="th-indicator" aria-hidden="true">
                  {indicator(col.key)}
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.length === 0 ? (
            <tr>
              <td colSpan={COLUMNS.length} className="muted small empty-row">
                {search.trim().length > 0
                  ? `No matches for "${search.trim()}".`
                  : minPercent === 0
                    ? 'No matches to show.'
                    : `No matches above ${minPercent}%. Lower the threshold to see more.`}
              </td>
            </tr>
          ) : (
            sorted.map((r) => {
              const aStyle = tintStyle(r.fighter_a_percent)
              const bStyle = tintStyle(r.fighter_b_percent)
              return (
                <tr key={`${r.matchup_id}-${r.direction}`}>
                  <td style={aStyle}>{r.fighter_a}</td>
                  <td className="num" style={aStyle}>
                    {r.fighter_a_percent}
                  </td>
                  <td style={bStyle}>{r.fighter_b}</td>
                  <td className="num" style={bStyle}>
                    {r.fighter_b_percent}
                  </td>
                </tr>
              )
            })
          )}
        </tbody>
      </table>
    </>
  )
}
