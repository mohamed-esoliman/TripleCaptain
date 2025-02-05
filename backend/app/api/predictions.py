from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import List, Optional

from app.db.database import get_async_session
from app.db.models import MLPrediction, Player
from app.core.dependencies import get_current_user_optional
from app.api.schemas import MLPredictionResponse
from app.ml.predictor_service import PredictorService
from app.services.fpl_client import get_season_string
from app.core.cache import cache_service, CacheKeys

router = APIRouter(prefix="/predictions", tags=["Predictions"])


@router.get("", response_model=List[MLPredictionResponse])
async def get_predictions(
    gameweek: int = Query(..., description="Gameweek number"),
    player_ids: Optional[List[int]] = Query(None, description="Filter by specific player IDs"),
    limit: int = Query(50, ge=1, le=500, description="Maximum number of predictions"),
    min_predicted_points: Optional[float] = Query(None, description="Minimum predicted points"),
    position: Optional[int] = Query(None, description="Filter by position"),
    db: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user_optional)
):
    """Get ML predictions for a gameweek."""
    
    season = get_season_string()
    
    # Build query
    query = select(MLPrediction).where(
        MLPrediction.gameweek == gameweek,
        MLPrediction.season == season
    )
    
    if player_ids:
        query = query.where(MLPrediction.player_id.in_(player_ids))
    
    if min_predicted_points:
        query = query.where(MLPrediction.predicted_points >= min_predicted_points)
    
    if position:
        # Join with Player to filter by position
        query = query.join(Player).where(Player.position == position)
    
    # Order by predicted points descending
    query = query.order_by(MLPrediction.predicted_points.desc()).limit(limit)
    
    result = await db.execute(query)
    predictions = result.scalars().all()
    
    return [MLPredictionResponse.from_orm(pred) for pred in predictions]


@router.get("/player/{player_id}/{gameweek}", response_model=MLPredictionResponse)
async def get_player_prediction(
    player_id: int,
    gameweek: int,
    db: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user_optional)
):
    """Get prediction for a specific player and gameweek."""
    
    season = get_season_string()
    
    result = await db.execute(
        select(MLPrediction).where(
            MLPrediction.player_id == player_id,
            MLPrediction.gameweek == gameweek,
            MLPrediction.season == season
        )
    )
    
    prediction = result.scalar_one_or_none()
    
    if not prediction:
        raise HTTPException(
            status_code=404, 
            detail=f"No prediction found for player {player_id} in gameweek {gameweek}"
        )
    
    return MLPredictionResponse.from_orm(prediction)


@router.post("/generate/{gameweek}")
async def generate_predictions(
    gameweek: int,
    player_ids: Optional[List[int]] = None,
    db: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user_optional)  # Could require admin role
):
    """Generate predictions for a gameweek (admin function)."""
    
    try:
        predictor_service = PredictorService()
        predictions_df = await predictor_service.generate_predictions(
            gameweek=gameweek,
            player_ids=player_ids,
            save_to_db=True
        )
        
        return {
            "message": f"Generated predictions for gameweek {gameweek}",
            "predictions_count": len(predictions_df),
            "gameweek": gameweek
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate predictions: {str(e)}"
        )


@router.get("/top-performers/{gameweek}")
async def get_top_performers(
    gameweek: int,
    limit: int = Query(20, ge=1, le=100, description="Number of top performers"),
    position: Optional[int] = Query(None, description="Filter by position"),
    db: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user_optional)
):
    """Get top predicted performers for a gameweek."""
    
    # Check cache first
    cache_key = CacheKeys.top_performers(gameweek, position)
    cached_result = await cache_service.get(cache_key)
    if cached_result:
        return cached_result
    
    season = get_season_string()
    
    # Build query with player details
    query = select(MLPrediction, Player).join(Player).where(
        MLPrediction.gameweek == gameweek,
        MLPrediction.season == season,
        Player.status == 'a'  # Only available players
    )
    
    if position:
        query = query.where(Player.position == position)
    
    query = query.order_by(MLPrediction.predicted_points.desc()).limit(limit)
    
    result = await db.execute(query)
    predictions_with_players = result.all()
    
    response_data = [
        {
            "player_id": prediction.player_id,
            "player_name": f"{player.first_name or ''} {player.second_name}".strip(),
            "web_name": player.web_name,
            "position": player.position,
            "team_id": player.team_id,
            "current_price": player.current_price / 10.0,  # Convert to millions
            "predicted_points": round(prediction.predicted_points, 1),
            "start_probability": round(prediction.start_probability, 2),
            "confidence_lower": round(prediction.confidence_lower, 1) if prediction.confidence_lower else None,
            "confidence_upper": round(prediction.confidence_upper, 1) if prediction.confidence_upper else None,
            "ceiling_points": round(prediction.ceiling_points, 1) if prediction.ceiling_points else None,
            "value_rating": round(prediction.predicted_points / (player.current_price / 10.0), 2)
        }
        for prediction, player in predictions_with_players
    ]
    
    # Cache for 30 minutes
    await cache_service.set(cache_key, response_data, expire=1800)
    
    return response_data


