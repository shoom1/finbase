"""
Centralized configuration management for FinBase.

This module provides configuration settings for:
- Database paths and connection parameters
- Rate limiting for API calls
- Logging configuration
- Data validation thresholds

Configuration priority (highest to lowest):
1. Explicit parameters (e.g., CLI arguments)
2. User config file (~/.finbaserc)
3. Environment variables (FINBASE_*)
4. Default values
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import os


def _get_default_db_path() -> str:
    """
    Get the default database path from user config or fallback.

    Priority:
    1. User config file (~/.finbaserc)
    2. Fallback to ~/.finbase/timeseries.db

    Returns:
        Database path as string
    """
    try:
        from finbase.config.user_config import get_configured_db_path
        db_path = get_configured_db_path()
        return str(db_path)
    except Exception:
        # Fallback if user_config module fails
        return str(Path.home() / ".finbase" / "timeseries.db")


@dataclass
class DatabaseConfig:
    """Database configuration settings."""

    path: str = field(default_factory=lambda: _get_default_db_path())
    timeout: float = 30.0
    check_same_thread: bool = False
    max_retries: int = 3

    @property
    def full_path(self) -> Path:
        """Get full path to database file."""
        return Path(self.path).expanduser()


@dataclass
class RateLimitConfig:
    """Rate limiting configuration for data providers."""

    # YFinance rate limits
    yfinance_delay_seconds: float = 5.0
    yfinance_batch_size: int = 10
    yfinance_batch_pause: float = 30.0
    yfinance_max_retries: int = 3

    # Future: FRED API rate limits
    fred_requests_per_minute: int = 120
    fred_max_retries: int = 3

    # Future: Polygon.io rate limits
    polygon_requests_per_minute: int = 5
    polygon_max_retries: int = 3


@dataclass
class LoggingConfig:
    """Logging configuration settings."""

    log_dir: str = "logs"
    log_level: str = "INFO"
    console_output: bool = True
    file_output: bool = True
    max_log_size_mb: int = 10
    backup_count: int = 5

    @property
    def max_bytes(self) -> int:
        """Get max log size in bytes."""
        return self.max_log_size_mb * 1_000_000


@dataclass
class ValidationConfig:
    """Data validation configuration settings."""

    # Minimum data points required
    min_data_points: int = 100

    # Maximum percentage of missing business days allowed
    max_missing_pct: float = 0.10  # 10%

    # Maximum single-day return (absolute value)
    max_single_day_return: float = 0.50  # 50%

    # Require OHLC consistency
    validate_ohlc: bool = True

    # Detect outliers using standard deviations
    outlier_std_threshold: float = 5.0


@dataclass
class Settings:
    """Main application settings."""

    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    rate_limit: RateLimitConfig = field(default_factory=RateLimitConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    validation: ValidationConfig = field(default_factory=ValidationConfig)

    # Environment
    environment: str = field(default_factory=lambda: os.getenv('FINBASE_ENV', 'development'))

    @classmethod
    def load_from_env(cls) -> 'Settings':
        """
        Load settings from environment variables and user config.

        Configuration priority:
        1. Environment variables (if set)
        2. User config file (~/.finbaserc)
        3. Default values

        Environment variables:
            FINBASE_ENV: Environment name (development, production, test)
            FINBASE_DB_PATH: Database file path (overrides user config)
            FINBASE_LOG_LEVEL: Logging level (DEBUG, INFO, WARNING, ERROR)
            FINBASE_LOG_DIR: Log directory
            FINBASE_YFINANCE_DELAY: Delay between YFinance requests (seconds)
            FINBASE_YFINANCE_BATCH_SIZE: Batch size for YFinance requests
            FINBASE_YFINANCE_BATCH_PAUSE: Pause after each batch (seconds)

        Returns:
            Settings instance configured from environment
        """
        settings = cls()

        # Database settings
        if db_path := os.getenv('FINBASE_DB_PATH'):
            settings.database.path = db_path

        if db_timeout := os.getenv('FINBASE_DB_TIMEOUT'):
            settings.database.timeout = float(db_timeout)

        # Logging settings
        if log_level := os.getenv('FINBASE_LOG_LEVEL'):
            settings.logging.log_level = log_level.upper()

        if log_dir := os.getenv('FINBASE_LOG_DIR'):
            settings.logging.log_dir = log_dir

        # Rate limiting settings
        if yf_delay := os.getenv('FINBASE_YFINANCE_DELAY'):
            settings.rate_limit.yfinance_delay_seconds = float(yf_delay)

        if yf_batch_size := os.getenv('FINBASE_YFINANCE_BATCH_SIZE'):
            settings.rate_limit.yfinance_batch_size = int(yf_batch_size)

        if yf_batch_pause := os.getenv('FINBASE_YFINANCE_BATCH_PAUSE'):
            settings.rate_limit.yfinance_batch_pause = float(yf_batch_pause)

        return settings

    @classmethod
    def for_testing(cls) -> 'Settings':
        """
        Create settings optimized for testing.

        Returns:
            Settings instance for test environment
        """
        settings = cls()
        settings.environment = 'test'
        settings.database.path = ':memory:'
        settings.logging.console_output = False
        settings.logging.file_output = False
        settings.rate_limit.yfinance_delay_seconds = 0.0
        settings.rate_limit.yfinance_batch_pause = 0.0

        return settings


# Global settings instance
_settings: Optional[Settings] = None


def get_settings(reload: bool = False) -> Settings:
    """
    Get the global settings instance.

    Args:
        reload: Force reload settings from environment

    Returns:
        Global Settings instance
    """
    global _settings

    if _settings is None or reload:
        _settings = Settings.load_from_env()

    return _settings
