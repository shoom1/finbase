"""
Static + subprocess guards that ``scripts/setup_database.py`` is import-safe.

Until recently, ``configure_application_logging()`` ran at module scope:
simply importing the script installed root-logger handlers and (in the
default config) created a ``logs/`` directory — a surprise for anything
that imported the module for its helpers or ran it under test
collection. These checks pin the expected library-shaped behavior.
"""

from pathlib import Path
import subprocess
import sys
import textwrap

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "setup_database.py"


def test_configure_application_logging_not_called_at_module_scope():
    """``configure_application_logging()`` must be called inside ``main()``,
    never at top level — otherwise tests that import the script silently
    reconfigure global logging and filesystem state."""
    source = SCRIPT.read_text(encoding="utf-8")

    # Find the call site(s). We accept zero or one at module scope;
    # more than zero is a regression.
    lines = source.splitlines()
    module_scope_calls = []
    indent_stack = []
    for i, line in enumerate(lines, start=1):
        stripped = line.lstrip()
        if not stripped or stripped.startswith("#"):
            continue
        # A line starting in column 0 that calls the function with no preceding
        # def/class block is a module-scope call.
        if stripped.startswith("configure_application_logging(") and not line.startswith((" ", "\t")):
            module_scope_calls.append(i)

    assert module_scope_calls == [], (
        f"configure_application_logging() is called at module scope on "
        f"lines {module_scope_calls}. Move it inside main() so importing "
        f"the script does not reconfigure logging."
    )


def test_main_calls_configure_application_logging():
    """The entry point must still configure logging when actually run."""
    source = SCRIPT.read_text(encoding="utf-8")
    assert "configure_application_logging()" in source, (
        "main() no longer calls configure_application_logging(); the CLI "
        "would run with a silent NullHandler."
    )


def test_import_setup_database_creates_no_logs_dir(tmp_path):
    """Importing the script in a fresh HOME must not create ``logs/``
    (the default ``LoggingConfig.log_dir``)."""
    script = textwrap.dedent(
        f"""
        import os, sys
        os.environ["HOME"] = {str(tmp_path)!r}
        os.chdir({str(tmp_path)!r})
        sys.path.insert(0, {str(REPO_ROOT / 'scripts')!r})
        sys.path.insert(0, {str(REPO_ROOT / 'src')!r})
        import importlib
        importlib.import_module("setup_database")
        """
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert not (tmp_path / "logs").exists(), (
        "Importing setup_database created a logs/ directory — that means "
        "configure_application_logging() is still executing at module "
        "scope."
    )
