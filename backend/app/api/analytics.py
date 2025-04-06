from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Dict, Any

from app.db.database import get_async_session
from app.core.dependencies import get_current_user
from app.db.models import User, PlayerStatistic, Player, Team, Fixture, MLPrediction
from app.services.fpl_client import get_season_string


router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/performance")
async def user_performance(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Return placeholder user performance analytics.
    In a full implementation, this would use linked FPL entry history.
    """

    season = get_season_string()

    # Basic system-wide stats as a proxy for now
    total_players = (await db.execute(select(func.count(Player.id)))).scalar() or 0
    total_predictions = (
        await db.execute(select(func.count(MLPrediction.id)))
    ).scalar() or 0

    return {
        "user_id": current_user.id,
        "season": season,
        "summary": {
            "tracked_players": total_players,
            "available_predictions": total_predictions,
        },
    }


@router.get("/trends")
async def market_trends(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Return simple market trend signals derived from Player data."""

    # Top transfers in/out this event
    top_in = (
        (
            await db.execute(
                select(Player).order_by(Player.transfers_in_event.desc()).limit(10)
            )
        )
        .scalars()
        .all()
    )
    top_out = (
        (
            await db.execute(
                select(Player).order_by(Player.transfers_out_event.desc()).limit(10)
            )
        )
        .scalars()
        .all()
    )

    def to_summary(p: Player):
        return {
            "player_id": p.id,
            "name": f"{p.first_name or ''} {p.second_name}".strip(),
            "web_name": p.web_name,
            "team_id": p.team_id,
            "position": p.position,
            "price": p.current_price / 10.0,
            "form": p.form,
            "selected_by_percent": p.selected_by_percent,
        }

    return {
        "top_transfers_in": [to_summary(p) for p in top_in],
        "top_transfers_out": [to_summary(p) for p in top_out],
    }


@router.get("/fixtures")
async def fixture_difficulty(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Provide fixture difficulty snapshot for upcoming weeks."""

    season = get_season_string()

    # Next 5 gameweeks difficulty per team
    fixtures = (
        (
            await db.execute(
                select(Fixture).where(
                    (Fixture.season == season) & (Fixture.finished == False)
                )
            )
        )
        .scalars()
        .all()
    )

    by_team: Dict[int, Any] = {}
    for fx in fixtures:
        for team_id, is_home, difficulty in [
            (fx.team_h_id, True, fx.team_h_difficulty),
            (fx.team_a_id, False, fx.team_a_difficulty),
        ]:
            by_team.setdefault(team_id, []).append(
                {
                    "gameweek": fx.gameweek,
                    "is_home": is_home,
                    "difficulty": difficulty,
                    "opponent": fx.team_a_id if is_home else fx.team_h_id,
                }
            )

    summary = [
        {
            "team_id": team_id,
            "avg_next5": round(
                sum(x["difficulty"] for x in entries[:5]) / max(1, len(entries[:5])), 2
            ),
            "entries": entries[:5],
        }
        for team_id, entries in by_team.items()
    ]
    summary.sort(key=lambda x: x["avg_next5"])  # easier first

    return {"fixture_difficulty": summary}
