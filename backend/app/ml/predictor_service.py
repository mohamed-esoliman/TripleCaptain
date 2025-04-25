import asyncio
import pandas as pd
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
import logging

from app.db.database import AsyncSessionLocal
from app.db.models import Player, PlayerStatistic, MLPrediction
from app.ml.feature_engineering import FeatureEngineer
from app.ml.models import MLPredictor
from app.services.fpl_client import get_season_string, get_current_gameweek
from app.core.config import settings

logger = logging.getLogger(__name__)


class PredictorService:
    """Service for managing ML predictions."""

    def __init__(self):
        self.feature_engineer = FeatureEngineer()
        self.predictor = MLPredictor()
        self.season = get_season_string()

    async def prepare_training_data(
        self,
        db: AsyncSession,
        seasons: List[str] = None,
        min_minutes_threshold: int = 30,
    ) -> pd.DataFrame:
        """Prepare historical training data for model training."""

        if seasons is None:
            seasons = [self.season]

        logger.info(f"Preparing training data for seasons: {seasons}")

        # Get all historical player statistics
        stats_query = (
            select(
                PlayerStatistic.player_id,
                PlayerStatistic.gameweek,
                PlayerStatistic.season,
                PlayerStatistic.minutes,
                PlayerStatistic.total_points,
                PlayerStatistic.goals_scored,
                PlayerStatistic.assists,
                PlayerStatistic.clean_sheets,
                PlayerStatistic.goals_conceded,
                PlayerStatistic.yellow_cards,
                PlayerStatistic.red_cards,
                PlayerStatistic.saves,
                PlayerStatistic.bonus,
                PlayerStatistic.bps,
                PlayerStatistic.influence,
                PlayerStatistic.creativity,
                PlayerStatistic.threat,
                PlayerStatistic.ict_index,
                PlayerStatistic.expected_goals,
                PlayerStatistic.expected_assists,
                PlayerStatistic.was_home,
                PlayerStatistic.starts,
            )
            .where(
                PlayerStatistic.season.in_(seasons),
                PlayerStatistic.minutes
                >= min_minutes_threshold,  # Only include games where player actually played
            )
            .order_by(
                PlayerStatistic.season,
                PlayerStatistic.gameweek,
                PlayerStatistic.player_id,
            )
        )

        result = await db.execute(stats_query)
        stats_data = result.all()

        if not stats_data:
            raise ValueError("No training data found")

        logger.info(f"Found {len(stats_data)} statistical records")

        # Convert to DataFrame
        stats_df = pd.DataFrame(
            [
                {
                    "player_id": row.player_id,
                    "gameweek": row.gameweek,
                    "season": row.season,
                    "minutes": row.minutes,
                    "total_points": row.total_points,
                    "goals_scored": row.goals_scored,
                    "assists": row.assists,
                    "clean_sheets": row.clean_sheets,
                    "goals_conceded": row.goals_conceded,
                    "yellow_cards": row.yellow_cards,
                    "red_cards": row.red_cards,
                    "saves": row.saves,
                    "bonus": row.bonus,
                    "bps": row.bps,
                    "influence": float(row.influence),
                    "creativity": float(row.creativity),
                    "threat": float(row.threat),
                    "ict_index": float(row.ict_index),
                    "expected_goals": float(row.expected_goals),
                    "expected_assists": float(row.expected_assists),
                    "was_home": row.was_home,
                    "starts": row.starts,
                }
                for row in stats_data
            ]
        )

        # Build features purely in pandas to avoid per-row DB calls (prevents greenlet issues)
        records: List[Dict[str, Any]] = []

        for (player_id, season), g in stats_df.groupby(["player_id", "season"]):
            g = g.sort_values("gameweek").reset_index(drop=True)

            # Shifted to use ONLY past games for features
            tp_shift = g["total_points"].shift(1)
            min_shift = g["minutes"].shift(1)
            starts_shift = g["starts"].shift(1)
            goals_shift = g["goals_scored"].shift(1)
            assists_shift = g["assists"].shift(1)
            bonus_shift = g["bonus"].shift(1)
            bps_shift = g["bps"].shift(1)
            infl_shift = g["influence"].shift(1)
            crea_shift = g["creativity"].shift(1)
            thr_shift = g["threat"].shift(1)
            ict_shift = g["ict_index"].shift(1)

            # Rolling windows over past games
            points_last_3 = tp_shift.rolling(3, min_periods=1).sum().fillna(0)
            points_last_5 = tp_shift.rolling(5, min_periods=1).sum().fillna(0)
            avg_points_last_5 = tp_shift.rolling(5, min_periods=1).mean().fillna(0)
            avg_minutes_last_5 = min_shift.rolling(5, min_periods=1).mean().fillna(0)
            games_started_last_5 = (
                starts_shift.rolling(5, min_periods=1).sum().fillna(0)
            )

            # Per-90 estimates from last 10 games
            goals_last_10 = goals_shift.rolling(10, min_periods=1).sum().fillna(0)
            assists_last_10 = assists_shift.rolling(10, min_periods=1).sum().fillna(0)
            minutes_last_10 = (
                min_shift.rolling(10, min_periods=1).sum().replace(0, np.nan)
            )
            goals_per_90 = (goals_last_10 * 90.0 / minutes_last_10).fillna(0)
            assists_per_90 = (assists_last_10 * 90.0 / minutes_last_10).fillna(0)
            points_per_90 = (
                tp_shift.rolling(10, min_periods=1).sum() * 90.0 / minutes_last_10
            ).fillna(0)

            avg_bps = bps_shift.rolling(5, min_periods=1).mean().fillna(0)
            avg_influence = infl_shift.rolling(5, min_periods=1).mean().fillna(0)
            avg_creativity = crea_shift.rolling(5, min_periods=1).mean().fillna(0)
            avg_threat = thr_shift.rolling(5, min_periods=1).mean().fillna(0)
            avg_ict = ict_shift.rolling(5, min_periods=1).mean().fillna(0)

            for i, row in g.iterrows():
                records.append(
                    {
                        # identifiers + target
                        "player_id": int(player_id),
                        "season": season,
                        "gameweek": int(row["gameweek"]),
                        "total_points": float(row["total_points"]),
                        # recent form features (past-only)
                        "points_last_3": float(points_last_3.iloc[i]),
                        "points_last_5": float(points_last_5.iloc[i]),
                        "avg_points_last_5": float(avg_points_last_5.iloc[i]),
                        "avg_minutes_last_5": float(avg_minutes_last_5.iloc[i]),
                        "games_started_last_5": float(games_started_last_5.iloc[i]),
                        # per-90 recent rates
                        "goals_per_90": float(goals_per_90.iloc[i]),
                        "assists_per_90": float(assists_per_90.iloc[i]),
                        "points_per_90": float(points_per_90.iloc[i]),
                        # simple aggregates/means
                        "avg_bps": float(avg_bps.iloc[i]),
                        "avg_influence": float(avg_influence.iloc[i]),
                        "avg_creativity": float(avg_creativity.iloc[i]),
                        "avg_threat": float(avg_threat.iloc[i]),
                        "avg_ict_index": float(avg_ict.iloc[i]),
                        # current match simple inputs (allowed; models will learn mapping)
                        "minutes": float(row["minutes"]),
                        "goals_scored": float(row["goals_scored"]),
                        "assists": float(row["assists"]),
                        "clean_sheets": float(row["clean_sheets"]),
                        "goals_conceded": float(row["goals_conceded"]),
                        "bonus": float(row["bonus"]),
                        "bps": float(row["bps"]),
                        "was_home": 1.0 if bool(row["was_home"]) else 0.0,
                        "starts": float(row["starts"]),
                    }
                )

        training_df = pd.DataFrame(records)
        logger.info(
            f"Generated training data with {len(training_df)} records and {len(training_df.columns)} features"
        )

        return training_df

    async def train_models(
        self,
        training_data: Optional[pd.DataFrame] = None,
        seasons: Optional[List[str]] = None,
    ) -> Dict[str, Dict[str, float]]:
        """Train all ML models."""

        async with AsyncSessionLocal() as db:
            if training_data is None:
                # Prepare training data from database
                training_data = await self.prepare_training_data(db, seasons=seasons)

            logger.info("Starting model training")

            # Train points predictor
            points_metrics = self.predictor.train_points_predictor(training_data)

            # Train minutes predictor
            minutes_metrics = self.predictor.train_minutes_predictor(training_data)

            # Train quantile models
            quantile_metrics = self.predictor.train_quantile_models(training_data)

            # Save trained models
            model_path = self.predictor.save_models()

            metrics = {
                "points": points_metrics,
                "minutes": minutes_metrics,
                **quantile_metrics,
                "model_path": model_path,
                "training_samples": len(training_data),
            }

            logger.info("Model training completed successfully")
            return metrics

    async def generate_predictions(
        self,
        gameweek: int,
        player_ids: Optional[List[int]] = None,
        save_to_db: bool = True,
    ) -> pd.DataFrame:
        """Generate predictions for a specific gameweek."""

        async with AsyncSessionLocal() as db:
            logger.info(f"Generating predictions for gameweek {gameweek}")

            # Generate features for all players
            features_df = await self.feature_engineer.get_all_player_features(
                db, gameweek, player_ids
            )

            if features_df.empty:
                logger.warning(f"No features generated for gameweek {gameweek}")
                # Fallback heuristic predictions when models/features unavailable
                fallback_df = await self._generate_fallback_predictions(
                    db, gameweek, player_ids
                )
                if save_to_db and not fallback_df.empty:
                    await self._save_predictions_to_db(db, fallback_df)
                return fallback_df

            # Load models if not already loaded
            if not self.predictor.models:
                model_path = f"models/fpl_predictor_{settings.MODEL_VERSION}.joblib"
                try:
                    self.predictor.load_models(model_path)
                except FileNotFoundError:
                    logger.warning(
                        f"Model file not found: {model_path}. Falling back to heuristic predictions."
                    )
                    fallback_df = await self._generate_fallback_predictions(
                        db, gameweek, player_ids
                    )
                    if save_to_db and not fallback_df.empty:
                        await self._save_predictions_to_db(db, fallback_df)
                    return fallback_df

            # Make predictions
            predictions_df = self.predictor.predict(features_df)

            if save_to_db:
                await self._save_predictions_to_db(db, predictions_df)

            logger.info(f"Generated predictions for {len(predictions_df)} players")
            return predictions_df

    async def _save_predictions_to_db(
        self, db: AsyncSession, predictions_df: pd.DataFrame
    ) -> None:
        """Save predictions to database."""

        logger.info(f"Saving {len(predictions_df)} predictions to database")

        for _, row in predictions_df.iterrows():
            player_id = int(row["player_id"])
            gameweek = int(row["gameweek"])

            # Try update first (manual upsert to avoid unique constraint requirement)
            update_stmt = (
                MLPrediction.__table__.update()
                .where(
                    (MLPrediction.player_id == player_id)
                    & (MLPrediction.gameweek == gameweek)
                    & (MLPrediction.season == self.season)
                )
                .values(
                    predicted_points=float(row.get("predicted_points", 0)),
                    confidence_lower=(
                        float(row.get("confidence_lower", 0))
                        if pd.notna(row.get("confidence_lower"))
                        else None
                    ),
                    confidence_upper=(
                        float(row.get("confidence_upper", 0))
                        if pd.notna(row.get("confidence_upper"))
                        else None
                    ),
                    start_probability=float(row.get("start_probability", 0.5)),
                    predicted_minutes=float(row.get("predicted_minutes", 0)),
                    ceiling_points=(
                        float(row.get("ceiling_points", 0))
                        if pd.notna(row.get("ceiling_points"))
                        else None
                    ),
                    floor_points=(
                        float(row.get("floor_points", 0))
                        if pd.notna(row.get("floor_points"))
                        else None
                    ),
                    variance=(
                        float(row.get("variance", 0))
                        if pd.notna(row.get("variance"))
                        else None
                    ),
                    model_version=self.predictor.model_version,
                    created_at=datetime.utcnow(),
                )
            )
            result = await db.execute(update_stmt)

            if result.rowcount == 0:
                # Insert if nothing updated
                insert_stmt = pg_insert(MLPrediction).values(
                    player_id=player_id,
                    gameweek=gameweek,
                    season=self.season,
                    predicted_points=float(row.get("predicted_points", 0)),
                    confidence_lower=(
                        float(row.get("confidence_lower", 0))
                        if pd.notna(row.get("confidence_lower"))
                        else None
                    ),
                    confidence_upper=(
                        float(row.get("confidence_upper", 0))
                        if pd.notna(row.get("confidence_upper"))
                        else None
                    ),
                    start_probability=float(row.get("start_probability", 0.5)),
                    predicted_minutes=float(row.get("predicted_minutes", 0)),
                    ceiling_points=(
                        float(row.get("ceiling_points", 0))
                        if pd.notna(row.get("ceiling_points"))
                        else None
                    ),
                    floor_points=(
                        float(row.get("floor_points", 0))
                        if pd.notna(row.get("floor_points"))
                        else None
                    ),
                    variance=(
                        float(row.get("variance", 0))
                        if pd.notna(row.get("variance"))
                        else None
                    ),
                    model_version=self.predictor.model_version,
                    features={},
                    created_at=datetime.utcnow(),
                )
                await db.execute(insert_stmt)

        await db.commit()
        logger.info("Predictions saved successfully")

    async def _generate_fallback_predictions(
        self, db: AsyncSession, gameweek: int, player_ids: Optional[List[int]] = None
    ) -> pd.DataFrame:
        """Generate simple heuristic predictions when ML models/feature data are unavailable."""
        from app.db.models import Player

        query = select(Player)
        if player_ids:
            query = query.where(Player.id.in_(player_ids))
        result = await db.execute(query)
        players = result.scalars().all()

        rows: List[Dict[str, Any]] = []
        for p in players:
            if p.status != "a":
                sp = float(
                    (p.chance_playing_this or p.chance_playing_next or 0) / 100.0
                )
            else:
                sp = float(
                    (p.chance_playing_this or p.chance_playing_next or 80) / 100.0
                )

            base = p.ep_next or p.ep_this or (p.form or 0.0)
            try:
                pp = float(base)
            except Exception:
                pp = 0.0

            pm = sp * 90.0
            ceiling = pp * 1.6
            floor = max(0.0, pp * 0.4)
            var = ((ceiling - floor) / 4.0) ** 2

            rows.append(
                {
                    "player_id": p.id,
                    "gameweek": gameweek,
                    "predicted_points": pp,
                    "start_probability": min(1.0, max(0.0, sp)),
                    "predicted_minutes": pm,
                    "ceiling_points": ceiling,
                    "floor_points": floor,
                    "variance": var,
                    "model_version": self.predictor.model_version,
                }
            )

        df = pd.DataFrame(rows)
        return df

    async def get_predictions(
        self, db: AsyncSession, gameweek: int, player_ids: Optional[List[int]] = None
    ) -> List[MLPrediction]:
        """Get predictions from database."""

        query = select(MLPrediction).where(
            MLPrediction.gameweek == gameweek, MLPrediction.season == self.season
        )

        if player_ids:
            query = query.where(MLPrediction.player_id.in_(player_ids))

        result = await db.execute(query.order_by(MLPrediction.predicted_points.desc()))
        return result.scalars().all()

    async def update_predictions_for_current_gameweek(self) -> Dict[str, Any]:
        """Update predictions for the current gameweek."""

        async with AsyncSessionLocal() as db:
            # Get current gameweek from FPL API data
            from app.services.fpl_client import FPLClient

            async with FPLClient() as fpl_client:
                bootstrap_data = await fpl_client.get_bootstrap_static()
                current_gw = get_current_gameweek(bootstrap_data["events"])

            if not current_gw:
                logger.warning("Could not determine current gameweek")
                return {"error": "Current gameweek not found"}

            # Generate predictions
            predictions_df = await self.generate_predictions(current_gw)

            return {
                "gameweek": current_gw,
                "predictions_generated": len(predictions_df),
                "model_version": self.predictor.model_version,
            }

    async def evaluate_model_performance(
        self, gameweek: int, seasons: Optional[List[str]] = None
    ) -> Dict[str, float]:
        """Evaluate model performance against actual results."""

        if seasons is None:
            seasons = [self.season]

        async with AsyncSessionLocal() as db:
            # Get predictions and actual results
            query = (
                select(
                    MLPrediction.player_id,
                    MLPrediction.gameweek,
                    MLPrediction.predicted_points,
                    MLPrediction.start_probability,
                    PlayerStatistic.total_points,
                    PlayerStatistic.minutes,
                )
                .join(
                    PlayerStatistic,
                    (MLPrediction.player_id == PlayerStatistic.player_id)
                    & (MLPrediction.gameweek == PlayerStatistic.gameweek)
                    & (MLPrediction.season == PlayerStatistic.season),
                )
                .where(
                    MLPrediction.gameweek == gameweek, MLPrediction.season.in_(seasons)
                )
            )

            result = await db.execute(query)
            evaluation_data = result.all()

            if not evaluation_data:
                return {"error": "No evaluation data found"}

            # Calculate metrics
            predicted_points = [row.predicted_points for row in evaluation_data]
            actual_points = [row.total_points for row in evaluation_data]
            predicted_starts = [row.start_probability for row in evaluation_data]
            actual_starts = [
                1.0 if row.minutes > 60 else 0.0 for row in evaluation_data
            ]

            from sklearn.metrics import (
                mean_absolute_error,
                mean_squared_error,
                r2_score,
            )

            points_mae = mean_absolute_error(actual_points, predicted_points)
            points_rmse = np.sqrt(mean_squared_error(actual_points, predicted_points))
            points_r2 = r2_score(actual_points, predicted_points)

            starts_mae = mean_absolute_error(actual_starts, predicted_starts)
            starts_accuracy = np.mean(
                (np.array(predicted_starts) > 0.5) == np.array(actual_starts)
            )

            return {
                "gameweek": gameweek,
                "samples": len(evaluation_data),
                "points_mae": float(points_mae),
                "points_rmse": float(points_rmse),
                "points_r2": float(points_r2),
                "starts_mae": float(starts_mae),
                "starts_accuracy": float(starts_accuracy),
            }
