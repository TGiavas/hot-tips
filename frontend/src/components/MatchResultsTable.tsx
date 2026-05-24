import { useMemo, useState } from 'react'

import type { MatchResult } from '../types'

type Props = {
  results: MatchResult[]
}

type SortKey = 'default' | 'fighter_a' | 'a_pct' | 'fighter_b' | 'b_pct'
type SortDir = 'asc' | 'desc'

type Column = {
  key: Exclude<SortKey, 'default'>
  label: string
  numeric: boolean
}

const COLUMNS: Column[] = [
  { key: 'fighter_a', label: 'Fighter A', numeric: false },
  { key: 'a_pct', label: 'A %', numeric: true },
  { key: 'fighter_b', label: 'Fighter B', numeric: false },
  { key: 'b_pct', label: 'B %', numeric: true },
]

export const MatchResultsTable = ({ results }: Props) => {
  const [sortKey, setSortKey] = useState<SortKey>('default')
  const [sortDir, setSortDir] = useState<SortDir>('desc')

  const sorted = useMemo(() => {
    if (sortKey === 'default') return results
    const factor = sortDir === 'asc' ? 1 : -1
    const compare = (a: MatchResult, b: MatchResult): number => {
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
    }
    return [...results].sort(compare)
  }, [results, sortKey, sortDir])

  const onHeaderClick = (key: Column['key']) => {
    if (sortKey === key) {
      // Cycle: asc -> desc -> default.
      if (sortDir === 'asc') {
        setSortDir('desc')
      } else {
        setSortKey('default')
      }
    } else {
      setSortKey(key)
      // Numeric columns default to descending (biggest first feels right);
      // string columns default to ascending (A-Z).
      setSortDir(COLUMNS.find((c) => c.key === key)?.numeric ? 'desc' : 'asc')
    }
  }

  const indicator = (key: Column['key']): string => {
    if (sortKey !== key) return '⇅'
    return sortDir === 'asc' ? '▲' : '▼'
  }

  return (
    <div className="scroll">
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
          {sorted.map((r) => (
            <tr key={r.matchup_id}>
              <td>{r.fighter_a}</td>
              <td className="num">{r.fighter_a_percent}</td>
              <td>{r.fighter_b}</td>
              <td className="num">{r.fighter_b_percent}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
