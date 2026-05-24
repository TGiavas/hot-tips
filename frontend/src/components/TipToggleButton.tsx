import type { ActiveTip } from '../types'

type Props = {
  tipId: number
  label: string
  active: ActiveTip | undefined
  poolFull: boolean
  pending: boolean
  canEdit: boolean
  onClick: (tipId: number) => void
}

export const TipToggleButton = ({
  tipId,
  label,
  active,
  poolFull,
  pending,
  canEdit,
  onClick,
}: Props) => {
  const isActive = active !== undefined
  // Disable when:
  //   * the user isn't authenticated (read-only mode),
  //   * a request for this tip is in flight, or
  //   * the pool is full AND this tip is currently inactive (you can always
  //     remove an active tip, even at the cap).
  const disabled = !canEdit || pending || (!isActive && poolFull)
  const title = canEdit
    ? undefined
    : 'Sign in to edit'
  return (
    <button
      type="button"
      className={`toggle-btn${isActive ? ' active' : ''}${canEdit ? '' : ' read-only'}`}
      disabled={disabled}
      onClick={() => onClick(tipId)}
      aria-pressed={isActive}
      title={title}
    >
      <span className="label">{label}</span>
    </button>
  )
}
