export type Fighter = {
  id: number
  name: string
  sort_order: number
}

export type FighterRef = {
  id: number
  name: string
}

export type Matchup = {
  matchup_id: number
  fighter_a: FighterRef
  fighter_b: FighterRef
  sort_order: number
}

export type TipBase = {
  tip_id: number
  label: string
  tip_type: 'fighter' | 'matchup'
  fighter_id: number | null
  matchup_id: number | null
  target_fighter_id: number
  modifier: number
  sort_order: number
}

export type FighterTip = TipBase & {
  tip_type: 'fighter'
  fighter_id: number
  matchup_id: null
  fighter_name: string
}

export type MatchupTip = TipBase & {
  tip_type: 'matchup'
  matchup_id: number
  fighter_id: null
  matchup_label: string
  target_fighter_name: string
}

export type ActiveTip = {
  tip_id: number
  submitted_by: { id: number; display_name: string }
}

export type MatchResult = {
  matchup_id: number
  fighter_a: string
  fighter_a_percent: number
  fighter_b: string
  fighter_b_percent: number
}

export type ArenaState = {
  game_day: string
  known_tip_count: number
  max_tips: number
  fighters: Fighter[]
  matchups: Matchup[]
  fighter_tips: FighterTip[]
  matchup_tips: MatchupTip[]
  active_tips: ActiveTip[]
  match_results: MatchResult[]
}

export type WhoAmI = {
  id: number
  username: string
  display_name: string
  is_staff: boolean
}
