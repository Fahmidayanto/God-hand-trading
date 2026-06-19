"""Application configuration."""

from functools import lru_cache
from typing import List, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",  # Ignore extra fields from .env
    )

    # Application
    APP_NAME: str = "God Hand Trading Backend"
    APP_VERSION: str = "1.0.0"
    APP_ENV: str = "development"
    DEBUG: bool = True

    # API
    API_V1_PREFIX: str = "/api/v1"
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000

    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:1420",  # React Router (Vite)
        "http://localhost:5173",  # Vite default
        "http://localhost:3000",  # Alternative
        "http://127.0.0.1:1420",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
        "file://",  # For local HTML files
    ]

    # MT5
    MT5_LOGIN: int = 108186726
    MT5_PASSWORD: str = "J-Ys7lDg"
    MT5_SERVER: str = "MetaQuotes-Demo"
    MT5_PATH: str = "C:/Program Files/MetaTrader 5/terminal64.exe"
    MT5_TIMEOUT: int = 60000  # milliseconds
    # Broker timezone offset from UTC (e.g., 3 for GMT+3, 2 for GMT+2, -5 for GMT-5)
    # MT5 timestamps are in broker server time; convert to UTC for chart consistency
    MT5_BROKER_TIMEZONE_OFFSET: int = 3
    
    # Chart display timezone: 'utc' | 'broker' | 'local'
    # - 'utc': Show UTC time (default, consistent across users)
    # - 'broker': Show broker server time (MT5 native)
    # - 'local': Show user's browser local time
    CHART_TIMEZONE_DISPLAY: str = "utc"

    # Trading
    TRADING_SYMBOL: str = "XAUUSD"
    TRADING_MODE: str = "paper"  # paper or live
    MAX_RISK_PER_TRADE: float = 0.02
    MAX_DAILY_LOSS: float = 0.03
    MAX_OPEN_POSITIONS: int = 3

    # Database (Legacy SQLite — kept for reference)
    DATABASE_URL: str = "sqlite:///./godhand.db"
    DATABASE_ECHO: bool = False

    # Neon PostgreSQL (Track 1 & Track 2 persistence)
    PGHOST: str = ""
    PGDATABASE: str = "neondb"
    PGUSER: str = ""
    PGPASSWORD: str = ""
    PGSSLMODE: str = "require"

    # Track 1 pipeline
    TRACK1_INTERVAL_SECONDS: int = 30   # How often to sync data (seconds)

    # Security
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # Redis (for caching and WebSocket)
    REDIS_URL: str = "redis://localhost:6379/0"
    CACHE_TTL: int = 300  # seconds

    # Telegram
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""

    # Agents
    CONSENSUS_THRESHOLD: float = 0.70
    AGENT_WEIGHT_STRUCTURE: float = 0.35
    AGENT_WEIGHT_ML: float = 0.30
    AGENT_WEIGHT_RISK: float = 0.20
    AGENT_WEIGHT_SENTIMENT: float = 0.15


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
