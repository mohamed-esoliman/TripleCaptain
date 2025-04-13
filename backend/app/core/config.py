from pydantic_settings import BaseSettings
from typing import List, Optional
import os


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "TripleCaptain API"
    VERSION: str = "1.0.0"
    DESCRIPTION: str = "Fantasy Premier League optimization platform API"
    DEBUG: bool = True
    ENVIRONMENT: str = "development"
    
    # Database
    DATABASE_URL: str = "postgresql://postgres:password@localhost:5432/triplecaptain"
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379"
    
    # Security
    JWT_SECRET: str = "your-super-secret-jwt-key-change-this-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # CORS
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    
    # FPL API
    FPL_BASE_URL: str = "https://fantasy.premierleague.com/api/"
    
    # Cache settings
    CACHE_TTL_PLAYERS: int = 86400  # 24 hours
    CACHE_TTL_PREDICTIONS: int = 604800  # 1 week
    CACHE_TTL_OPTIMIZATION: int = 86400  # 24 hours
    
    # ML Model settings
    MODEL_VERSION: str = "1.0.0"
    RETRAIN_THRESHOLD_GAMES: int = 5  # Retrain after 5 new gameweeks
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()