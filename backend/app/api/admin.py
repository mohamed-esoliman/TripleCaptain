from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, Optional

from app.db.database import get_async_session
from app.core.dependencies import get_current_user
from app.db.models import User
from app.services.background_tasks import task_manager
from app.core.cache import cache_service

router = APIRouter(prefix="/admin", tags=["Admin"])


# In a real application, you'd want proper admin role checking
async def get_admin_user(current_user: User = Depends(get_current_user)) -> User:
    """Get current user and verify admin privileges."""
    # For now, any authenticated user can access admin endpoints
    # In production, you'd check for admin role/permissions
    return current_user


@router.post("/tasks/{task_name}")
async def run_background_task(
    task_name: str,
    gameweek: Optional[int] = None,
    pattern: Optional[str] = None,
    admin_user: User = Depends(get_admin_user),
) -> Dict[str, Any]:
    """Manually trigger background tasks."""

    valid_tasks = ["data_sync", "generate_predictions", "train_models", "clear_cache"]

    if task_name not in valid_tasks:
        raise HTTPException(
            status_code=400, detail=f"Invalid task name. Valid tasks: {valid_tasks}"
        )

    kwargs = {}
    if gameweek is not None:
        kwargs["gameweek"] = gameweek
    if pattern is not None:
        kwargs["pattern"] = pattern

    result = await task_manager.run_manual_task(task_name, **kwargs)

    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result["message"])

    return result


@router.get("/cache/stats")
async def get_cache_stats(admin_user: User = Depends(get_admin_user)) -> Dict[str, Any]:
    """Get cache statistics and health."""

    try:
        # Check Redis health
        health = await cache_service.health_check()

        # Get Redis info (if accessible)
        redis_client = await cache_service.get_async_redis()
        info = await redis_client.info()

        return {
            "health": health,
            "redis_version": info.get("redis_version"),
            "used_memory": info.get("used_memory_human"),
            "connected_clients": info.get("connected_clients"),
            "total_commands_processed": info.get("total_commands_processed"),
            "keyspace": {
                db: info.get(f"db{db}", {}) for db in range(16) if info.get(f"db{db}")
            },
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get cache stats: {str(e)}"
        )


@router.delete("/cache")
async def clear_cache(
    pattern: str = "*", admin_user: User = Depends(get_admin_user)
) -> Dict[str, Any]:
    """Clear cache entries matching pattern."""

    try:
        cleared_count = await cache_service.clear_pattern(pattern)
        return {
            "message": f"Cleared {cleared_count} cache entries",
            "pattern": pattern,
            "cleared_count": cleared_count,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cache clear failed: {str(e)}")


@router.get("/health")
async def health_check(
    db: AsyncSession = Depends(get_async_session),
    admin_user: User = Depends(get_admin_user),
) -> Dict[str, Any]:
    """Comprehensive health check for all services."""

    health_status = {
        "status": "healthy",
        "timestamp": "2024-01-15T10:00:00Z",
        "services": {},
    }

    # Database health
    try:
        await db.execute("SELECT 1")
        health_status["services"]["database"] = {"status": "healthy"}
    except Exception as e:
        health_status["services"]["database"] = {"status": "unhealthy", "error": str(e)}
        health_status["status"] = "degraded"

    # Redis health
    try:
        redis_health = await cache_service.health_check()
        health_status["services"]["redis"] = {
            "status": "healthy" if redis_health else "unhealthy"
        }
        if not redis_health:
            health_status["status"] = "degraded"
    except Exception as e:
        health_status["services"]["redis"] = {"status": "unhealthy", "error": str(e)}
        health_status["status"] = "degraded"

    # FPL API health
    try:
        from app.services.fpl_client import FPLClient

        async with FPLClient() as client:
            # Try a simple API call
            bootstrap = await client.get_bootstrap_static()
            if bootstrap:
                health_status["services"]["fpl_api"] = {"status": "healthy"}
            else:
                health_status["services"]["fpl_api"] = {"status": "unhealthy"}
                health_status["status"] = "degraded"
    except Exception as e:
        health_status["services"]["fpl_api"] = {"status": "unhealthy", "error": str(e)}
        health_status["status"] = "degraded"

    return health_status


@router.get("/stats")
async def get_system_stats(
    db: AsyncSession = Depends(get_async_session),
    admin_user: User = Depends(get_admin_user),
) -> Dict[str, Any]:
    """Get system statistics."""

    try:
        from app.db.models import Player, Team, MLPrediction, User, PlayerStatistic
        from sqlalchemy import func, select

        # Get database counts
        stats = {}

        # Player count
        result = await db.execute(select(func.count(Player.id)))
        stats["total_players"] = result.scalar()

        # Team count
        result = await db.execute(select(func.count(Team.id)))
        stats["total_teams"] = result.scalar()

        # User count
        result = await db.execute(select(func.count(User.id)))
        stats["total_users"] = result.scalar()

        # Prediction count
        result = await db.execute(select(func.count(MLPrediction.id)))
        stats["total_predictions"] = result.scalar()

        # Statistics count
        result = await db.execute(select(func.count(PlayerStatistic.id)))
        stats["total_statistics"] = result.scalar()

        # Recent activity
        from datetime import datetime, timedelta

        one_day_ago = datetime.utcnow() - timedelta(days=1)

        result = await db.execute(
            select(func.count(User.id)).where(User.created_at >= one_day_ago)
        )
        stats["new_users_24h"] = result.scalar()

        return {
            "database_stats": stats,
            "api_version": "1.0.0",
            "environment": "development",
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")


@router.get("/logs/recent")
async def get_recent_logs(
    limit: int = 100, admin_user: User = Depends(get_admin_user)
) -> Dict[str, Any]:
    """Get recent system logs."""

    # In a real implementation, you'd read from actual log files
    # For now, return mock log data
    return {
        "message": "Log endpoint not implemented",
        "note": "In production, this would return recent application logs",
        "limit": limit,
    }
