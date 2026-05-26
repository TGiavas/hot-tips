/**
 * Helpers that turn the arena state into plain-text snapshots suitable for
 * pasting into Discord, taking notes, or shipping as a `.txt` file.
 */
import type { ActiveTip, ArenaState } from './types'

/**
 * Combined "today's tips" export — both Fighter Tips and Matchup Tips in
 * one document, since the user thinks of the bottom panel as a single
 * board even though the UI splits it into two tabs.
 */
export function buildTipsExportText(
  state: ArenaState,
  activeByTipId: Map<number, ActiveTip>,
): string {
  const lines: string[] = []
  lines.push(`Hot Tips - ${state.game_day}`)
  lines.push('')

  // Fighter tips section ----------------------------------------------------
  const tipsByFighter = new Map<number, { plus?: number; minus?: number }>()
  for (const tip of state.fighter_tips) {
    const row = tipsByFighter.get(tip.fighter_id) ?? {}
    if (tip.modifier > 0) row.plus = tip.tip_id
    else row.minus = tip.tip_id
    tipsByFighter.set(tip.fighter_id, row)
  }

  const activeFighter: string[] = []
  for (const fighter of state.fighters) {
    const row = tipsByFighter.get(fighter.id)
    if (row?.plus != null) {
      const a = activeByTipId.get(row.plus)
      if (a)
        activeFighter.push(
          `- ${fighter.name} +5% (${a.submitted_by.display_name})`,
        )
    }
    if (row?.minus != null) {
      const a = activeByTipId.get(row.minus)
      if (a)
        activeFighter.push(
          `- ${fighter.name} -5% (${a.submitted_by.display_name})`,
        )
    }
  }

  lines.push(`Fighter Tips (${activeFighter.length} active):`)
  if (activeFighter.length === 0) {
    lines.push('  (none)')
  } else {
    lines.push(...activeFighter)
  }
  lines.push('')

  // Matchup tips section ----------------------------------------------------
  const lookup = new Map<string, number>()
  for (const tip of state.matchup_tips) {
    if (tip.matchup_id == null) continue
    lookup.set(`${tip.matchup_id}:${tip.target_fighter_id}`, tip.tip_id)
  }

  const activeMatchup: string[] = []
  for (const m of state.matchups) {
    const aTipId = lookup.get(`${m.matchup_id}:${m.fighter_a.id}`)
    const bTipId = lookup.get(`${m.matchup_id}:${m.fighter_b.id}`)
    if (aTipId != null) {
      const a = activeByTipId.get(aTipId)
      if (a)
        activeMatchup.push(
          `- ${m.fighter_a.name} vs ${m.fighter_b.name} -> ${m.fighter_a.name} +10% (${a.submitted_by.display_name})`,
        )
    }
    if (bTipId != null) {
      const a = activeByTipId.get(bTipId)
      if (a)
        activeMatchup.push(
          `- ${m.fighter_a.name} vs ${m.fighter_b.name} -> ${m.fighter_b.name} +10% (${a.submitted_by.display_name})`,
        )
    }
  }

  lines.push(`Matchup Tips (${activeMatchup.length} active):`)
  if (activeMatchup.length === 0) {
    lines.push('  (none)')
  } else {
    lines.push(...activeMatchup)
  }
  lines.push('')

  lines.push(
    `Total: ${state.known_tip_count} / ${state.max_tips} tips active`,
  )

  return lines.join('\n')
}
