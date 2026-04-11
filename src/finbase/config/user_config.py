"""
User configuration management for FinBase.

Manages persistent user configuration stored in ~/.finbaserc (YAML format).
Handles database path configuration and user space directory setup.
"""

import yaml
from pathlib import Path
from typing import Optional, Dict, Any
from finbase.utils.logging import get_logger

logger = get_logger(__name__)

# Default paths
DEFAULT_CONFIG_PATH = Path.home() / ".finbaserc"
DEFAULT_USER_SPACE = Path.home() / ".finbase"
DEFAULT_DB_PATH = DEFAULT_USER_SPACE / "timeseries.db"


class UserConfig:
    """Manages user configuration in ~/.finbaserc (YAML format)."""

    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize user configuration.

        Args:
            config_path: Path to config file (defaults to ~/.finbaserc)
        """
        self.config_path = config_path or DEFAULT_CONFIG_PATH
        self._config = self._load()

    def _load(self) -> Dict[str, Any]:
        """
        Load configuration from YAML file.

        Returns:
            Dict containing configuration, or empty dict if file doesn't exist
        """
        if not self.config_path.exists():
            logger.info(f"Config file not found at {self.config_path}, using defaults")
            return {}

        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)
                if config is None:
                    logger.warning(f"Config file {self.config_path} is empty")
                    return {}
                logger.info(f"Loaded config from {self.config_path}")
                return config
        except yaml.YAMLError as e:
            logger.error(f"Failed to parse YAML config file {self.config_path}: {e}")
            return {}
        except Exception as e:
            logger.error(f"Failed to read config file {self.config_path}: {e}")
            return {}

    def _save(self) -> None:
        """Save configuration to YAML file."""
        try:
            # Create parent directory if needed
            self.config_path.parent.mkdir(parents=True, exist_ok=True)

            with open(self.config_path, 'w') as f:
                yaml.safe_dump(
                    self._config,
                    f,
                    default_flow_style=False,
                    sort_keys=False,
                    indent=2
                )
            logger.info(f"Saved config to {self.config_path}")
        except Exception as e:
            logger.error(f"Failed to save config to {self.config_path}: {e}")
            raise

    def get_db_path(self) -> Optional[Path]:
        """
        Get database path from configuration.

        Returns:
            Path to database file, or None if not configured
        """
        db_path_str = self._config.get('database', {}).get('path')
        if db_path_str:
            return Path(db_path_str).expanduser()
        return None

    def set_db_path(self, db_path: Path) -> None:
        """
        Set database path in configuration.

        Args:
            db_path: Path to database file
        """
        if 'database' not in self._config:
            self._config['database'] = {}

        # Store as string for YAML serialization
        self._config['database']['path'] = str(db_path)
        self._save()
        logger.info(f"Set database path to: {db_path}")

    def get_all(self) -> Dict[str, Any]:
        """
        Get all configuration.

        Returns:
            Dict containing all configuration
        """
        return self._config.copy()

    def set(self, key: str, value: Any) -> None:
        """
        Set a configuration value.

        Args:
            key: Configuration key (supports nested keys with dots, e.g. 'database.path')
            value: Configuration value
        """
        keys = key.split('.')
        current = self._config

        # Navigate to the nested dict, creating as needed
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]

        # Set the final value
        current[keys[-1]] = value
        self._save()
        logger.info(f"Set config {key} = {value}")

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value.

        Args:
            key: Configuration key (supports nested keys with dots, e.g. 'database.path')
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        keys = key.split('.')
        current = self._config

        try:
            for k in keys:
                current = current[k]
            return current
        except (KeyError, TypeError):
            return default


def initialize_user_space(db_path: Optional[Path] = None) -> Path:
    """
    Initialize user space directory structure.

    Creates ~/.finbase/ directory and sets up default database location.
    Saves configuration to ~/.finbaserc.

    Args:
        db_path: Optional custom database path. If None, uses ~/.finbase/timeseries.db

    Returns:
        Path to database file
    """
    # Determine database path
    if db_path is None:
        db_path = DEFAULT_DB_PATH
    else:
        db_path = Path(db_path).expanduser().resolve()

    # Create user space directory
    user_space_dir = db_path.parent
    user_space_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Created user space directory: {user_space_dir}")

    # Save to config
    config = UserConfig()
    config.set_db_path(db_path)

    logger.info(f"Initialized user space with database at: {db_path}")
    return db_path


def get_configured_db_path() -> Path:
    """
    Get the configured database path.

    Returns database path from config if available, otherwise returns default.

    Returns:
        Path to database file
    """
    config = UserConfig()
    db_path = config.get_db_path()

    if db_path is None:
        logger.info("No database path configured, using default")
        return DEFAULT_DB_PATH

    return db_path
