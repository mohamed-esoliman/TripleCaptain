from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import List

from app.db.database import get_async_session
from app.db.models import Team, Player
from app.core.dependencies import get_current_user_optional
from app.api.schemas import TeamResponse

router = APIRouter(prefix="/teams", tags=["Teams"])


@router.get("", response_model=List[TeamResponse])
async def get_teams(
    db: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user_optional)
):
    """Get all Premier League teams."""
    
    result = await db.execute(
        select(Team).order_by(Team.position.nulls_last(), Team.name)
    )
    teams = result.scalars().all()
    
    return [TeamResponse.from_orm(team) for team in teams]


@router.get("/{team_id}", response_model=TeamResponse)
async def get_team(
    team_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user_optional)
):
    """Get team details."""
    
    result = await db.execute(select(Team).where(Team.id == team_id))
    team = result.scalar_one_or_none()
    
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    
    return TeamResponse.from_orm(team)


@router.get("/{team_id}/players")
async def get_team_players(
    team_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user_optional)
):
    """Get all players for a team."""
    
    # Check if team exists
    team_result = await db.execute(select(Team).where(Team.id == team_id))
    if not team_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Team not found")
    
    # Get team players
    players_result = await db.execute(
        select(Player).where(Player.team_id == team_id).order_by(
            Player.position, Player.total_points.desc()
        )
    )
    players = players_result.scalars().all()
    
    return [
        {
            "id": player.id,
            "fpl_id": player.fpl_id,
            "name": f"{player.first_name or ''} {player.second_name}".strip(),
            "web_name": player.web_name,
            "position": player.position,
            "current_price": player.current_price / 10.0,
            "total_points": player.total_points,
            "form": player.form,
            "status": player.status,
            "selected_by_percent": player.selected_by_percent
        }
        for player in players
    ]


@router.get("/{team_id}/fixtures")
async def get_team_fixtures(
    team_id: int,
    upcoming_only: bool = True,
    limit: int = 10,
    db: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user_optional)
):
    """Get fixtures for a team."""
    
    # Check if team exists
    team_result = await db.execute(select(Team).where(Team.id == team_id))
    if not team_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Team not found")
    
    from app.db.models import Fixture
    from app.services.fpl_client import get_season_string
    
    season = get_season_string()
    
    # Build fixtures query
    query = select(Fixture).where(
        ((Fixture.team_h_id == team_id) | (Fixture.team_a_id == team_id)),
        Fixture.season == season
    )
    
    if upcoming_only:
        query = query.where(Fixture.finished == False)
        query = query.order_by(Fixture.kickoff_time)
    else:
        query = query.order_by(Fixture.gameweek.desc())
    
    query = query.limit(limit)
    
    result = await db.execute(query)
    fixtures = result.scalars().all()
    
    return [
        {
            "gameweek": fixture.gameweek,
            "opponent_team_id": fixture.team_a_id if fixture.team_h_id == team_id else fixture.team_h_id,
            "is_home": fixture.team_h_id == team_id,
            "difficulty": fixture.team_h_difficulty if fixture.team_h_id == team_id else fixture.team_a_difficulty,
            "kickoff_time": fixture.kickoff_time.isoformat() if fixture.kickoff_time else None,
            "finished": fixture.finished,
            "team_score": fixture.team_h_score if fixture.team_h_id == team_id else fixture.team_a_score,
            "opponent_score": fixture.team_a_score if fixture.team_h_id == team_id else fixture.team_h_score
        }
        for fixture in fixtures
    ]


@router.get("/{team_id}/strength")
async def get_team_strength_analysis(
    team_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user_optional)
):
    """Get detailed team strength analysis."""
    
    result = await db.execute(select(Team).where(Team.id == team_id))
    team = result.scalar_one_or_none()
    
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    
    # Calculate relative strengths (compared to average of 1000)
    avg_strength = 1000
    
    return {
        "team_id": team.id,
        "team_name": team.name,
        "overall_strength": {
            "home": team.strength_overall_home,
            "away": team.strength_overall_away,
            "home_rating": "Strong" if team.strength_overall_home > 1050 else "Average" if team.strength_overall_home > 950 else "Weak",
            "away_rating": "Strong" if team.strength_overall_away > 1050 else "Average" if team.strength_overall_away > 950 else "Weak"
        },
        "attack_strength": {
            "home": team.strength_attack_home,
            "away": team.strength_attack_away,
            "home_vs_average": round((team.strength_attack_home - avg_strength) / avg_strength * 100, 1),
            "away_vs_average": round((team.strength_attack_away - avg_strength) / avg_strength * 100, 1)
        },
        "defence_strength": {
            "home": team.strength_defence_home,
            "away": team.strength_defence_away,
            "home_vs_average": round((team.strength_defence_home - avg_strength) / avg_strength * 100, 1),
            "away_vs_average": round((team.strength_defence_away - avg_strength) / avg_strength * 100, 1)
        },
        "league_position": team.position,
        "form_guide": {
            "played": team.played,
            "won": team.won,
            "drawn": team.drawn,
            "lost": team.lost,
            "points": team.points,
            "win_rate": round(team.won / max(team.played, 1) * 100, 1)
        }
    }