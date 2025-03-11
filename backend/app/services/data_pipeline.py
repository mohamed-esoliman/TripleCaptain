import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, insert
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db.database import AsyncSessionLocal
from app.db.models import Player, Team, Fixture, PlayerStatistic, DataUpdateLog
from app.services.fpl_client import FPLClient, get_current_gameweek, get_season_string
from app.core.config import settings
import pandas as pd
import httpx

logger = logging.getLogger(__name__)


class DataPipelineError(Exception):
    """Base exception for data pipeline errors."""

    pass


class DataPipeline:
    """Manages the data pipeline for syncing FPL data to database."""

    def __init__(self):
        self.season = get_season_string()

    async def log_update(
        self,
        db: AsyncSession,
        update_type: str,
        status: str,
        gameweek: Optional[int] = None,
        records_processed: int = 0,
        error_message: Optional[str] = None,
        duration_seconds: Optional[float] = None,
        started_at: Optional[datetime] = None,
    ) -> DataUpdateLog:
        """Log data update operation."""
        log_entry = DataUpdateLog(
            update_type=update_type,
            gameweek=gameweek,
            season=self.season,
            status=status,
            records_processed=records_processed,
            error_message=error_message,
            duration_seconds=duration_seconds,
            started_at=started_at or datetime.utcnow(),
            completed_at=datetime.utcnow() if status in ["success", "error"] else None,
        )

        db.add(log_entry)
        await db.commit()
        await db.refresh(log_entry)
        return log_entry

    async def sync_teams(self, teams_data: List[Dict[str, Any]]) -> int:
        """Sync teams data to database."""
        async with AsyncSessionLocal() as db:
            start_time = datetime.utcnow()

            try:
                updated_count = 0

                for team_data in teams_data:
                    # Use upsert to handle both inserts and updates
                    stmt = pg_insert(Team).values(
                        fpl_id=team_data["id"],
                        name=team_data["name"],
                        short_name=team_data["short_name"],
                        code=team_data.get("code"),
                        strength=team_data.get("strength"),
                        strength_overall_home=team_data.get("strength_overall_home"),
                        strength_overall_away=team_data.get("strength_overall_away"),
                        strength_attack_home=team_data.get("strength_attack_home"),
                        strength_attack_away=team_data.get("strength_attack_away"),
                        strength_defence_home=team_data.get("strength_defence_home"),
                        strength_defence_away=team_data.get("strength_defence_away"),
                        position=team_data.get("position"),
                        played=team_data.get("played", 0),
                        won=team_data.get("win", 0),
                        drawn=team_data.get("draw", 0),
                        lost=team_data.get("loss", 0),
                        points=team_data.get("points", 0),
                        updated_at=datetime.utcnow(),
                    )

                    stmt = stmt.on_conflict_do_update(
                        index_elements=["fpl_id"],
                        set_={
                            "name": stmt.excluded.name,
                            "short_name": stmt.excluded.short_name,
                            "strength": stmt.excluded.strength,
                            "strength_overall_home": stmt.excluded.strength_overall_home,
                            "strength_overall_away": stmt.excluded.strength_overall_away,
                            "strength_attack_home": stmt.excluded.strength_attack_home,
                            "strength_attack_away": stmt.excluded.strength_attack_away,
                            "strength_defence_home": stmt.excluded.strength_defence_home,
                            "strength_defence_away": stmt.excluded.strength_defence_away,
                            "position": stmt.excluded.position,
                            "played": stmt.excluded.played,
                            "won": stmt.excluded.won,
                            "drawn": stmt.excluded.drawn,
                            "lost": stmt.excluded.lost,
                            "points": stmt.excluded.points,
                            "updated_at": stmt.excluded.updated_at,
                        },
                    )

                    await db.execute(stmt)
                    updated_count += 1

                await db.commit()
                duration = (datetime.utcnow() - start_time).total_seconds()

                await self.log_update(
                    db,
                    "teams",
                    "success",
                    records_processed=updated_count,
                    duration_seconds=duration,
                    started_at=start_time,
                )

                logger.info(f"Successfully synced {updated_count} teams")
                return updated_count

            except Exception as e:
                await db.rollback()
                duration = (datetime.utcnow() - start_time).total_seconds()

                await self.log_update(
                    db,
                    "teams",
                    "error",
                    error_message=str(e),
                    duration_seconds=duration,
                    started_at=start_time,
                )

                logger.error(f"Failed to sync teams: {e}")
                raise DataPipelineError(f"Team sync failed: {e}")

    async def sync_players(self, players_data: List[Dict[str, Any]]) -> int:
        """Sync players data to database."""
        async with AsyncSessionLocal() as db:
            start_time = datetime.utcnow()

            try:
                # First, get team mapping
                team_result = await db.execute(select(Team.id, Team.fpl_id))
                team_mapping = {fpl_id: id for id, fpl_id in team_result.all()}

                updated_count = 0

                for player_data in players_data:
                    team_id = team_mapping.get(player_data["team"])
                    if not team_id:
                        logger.warning(
                            f"Team {player_data['team']} not found for player {player_data['id']}"
                        )
                        continue

                    news_added = None
                    if player_data.get("news_added"):
                        try:
                            news_added = datetime.fromisoformat(
                                player_data["news_added"].replace("Z", "+00:00")
                            )
                        except (ValueError, AttributeError):
                            news_added = None

                    stmt = pg_insert(Player).values(
                        fpl_id=player_data["id"],
                        first_name=player_data.get("first_name"),
                        second_name=player_data["second_name"],
                        web_name=player_data["web_name"],
                        team_id=team_id,
                        position=player_data["element_type"],
                        current_price=player_data["now_cost"],
                        total_points=player_data["total_points"],
                        form=float(player_data.get("form", 0)),
                        status=player_data.get("status", "a"),
                        chance_playing_this=player_data.get(
                            "chance_of_playing_this_round"
                        ),
                        chance_playing_next=player_data.get(
                            "chance_of_playing_next_round"
                        ),
                        selected_by_percent=float(
                            player_data.get("selected_by_percent", 0)
                        ),
                        transfers_in_event=player_data.get("transfers_in_event", 0),
                        transfers_out_event=player_data.get("transfers_out_event", 0),
                        goals_scored=player_data.get("goals_scored", 0),
                        assists=player_data.get("assists", 0),
                        clean_sheets=player_data.get("clean_sheets", 0),
                        goals_conceded=player_data.get("goals_conceded", 0),
                        yellow_cards=player_data.get("yellow_cards", 0),
                        red_cards=player_data.get("red_cards", 0),
                        saves=player_data.get("saves", 0),
                        bonus=player_data.get("bonus", 0),
                        bps=player_data.get("bps", 0),
                        influence=float(player_data.get("influence", 0)),
                        creativity=float(player_data.get("creativity", 0)),
                        threat=float(player_data.get("threat", 0)),
                        ict_index=float(player_data.get("ict_index", 0)),
                        ep_this=float(player_data.get("ep_this", 0)),
                        ep_next=float(player_data.get("ep_next", 0)),
                        cost_change_event=player_data.get("cost_change_event", 0),
                        cost_change_start=player_data.get("cost_change_start", 0),
                        news=player_data.get("news"),
                        news_added=news_added,
                        photo=player_data.get("photo"),
                        updated_at=datetime.utcnow(),
                    )

                    stmt = stmt.on_conflict_do_update(
                        index_elements=["fpl_id"],
                        set_={
                            "first_name": stmt.excluded.first_name,
                            "second_name": stmt.excluded.second_name,
                            "web_name": stmt.excluded.web_name,
                            "team_id": stmt.excluded.team_id,
                            "current_price": stmt.excluded.current_price,
                            "total_points": stmt.excluded.total_points,
                            "form": stmt.excluded.form,
                            "status": stmt.excluded.status,
                            "chance_playing_this": stmt.excluded.chance_playing_this,
                            "chance_playing_next": stmt.excluded.chance_playing_next,
                            "selected_by_percent": stmt.excluded.selected_by_percent,
                            "transfers_in_event": stmt.excluded.transfers_in_event,
                            "transfers_out_event": stmt.excluded.transfers_out_event,
                            "goals_scored": stmt.excluded.goals_scored,
                            "assists": stmt.excluded.assists,
                            "clean_sheets": stmt.excluded.clean_sheets,
                            "goals_conceded": stmt.excluded.goals_conceded,
                            "yellow_cards": stmt.excluded.yellow_cards,
                            "red_cards": stmt.excluded.red_cards,
                            "saves": stmt.excluded.saves,
                            "bonus": stmt.excluded.bonus,
                            "bps": stmt.excluded.bps,
                            "influence": stmt.excluded.influence,
                            "creativity": stmt.excluded.creativity,
                            "threat": stmt.excluded.threat,
                            "ict_index": stmt.excluded.ict_index,
                            "ep_this": stmt.excluded.ep_this,
                            "ep_next": stmt.excluded.ep_next,
                            "cost_change_event": stmt.excluded.cost_change_event,
                            "cost_change_start": stmt.excluded.cost_change_start,
                            "news": stmt.excluded.news,
                            "news_added": stmt.excluded.news_added,
                            "updated_at": stmt.excluded.updated_at,
                        },
                    )

                    await db.execute(stmt)
                    updated_count += 1

                await db.commit()
                duration = (datetime.utcnow() - start_time).total_seconds()

                await self.log_update(
                    db,
                    "players",
                    "success",
                    records_processed=updated_count,
                    duration_seconds=duration,
                    started_at=start_time,
                )

                logger.info(f"Successfully synced {updated_count} players")
                return updated_count

            except Exception as e:
                await db.rollback()
                duration = (datetime.utcnow() - start_time).total_seconds()

                await self.log_update(
                    db,
                    "players",
                    "error",
                    error_message=str(e),
                    duration_seconds=duration,
                    started_at=start_time,
                )

                logger.error(f"Failed to sync players: {e}")
                raise DataPipelineError(f"Player sync failed: {e}")

    async def sync_fixtures(self, fixtures_data: List[Dict[str, Any]]) -> int:
        """Sync fixtures data to database."""
        async with AsyncSessionLocal() as db:
            start_time = datetime.utcnow()

            try:
                # Get team mapping
                team_result = await db.execute(select(Team.id, Team.fpl_id))
                team_mapping = {fpl_id: id for id, fpl_id in team_result.all()}

                updated_count = 0

                for fixture_data in fixtures_data:
                    team_h_id = team_mapping.get(fixture_data["team_h"])
                    team_a_id = team_mapping.get(fixture_data["team_a"])

                    if not team_h_id or not team_a_id:
                        logger.warning(
                            f"Teams not found for fixture {fixture_data['id']}"
                        )
                        continue

                    kickoff_time = None
                    if fixture_data.get("kickoff_time"):
                        try:
                            kickoff_time = datetime.fromisoformat(
                                fixture_data["kickoff_time"].replace("Z", "+00:00")
                            )
                        except (ValueError, AttributeError):
                            kickoff_time = None

                    stmt = pg_insert(Fixture).values(
                        fpl_id=fixture_data["id"],
                        gameweek=fixture_data.get("event"),
                        season=self.season,
                        team_h_id=team_h_id,
                        team_a_id=team_a_id,
                        team_h_score=fixture_data.get("team_h_score"),
                        team_a_score=fixture_data.get("team_a_score"),
                        team_h_difficulty=fixture_data.get("team_h_difficulty"),
                        team_a_difficulty=fixture_data.get("team_a_difficulty"),
                        kickoff_time=kickoff_time,
                        finished=fixture_data.get("finished", False),
                        finished_provisional=fixture_data.get(
                            "finished_provisional", False
                        ),
                        started=fixture_data.get("started", False),
                        minutes=fixture_data.get("minutes", 0),
                        provisional_start_time=fixture_data.get(
                            "provisional_start_time", False
                        ),
                        pulse_id=fixture_data.get("pulse_id"),
                        stats=fixture_data.get("stats"),
                        updated_at=datetime.utcnow(),
                    )

                    stmt = stmt.on_conflict_do_update(
                        index_elements=["fpl_id"],
                        set_={
                            "gameweek": stmt.excluded.gameweek,
                            "team_h_score": stmt.excluded.team_h_score,
                            "team_a_score": stmt.excluded.team_a_score,
                            "kickoff_time": stmt.excluded.kickoff_time,
                            "finished": stmt.excluded.finished,
                            "finished_provisional": stmt.excluded.finished_provisional,
                            "started": stmt.excluded.started,
                            "minutes": stmt.excluded.minutes,
                            "provisional_start_time": stmt.excluded.provisional_start_time,
                            "stats": stmt.excluded.stats,
                            "updated_at": stmt.excluded.updated_at,
                        },
                    )

                    await db.execute(stmt)
                    updated_count += 1

                await db.commit()
                duration = (datetime.utcnow() - start_time).total_seconds()

                await self.log_update(
                    db,
                    "fixtures",
                    "success",
                    records_processed=updated_count,
                    duration_seconds=duration,
                    started_at=start_time,
                )

                logger.info(f"Successfully synced {updated_count} fixtures")
                return updated_count

            except Exception as e:
                await db.rollback()
                duration = (datetime.utcnow() - start_time).total_seconds()

                await self.log_update(
                    db,
                    "fixtures",
                    "error",
                    error_message=str(e),
                    duration_seconds=duration,
                    started_at=start_time,
                )

                logger.error(f"Failed to sync fixtures: {e}")
                raise DataPipelineError(f"Fixture sync failed: {e}")

    async def full_data_sync(self) -> Dict[str, int]:
        """Perform complete data synchronization from FPL API."""
        logger.info("Starting full data synchronization")

        async with FPLClient() as fpl_client:
            try:
                # Get bootstrap data
                bootstrap_data = await fpl_client.get_bootstrap_static()

                # Sync teams first (required for players)
                teams_count = await self.sync_teams(bootstrap_data["teams"])

                # Sync players
                players_count = await self.sync_players(bootstrap_data["elements"])

                # Get and sync fixtures
                fixtures_data = await fpl_client.get_fixtures()
                fixtures_count = await self.sync_fixtures(fixtures_data)

                # Optionally backfill limited recent player statistics for current gameweek - 1
                events = bootstrap_data.get("events", [])
                current_gw = get_current_gameweek(events) or 1
                backfill_gw = max(1, current_gw - 1)
                try:
                    await self.update_player_statistics_for_gameweek(
                        fpl_client, backfill_gw
                    )
                except Exception as e:
                    logger.warning(f"Player stats backfill skipped: {e}")

                results = {
                    "teams": teams_count,
                    "players": players_count,
                    "fixtures": fixtures_count,
                }

                logger.info(f"Full sync completed: {results}")
                return results

            except Exception as e:
                logger.error(f"Full sync failed: {e}")
                raise DataPipelineError(f"Full sync failed: {e}")

    async def daily_update(self) -> Dict[str, int]:
        """Perform daily data update (lighter than full sync)."""
        logger.info("Starting daily data update")

        async with FPLClient() as fpl_client:
            try:
                # Get bootstrap data for player updates
                bootstrap_data = await fpl_client.get_bootstrap_static()

                # Update players (prices, form, availability)
                players_count = await self.sync_players(bootstrap_data["elements"])

                # Update fixtures (scores, status)
                fixtures_data = await fpl_client.get_fixtures()
                fixtures_count = await self.sync_fixtures(fixtures_data)

                # If a gameweek just finished, ingest detailed player stats
                events = bootstrap_data.get("events", [])
                for event in events:
                    if event.get("finished") and event.get("data_checked"):
                        gw = event["id"]
                        try:
                            await self.update_player_statistics_for_gameweek(
                                fpl_client, gw
                            )
                        except Exception as e:
                            logger.warning(f"Stats ingestion for GW{gw} failed: {e}")

                results = {"players": players_count, "fixtures": fixtures_count}

                logger.info(f"Daily update completed: {results}")
                return results

            except Exception as e:
                logger.error(f"Daily update failed: {e}")
                raise DataPipelineError(f"Daily update failed: {e}")

    async def update_player_statistics_for_gameweek(
        self, fpl_client: FPLClient, gameweek: int
    ) -> int:
        """Ingest player statistics from FPL live data for a specific gameweek."""
        logger.info(f"Updating player statistics for GW{gameweek}")

        async with AsyncSessionLocal() as db:
            start_time = datetime.utcnow()
            try:
                live = await fpl_client.get_gameweek_live(gameweek)
                elements = live.get("elements", [])

                # Map fpl_id -> player.id
                player_map_result = await db.execute(select(Player.id, Player.fpl_id))
                fpl_to_internal = {
                    fpl_id: pid for pid, fpl_id in player_map_result.all()
                }

                updated = 0
                for el in elements:
                    fpl_id = el.get("id")
                    pid = fpl_to_internal.get(fpl_id)
                    if not pid:
                        continue

                    stats = el.get("stats", {})
                    minutes = stats.get("minutes", 0)
                    total_points = stats.get("total_points", 0)
                    goals_scored = stats.get("goals_scored", 0)
                    assists = stats.get("assists", 0)
                    clean_sheets = stats.get("clean_sheets", 0)
                    goals_conceded = stats.get("goals_conceded", 0)
                    yellow_cards = stats.get("yellow_cards", 0)
                    red_cards = stats.get("red_cards", 0)
                    saves = stats.get("saves", 0)
                    bonus = stats.get("bonus", 0)
                    bps = stats.get("bps", 0)

                    # Manual upsert to avoid requiring a DB unique constraint
                    upd = (
                        PlayerStatistic.__table__.update()
                        .where(
                            (PlayerStatistic.player_id == pid)
                            & (PlayerStatistic.gameweek == gameweek)
                            & (PlayerStatistic.season == self.season)
                        )
                        .values(
                            minutes=minutes,
                            total_points=total_points,
                            goals_scored=goals_scored,
                            assists=assists,
                            clean_sheets=clean_sheets,
                            goals_conceded=goals_conceded,
                            yellow_cards=yellow_cards,
                            red_cards=red_cards,
                            saves=saves,
                            bonus=bonus,
                            bps=bps,
                        )
                    )
                    result = await db.execute(upd)
                    if result.rowcount == 0:
                        ins = pg_insert(PlayerStatistic).values(
                            player_id=pid,
                            gameweek=gameweek,
                            season=self.season,
                            minutes=minutes,
                            total_points=total_points,
                            goals_scored=goals_scored,
                            assists=assists,
                            clean_sheets=clean_sheets,
                            goals_conceded=goals_conceded,
                            yellow_cards=yellow_cards,
                            red_cards=red_cards,
                            saves=saves,
                            bonus=bonus,
                            bps=bps,
                            created_at=datetime.utcnow(),
                        )
                        await db.execute(ins)
                    updated += 1

                await db.commit()

                duration = (datetime.utcnow() - start_time).total_seconds()
                async with AsyncSessionLocal() as log_db:
                    await self.log_update(
                        log_db,
                        "stats",
                        "success",
                        gameweek=gameweek,
                        records_processed=updated,
                        duration_seconds=duration,
                        started_at=start_time,
                    )

                logger.info(f"Updated stats for {updated} players in GW{gameweek}")
                return updated

            except Exception as e:
                logger.error(f"Stats update for GW{gameweek} failed: {e}")
                async with AsyncSessionLocal() as log_db:
                    await self.log_update(
                        log_db,
                        "stats",
                        "error",
                        gameweek=gameweek,
                        error_message=str(e),
                        started_at=start_time,
                    )
                raise

    async def backfill_current_season_history(
        self, up_to_gw: int, max_players: Optional[int] = None
    ) -> int:
        """Backfill current-season per-GW statistics for all players up to a given GW using element-summary.

        This pulls granular per-match history for the current season only (past seasons are aggregate-only in FPL API).
        """
        logger.info(f"Backfilling current-season history up to GW{up_to_gw}")

        async with FPLClient() as fpl_client:
            async with AsyncSessionLocal() as db:
                start_time = datetime.utcnow()
                try:
                    # Maps for ids
                    player_map_result = await db.execute(
                        select(Player.id, Player.fpl_id)
                    )
                    fpl_to_player = {
                        fpl_id: pid for pid, fpl_id in player_map_result.all()
                    }

                    fixture_map_result = await db.execute(
                        select(Fixture.id, Fixture.fpl_id)
                    )
                    fpl_fixture_to_id = {
                        fpl_id: fid for fid, fpl_id in fixture_map_result.all()
                    }

                    team_map_result = await db.execute(select(Team.id, Team.fpl_id))
                    fpl_team_to_id = {
                        fpl_id: tid for tid, fpl_id in team_map_result.all()
                    }

                    # Fetch list of all fpl player ids from bootstrap
                    bootstrap = await fpl_client.get_bootstrap_static()
                    elements = bootstrap.get("elements", [])
                    fpl_ids = [el.get("id") for el in elements if el.get("id")]
                    if max_players:
                        fpl_ids = fpl_ids[:max_players]

                    summaries = await fpl_client.batch_get_player_summaries(
                        fpl_ids, max_concurrent=10
                    )

                    inserted = 0
                    for idx, summary in enumerate(summaries):
                        if not summary:
                            continue
                        history = summary.get("history", [])
                        # FPL returns current-season per-match history here
                        # We also need the element id; it may be present as 'id' on the summary payload or nested
                        # Try to infer from first history's 'element' or match to elements by any field
                        # Simpler: we cannot reliably get the element id from summary response without context,
                        # but batch_get_player_summaries maintains order aligned with fpl_ids list; we can map by index.
                        # Instead, add a fallback pass below to map via fixture stats if needed.
                        # Here, we skip if history empty.
                        if not history:
                            continue

                        # We don't have the associated fpl_id per summary item; derive from opponent/fixture is unnecessary.
                        # Each history item contains 'element' in some API versions; handle both cases.
                        # We'll iterate and insert rows for rounds <= up_to_gw.
                        # Map reliable player id from original fpl_ids order
                        fpl_player_id_ctx = fpl_ids[idx] if idx < len(fpl_ids) else None
                        pid_ctx = fpl_to_player.get(fpl_player_id_ctx)
                        if not pid_ctx:
                            continue
                        for h in history:
                            gw = int(h.get("round", 0))
                            if gw <= 0 or gw > up_to_gw:
                                continue

                            pid = pid_ctx

                            fixture_fpl_id = h.get("fixture")
                            fixture_id = (
                                fpl_fixture_to_id.get(fixture_fpl_id)
                                if fixture_fpl_id
                                else None
                            )
                            opp_team_id = (
                                fpl_team_to_id.get(h.get("opponent_team"))
                                if h.get("opponent_team")
                                else None
                            )

                            def fnum(key: str, default: float = 0.0) -> float:
                                v = h.get(key, default)
                                try:
                                    return float(v)
                                except Exception:
                                    return default

                            # Manual upsert (update-then-insert)
                            upd = (
                                PlayerStatistic.__table__.update()
                                .where(
                                    (PlayerStatistic.player_id == pid)
                                    & (PlayerStatistic.gameweek == gw)
                                    & (PlayerStatistic.season == self.season)
                                )
                                .values(
                                    fixture_id=fixture_id,
                                    opponent_team_id=opp_team_id,
                                    was_home=bool(h.get("was_home", False)),
                                    minutes=int(h.get("minutes", 0)),
                                    total_points=int(h.get("total_points", 0)),
                                    goals_scored=int(h.get("goals_scored", 0)),
                                    assists=int(h.get("assists", 0)),
                                    clean_sheets=int(h.get("clean_sheets", 0)),
                                    goals_conceded=int(h.get("goals_conceded", 0)),
                                    yellow_cards=int(h.get("yellow_cards", 0)),
                                    red_cards=int(h.get("red_cards", 0)),
                                    saves=int(h.get("saves", 0)),
                                    bonus=int(h.get("bonus", 0)),
                                    bps=int(h.get("bps", 0)),
                                    influence=fnum("influence"),
                                    creativity=fnum("creativity"),
                                    threat=fnum("threat"),
                                    ict_index=fnum("ict_index"),
                                    expected_goals=fnum("expected_goals"),
                                    expected_assists=fnum("expected_assists"),
                                    expected_goal_involvements=fnum(
                                        "expected_goal_involvements"
                                    ),
                                    expected_goals_conceded=fnum(
                                        "expected_goals_conceded"
                                    ),
                                )
                            )
                            res = await db.execute(upd)
                            if res.rowcount == 0:
                                ins = pg_insert(PlayerStatistic).values(
                                    player_id=pid,
                                    gameweek=gw,
                                    season=self.season,
                                    fixture_id=fixture_id,
                                    opponent_team_id=opp_team_id,
                                    was_home=bool(h.get("was_home", False)),
                                    minutes=int(h.get("minutes", 0)),
                                    total_points=int(h.get("total_points", 0)),
                                    goals_scored=int(h.get("goals_scored", 0)),
                                    assists=int(h.get("assists", 0)),
                                    clean_sheets=int(h.get("clean_sheets", 0)),
                                    goals_conceded=int(h.get("goals_conceded", 0)),
                                    yellow_cards=int(h.get("yellow_cards", 0)),
                                    red_cards=int(h.get("red_cards", 0)),
                                    saves=int(h.get("saves", 0)),
                                    bonus=int(h.get("bonus", 0)),
                                    bps=int(h.get("bps", 0)),
                                    influence=fnum("influence"),
                                    creativity=fnum("creativity"),
                                    threat=fnum("threat"),
                                    ict_index=fnum("ict_index"),
                                    expected_goals=fnum("expected_goals"),
                                    expected_assists=fnum("expected_assists"),
                                    expected_goal_involvements=fnum(
                                        "expected_goal_involvements"
                                    ),
                                    expected_goals_conceded=fnum(
                                        "expected_goals_conceded"
                                    ),
                                    created_at=datetime.utcnow(),
                                )
                                await db.execute(ins)
                            inserted += 1

                    await db.commit()

                    duration = (datetime.utcnow() - start_time).total_seconds()
                    async with AsyncSessionLocal() as log_db:
                        await self.log_update(
                            log_db,
                            "stats",
                            "success",
                            gameweek=up_to_gw,
                            records_processed=inserted,
                            duration_seconds=duration,
                            started_at=start_time,
                        )

                    logger.info(
                        f"Backfill complete. Inserted/updated {inserted} rows up to GW{up_to_gw}"
                    )
                    return inserted

                except Exception as e:
                    logger.error(f"Backfill failed: {e}")
                    async with AsyncSessionLocal() as log_db:
                        await self.log_update(
                            log_db,
                            "stats",
                            "error",
                            gameweek=up_to_gw,
                            error_message=str(e),
                            started_at=start_time,
                        )
                    raise

    async def backfill_last_season_from_public_dataset(
        self, max_gameweek: int = 38
    ) -> int:
        """Backfill the complete previous season (GW1..max_gameweek) using public CSVs.

        Source: vaastav/Fantasy-Premier-League repository raw CSVs per GW.
        """
        # Derive previous season string (e.g., 2025-26 -> 2024-25)
        curr = self.season
        try:
            start_year = int(curr.split("-")[0])
            prev_start = start_year - 1
            prev_end = str(start_year)[-2:]
            prev_season = f"{prev_start}-{prev_end}"
        except Exception:
            # Fallback: assume last year
            prev_season = curr

        logger.info(f"Backfilling previous season from public dataset: {prev_season}")

        base_url = f"https://raw.githubusercontent.com/vaastav/Fantasy-Premier-League/master/data/{prev_season}/gws/gw{{gw}}.csv"

        async with AsyncSessionLocal() as db:
            # Build player and team mappings
            player_map_result = await db.execute(select(Player.id, Player.fpl_id))
            fpl_to_player = {fpl_id: pid for pid, fpl_id in player_map_result.all()}

            team_map_result = await db.execute(select(Team.id, Team.fpl_id))
            fpl_team_to_id = {fpl_id: tid for tid, fpl_id in team_map_result.all()}

            fixture_map_result = await db.execute(select(Fixture.id, Fixture.fpl_id))
            fpl_fixture_to_id = {
                fpl_id: fid for fid, fpl_id in fixture_map_result.all()
            }

        total_inserted = 0
        async with httpx.AsyncClient(timeout=30) as client:
            for gw in range(1, max_gameweek + 1):
                url = base_url.format(gw=gw)
                try:
                    resp = await client.get(url)
                    if resp.status_code != 200:
                        logger.warning(
                            f"GW{gw} dataset not found ({resp.status_code}): {url}"
                        )
                        continue
                    content = resp.content
                except Exception as e:
                    logger.warning(f"Failed to fetch GW{gw} CSV: {e}")
                    continue

                try:
                    df = pd.read_csv(pd.compat.StringIO(content.decode("utf-8")))
                except Exception:
                    # Fallback using io.StringIO
                    import io

                    df = pd.read_csv(io.StringIO(content.decode("utf-8")))

                # Normalize expected columns
                col = lambda name: name if name in df.columns else None

                # Required mappings
                required_cols = ["element", "minutes", "total_points"]
                if not all(c in df.columns for c in required_cols):
                    logger.warning(f"GW{gw} CSV missing required columns; skipping")
                    continue

                # Ingest in chunks
                rows = df.to_dict("records")
                batch = 0
                async with AsyncSessionLocal() as db:
                    for r in rows:
                        fpl_player_id = int(r.get("element"))
                        pid = fpl_to_player.get(fpl_player_id)
                        if not pid:
                            continue

                        fixture_fpl_id = r.get("fixture")
                        fixture_id = (
                            fpl_fixture_to_id.get(int(fixture_fpl_id))
                            if pd.notna(fixture_fpl_id)
                            else None
                        )
                        opp_team = r.get("opponent_team")
                        opponent_team_id = (
                            fpl_team_to_id.get(int(opp_team))
                            if pd.notna(opp_team)
                            else None
                        )

                        def fget(k, default=0.0):
                            v = r.get(k)
                            try:
                                if pd.isna(v):
                                    return default
                            except Exception:
                                pass
                            try:
                                return float(v)
                            except Exception:
                                try:
                                    return int(v)
                                except Exception:
                                    return default

                        was_home = (
                            bool(r.get("was_home"))
                            if "was_home" in df.columns
                            else False
                        )

                        # Manual upsert
                        upd = (
                            PlayerStatistic.__table__.update()
                            .where(
                                (PlayerStatistic.player_id == pid)
                                & (PlayerStatistic.gameweek == gw)
                                & (PlayerStatistic.season == prev_season)
                            )
                            .values(
                                fixture_id=fixture_id,
                                opponent_team_id=opponent_team_id,
                                was_home=was_home,
                                minutes=int(fget("minutes", 0)),
                                total_points=int(fget("total_points", 0)),
                                goals_scored=int(fget("goals_scored", 0)),
                                assists=int(fget("assists", 0)),
                                clean_sheets=int(fget("clean_sheets", 0)),
                                goals_conceded=int(fget("goals_conceded", 0)),
                                yellow_cards=int(fget("yellow_cards", 0)),
                                red_cards=int(fget("red_cards", 0)),
                                saves=int(fget("saves", 0)),
                                bonus=int(fget("bonus", 0)),
                                bps=int(fget("bps", 0)),
                                influence=fget("influence", 0.0),
                                creativity=fget("creativity", 0.0),
                                threat=fget("threat", 0.0),
                                ict_index=fget("ict_index", 0.0),
                                expected_goals=fget("expected_goals", fget("xG", 0.0)),
                                expected_assists=fget(
                                    "expected_assists", fget("xA", 0.0)
                                ),
                                expected_goal_involvements=fget(
                                    "expected_goal_involvements", fget("xGI", 0.0)
                                ),
                                expected_goals_conceded=fget(
                                    "expected_goals_conceded", fget("xGC", 0.0)
                                ),
                            )
                        )
                        res = await db.execute(upd)
                        if res.rowcount == 0:
                            ins = pg_insert(PlayerStatistic).values(
                                player_id=pid,
                                gameweek=gw,
                                season=prev_season,
                                fixture_id=fixture_id,
                                opponent_team_id=opponent_team_id,
                                was_home=was_home,
                                minutes=int(fget("minutes", 0)),
                                total_points=int(fget("total_points", 0)),
                                goals_scored=int(fget("goals_scored", 0)),
                                assists=int(fget("assists", 0)),
                                clean_sheets=int(fget("clean_sheets", 0)),
                                goals_conceded=int(fget("goals_conceded", 0)),
                                yellow_cards=int(fget("yellow_cards", 0)),
                                red_cards=int(fget("red_cards", 0)),
                                saves=int(fget("saves", 0)),
                                bonus=int(fget("bonus", 0)),
                                bps=int(fget("bps", 0)),
                                influence=fget("influence", 0.0),
                                creativity=fget("creativity", 0.0),
                                threat=fget("threat", 0.0),
                                ict_index=fget("ict_index", 0.0),
                                expected_goals=fget("expected_goals", fget("xG", 0.0)),
                                expected_assists=fget(
                                    "expected_assists", fget("xA", 0.0)
                                ),
                                expected_goal_involvements=fget(
                                    "expected_goal_involvements", fget("xGI", 0.0)
                                ),
                                expected_goals_conceded=fget(
                                    "expected_goals_conceded", fget("xGC", 0.0)
                                ),
                                created_at=datetime.utcnow(),
                            )
                            await db.execute(ins)

                        batch += 1
                        total_inserted += 1

                    await db.commit()
                logger.info(f"Backfilled GW{gw} ({batch} rows)")

        logger.info(f"Previous season backfill complete: {total_inserted} rows")
        return total_inserted
