import type { ActiveTip, ArenaState } from '../types'
import { TipToggleButton } from './TipToggleButton'

type Props = {
  state: ArenaState
  activeByTipId: Map<number, ActiveTip>
  pendingTipIds: Set<number>
  canEdit: boolean
  onToggle: (tipId: number) => void
}

export const MatchupTipsTab = ({
  state,
  activeByTipId,
  pendingTipIds,
  canEdit,
  onToggle,
}: Props) => {
  const poolFull = state.known_tip_count >= state.max_tips

  // Each matchup has two +10% tips. Find them by (matchup_id, target_fighter_id).
  const lookup = new Map<string, number>()
  for (const tip of state.matchup_tips) {
    if (tip.matchup_id == null) continue
    lookup.set(`${tip.matchup_id}:${tip.target_fighter_id}`, tip.tip_id)
  }

  return (
    <div className="scroll">
      <table>
        <thead>
          <tr>
            <th>Matchup</th>
            <th>Fighter A +10%</th>
            <th>Fighter B +10%</th>
            <th>Submitted by</th>
          </tr>
        </thead>
        <tbody>
          {state.matchups.map((m) => {
            const aTipId = lookup.get(`${m.matchup_id}:${m.fighter_a.id}`)
            const bTipId = lookup.get(`${m.matchup_id}:${m.fighter_b.id}`)
            const aActive = aTipId != null ? activeByTipId.get(aTipId) : undefined
            const bActive = bTipId != null ? activeByTipId.get(bTipId) : undefined
            return (
              <tr key={m.matchup_id}>
                <td>
                  {m.fighter_a.name} vs {m.fighter_b.name}
                </td>
                <td>
                  {aTipId != null ? (
                    <TipToggleButton
                      tipId={aTipId}
                      label={`${m.fighter_a.name} +10%`}
                      active={aActive}
                      poolFull={poolFull}
                      pending={pendingTipIds.has(aTipId)}
                      canEdit={canEdit}
                      onClick={onToggle}
                    />
                  ) : null}
                </td>
                <td>
                  {bTipId != null ? (
                    <TipToggleButton
                      tipId={bTipId}
                      label={`${m.fighter_b.name} +10%`}
                      active={bActive}
                      poolFull={poolFull}
                      pending={pendingTipIds.has(bTipId)}
                      canEdit={canEdit}
                      onClick={onToggle}
                    />
                  ) : null}
                </td>
                <td className="submitters">
                  {aActive ? (
                    <div>
                      <span className="badge">{m.fighter_a.name}</span>{' '}
                      {aActive.submitted_by.display_name}
                    </div>
                  ) : null}
                  {bActive ? (
                    <div>
                      <span className="badge">{m.fighter_b.name}</span>{' '}
                      {bActive.submitted_by.display_name}
                    </div>
                  ) : null}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
