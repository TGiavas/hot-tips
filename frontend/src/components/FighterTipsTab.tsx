import type { ActiveTip, ArenaState } from '../types'
import { TipToggleButton } from './TipToggleButton'

type Props = {
  state: ArenaState
  activeByTipId: Map<number, ActiveTip>
  pendingTipIds: Set<number>
  canEdit: boolean
  onToggle: (tipId: number) => void
}

export const FighterTipsTab = ({
  state,
  activeByTipId,
  pendingTipIds,
  canEdit,
  onToggle,
}: Props) => {
  const poolFull = state.known_tip_count >= state.max_tips

  // Group fighter tips by their fighter, then render one row per fighter
  // with a +5% button and a -5% button.
  const tipsByFighter = new Map<number, { plus?: number; minus?: number }>()
  for (const tip of state.fighter_tips) {
    const row = tipsByFighter.get(tip.fighter_id) ?? {}
    if (tip.modifier > 0) row.plus = tip.tip_id
    else row.minus = tip.tip_id
    tipsByFighter.set(tip.fighter_id, row)
  }

  return (
    <table>
      <thead>
        <tr>
          <th>Fighter</th>
          <th>+5%</th>
          <th>-5%</th>
          <th>Submitted by</th>
        </tr>
      </thead>
      <tbody>
        {state.fighters.map((fighter) => {
          const row = tipsByFighter.get(fighter.id)
          const plusActive = row?.plus != null ? activeByTipId.get(row.plus) : undefined
          const minusActive = row?.minus != null ? activeByTipId.get(row.minus) : undefined
          return (
            <tr key={fighter.id}>
              <td>{fighter.name}</td>
              <td>
                {row?.plus != null ? (
                  <TipToggleButton
                    tipId={row.plus}
                    label={`${fighter.name} +5%`}
                    active={plusActive}
                    poolFull={poolFull}
                    pending={pendingTipIds.has(row.plus)}
                    canEdit={canEdit}
                    onClick={onToggle}
                  />
                ) : null}
              </td>
              <td>
                {row?.minus != null ? (
                  <TipToggleButton
                    tipId={row.minus}
                    label={`${fighter.name} -5%`}
                    active={minusActive}
                    poolFull={poolFull}
                    pending={pendingTipIds.has(row.minus)}
                    canEdit={canEdit}
                    onClick={onToggle}
                  />
                ) : null}
              </td>
              <td className="submitters">
                {plusActive ? (
                  <div>
                    <span className="badge badge-plus">+5%</span>{' '}
                    {plusActive.submitted_by.display_name}
                  </div>
                ) : null}
                {minusActive ? (
                  <div>
                    <span className="badge badge-minus">-5%</span>{' '}
                    {minusActive.submitted_by.display_name}
                  </div>
                ) : null}
              </td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}
