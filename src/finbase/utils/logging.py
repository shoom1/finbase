"""
Logging configuration and utilities for FinBase.

Library policy: importing any finbase module must NOT touch the filesystem
or attach console handlers. Modules call `get_logger(__name__)` which only
returns a stdlib logger and adds a `NullHandler` once on the root finbase
logger so that records are silently dropped if the application never opts
in.

Application policy: entry-point scripts (CLI, dashboard, examples) call
`configure_application_logging()` once at startup. That is the only place
that ever creates files or writes to stderr.
"""

import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Optional


_PACKAGE_LOGGER_NAME = "finbase"
_DEFAULT_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
_DEFAULT_DATEFMT = "%Y-%m-%d %H:%M:%S"


class ColoredFormatter(logging.Formatter):
    """Colorize the levelname when stderr is a TTY."""

    COLORS = {
        "DEBUG": "\033[36m",
        "INFO": "\033[32m",
        "WARNING": "\033[33m",
        "ERROR": "\033[31m",
        "CRITICAL": "\033[35m",
    }
    RESET = "\033[0m"

    def format(self, record):
        if hasattr(sys.stderr, "isatty") and sys.stderr.isatty():
            levelname = record.levelname
            if levelname in self.COLORS:
                record.levelname = f"{self.COLORS[levelname]}{levelname}{self.RESET}"
        return super().format(record)


def _ensure_null_handler() -> logging.Logger:
    """Attach a NullHandler to the package root logger exactly once."""
    root = logging.getLogger(_PACKAGE_LOGGER_NAME)
    if not any(isinstance(h, logging.NullHandler) for h in root.handlers):
        root.addHandler(logging.NullHandler())
    return root


def get_logger(name: str) -> logging.Logger:
    """
    Return a stdlib logger for `name`.

    Side-effect-free: only ensures the package root has a NullHandler so
    library users who never configure logging don't see "No handlers could
    be found" warnings.
    """
    _ensure_null_handler()
    return logging.getLogger(name)


def configure_application_logging(
    log_dir: Optional[str] = None,
    log_level: str = "INFO",
    console_output: bool = True,
    file_output: bool = True,
    max_bytes: int = 10_000_000,
    backup_count: int = 5,
) -> logging.Logger:
    """
    Configure the package root logger for an application entry point.

    Idempotent: calling more than once replaces previously installed
    handlers. Safe to call from `scripts/setup_database.py`,
    `dashboard_app.py`, etc.

    Args:
        log_dir: Directory for rotating log files. If None, falls back to
            `Settings.logging.log_dir`. Resolved relative to the user's
            home (`~/.finbase/logs`) when not absolute, so different cwds
            don't sprout new directories.
        log_level: Threshold for the package logger.
        console_output: Mirror records to stderr.
        file_output: Write records to a rotating file in `log_dir`.
        max_bytes: Per-file rotation size.
        backup_count: Number of rotated backups to retain.

    Returns:
        The configured package root logger.
    """
    root = _ensure_null_handler()

    # Tear down any previously installed non-Null handlers so re-config is clean.
    for handler in list(root.handlers):
        if not isinstance(handler, logging.NullHandler):
            root.removeHandler(handler)
            try:
                handler.close()
            except Exception:
                pass

    root.setLevel(getattr(logging, log_level.upper()))
    root.propagate = False

    if console_output:
        console = logging.StreamHandler(sys.stderr)
        console.setLevel(getattr(logging, log_level.upper()))
        console.setFormatter(
            ColoredFormatter(_DEFAULT_FORMAT, datefmt=_DEFAULT_DATEFMT)
        )
        root.addHandler(console)

    if file_output:
        resolved_dir = _resolve_log_dir(log_dir)
        resolved_dir.mkdir(parents=True, exist_ok=True)

        file_handler = logging.handlers.RotatingFileHandler(
            resolved_dir / "finbase.log",
            maxBytes=max_bytes,
            backupCount=backup_count,
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(
            logging.Formatter(_DEFAULT_FORMAT, datefmt=_DEFAULT_DATEFMT)
        )
        root.addHandler(file_handler)

    return root


def _resolve_log_dir(log_dir: Optional[str]) -> Path:
    """Resolve `log_dir` against settings/home so cwd is irrelevant."""
    if log_dir is None:
        # Lazy import: settings imports get_logger via cascading modules.
        from ..config import get_settings

        log_dir = get_settings().logging.log_dir

    path = Path(log_dir).expanduser()
    if not path.is_absolute():
        path = Path.home() / ".finbase" / path
    return path


# Initialize the NullHandler at module import — that *is* allowed; it does
# no I/O and prevents "No handlers" warnings without touching the filesystem.
_ensure_null_handler()
