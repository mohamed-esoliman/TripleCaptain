import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any
from contextlib import asynccontextmanager

from app.services.data_pipeline import DataPipeline
from app.services.fpl_client import FPLClient, get_current_gameweek, get_season_string
from app.ml.predictor_service import PredictorService
from app.core.cache import cache_service
from app.core.config import settings

logger = logging.getLogger(__name__)


class BackgroundTaskManager:
    """Manages background tasks for data updates and model training."""

    def __init__(self):
        self.running_tasks = set()
        self.task_schedules = {}
        self.data_pipeline = DataPipeline()
        self.predictor_service = PredictorService()

    async def start_scheduled_tasks(self):
        """Start all scheduled background tasks."""
        logger.info("Starting background task manager...")

        # Schedule daily data updates
        self.running_tasks.add(asyncio.create_task(self._run_daily_data_update()))

        # Schedule hourly prediction updates
        self.running_tasks.add(
            asyncio.create_task(self._run_hourly_prediction_update())
        )

        # Schedule cache cleanup
        self.running_tasks.add(asyncio.create_task(self._run_cache_cleanup()))

        # Schedule model performance monitoring
        self.running_tasks.add(asyncio.create_task(self._run_model_monitoring()))

        logger.info(f"Started {len(self.running_tasks)} background tasks")

    async def stop_scheduled_tasks(self):
        """Stop all scheduled background tasks."""
        logger.info("Stopping background tasks...")

        for task in self.running_tasks:
            task.cancel()

        await asyncio.gather(*self.running_tasks, return_exceptions=True)
        self.running_tasks.clear()

        logger.info("All background tasks stopped")

    async def _run_daily_data_update(self):
        """Run daily data synchronization from FPL API."""
        while True:
            try:
                await self._daily_data_update()
                # Sleep until next day at 6 AM
                now = datetime.now()
                next_run = now.replace(hour=6, minute=0, second=0, microsecond=0)
                if next_run <= now:
                    next_run += timedelta(days=1)

                sleep_seconds = (next_run - now).total_seconds()
                await asyncio.sleep(sleep_seconds)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Daily data update failed: {e}")
                # Wait 1 hour before retrying
                await asyncio.sleep(3600)

    async def _daily_data_update(self):
        """Perform daily data synchronization."""
        logger.info("Starting daily data update...")

        try:
            # Sync basic data (teams, players, fixtures)
            results = await self.data_pipeline.daily_update()
            logger.info(f"Daily data update completed: {results}")

            # Check if there are new gameweek results to process
            async with FPLClient() as fpl_client:
                bootstrap_data = await fpl_client.get_bootstrap_static()
                events = bootstrap_data.get("events", [])

                # Look for recently finished gameweeks
                for event in events:
                    if event.get("finished") and event.get("data_checked"):
                        gameweek = event["id"]

                        # Check if we have detailed stats for this gameweek
                        await self._process_gameweek_completion(gameweek)

            # Clear relevant caches after data update
            await self._clear_data_caches()

        except Exception as e:
            logger.error(f"Daily data update failed: {e}")
            raise

    async def _process_gameweek_completion(self, gameweek: int):
        """Process completion of a gameweek."""
        logger.info(f"Processing gameweek {gameweek} completion...")

        try:
            # Update player statistics from live data
            async with FPLClient() as fpl_client:
                await self.data_pipeline.update_player_statistics_for_gameweek(
                    fpl_client, gameweek
                )

            # Generate predictions for next gameweek
            next_gameweek = gameweek + 1
            if next_gameweek <= 38:  # Premier League has 38 gameweeks
                await self._generate_predictions_for_gameweek(next_gameweek)

            logger.info(f"Gameweek {gameweek} processing completed")

        except Exception as e:
            logger.error(f"Gameweek {gameweek} processing failed: {e}")

    async def _run_hourly_prediction_update(self):
        """Update predictions every hour during active periods."""
        while True:
            try:
                await self._update_current_predictions()
                await asyncio.sleep(3600)  # 1 hour

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Hourly prediction update failed: {e}")
                await asyncio.sleep(3600)

    async def _update_current_predictions(self):
        """Update predictions for current and next gameweek."""
        logger.info("Updating current predictions...")

        try:
            async with FPLClient() as fpl_client:
                bootstrap_data = await fpl_client.get_bootstrap_static()
                current_gw = get_current_gameweek(bootstrap_data.get("events", []))

                if current_gw:
                    # Ensure stats are ingested for the most recent finished GW
                    for event in bootstrap_data.get("events", []):
                        if (
                            event.get("finished")
                            and event.get("data_checked")
                            and event["id"] == current_gw - 1
                        ):
                            try:
                                await self.data_pipeline.update_player_statistics_for_gameweek(
                                    fpl_client, event["id"]
                                )
                            except Exception as e:
                                logger.warning(
                                    f"Stats ingestion during prediction update failed: {e}"
                                )
                    # Update predictions for current gameweek
                    await self._generate_predictions_for_gameweek(current_gw)

                    # Update predictions for next gameweek if not too far ahead
                    if current_gw < 38:
                        await self._generate_predictions_for_gameweek(current_gw + 1)

                    # Clear prediction caches
                    await self._clear_prediction_caches(current_gw)

        except Exception as e:
            logger.error(f"Prediction update failed: {e}")

    async def _generate_predictions_for_gameweek(self, gameweek: int):
        """Generate ML predictions for a specific gameweek."""
        logger.info(f"Generating predictions for gameweek {gameweek}...")

        try:
            predictions_df = await self.predictor_service.generate_predictions(
                gameweek=gameweek, save_to_db=True
            )
            logger.info(f"Generated {len(predictions_df)} predictions for GW{gameweek}")

        except Exception as e:
            logger.error(f"Prediction generation for GW{gameweek} failed: {e}")

    async def _run_cache_cleanup(self):
        """Run cache cleanup every few hours."""
        while True:
            try:
                await self._cleanup_expired_cache()
                await asyncio.sleep(7200)  # 2 hours

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cache cleanup failed: {e}")
                await asyncio.sleep(7200)

    async def _cleanup_expired_cache(self):
        """Clean up expired cache entries."""
        logger.info("Cleaning up expired cache entries...")

        try:
            # Clean up optimization cache (older than 1 day)
            await cache_service.clear_pattern("optimization:*")

            # Clean up old prediction caches
            current_gw = 1  # This should be determined from current state
            for old_gw in range(max(1, current_gw - 5), current_gw):
                await cache_service.clear_pattern(f"*gw{old_gw}*")

            logger.info("Cache cleanup completed")

        except Exception as e:
            logger.error(f"Cache cleanup failed: {e}")

    async def _run_model_monitoring(self):
        """Monitor model performance and trigger retraining if needed."""
        while True:
            try:
                await self._monitor_model_performance()
                await asyncio.sleep(86400)  # 24 hours

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Model monitoring failed: {e}")
                await asyncio.sleep(86400)

    async def _monitor_model_performance(self):
        """Monitor and evaluate model performance."""
        logger.info("Monitoring model performance...")

        try:
            # Evaluate model performance for recent gameweeks
            recent_gameweeks = [1, 2, 3]  # This should be determined dynamically

            total_mae = 0
            total_samples = 0

            for gameweek in recent_gameweeks:
                performance = await self.predictor_service.evaluate_model_performance(
                    gameweek
                )
                if "samples" in performance and performance["samples"] > 0:
                    total_mae += (
                        performance.get("points_mae", 0) * performance["samples"]
                    )
                    total_samples += performance["samples"]

            if total_samples > 0:
                avg_mae = total_mae / total_samples
                logger.info(f"Average MAE across recent gameweeks: {avg_mae:.2f}")

                # Trigger retraining if performance degrades significantly
                if avg_mae > 3.0:  # Threshold for poor performance
                    logger.warning(
                        "Model performance degraded, considering retraining..."
                    )
                    # In a full implementation, this would trigger model retraining

        except Exception as e:
            logger.error(f"Model monitoring failed: {e}")

    async def _clear_data_caches(self):
        """Clear caches related to player and team data."""
        try:
            await cache_service.clear_pattern("players:*")
            await cache_service.clear_pattern("player:*")
            await cache_service.clear_pattern("team:*")
            logger.info("Data caches cleared")
        except Exception as e:
            logger.error(f"Failed to clear data caches: {e}")

    async def _clear_prediction_caches(self, gameweek: int):
        """Clear prediction-related caches."""
        try:
            await cache_service.clear_pattern(f"*gw{gameweek}*")
            await cache_service.clear_pattern("top_performers:*")
            await cache_service.clear_pattern("captain_options:*")
            await cache_service.clear_pattern("differentials:*")
            logger.info(f"Prediction caches cleared for GW{gameweek}")
        except Exception as e:
            logger.error(f"Failed to clear prediction caches: {e}")

    async def run_manual_task(self, task_name: str, **kwargs) -> Dict[str, Any]:
        """Run a background task manually (for admin endpoints)."""
        logger.info(f"Running manual task: {task_name}")

        try:
            if task_name == "data_sync":
                results = await self.data_pipeline.full_data_sync()
                return {"status": "success", "results": results}

            elif task_name == "generate_predictions":
                gameweek = kwargs.get("gameweek", 1)
                predictions_df = await self.predictor_service.generate_predictions(
                    gameweek
                )
                return {
                    "status": "success",
                    "gameweek": gameweek,
                    "predictions_count": len(predictions_df),
                }

            elif task_name == "train_models":
                metrics = await self.predictor_service.train_models()
                return {"status": "success", "metrics": metrics}

            elif task_name == "clear_cache":
                pattern = kwargs.get("pattern", "*")
                count = await cache_service.clear_pattern(pattern)
                return {"status": "success", "cleared_keys": count}

            else:
                return {"status": "error", "message": f"Unknown task: {task_name}"}

        except Exception as e:
            logger.error(f"Manual task {task_name} failed: {e}")
            return {"status": "error", "message": str(e)}


# Global task manager instance
task_manager = BackgroundTaskManager()