@router.get("/differentials/{gameweek}")
async def get_differentials(
    gameweek: int,
    max_ownership: float = Query(5.0, description="Maximum ownership percentage"),
    min_predicted_points: float = Query(4.0, description="Minimum predicted points"),
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user_optional)
):
    """Get differential players (low ownership, high predicted points)."""
    
    season = get_season_string()
    
    query = select(MLPrediction, Player).join(Player).where(
        MLPrediction.gameweek == gameweek,
        MLPrediction.season == season,
        MLPrediction.predicted_points >= min_predicted_points,
        Player.selected_by_percent <= max_ownership,
        Player.status == 'a'
    ).order_by(
        (MLPrediction.predicted_points / Player.selected_by_percent.nulls_last()).desc()
    ).limit(limit)
    
    result = await db.execute(query)
    differentials = result.all()
    
    return [
        {
            "player_id": prediction.player_id,
            "player_name": f"{player.first_name or ''} {player.second_name}".strip(),
            "web_name": player.web_name,
            "position": player.position,
            "team_id": player.team_id,
            "current_price": player.current_price / 10.0,
            "predicted_points": round(prediction.predicted_points, 1),
            "selected_by_percent": player.selected_by_percent,
            "differential_score": round(prediction.predicted_points / max(player.selected_by_percent, 0.1), 2)
        }
        for prediction, player in differentials
    ]


@router.get("/captain-options/{gameweek}")
async def get_captain_options(
    gameweek: int,
    limit: int = Query(10, ge=1, le=20),
    db: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user_optional)
):
    """Get best captain options for a gameweek."""
    
    season = get_season_string()
    
    # Get top predicted performers with good start probability
    query = select(MLPrediction, Player).join(Player).where(
        MLPrediction.gameweek == gameweek,
        MLPrediction.season == season,
        MLPrediction.start_probability >= 0.7,  # Likely to start
        Player.status == 'a'
    ).order_by(MLPrediction.predicted_points.desc()).limit(limit)
    
    result = await db.execute(query)
    captain_options = result.all()
    
    return [
        {
            "player_id": prediction.player_id,
            "player_name": f"{player.first_name or ''} {player.second_name}".strip(),
            "web_name": player.web_name,
            "position": player.position,
            "team_id": player.team_id,
            "predicted_points": round(prediction.predicted_points, 1),
            "expected_captain_points": round(prediction.predicted_points * 2, 1),
            "start_probability": round(prediction.start_probability, 2),
            "ceiling_points": round(prediction.ceiling_points * 2, 1) if prediction.ceiling_points else None,
            "variance": round(prediction.variance, 2) if prediction.variance else None,
            "risk_adjusted_score": round(
                prediction.predicted_points * 2 - (prediction.variance or 0) * 0.1, 1
            )
        }
        for prediction, player in captain_options
    ]


@router.get("/model-performance")
async def get_model_performance(
    gameweeks: int = Query(5, description="Number of recent gameweeks to evaluate"),
    db: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user_optional)
):
    """Get model performance metrics."""
    
    try:
        predictor_service = PredictorService()
        
        # This would need to be implemented in predictor_service
        # For now, return mock performance data
        return {
            "model_version": "1.0.0",
            "evaluation_period": f"Last {gameweeks} gameweeks",
            "metrics": {
                "mean_absolute_error": 2.1,
                "root_mean_square_error": 3.2,
                "r2_score": 0.28,
                "accuracy_within_2_points": 0.67,
                "start_prediction_accuracy": 0.84
            },
            "last_updated": "2024-01-15T10:30:00Z"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get model performance: {str(e)}"
        )