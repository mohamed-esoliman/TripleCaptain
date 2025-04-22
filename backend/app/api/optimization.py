from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import List, Optional, Dict, Any

from app.db.database import get_async_session
from app.db.models import Player, MLPrediction, Team
from app.core.dependencies import get_current_user, get_current_user_optional
from app.api.schemas import (
    OptimizationRequest,
    OptimizationResponse,
    TransferPlanRequest,
    TransferPlanResponse,
    FormationRequest,
    CaptainRequest,
)
from app.optimization.squad_optimizer import (
    SquadOptimizer,
    PlayerData,
    OptimizationConstraints,
)
from app.optimization.transfer_planner import TransferPlanner
from app.services.fpl_client import get_season_string, FPLClient, get_current_gameweek

router = APIRouter(prefix="/optimization", tags=["Optimization"])


async def _get_player_data(
    db: AsyncSession, gameweek: int, player_ids: Optional[List[int]] = None
) -> List[PlayerData]:
    """Helper function to get player data for optimization."""

    season = get_season_string()

    # Build query to get players with predictions
    query = (
        select(Player, MLPrediction)
        .join(
            MLPrediction,
            (Player.id == MLPrediction.player_id)
            & (MLPrediction.gameweek == gameweek)
            & (MLPrediction.season == season),
        )
        .where(Player.status == "a")
    )  # Only available players

    if player_ids:
        query = query.where(Player.id.in_(player_ids))

    result = await db.execute(query)
    players_with_predictions = result.all()

    player_data: List[PlayerData] = []
    for player, prediction in players_with_predictions:
        player_data.append(
            PlayerData(
                id=player.id,
                position=player.position,
                team_id=player.team_id,
                price=player.current_price / 10.0,  # Convert to millions
                predicted_points=float(prediction.predicted_points),
                start_probability=float(prediction.start_probability or 0.9),
                name=f"{player.first_name or ''} {player.second_name}".strip(),
                variance=float(prediction.variance or 0.0),
                ceiling_points=float(
                    prediction.ceiling_points or prediction.predicted_points
                ),
                floor_points=float(
                    prediction.floor_points or (prediction.predicted_points * 0.5)
                ),
            )
        )

    # Fallback: if no ML predictions exist, synthesize from player fields
    if not player_data:
        base_query = select(Player).where(Player.status == "a")
        if player_ids:
            base_query = base_query.where(Player.id.in_(player_ids))
        # Prefer higher-scoring players to limit problem size
        base_query = base_query.order_by(Player.total_points.desc()).limit(300)

        base_res = await db.execute(base_query)
        players_only = base_res.scalars().all()

        for player in players_only:
            predicted = float(player.ep_next or player.ep_this or player.form or 2.0)
            player_data.append(
                PlayerData(
                    id=player.id,
                    position=player.position,
                    team_id=player.team_id,
                    price=player.current_price / 10.0,
                    predicted_points=predicted,
                    start_probability=0.9,
                    name=f"{player.first_name or ''} {player.second_name}".strip(),
                    variance=0.5,
                    ceiling_points=predicted * 1.3,
                    floor_points=predicted * 0.6,
                )
            )

    return player_data


@router.post("/squad", response_model=Dict[str, Any])
async def optimize_squad(
    request: OptimizationRequest,
    db: AsyncSession = Depends(get_async_session),
    current_user=Depends(get_current_user_optional),
):
    """Optimize squad selection for a gameweek."""

    try:
        # Get player data
        player_data = await _get_player_data(db, request.gameweek)

        if not player_data:
            raise HTTPException(
                status_code=404,
                detail=f"No player data found for gameweek {request.gameweek}",
            )

        # Create optimization constraints
        constraints = OptimizationConstraints(
            budget=request.budget or 100.0,
            squad_size=15,
            starting_xi_size=11,
            max_players_per_team=3,
            formation=request.formation,
            excluded_players=request.excluded_players or [],
            required_players=None,  # Could be added from request
            risk_tolerance=request.risk_tolerance or 0.5,
        )

        # Run optimization
        optimizer = SquadOptimizer()
        result = optimizer.optimize_squad(player_data, constraints)

        return result

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Optimization failed: {str(e)}")


