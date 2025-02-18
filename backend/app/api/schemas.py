from pydantic import BaseModel, EmailStr, Field, validator, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class UserRegister(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8, max_length=100)
    fpl_team_id: Optional[int] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    email: str
    username: str
    fpl_team_id: Optional[int]
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    username: Optional[str] = None
    fpl_team_id: Optional[int] = None


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class PlayerStatus(str, Enum):
    AVAILABLE = "a"
    INJURED = "i"
    SUSPENDED = "s"
    UNAVAILABLE = "u"


class Position(int, Enum):
    GOALKEEPER = 1
    DEFENDER = 2
    MIDFIELDER = 3
    FORWARD = 4


class PlayerResponse(BaseModel):
    id: int
    fpl_id: int
    first_name: Optional[str]
    second_name: str
    web_name: str
    team_id: int
    position: int
    current_price: int  # In 0.1M units
    total_points: int
    form: float
    status: str
    chance_playing_this: Optional[int]
    chance_playing_next: Optional[int]
    selected_by_percent: float
    goals_scored: int
    assists: int
    clean_sheets: int
    ep_this: float
    ep_next: float
    news: Optional[str]

    class Config:
        from_attributes = True


class PlayerDetailResponse(PlayerResponse):
    goals_conceded: int
    yellow_cards: int
    red_cards: int
    saves: int
    bonus: int
    bps: int
    influence: float
    creativity: float
    threat: float
    ict_index: float
    transfers_in_event: int
    transfers_out_event: int
    cost_change_event: int
    cost_change_start: int
    photo: Optional[str]

    class Config:
        from_attributes = True


class TeamResponse(BaseModel):
    id: int
    fpl_id: int
    name: str
    short_name: str
    strength: int
    strength_overall_home: int
    strength_overall_away: int
    strength_attack_home: int
    strength_attack_away: int
    strength_defence_home: int
    strength_defence_away: int
    position: Optional[int]
    played: int
    won: int
    drawn: int
    lost: int
    points: int

    class Config:
        from_attributes = True


class FixtureResponse(BaseModel):
    id: int
    fpl_id: int
    gameweek: int
    season: str
    team_h_id: int
    team_a_id: int
    team_h_score: Optional[int]
    team_a_score: Optional[int]
    team_h_difficulty: int
    team_a_difficulty: int
    kickoff_time: Optional[datetime]
    finished: bool

    class Config:
        from_attributes = True


class PlayerStatisticResponse(BaseModel):
    id: int
    player_id: int
    gameweek: int
    season: str
    opponent_team_id: Optional[int]
    was_home: Optional[bool]
    minutes: int
    goals_scored: int
    assists: int
    clean_sheets: int
    goals_conceded: int
    yellow_cards: int
    red_cards: int
    saves: int
    bonus: int
    total_points: int
    expected_goals: float
    expected_assists: float

    class Config:
        from_attributes = True


class MLPredictionResponse(BaseModel):
    id: int
    player_id: int
    gameweek: int
    season: str
    predicted_points: float
    confidence_lower: Optional[float]
    confidence_upper: Optional[float]
    start_probability: float
    predicted_minutes: float
    ceiling_points: Optional[float]
    floor_points: Optional[float]
    variance: Optional[float]
    model_version: str

    model_config = ConfigDict(from_attributes=True, protected_namespaces=())


class OptimizationRequest(BaseModel):
    gameweek: int
    budget: float = 100.0  # Budget in millions
    formation: Optional[str] = None  # e.g., "3-4-3"
    risk_tolerance: float = Field(default=0.5, ge=0.0, le=1.0)
    excluded_players: Optional[List[int]] = []
    min_team_players: Optional[Dict[int, int]] = {}  # team_id: min_players
    max_team_players: Optional[Dict[int, int]] = {}  # team_id: max_players
    captain_options: Optional[List[int]] = []


class SquadPlayer(BaseModel):
    player_id: int
    position: int
    price: float
    predicted_points: float
    is_starter: bool
    is_captain: bool


class OptimizationResponse(BaseModel):
    squad: List[SquadPlayer]
    formation: str
    total_cost: float
    predicted_points: float
    captain_id: int
    bench: List[SquadPlayer]
    alternatives: Optional[List[Dict[str, Any]]] = []


class TransferPlanRequest(BaseModel):
    current_squad: List[int]  # List of player IDs
    planning_horizon: int = Field(default=5, ge=1, le=10)
    max_transfers_per_week: int = Field(default=1, ge=0, le=5)
    available_chips: Dict[str, bool] = {
        "wildcard": False,
        "free_hit": False,
        "bench_boost": False,
        "triple_captain": False,
    }


class TransferOption(BaseModel):
    player_out_id: int
    player_in_id: int
    cost: int  # Transfer cost in points
    expected_gain: float


class TransferPlanResponse(BaseModel):
    gameweek_plans: List[Dict[str, Any]]
    total_expected_gain: float
    chip_recommendations: Dict[str, Optional[int]]  # chip: recommended gameweek


class PlayerFilters(BaseModel):
    position: Optional[int] = None
    team_id: Optional[int] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    min_points: Optional[int] = None
    status: Optional[str] = "a"
    available_only: bool = True


class PlayersResponse(BaseModel):
    players: List[PlayerResponse]
    total: int
    page: int
    page_size: int


class FormationRequest(BaseModel):
    gameweek: int
    required_players: List[int]


class CaptainRequest(BaseModel):
    player_ids: List[int]
    gameweek: Optional[int] = None
