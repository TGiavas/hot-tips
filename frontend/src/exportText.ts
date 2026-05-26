/**
 * Helpers that turn the arena state into plain-text snapshots suitable for
 * pasting into game chat.
 *
 * Format is intentionally terse — no titles, no submitter names, no counts,
 * no separators. Fighter tips read as e.g. `Corrrak +5`, matchup tips as
 * e.g. `Corrrak > Leo`. Fighter tips come first, then matchup tips, all in
 * one continuous list.
 */
import type { ActiveTip, ArenaState } from './types'

export function buildTipsExportText(
  state: ArenaState,
  activeByTipId: Map<number, ActiveTip>,
): string {
  // Fighter tips: "Fighter +5" / "Fighter -5" -------------------------------
  const tipsByFighter = new Map<number, { plus?: number; minus?: number }>()
  for (const tip of state.fighter_tips) {
    const row = tipsByFighter.get(tip.fighter_id) ?? {}
    if (tip.modifier > 0) row.plus = tip.tip_id
    else row.minus = tip.tip_id
    tipsByFighter.set(tip.fighter_id, row)
  }

  const fighterLines: string[] = []
  for (const fighter of state.fighters) {
    const row = tipsByFighter.get(fighter.id)
    if (row?.plus != null && activeByTipId.has(row.plus)) {
      fighterLines.push(`${fighter.name} +5`)
    }
    if (row?.minus != null && activeByTipId.has(row.minus)) {
      fighterLines.push(`${fighter.name} -5`)
    }
  }

  // Matchup tips: "Winner > Loser" ------------------------------------------
  const lookup = new Map<string, number>()
  for (const tip of state.matchup_tips) {
    if (tip.matchup_id == null) continue
    lookup.set(`${tip.matchup_id}:${tip.target_fighter_id}`, tip.tip_id)
  }

  const matchupLines: string[] = []
  for (const m of state.matchups) {
    const aTipId = lookup.get(`${m.matchup_id}:${m.fighter_a.id}`)
    const bTipId = lookup.get(`${m.matchup_id}:${m.fighter_b.id}`)
    if (aTipId != null && activeByTipId.has(aTipId)) {
      matchupLines.push(`${m.fighter_a.name} > ${m.fighter_b.name}`)
    }
    if (bTipId != null && activeByTipId.has(bTipId)) {
      matchupLines.push(`${m.fighter_b.name} > ${m.fighter_a.name}`)
    }
  }

  return [...fighterLines, ...matchupLines].join('\n')
}
