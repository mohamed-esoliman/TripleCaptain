from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    JSON,
    Text,
    UniqueConstraint,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    fpl_team_id = Column(Integer, nullable=True)  # Optional FPL team linking
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    squads = relationship("UserSquad", back_populates="user")


class Team(Base):
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True, index=True)
    fpl_id = Column(Integer, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    short_name = Column(String, nullable=False)
    code = Column(Integer)
    strength = Column(Integer)
    strength_overall_home = Column(Integer)
    strength_overall_away = Column(Integer)
    strength_attack_home = Column(Integer)
    strength_attack_away = Column(Integer)
    strength_defence_home = Column(Integer)
    strength_defence_away = Column(Integer)
    position = Column(Integer)  # League position
    played = Column(Integer, default=0)
    won = Column(Integer, default=0)
    drawn = Column(Integer, default=0)
    lost = Column(Integer, default=0)
    points = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    players = relationship("Player", back_populates="team")
    home_fixtures = relationship(
        "Fixture", foreign_keys="Fixture.team_h_id", back_populates="home_team"
    )
    away_fixtures = relationship(
        "Fixture", foreign_keys="Fixture.team_a_id", back_populates="away_team"
    )


class Player(Base):
    __tablename__ = "players"

    id = Column(Integer, primary_key=True, index=True)
    fpl_id = Column(Integer, unique=True, index=True, nullable=False)
    first_name = Column(String)
    second_name = Column(String, nullable=False)
    web_name = Column(String, nullable=False)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    position = Column(Integer, nullable=False)  # 1=GKP, 2=DEF, 3=MID, 4=FWD
    current_price = Column(Integer, nullable=False)  # Price in 0.1M units
    total_points = Column(Integer, default=0)
    form = Column(Float, default=0.0)
    status = Column(
        String, default="a"
    )  # a=available, i=injured, s=suspended, u=unavailable
    chance_playing_this = Column(Integer)
    chance_playing_next = Column(Integer)
    selected_by_percent = Column(Float, default=0.0)
    transfers_in_event = Column(Integer, default=0)
    transfers_out_event = Column(Integer, default=0)
    goals_scored = Column(Integer, default=0)
    assists = Column(Integer, default=0)
    clean_sheets = Column(Integer, default=0)
    goals_conceded = Column(Integer, default=0)
    yellow_cards = Column(Integer, default=0)
    red_cards = Column(Integer, default=0)
    saves = Column(Integer, default=0)
    bonus = Column(Integer, default=0)
    bps = Column(Integer, default=0)  # Bonus Points System
    influence = Column(Float, default=0.0)
    creativity = Column(Float, default=0.0)
    threat = Column(Float, default=0.0)
    ict_index = Column(Float, default=0.0)
    ep_this = Column(Float, default=0.0)  # Expected points this GW
    ep_next = Column(Float, default=0.0)  # Expected points next GW
    cost_change_event = Column(Integer, default=0)
    cost_change_start = Column(Integer, default=0)
    news = Column(Text)
    news_added = Column(DateTime(timezone=True))
    photo = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    team = relationship("Team", back_populates="players")
    statistics = relationship("PlayerStatistic", back_populates="player")
    predictions = relationship("MLPrediction", back_populates="player")

    # Indexes
    __table_args__ = (
        Index("idx_player_position", "position"),
        Index("idx_player_team", "team_id"),
        Index("idx_player_price", "current_price"),
        Index("idx_player_status", "status"),
    )


class PlayerStatistic(Base):
    __tablename__ = "player_statistics"

    id = Column(Integer, primary_key=True, index=True)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    gameweek = Column(Integer, nullable=False)
    season = Column(String, nullable=False)
    fixture_id = Column(Integer, ForeignKey("fixtures.id"))
    opponent_team_id = Column(Integer, ForeignKey("teams.id"))
    was_home = Column(Boolean)
    minutes = Column(Integer, default=0)
    goals_scored = Column(Integer, default=0)
    assists = Column(Integer, default=0)
    clean_sheets = Column(Integer, default=0)
    goals_conceded = Column(Integer, default=0)
    own_goals = Column(Integer, default=0)
    penalties_saved = Column(Integer, default=0)
    penalties_missed = Column(Integer, default=0)
    yellow_cards = Column(Integer, default=0)
    red_cards = Column(Integer, default=0)
    saves = Column(Integer, default=0)
    bonus = Column(Integer, default=0)
    bps = Column(Integer, default=0)
    influence = Column(Float, default=0.0)
    creativity = Column(Float, default=0.0)
    threat = Column(Float, default=0.0)
    ict_index = Column(Float, default=0.0)
    total_points = Column(Integer, default=0)
    starts = Column(Integer, default=0)
    expected_goals = Column(Float, default=0.0)
    expected_assists = Column(Float, default=0.0)
    expected_goal_involvements = Column(Float, default=0.0)
    expected_goals_conceded = Column(Float, default=0.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    player = relationship("Player", back_populates="statistics")
    fixture = relationship("Fixture", back_populates="player_stats")
    opponent_team = relationship("Team", foreign_keys=[opponent_team_id])

    # Indexes
    __table_args__ = (
        Index("idx_player_gameweek", "player_id", "gameweek"),
        Index("idx_gameweek_season", "gameweek", "season"),
        Index("idx_season", "season"),
        UniqueConstraint("player_id", "gameweek", "season", name="uq_player_gw_season"),
    )


class Fixture(Base):
    __tablename__ = "fixtures"

    id = Column(Integer, primary_key=True, index=True)
    fpl_id = Column(Integer, unique=True, index=True, nullable=False)
    gameweek = Column(Integer, nullable=False)
    season = Column(String, nullable=False)
    team_h_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    team_a_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    team_h_score = Column(Integer)
    team_a_score = Column(Integer)
    team_h_difficulty = Column(Integer)  # 1-5 difficulty rating
    team_a_difficulty = Column(Integer)
    kickoff_time = Column(DateTime(timezone=True))
    finished = Column(Boolean, default=False)
    finished_provisional = Column(Boolean, default=False)
    started = Column(Boolean, default=False)
    minutes = Column(Integer, default=0)
    provisional_start_time = Column(Boolean, default=False)
    pulse_id = Column(Integer)
    stats = Column(JSON)  # Fixture statistics in JSON format
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    home_team = relationship(
        "Team", foreign_keys=[team_h_id], back_populates="home_fixtures"
    )
    away_team = relationship(
        "Team", foreign_keys=[team_a_id], back_populates="away_fixtures"
    )
    player_stats = relationship("PlayerStatistic", back_populates="fixture")

    # Indexes
    __table_args__ = (
        Index("idx_fixture_gameweek", "gameweek"),
        Index("idx_fixture_teams", "team_h_id", "team_a_id"),
        Index("idx_fixture_kickoff", "kickoff_time"),
    )


class MLPrediction(Base):
    __tablename__ = "ml_predictions"

    id = Column(Integer, primary_key=True, index=True)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    gameweek = Column(Integer, nullable=False)
    season = Column(String, nullable=False)
    predicted_points = Column(Float, nullable=False)
    confidence_lower = Column(Float)  # Lower confidence bound
    confidence_upper = Column(Float)  # Upper confidence bound
    start_probability = Column(Float, default=0.5)  # Probability of starting (>60 mins)
    predicted_minutes = Column(Float, default=0.0)
    ceiling_points = Column(Float)  # 90th percentile scenario
    floor_points = Column(Float)  # 10th percentile scenario
    variance = Column(Float)  # Risk measure
    model_version = Column(String, nullable=False)
    features = Column(JSON)  # Feature values used for prediction
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    player = relationship("Player", back_populates="predictions")

    # Indexes
    __table_args__ = (
        Index("idx_prediction_gameweek", "gameweek", "season"),
        Index("idx_prediction_player_gw", "player_id", "gameweek"),
        Index("idx_prediction_points", "predicted_points"),
    )


class UserSquad(Base):
    __tablename__ = "user_squads"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    gameweek = Column(Integer, nullable=False)
    season = Column(String, nullable=False)
    squad_data = Column(JSON, nullable=False)  # 15 player squad with formation
    total_cost = Column(Float, nullable=False)
    predicted_points = Column(Float)
    formation = Column(String)  # e.g., "3-4-3"
    captain_id = Column(Integer, ForeignKey("players.id"))
    vice_captain_id = Column(Integer, ForeignKey("players.id"))
    is_current = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="squads")
    captain = relationship("Player", foreign_keys=[captain_id])
    vice_captain = relationship("Player", foreign_keys=[vice_captain_id])

    # Indexes
    __table_args__ = (
        Index("idx_user_gameweek", "user_id", "gameweek"),
        Index("idx_user_current", "user_id", "is_current"),
    )


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    token = Column(String, unique=True, index=True, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    is_revoked = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user = relationship("User")

    # Indexes
    __table_args__ = (
        Index("idx_refresh_token", "token"),
        Index("idx_refresh_user_id", "user_id"),
    )


class OptimizationCache(Base):
    __tablename__ = "optimization_cache"

    id = Column(Integer, primary_key=True, index=True)
    cache_key = Column(String, unique=True, index=True, nullable=False)
    gameweek = Column(Integer, nullable=False)
    season = Column(String, nullable=False)
    constraints = Column(JSON, nullable=False)  # Optimization constraints
    result = Column(JSON, nullable=False)  # Optimization result
    predicted_points = Column(Float)
    formation = Column(String)
    total_cost = Column(Float)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Indexes
    __table_args__ = (
        Index("idx_cache_gameweek", "gameweek", "season"),
        Index("idx_cache_expires", "expires_at"),
    )


class DataUpdateLog(Base):
    __tablename__ = "data_update_logs"

    id = Column(Integer, primary_key=True, index=True)
    update_type = Column(
        String, nullable=False
    )  # 'players', 'fixtures', 'stats', 'predictions'
    gameweek = Column(Integer)
    season = Column(String)
    status = Column(String, nullable=False)  # 'success', 'error', 'partial'
    records_processed = Column(Integer, default=0)
    error_message = Column(Text)
    duration_seconds = Column(Float)
    started_at = Column(DateTime(timezone=True), nullable=False)
    completed_at = Column(DateTime(timezone=True))

    # Indexes
    __table_args__ = (
        Index("idx_update_type_status", "update_type", "status"),
        Index("idx_update_started", "started_at"),
    )
