from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Dict, Any, List

from app.db.database import get_async_session
from app.db.models import User, UserSquad, Player
from app.core.dependencies import get_current_user
from app.services.fpl_client import FPLClient, get_season_string, get_current_gameweek
from app.db.models import MLPrediction
from sqlalchemy import func


router = APIRouter(prefix="/squads", tags=["Squads"])


@router.get("/current")
async def get_current_squad(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Return the user's current saved squad (if any)."""

    result = await db.execute(
        select(UserSquad)
        .where(UserSquad.user_id == current_user.id)
        .where(UserSquad.is_current == True)  # noqa: E712
        .order_by(UserSquad.updated_at.desc())
    )
    squad = result.scalar_one_or_none()

    if not squad:
        return {"message": "No current squad saved", "squad": None}

    return {
        "id": squad.id,
        "gameweek": squad.gameweek,
        "season": squad.season,
        "squad": squad.squad_data,
        "formation": squad.formation,
        "captain_id": squad.captain_id,
        "vice_captain_id": squad.vice_captain_id,
        "total_cost": squad.total_cost,
        "predicted_points": squad.predicted_points,
        "updated_at": squad.updated_at,
    }


@router.post("/save")
async def save_squad(
    payload: Dict[str, Any],
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Save a squad snapshot for the user and mark it current."""

    required_fields = ["gameweek", "season", "squad", "total_cost"]
    for field in required_fields:
        if field not in payload:
            raise HTTPException(status_code=400, detail=f"Missing field: {field}")

    # Mark any existing current squad as not current
    result = await db.execute(
        select(UserSquad).where(
            (UserSquad.user_id == current_user.id)
            & (UserSquad.is_current == True)  # noqa: E712
        )
    )
    current = result.scalar_one_or_none()
    if current:
        current.is_current = False

    squad = UserSquad(
        user_id=current_user.id,
        gameweek=int(payload["gameweek"]),
        season=str(payload["season"]),
        squad_data=payload["squad"],
        total_cost=float(payload["total_cost"]),
        predicted_points=float(payload.get("predicted_points", 0.0)),
        formation=str(payload.get("formation", "")),
        captain_id=payload.get("captain_id"),
        vice_captain_id=payload.get("vice_captain_id"),
        is_current=True,
    )

    db.add(squad)
    await db.commit()
    await db.refresh(squad)

    return {"message": "Squad saved", "id": squad.id}


@router.post("/import-from-fpl")
async def import_from_fpl(
    payload: Dict[str, Any],
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Import squad from FPL by entry_id, save as current, and return snapshot."""

    entry_id = int(payload.get("entry_id") or current_user.fpl_team_id or 0)
    if not entry_id:
        raise HTTPException(
            status_code=400, detail="Missing entry_id and no fpl_team_id on user"
        )

    # Determine current or next gameweek from FPL bootstrap and fetch picks
    try:
        async with FPLClient() as fpl:
            bootstrap = await fpl.get_bootstrap_static()
            events = bootstrap.get("events", [])
            # Prefer last finished GW, then current/next
            last_finished = 0
            for e in events:
                if e.get("finished"):
                    last_finished = max(last_finished, int(e.get("id", 0)))
            current_or_next = get_current_gameweek(events) or (
                events[0]["id"] if events else 1
            )

            # Also look at entry history to find last event they played
            hist = await fpl.get_entry_history(entry_id)
            current_list = hist.get("current", [])
            last_played = 0
            for row in current_list:
                last_played = max(last_played, int(row.get("event", 0)))

            # Build candidate GW list (unique, positive)
            candidates = []
            for g in [
                last_played,
                current_or_next,
                last_finished,
                max(1, last_finished - 1),
            ]:
                if g and g not in candidates:
                    candidates.append(int(g))

            picks = []
            used_gw = None
            for g in candidates[:5]:
                try:
                    data = await fpl.get_entry_picks(entry_id, g)
                    p = data.get("picks", [])
                    if p:
                        picks = p
                        used_gw = g
                        break
                except Exception:
                    continue

            if not picks:
                raise HTTPException(
                    status_code=404,
                    detail="No picks found for this entry (tried recent gameweeks)",
                )
    except HTTPException:
        raise
    except Exception as e:
        # Surface a clean error instead of raw exception to avoid broken responses (helps CORS)
        msg = str(e)
        status_code = 404 if "Not found" in msg or "404" in msg else 502
        raise HTTPException(status_code=status_code, detail=f"FPL fetch failed: {msg}")

    # Map FPL element ids to our internal player ids
    element_ids = [p.get("element") for p in picks]
    result = await db.execute(select(Player).where(Player.fpl_id.in_(element_ids)))
    players = result.scalars().all()
    fpl_to_internal = {p.fpl_id: p for p in players}

    # Build squad arrays
    starting = []
    bench = []
    captain_id = None
    vice_id = None

    # Try to enrich with predicted points if available
    season = get_season_string()
    preds_q = select(MLPrediction).where(
        (MLPrediction.season == season) & (MLPrediction.gameweek == used_gw)
    )
    preds_res = await db.execute(preds_q)
    preds = {r.player_id: r for r in preds_res.scalars().all()}

    for p in picks:
        element = p.get("element")
        internal = fpl_to_internal.get(element)
        if not internal:
            # Skip unknown players
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
        item = {
            "player_id": internal.id,
            "name": f"{internal.first_name or ''} {internal.second_name}".strip(),
            "position": internal.position,
            "team_id": internal.team_id,
            "price": internal.current_price / 10.0,
            "predicted_points": round(predicted_points, 1),
            "is_starter": position and position <= 11,
            "is_captain": is_captain,
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

    formation_counts = {1: 0, 2: 0, 3: 0, 4: 0}
    for s in starting:
        formation_counts[s["position"]] += 1
    formation = f"{formation_counts[2]}-{formation_counts[3]}-{formation_counts[4]}"

    total_cost = round(
        sum(s["price"] for s in starting) + sum(b["price"] for b in bench), 1
    )
    predicted_points = round(sum(s["predicted_points"] for s in starting), 1)

    # Save as current squad
    save_payload = {
        "gameweek": used_gw,
        "season": season,
        "squad": {"starting_xi": starting, "bench": bench},
        "formation": formation,
        "captain_id": captain_id,
        "vice_captain_id": vice_id,
        "total_cost": total_cost,
        "predicted_points": predicted_points,
    }

    await save_squad(save_payload, db=db, current_user=current_user)  # reuse logic

    return {"message": "Imported from FPL", **save_payload}


@router.get("/history")
async def squad_history(
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """Return historical squads for the user."""

    result = await db.execute(
        select(UserSquad)
        .where(UserSquad.user_id == current_user.id)
        .order_by(UserSquad.created_at.desc())
    )
    squads = result.scalars().all()

    return [
        {
            "id": s.id,
            "gameweek": s.gameweek,
            "season": s.season,
            "formation": s.formation,
            "total_cost": s.total_cost,
            "predicted_points": s.predicted_points,
            "is_current": s.is_current,
            "created_at": s.created_at,
        }
        for s in squads
    ]
