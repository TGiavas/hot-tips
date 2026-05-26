import { useMemo, useState } from 'react'

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

// Each backend match shows up exactly once, but oriented so the leading
// fighter is always in the left column. Ties keep the original direction.
// (The cartesian-product approach added duplicate rows at low thresholds;
// users found the duplicates confusing, so we collapse them.)
type Row = MatchResult & { direction: 'forward' | 'reversed' }

export const MatchResultsTable = ({ results, gameDay }: Props) => {
  const [sortKey, setSortKey] = useState<SortKey>('a_pct')
  const [sortDir, setSortDir] = useState<SortDir>('desc')
  // 55% is the first "real" favorite tier (a single +5% fighter tip nudges
  // a match here), so it's a sensible default that hides 50/50 noise without
  // hiding modest favorites.
  const [minPercent, setMinPercent] = useState<number>(55)

  const oriented: Row[] = useMemo(
    () =>
      results.map((r): Row =>
        r.fighter_a_percent >= r.fighter_b_percent
          ? { ...r, direction: 'forward' }
          : {
              ...r,
              fighter_a: r.fighter_b,
              fighter_b: r.fighter_a,
              fighter_a_percent: r.fighter_b_percent,
              fighter_b_percent: r.fighter_a_percent,
              direction: 'reversed',
            },
      ),
    [results],
  )

  const filtered = useMemo(
    () => oriented.filter((r) => r.fighter_a_percent >= minPercent),
    [oriented, minPercent],
  )

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
  // Format is intentionally terse — meant to be pasted directly into game chat.
  // Example: "Corrrak > Gloz (60%)"
  const buildExportText = (): string =>
    sorted
      .map(
        (r) =>
          `${r.fighter_a} > ${r.fighter_b} (${r.fighter_a_percent}%)`,
      )
      .join('\n')

  return (
    <>
      <div className="table-toolbar">
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
          Showing {sorted.length} of {oriented.length} rows
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
                {minPercent === 0
                  ? 'No matches to show.'
                  : `No matches above ${minPercent}%. Lower the threshold to see more.`}
              </td>
            </tr>
          ) : (
            sorted.map((r) => (
              <tr key={`${r.matchup_id}-${r.direction}`}>
                <td>{r.fighter_a}</td>
                <td className="num">{r.fighter_a_percent}</td>
                <td>{r.fighter_b}</td>
                <td className="num">{r.fighter_b_percent}</td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </>
  )
}
