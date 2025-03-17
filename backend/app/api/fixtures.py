from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional

from app.db.database import get_async_session
from app.db.models import Fixture
from app.core.dependencies import get_current_user_optional
from app.api.schemas import FixtureResponse
from app.services.fpl_client import get_season_string


router = APIRouter(prefix="/fixtures", tags=["Fixtures"])


@router.get("", response_model=List[FixtureResponse])
async def list_fixtures(
    gameweek: Optional[int] = Query(None, description="Filter by gameweek"),
    team_id: Optional[int] = Query(None, description="Filter by team id"),
    future_only: bool = Query(False, description="Only upcoming fixtures"),
    limit: int = Query(200, ge=1, le=1000),
    db: AsyncSession = Depends(get_async_session),
    current_user=Depends(get_current_user_optional),
):
    """List fixtures with optional filtering."""

    season = get_season_string()

    query = select(Fixture).where(Fixture.season == season)

    if gameweek is not None:
        query = query.where(Fixture.gameweek == gameweek)

    if team_id is not None:
        query = query.where(
            (Fixture.team_h_id == team_id) | (Fixture.team_a_id == team_id)
        )

    if future_only:
        query = query.where(Fixture.finished == False)  # noqa: E712
        query = query.order_by(Fixture.kickoff_time)
    else:
        query = query.order_by(Fixture.gameweek, Fixture.kickoff_time)

    query = query.limit(limit)

    result = await db.execute(query)
    fixtures = result.scalars().all()
    return [FixtureResponse.from_orm(fx) for fx in fixtures]


@router.get("/{fixture_id}", response_model=FixtureResponse)
async def get_fixture(
    fixture_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user=Depends(get_current_user_optional),
):
    """Get a single fixture by id."""

    result = await db.execute(select(Fixture).where(Fixture.id == fixture_id))
    fixture = result.scalar_one_or_none()
    if not fixture:
        raise HTTPException(status_code=404, detail="Fixture not found")
    return FixtureResponse.from_orm(fixture)
