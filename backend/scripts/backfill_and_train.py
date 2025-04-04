import os
import sys
import asyncio
from sqlalchemy import select, func

# Ensure backend root is on sys.path so `app` package can be imported
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_ROOT = os.path.dirname(CURRENT_DIR)
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from app.services.data_pipeline import DataPipeline
from app.ml.predictor_service import PredictorService
from app.db.database import AsyncSessionLocal
from app.db.models import PlayerStatistic


async def backfill_previous_season() -> str:
    dp = DataPipeline()
    curr = dp.season
    try:
        start = int(curr.split("-")[0])
        prev_season = f"{start-1}-{str(start)[-2:]}"
    except Exception:
        prev_season = curr

    print(
        f"[INFO] Starting previous-season backfill for {prev_season} (GW1-38)...",
        flush=True,
    )
    rows = await dp.backfill_last_season_from_public_dataset(38)
    print(
        f"[INFO] Backfill completed for {prev_season}. Rows ingested/updated: {rows}",
        flush=True,
    )
    return prev_season


async def count_stats(season: str) -> None:
    async with AsyncSessionLocal() as db:
        total = await db.execute(
            select(func.count())
            .select_from(PlayerStatistic)
            .where(PlayerStatistic.season == season)
        )
        max_gw = await db.execute(
            select(func.max(PlayerStatistic.gameweek)).where(
                PlayerStatistic.season == season
            )
        )
        print(
            f"[INFO] PlayerStatistic rows for {season}: {total.scalar()} | max_gw: {max_gw.scalar()}",
            flush=True,
        )


async def train_on_season(season: str) -> None:
    ps = PredictorService()
    print(f"[INFO] Training models on season {season}...", flush=True)
    try:
        metrics = await ps.train_models(seasons=[season])
        print(
            f"[INFO] Training complete. Samples: {metrics.get('training_samples')} | Model: {metrics.get('model_path')}",
            flush=True,
        )
    except Exception as e:
        print(f"[WARN] Training failed: {e}", flush=True)


async def main():
    season = await backfill_previous_season()
    await count_stats(season)
    await train_on_season(season)
    print("[DONE] Previous-season backfill and training finished.", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
