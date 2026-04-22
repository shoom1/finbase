"""
Regression tests for module-import side effects.

These are subprocess tests because by the time pytest collects, finbase is
already imported into the test runner — we can't observe the side effect in
the same process. Each test spawns a fresh `python -c` in an empty temp
directory and asserts the working directory stays clean.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest


def _run_in_temp_cwd(tmp_path: Path, script: str) -> subprocess.CompletedProcess:
    """Run a one-liner in a clean temp cwd and capture output."""
    return subprocess.run(
        [sys.executable, "-c", script],
        cwd=str(tmp_path),
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
        capture_output=True,
        text=True,
        check=False,
    )


def _list_artifacts(tmp_path: Path) -> list[str]:
    """Return entries the import created in the temp cwd, sorted."""
    return sorted(p.name for p in tmp_path.iterdir())


def test_import_finbase_creates_no_logs_dir(tmp_path):
    """`import finbase` must not write anything to the current directory."""
    result = _run_in_temp_cwd(tmp_path, "import finbase")
    assert result.returncode == 0, (
        f"import failed:\nstdout={result.stdout}\nstderr={result.stderr}"
    )
    artifacts = _list_artifacts(tmp_path)
    assert artifacts == [], (
        f"import finbase created files in cwd: {artifacts}. "
        f"Library imports must be side-effect-free."
    )


def test_import_dataclient_creates_no_logs_dir(tmp_path):
    """Same guarantee for the most common public import path."""
    result = _run_in_temp_cwd(tmp_path, "from finbase import DataClient")
    assert result.returncode == 0, (
        f"import failed:\nstdout={result.stdout}\nstderr={result.stderr}"
    )
    artifacts = _list_artifacts(tmp_path)
    assert artifacts == [], (
        f"`from finbase import DataClient` created files in cwd: {artifacts}"
    )


def test_import_timeseries_db_creates_no_logs_dir(tmp_path):
    """Importing the database module directly must also be inert."""
    result = _run_in_temp_cwd(
        tmp_path,
        "from finbase.data.database.timeseries_db import TimeSeriesDB",
    )
    assert result.returncode == 0, (
        f"import failed:\nstdout={result.stdout}\nstderr={result.stderr}"
    )
    artifacts = _list_artifacts(tmp_path)
    assert artifacts == [], (
        f"importing TimeSeriesDB created files in cwd: {artifacts}"
    )
