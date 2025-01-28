from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Dict, Any, List, Optional

from app.db.database import get_async_session
from app.db.models import User, Player, MLPrediction
from app.core.dependencies import get_current_user
from app.services.fpl_client import (
    FPLClient,
    get_current_gameweek,
    get_season_string,
)


router = APIRouter(prefix="/team", tags=["Team"])


@router.get("/summary")
async def team_summary(
    entry_id: Optional[int] = Query(
        None, description="FPL entry ID (defaults to user's fpl_team_id)"
    ),
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Return the user's team summary: squad, value, GW points, totals, rank.

    Uses FPL entry history and picks for most-relevant gameweek.
    """

    resolved_entry_id = int(entry_id or current_user.fpl_team_id or 0)
    if not resolved_entry_id:
        raise HTTPException(
            status_code=400,
            detail="No FPL team linked. Provide entry_id or set fpl_team_id on user.",
        )

    async with FPLClient() as fpl:
        # Bootstrap to figure out current gameweek
        bootstrap = await fpl.get_bootstrap_static()
        events = bootstrap.get("events", [])
        current_or_next = get_current_gameweek(events) or (
            events[0]["id"] if events else 1
        )

        # History: contains per-GW points, total_points, value and often overall_rank
        hist = await fpl.get_entry_history(resolved_entry_id)
        current_rows: List[Dict[str, Any]] = hist.get("current", [])
        last_played = 0
        for row in current_rows:
            try:
                last_played = max(last_played, int(row.get("event", 0)))
            except Exception:
                continue

        # Choose a GW to fetch picks for
        candidate_gws: List[int] = []
        for g in [last_played, current_or_next, max(1, (last_played or 1) - 1)]:
            if g and g not in candidate_gws:
                candidate_gws.append(int(g))

        picks: List[Dict[str, Any]] = []
        used_gw: Optional[int] = None
        for g in candidate_gws:
            try:
                data = await fpl.get_entry_picks(resolved_entry_id, g)
                p = data.get("picks", [])
                if p:
                    picks = p
                    used_gw = g
                    break
            except Exception:
                continue

        if not picks:
            raise HTTPException(status_code=404, detail="No picks found for this entry")

    # Map FPL element ids to internal player ids
    element_ids = [p.get("element") for p in picks]
    result = await db.execute(select(Player).where(Player.fpl_id.in_(element_ids)))
    players = result.scalars().all()
    fpl_to_internal = {p.fpl_id: p for p in players}

    # Predictions for the used GW (if available)
    season = get_season_string()
    preds_q = select(MLPrediction).where(
        (MLPrediction.season == season) & (MLPrediction.gameweek == used_gw)
    )
    preds_res = await db.execute(preds_q)
    preds = {r.player_id: r for r in preds_res.scalars().all()}

    # Live/factual GW stats for each element (minutes, total_points)
    gw_live_stats: Dict[int, Dict[str, Any]] = {}
    try:
        async with FPLClient() as fpl:
            live = await fpl.get_gameweek_live(int(used_gw or 0))
            # live['elements'] is a list of { id: element_id, stats: { minutes, total_points, ... } }
            for el in live.get("elements", []):
                el_id = int(el.get("id")) if el.get("id") is not None else None
                stats = el.get("stats", {})
                if el_id is not None:
                    gw_live_stats[el_id] = stats
    except Exception:
        gw_live_stats = {}

    starting: List[Dict[str, Any]] = []
    bench: List[Dict[str, Any]] = []
    captain_id: Optional[int] = None
    vice_id: Optional[int] = None

    for p in picks:
        element = p.get("element")
        internal = fpl_to_internal.get(element)
        if not internal:
            continue
        is_captain = bool(p.get("is_captain"))
        is_vice = bool(p.get("is_vice_captain"))
        position = int(p.get("position") or 0)

        pred = preds.get(internal.id)
        predicted_points = (
            float(pred.predicted_points)
            if pred
            else float(internal.ep_next or internal.ep_this or internal.form or 2.0)
        )

        # Factual GW points: only if minutes > 0, else None
        el_stats = gw_live_stats.get(int(element))
        gw_points = None
        if el_stats is not None:
            try:
                minutes_played = int(el_stats.get("minutes", 0))
                if minutes_played > 0:
                    gw_points = int(el_stats.get("total_points") or 0)
            except Exception:
                gw_points = None
        item = {
            "player_id": internal.id,
            "name": f"{internal.first_name or ''} {internal.second_name}".strip(),
            "position": internal.position,
            "team_id": internal.team_id,
            "price": internal.current_price / 10.0,
            "predicted_points": round(predicted_points, 1),
            "gw_points": gw_points,
            "is_starter": position and position <= 11,
            "is_captain": is_captain,
            "is_vice_captain": is_vice,
        }

        if position and position <= 11:
            starting.append(item)
        else:
            bench.append(item)

        if is_captain:
            captain_id = internal.id
        if is_vice:
            vice_id = internal.id

    if not starting:
        raise HTTPException(
            status_code=400, detail="Could not map FPL picks to internal players"
        )

    # Formation, value, points, rank from history rows
    formation_counts = {1: 0, 2: 0, 3: 0, 4: 0}
    for s in starting:
        formation_counts[s["position"]] += 1
    formation = f"{formation_counts[2]}-{formation_counts[3]}-{formation_counts[4]}"

    team_value: Optional[float] = None
    bank: Optional[float] = None
    gw_points: int = 0
    total_points: int = 0
    overall_rank: Optional[int] = None

    # Find the row for used_gw and the latest row overall
    row_used = None
    latest_row = None
    latest_event = -1
    for row in current_rows:
        try:
            ev = int(row.get("event", 0))
        except Exception:
            continue
        if used_gw and ev == used_gw:
            row_used = row
        if ev > latest_event:
            latest_event = ev
            latest_row = row

    if row_used:
        gw_points = int(row_used.get("points") or 0)
        # Value is in 0.1M units
        if row_used.get("value") is not None:
            try:
                team_value = float(row_used.get("value", 0)) / 10.0
            except Exception:
                team_value = None
    if latest_row:
        total_points = int(latest_row.get("total_points") or 0)
        if latest_row.get("overall_rank") is not None:
            try:
                overall_rank = int(latest_row.get("overall_rank"))
            except Exception:
                overall_rank = None

    # Fallback for value if not present in history
    if team_value is None:
        team_value = round(
            sum(s["price"] for s in starting) + sum(b["price"] for b in bench), 1
        )

    return {
        "entry_id": resolved_entry_id,
        "gameweek": used_gw,
        "season": season,
        "squad": {"starting_xi": starting, "bench": bench},
        "formation": formation,
        "captain_id": captain_id,
        "vice_captain_id": vice_id,
        "team_value": team_value,
        "bank": bank,
        "gw_points": gw_points,
        "total_points": total_points,
        "overall_rank": overall_rank,
    }