@router.post("/formation")
async def optimize_formation(
    request: FormationRequest,
    db: AsyncSession = Depends(get_async_session),
    current_user=Depends(get_current_user_optional),
):
    """Find the best formation for a given set of players."""

    try:
        # Get player data for specified players
        player_data = await _get_player_data(
            db, request.gameweek, request.required_players
        )

        if len(player_data) != 15:
            raise HTTPException(
                status_code=400, detail=f"Expected 15 players, got {len(player_data)}"
            )

        constraints = OptimizationConstraints(
            budget=200.0,  # High budget since players are pre-selected
            squad_size=15,
            starting_xi_size=11,
            max_players_per_team=15,  # No team restrictions
            required_players=request.required_players,
            risk_tolerance=0.5,
        )

        optimizer = SquadOptimizer()
        result = optimizer.find_best_formation(player_data, constraints)

        return result

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Formation optimization failed: {str(e)}"
        )


@router.post("/captain")
async def optimize_captain(
    request: CaptainRequest,
    db: AsyncSession = Depends(get_async_session),
    current_user=Depends(get_current_user_optional),
):
    """Optimize captain choice for a given squad."""

    try:
        # Get player data for specified players (fallback gw if not provided)
        gw = request.gameweek or 1
        player_data = await _get_player_data(db, gw, request.player_ids)

        if not player_data:
            raise HTTPException(
                status_code=404, detail="No player data found for the specified players"
            )

        optimizer = SquadOptimizer()
        result = optimizer.optimize_captain_choice(player_data, request.player_ids)

        return result

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Captain optimization failed: {str(e)}"
        )


@router.post("/transfers")
async def plan_transfers(
    request: TransferPlanRequest,
    db: AsyncSession = Depends(get_async_session),
    current_user=Depends(get_current_user_optional),
):
    """Plan transfers across multiple gameweeks."""

    try:
        # Get current squad player data
        # Determine current gameweek from FPL bootstrap
        try:
            async with FPLClient() as fpl:
                bootstrap = await fpl.get_bootstrap_static()
                events = bootstrap.get("events", [])
                current_gameweek = get_current_gameweek(events) or 1
        except Exception:
            current_gameweek = 1
        current_squad_data = await _get_player_data(
            db, current_gameweek, request.current_squad
        )

        # Get all player data for planning
        all_player_data = await _get_player_data(db, current_gameweek)

        if not current_squad_data:
            raise HTTPException(
                status_code=400, detail="Could not find data for current squad players"
            )

        # Create transfer planner
        optimizer = SquadOptimizer()
        planner = TransferPlanner(optimizer)

        # Plan transfers
        result = planner.plan_transfers(
            current_squad=current_squad_data,
            all_players=all_player_data,
            planning_horizon=request.planning_horizon or 5,
            max_transfers_per_week=request.max_transfers_per_week or 1,
            available_chips=request.available_chips or {},
            current_gameweek=current_gameweek,
        )

        return result

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Transfer planning failed: {str(e)}"
        )


