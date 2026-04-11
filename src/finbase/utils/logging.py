"""
Logging configuration and utilities for FinBase.

This module provides a centralized logging setup with:
- Console and file handlers
- Log rotation
- Configurable log levels
- Structured log formatting
"""

import logging
import logging.handlers
from pathlib import Path
from typing import Optional
import sys


class ColoredFormatter(logging.Formatter):
    """Custom formatter with color support for console output."""

    # ANSI color codes
    COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[35m'  # Magenta
    }
    RESET = '\033[0m'

    def format(self, record):
        """Format the log record with colors for console output."""
        if hasattr(sys.stderr, 'isatty') and sys.stderr.isatty():
            # Add color to levelname
            levelname = record.levelname
            if levelname in self.COLORS:
                record.levelname = f"{self.COLORS[levelname]}{levelname}{self.RESET}"

        return super().format(record)


def setup_logger(
    name: str,
    log_dir: str = "logs",
    log_level: str = "INFO",
    console_output: bool = True,
    file_output: bool = True,
    max_bytes: int = 10_000_000,  # 10MB
    backup_count: int = 5
) -> logging.Logger:
    """
    Set up a logger with console and file handlers.

    Args:
        name: Logger name (typically __name__ of the module)
        log_dir: Directory for log files
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        console_output: Whether to output to console
        file_output: Whether to output to file
        max_bytes: Maximum size of log file before rotation
        backup_count: Number of backup files to keep

    Returns:
        Configured logger instance

    Example:
        >>> from finbase.utils.logging import setup_logger
        >>> logger = setup_logger(__name__)
        >>> logger.info("Application started")
        >>> logger.error("An error occurred", exc_info=True)
    """
    logger = logging.getLogger(name)

    # Avoid duplicate handlers if logger already configured
    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, log_level.upper()))

    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    colored_formatter = ColoredFormatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Console handler
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(colored_formatter)
        logger.addHandler(console_handler)

    # File handler with rotation
    if file_output:
        log_path = Path(log_dir)
        log_path.mkdir(exist_ok=True)

        # Sanitize logger name for filename
        safe_name = name.replace('.', '_')
        file_handler = logging.handlers.RotatingFileHandler(
            log_path / f"{safe_name}.log",
            maxBytes=max_bytes,
            backupCount=backup_count
        )
        file_handler.setLevel(logging.DEBUG)  # File gets all levels
        file_handler.setFormatter(detailed_formatter)
        logger.addHandler(file_handler)

    # Prevent propagation to root logger
    logger.propagate = False

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get an existing logger or create a new one with default settings.

    Args:
        name: Logger name (typically __name__ of the module)

    Returns:
        Logger instance
    """
    logger = logging.getLogger(name)

    if not logger.handlers:
        return setup_logger(name)

    return logger


# Create a default logger for the package
default_logger = setup_logger('finbase')
