export interface User {
  id: number;
  email: string;
  username: string;
  fpl_team_id?: number;
  is_active: boolean;
  created_at: string;
}

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface RegisterData {
  email: string;
  username: string;
  password: string;
  fpl_team_id?: number;
}

export enum Position {
  GOALKEEPER = 1,
  DEFENDER = 2,
  MIDFIELDER = 3,
  FORWARD = 4,
}

export const POSITION_NAMES = {
  [Position.GOALKEEPER]: 'Goalkeeper',
  [Position.DEFENDER]: 'Defender',
  [Position.MIDFIELDER]: 'Midfielder',
  [Position.FORWARD]: 'Forward',
} as const;

export const POSITION_SHORT_NAMES = {
  [Position.GOALKEEPER]: 'GKP',
  [Position.DEFENDER]: 'DEF',
  [Position.MIDFIELDER]: 'MID',
  [Position.FORWARD]: 'FWD',
} as const;

export interface Player {
  id: number;
  fpl_id: number;
  first_name?: string;
  second_name: string;
  web_name: string;
  team_id: number;
  position: Position;
  current_price: number; // In 0.1M units
  total_points: number;
  form: number;
  status: 'a' | 'i' | 's' | 'u'; // available, injured, suspended, unavailable
  chance_playing_this?: number;
  chance_playing_next?: number;
  selected_by_percent: number;
  goals_scored: number;
  assists: number;
  clean_sheets: number;
  ep_this: number;
  ep_next: number;
  news?: string;
}

export interface PlayerDetail extends Player {
  goals_conceded: number;
  yellow_cards: number;
  red_cards: number;
  saves: number;
  bonus: number;
  bps: number;
  influence: number;
  creativity: number;
  threat: number;
  ict_index: number;
  transfers_in_event: number;
  transfers_out_event: number;
  cost_change_event: number;
  cost_change_start: number;
  photo?: string;
}

export interface Team {
  id: number;
  fpl_id: number;
  name: string;
  short_name: string;
  strength: number;
  strength_overall_home: number;
  strength_overall_away: number;
  strength_attack_home: number;
  strength_attack_away: number;
  strength_defence_home: number;
  strength_defence_away: number;
  position?: number;
  played: number;
  won: number;
  drawn: number;
  lost: number;
  points: number;
}

export interface Fixture {
  id: number;
  fpl_id: number;
  gameweek: number;
  season: string;
  team_h_id: number;
  team_a_id: number;
  team_h_score?: number;
  team_a_score?: number;
  team_h_difficulty: number;
  team_a_difficulty: number;
  kickoff_time?: string;
  finished: boolean;
}

export interface MLPrediction {
  id: number;
  player_id: number;
  gameweek: number;
  season: string;
  predicted_points: number;
  confidence_lower?: number;
  confidence_upper?: number;
  start_probability: number;
  predicted_minutes: number;
  ceiling_points?: number;
  floor_points?: number;
  variance?: number;
  model_version: string;
}

export interface SquadPlayer {
  player_id: number;
  position: Position;
  price: number;
  predicted_points: number;
  gw_points?: number;
  is_starter: boolean;
  is_captain: boolean;
  is_vice_captain?: boolean;
  name?: string;
  team_id?: number;
}

export interface OptimizationRequest {
  gameweek: number;
  budget?: number;
  formation?: string;
  risk_tolerance?: number;
  excluded_players?: number[];
  min_team_players?: Record<number, number>;
  max_team_players?: Record<number, number>;
  captain_options?: number[];
}

export interface OptimizationResult {
  squad: SquadPlayer[];
  starting_xi: SquadPlayer[];
  bench: SquadPlayer[];
  formation: string;
  total_cost: number;
  predicted_points: number;
  captain_id: number;
  alternatives?: any[];
}

export interface TransferOption {
  player_out_id: number;
  player_in_id: number;
  cost: number;
  expected_gain: number;
  price_change: number;
  gameweek: number;
}

export interface GameweekPlan {
  gameweek: number;
  transfers: TransferOption[];
  expected_points: number;
  squad_value: number;
  free_transfers: number;
  total_transfer_cost: number;
  net_expected_gain: number;
}

export interface ChipStrategy {
  chip_type: 'wildcard' | 'bench_boost' | 'triple_captain' | 'free_hit';
  recommended_gameweek?: number;
  expected_benefit: number;
  confidence: number;
}

export interface TransferPlanRequest {
  current_squad: number[];
  planning_horizon?: number;
  max_transfers_per_week?: number;
  available_chips?: Record<string, boolean>;
}

export interface TransferPlanResult {
  gameweek_plans: GameweekPlan[];
  chip_recommendations: Record<string, ChipStrategy>;
  total_expected_gain: number;
  total_transfer_costs: number;
  planning_horizon: number;
}

export interface PlayerFilters {
  position?: Position;
  team_id?: number;
  min_price?: number;
  max_price?: number;
  min_points?: number;
  status?: string;
  available_only?: boolean;
}

export interface PlayersResponse {
  players: Player[];
  total: number;
  page: number;
  page_size: number;
}

export interface ApiError {
  detail: string;
  errors?: any[];
}

export interface TeamSummary {
  entry_id: number;
  gameweek: number;
  season: string;
  squad: {
    starting_xi: SquadPlayer[];
    bench: SquadPlayer[];
  };
  formation: string;
  captain_id?: number;
  vice_captain_id?: number;
  team_value: number;
  bank?: number;
  gw_points: number;
  total_points: number;
  overall_rank?: number;
}