@router.get("/chips/analysis/{gameweek}")
async def analyze_chip_usage(
    gameweek: int,
    available_chips: str = "wildcard,bench_boost,triple_captain,free_hit",
    db: AsyncSession = Depends(get_async_session),
    current_user=Depends(get_current_user_optional),
):
    """Analyze optimal chip usage for a gameweek."""

    try:
        chips = available_chips.split(",") if available_chips else []
        chips_dict = {chip.strip(): True for chip in chips}

        # Get player data
        player_data = await _get_player_data(db, gameweek)

        if not player_data:
            # Fallback: use latest available gameweek for this season
            try:
                season = get_season_string()
                from sqlalchemy import select, func

                max_gw_q = select(func.max(MLPrediction.gameweek)).where(
                    MLPrediction.season == season
                )
                max_gw_result = await db.execute(max_gw_q)
                fallback_gw = max_gw_result.scalar()
            except Exception:
                fallback_gw = None

            if fallback_gw:
                player_data = await _get_player_data(db, fallback_gw)
                gameweek = fallback_gw  # update gw used downstream

        if not player_data:
            raise HTTPException(
                status_code=404, detail=f"No player data found for quick pick"
            )

        # Mock analysis - in a full implementation this would be more sophisticated
        chip_analysis = {}

        if "triple_captain" in chips_dict:
            # Find best captain candidate
            best_captain = max(
                player_data, key=lambda p: p.predicted_points * p.start_probability
            )
            triple_captain_benefit = (
                best_captain.predicted_points * best_captain.start_probability
            )

            chip_analysis["triple_captain"] = {
                "recommended": triple_captain_benefit > 10.0,
                "expected_benefit": round(triple_captain_benefit, 1),
                "best_candidate": {
                    "player_id": best_captain.id,
                    "name": best_captain.name,
                    "predicted_points": round(best_captain.predicted_points, 1),
                },
            }

        if "bench_boost" in chips_dict:
            # Estimate bench boost value
            sorted_players = sorted(
                player_data, key=lambda p: p.predicted_points, reverse=True
            )
            bench_candidates = sorted_players[11:15]  # Typical bench players
            bench_boost_benefit = sum(
                p.predicted_points * p.start_probability for p in bench_candidates
            )

            chip_analysis["bench_boost"] = {
                "recommended": bench_boost_benefit > 8.0,
                "expected_benefit": round(bench_boost_benefit, 1),
                "bench_strength": len(
                    [p for p in bench_candidates if p.predicted_points > 2.0]
                ),
            }

        return {
            "gameweek": gameweek,
            "chip_analysis": chip_analysis,
            "recommendation": "Consider Triple Captain if you have a reliable high-scorer",
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chip analysis failed: {str(e)}")


@router.get("/fixture-analysis")
async def analyze_fixtures(
    gameweeks: int = 5,
    db: AsyncSession = Depends(get_async_session),
    current_user=Depends(get_current_user_optional),
):
    """Analyze fixture difficulty for teams over upcoming gameweeks."""

    try:
        from app.db.models import Fixture

        season = get_season_string()
        current_gameweek = 1  # This should be determined from current FPL state

        # Get upcoming fixtures
        fixtures_query = (
            select(Fixture)
            .where(
                Fixture.season == season,
                Fixture.gameweek >= current_gameweek,
                Fixture.gameweek < current_gameweek + gameweeks,
                Fixture.finished == False,
            )
            .order_by(Fixture.gameweek, Fixture.kickoff_time)
        )

        fixtures_result = await db.execute(fixtures_query)
        fixtures = fixtures_result.scalars().all()

        # Group by team and calculate average difficulty
        team_fixtures = {}
        for fixture in fixtures:
            # Home team
            if fixture.team_h_id not in team_fixtures:
                team_fixtures[fixture.team_h_id] = []
            team_fixtures[fixture.team_h_id].append(
                {
                    "gameweek": fixture.gameweek,
                    "is_home": True,
                    "difficulty": fixture.team_h_difficulty,
                    "opponent_id": fixture.team_a_id,
                }
            )

            # Away team
            if fixture.team_a_id not in team_fixtures:
                team_fixtures[fixture.team_a_id] = []
            team_fixtures[fixture.team_a_id].append(
                {
                    "gameweek": fixture.gameweek,
                    "is_home": False,
                    "difficulty": fixture.team_a_difficulty,
                    "opponent_id": fixture.team_h_id,
                }
            )

        # Calculate fixture ratings
        fixture_analysis = []
        for team_id, team_fixtures_list in team_fixtures.items():
            avg_difficulty = sum(f["difficulty"] for f in team_fixtures_list) / len(
                team_fixtures_list
            )
            home_games = sum(1 for f in team_fixtures_list if f["is_home"])

            fixture_analysis.append(
                {
                    "team_id": team_id,
                    "avg_difficulty": round(avg_difficulty, 2),
                    "home_games": home_games,
                    "away_games": len(team_fixtures_list) - home_games,
                    "total_games": len(team_fixtures_list),
                    "fixtures": team_fixtures_list,
                }
            )

        # Sort by average difficulty (lower is better)
        fixture_analysis.sort(key=lambda x: x["avg_difficulty"])

        return {
            "gameweek_range": f"{current_gameweek}-{current_gameweek + gameweeks - 1}",
            "best_fixtures": fixture_analysis[:5],
            "worst_fixtures": fixture_analysis[-5:],
            "all_teams": fixture_analysis,
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Fixture analysis failed: {str(e)}"
        )


@router.post("/quick-pick/{gameweek}")
async def quick_pick_squad(
    gameweek: int,
    formation: str = "3-4-3",
    risk_tolerance: float = 0.5,
    db: AsyncSession = Depends(get_async_session),
    current_user=Depends(get_current_user_optional),
):
    """Generate a quick squad pick for beginners."""

    try:
        # Get player data
        player_data = await _get_player_data(db, gameweek)

        if not player_data:
            raise HTTPException(
                status_code=404, detail=f"No player data found for gameweek {gameweek}"
            )

        optimizer = SquadOptimizer()

        # Attempt 1: full 15-man squad under normal constraints
        try:
            constraints = OptimizationConstraints(
                budget=100.0,
                formation=formation,
                risk_tolerance=risk_tolerance,
                squad_size=15,
                starting_xi_size=11,
                max_players_per_team=3,
            )
            result = optimizer.optimize_squad(player_data, constraints)
        except Exception as e1:
            # Attempt 2: fallback to starting XI only, relaxed team cap and budget
            constraints = OptimizationConstraints(
                budget=120.0,
                formation=formation,
                risk_tolerance=risk_tolerance,
                squad_size=11,
                starting_xi_size=11,
                max_players_per_team=15,
            )
            try:
                result = optimizer.optimize_squad(player_data, constraints)
            except Exception:
                # Attempt 3: greedy fallback to build a valid XI
                from collections import defaultdict

                def_counts = int(formation.split("-")[0]) if formation else 3
                mid_counts = int(formation.split("-")[1]) if formation else 4
                fwd_counts = int(formation.split("-")[2]) if formation else 3

                # Sort players by predicted points
                sorted_players = sorted(
                    player_data, key=lambda p: p.predicted_points, reverse=True
                )

                team_counts = defaultdict(int)
                budget_left = constraints.budget

                def take(players, need):
                    chosen = []
                    nonlocal budget_left
                    for p in players:
                        if len(chosen) >= need:
                            break
                        if team_counts[p.team_id] >= constraints.max_players_per_team:
                            continue
                        if p.price > budget_left:
                            continue
                        chosen.append(p)
                        team_counts[p.team_id] += 1
                        budget_left -= p.price
                    return chosen

                gkp = take([p for p in sorted_players if p.position == 1], 1)
                defs = take([p for p in sorted_players if p.position == 2], def_counts)
                mids = take([p for p in sorted_players if p.position == 3], mid_counts)
                fwds = take([p for p in sorted_players if p.position == 4], fwd_counts)

                starting = gkp + defs + mids + fwds
                if len(starting) < 11:
                    # Fill remaining with any position
                    remaining = take(
                        [p for p in sorted_players if p not in starting],
                        11 - len(starting),
                    )
                    starting += remaining

                # Captain: best predicted among starters
                captain = max(starting, key=lambda p: p.predicted_points)

                total_cost = round(sum(p.price for p in starting), 1)
                predicted_points = round(
                    sum(p.predicted_points * p.start_probability for p in starting)
                    + captain.predicted_points * captain.start_probability,
                    1,
                )

                def to_dict(p, is_starter, is_captain):
                    return {
                        "player_id": p.id,
                        "name": p.name,
                        "position": p.position,
                        "team_id": p.team_id,
                        "price": p.price,
                        "predicted_points": round(p.predicted_points, 1),
                        "start_probability": round(p.start_probability, 2),
                        "is_starter": is_starter,
                        "is_captain": is_captain,
                        "variance": round(p.variance, 2),
                    }

                result = {
                    "squad": [to_dict(p, True, p.id == captain.id) for p in starting],
                    "starting_xi": [
                        to_dict(p, True, p.id == captain.id) for p in starting
                    ],
                    "bench": [],
                    "formation": formation or "3-4-3",
                    "total_cost": total_cost,
                    "predicted_points": predicted_points,
                    "captain_id": captain.id,
                    "alternatives": [],
                }

        # Add explanation for beginners
        budget_limit = constraints.budget
        result["explanation"] = {
            "formation": f"Using {formation} formation",
            "budget_used": f"£{result['total_cost']}M out of £{budget_limit}M budget",
            "predicted_return": f"{result['predicted_points']} points expected",
            "risk_level": (
                "Low"
                if risk_tolerance < 0.4
                else "Medium" if risk_tolerance < 0.7 else "High"
            ),
            "gameweek": gameweek,
        }

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Quick pick failed: {type(e).__name__}: {e}"
        )
