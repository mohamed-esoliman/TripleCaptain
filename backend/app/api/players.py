from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from typing import List, Optional

from app.db.database import get_async_session
from app.db.models import Player, Team, PlayerStatistic
from app.core.dependencies import get_current_user_optional
from app.api.schemas import (
    PlayerResponse, PlayerDetailResponse, PlayersResponse, 
    PlayerFilters, Position
)
from app.core.cache import cache_service, CacheKeys

router = APIRouter(prefix="/players", tags=["Players"])


@router.get("", response_model=PlayersResponse)
async def get_players(
    position: Optional[int] = Query(None, description="Position filter (1=GKP, 2=DEF, 3=MID, 4=FWD)"),
    team: Optional[int] = Query(None, description="Team ID filter"),
    min_price: Optional[float] = Query(None, description="Minimum price in millions"),
    max_price: Optional[float] = Query(None, description="Maximum price in millions"),
    min_points: Optional[int] = Query(None, description="Minimum total points"),
    status: Optional[str] = Query("a", description="Player status (a=available, i=injured, s=suspended)"),
    available_only: bool = Query(True, description="Only show available players"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    db: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user_optional)
):
    """Get players with filtering and pagination."""
    
    # Create cache key from filters
    import hashlib
    filters_str = f"{position}-{team}-{min_price}-{max_price}-{min_points}-{status}-{available_only}-{page}-{page_size}"
    filters_hash = hashlib.md5(filters_str.encode()).hexdigest()
    cache_key = CacheKeys.players_data(filters_hash)
    
    # Try to get from cache
    cached_result = await cache_service.get(cache_key)
    if cached_result:
        return PlayersResponse(**cached_result)
    
    # Build query
    query = select(Player).options(selectinload(Player.team))
    
    # Apply filters
    if position:
        query = query.where(Player.position == position)
    
    if team:
        query = query.where(Player.team_id == team)
    
    if min_price:
        query = query.where(Player.current_price >= int(min_price * 10))  # Convert to 0.1M units
    
    if max_price:
        query = query.where(Player.current_price <= int(max_price * 10))
    
    if min_points:
        query = query.where(Player.total_points >= min_points)
    
    if status and available_only:
        query = query.where(Player.status == status)
    elif available_only:
        query = query.where(Player.status == 'a')
    
    # Get total count
    count_query = select(func.count(Player.id))
    if position:
        count_query = count_query.where(Player.position == position)
    if team:
        count_query = count_query.where(Player.team_id == team)
    if min_price:
        count_query = count_query.where(Player.current_price >= int(min_price * 10))
    if max_price:
        count_query = count_query.where(Player.current_price <= int(max_price * 10))
    if min_points:
        count_query = count_query.where(Player.total_points >= min_points)
    if status and available_only:
        count_query = count_query.where(Player.status == status)
    elif available_only:
        count_query = count_query.where(Player.status == 'a')
    
    count_result = await db.execute(count_query)
    total = count_result.scalar()
    
    # Apply pagination
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)
    
    # Order by total points descending
    query = query.order_by(Player.total_points.desc())
    
    result = await db.execute(query)
    players = result.scalars().all()
    
    response = PlayersResponse(
        players=[PlayerResponse.from_orm(player) for player in players],
        total=total,
        page=page,
        page_size=page_size
    )
    
    # Cache the result for 5 minutes
    await cache_service.set(cache_key, response.dict(), expire=300)
    
    return response


@router.get("/{player_id}", response_model=PlayerDetailResponse)
async def get_player(
    player_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user_optional)
):
    """Get detailed player information."""
    
    result = await db.execute(
        select(Player)
        .options(selectinload(Player.team))
        .where(Player.id == player_id)
    )
    player = result.scalar_one_or_none()
    
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
    
    return PlayerDetailResponse.from_orm(player)


@router.get("/{player_id}/history")
async def get_player_history(
    player_id: int,
    season: Optional[str] = Query(None, description="Season filter (e.g., '2024-25')"),
    limit: int = Query(10, ge=1, le=50, description="Number of recent games"),
    db: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user_optional)
):
    """Get player's historical performance."""
    
    # Check if player exists
    player_result = await db.execute(select(Player).where(Player.id == player_id))
    if not player_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Player not found")
    
    # Build history query
    query = select(PlayerStatistic).where(PlayerStatistic.player_id == player_id)
    
    if season:
        query = query.where(PlayerStatistic.season == season)
    
    query = query.order_by(PlayerStatistic.gameweek.desc()).limit(limit)
    
    result = await db.execute(query)
    history = result.scalars().all()
    
    return [
        {
            "gameweek": stat.gameweek,
            "season": stat.season,
            "minutes": stat.minutes,
            "total_points": stat.total_points,
            "goals_scored": stat.goals_scored,
            "assists": stat.assists,
            "clean_sheets": stat.clean_sheets,
            "goals_conceded": stat.goals_conceded,
            "yellow_cards": stat.yellow_cards,
            "red_cards": stat.red_cards,
            "saves": stat.saves,
            "bonus": stat.bonus,
            "bps": stat.bps,
            "influence": float(stat.influence),
            "creativity": float(stat.creativity),
            "threat": float(stat.threat),
            "ict_index": float(stat.ict_index),
            "expected_goals": float(stat.expected_goals),
            "expected_assists": float(stat.expected_assists),
            "was_home": stat.was_home,
            "starts": stat.starts,
            "opponent_team_id": stat.opponent_team_id
        }
        for stat in history
    ]


@router.get("/{player_id}/fixtures")
async def get_player_fixtures(
    player_id: int,
    limit: int = Query(5, ge=1, le=10, description="Number of upcoming fixtures"),
    db: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user_optional)
):
    """Get player's upcoming fixtures with difficulty ratings."""
    
    # Check if player exists and get team
    result = await db.execute(
        select(Player)
        .options(selectinload(Player.team))
        .where(Player.id == player_id)
    )
    player = result.scalar_one_or_none()
    
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
    
    # Get upcoming fixtures for player's team
    from app.db.models import Fixture
    from app.services.fpl_client import get_season_string
    
    season = get_season_string()
    
    fixtures_query = select(Fixture).where(
        ((Fixture.team_h_id == player.team_id) | (Fixture.team_a_id == player.team_id)),
        Fixture.season == season,
        Fixture.finished == False
    ).order_by(Fixture.kickoff_time).limit(limit)
    
    fixtures_result = await db.execute(fixtures_query)
    fixtures = fixtures_result.scalars().all()
    
    return [
        {
            "gameweek": fixture.gameweek,
            "opponent_team_id": fixture.team_a_id if fixture.team_h_id == player.team_id else fixture.team_h_id,
            "is_home": fixture.team_h_id == player.team_id,
            "difficulty": fixture.team_h_difficulty if fixture.team_h_id == player.team_id else fixture.team_a_difficulty,
            "kickoff_time": fixture.kickoff_time.isoformat() if fixture.kickoff_time else None
        }
        for fixture in fixtures
    ]