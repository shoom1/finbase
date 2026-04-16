"""
Smoke tests for top-level entry points (dashboard app and example scripts).

These exist because the entry points sit *outside* the finbase package and
import paths drift away from the package layout silently — pytest never
catches it because pytest only collects from `tests/` and the package itself.

Each test py-compiles the file (so syntax errors and obvious import name
typos surface) and then statically inspects the import statements to confirm
they reference real modules in the installed `finbase` package, not the
historical `src.*` layout.
"""

import ast
import importlib
import importlib.util
import py_compile
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
DASHBOARD_APP = REPO_ROOT / "dashboard_app.py"
EXAMPLES_DIR = REPO_ROOT / "examples"

ENTRY_POINTS = [
    DASHBOARD_APP,
    EXAMPLES_DIR / "sp500_wikipedia_example.py",
    EXAMPLES_DIR / "index_management_example.py",
    EXAMPLES_DIR / "load_index_data_example.py",
    EXAMPLES_DIR / "client_api_examples.py",
]


def _imported_modules(path: Path) -> list[str]:
    """Return the list of fully-qualified modules imported by `path`."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                modules.append(node.module)
    return modules


@pytest.mark.parametrize("entry_point", ENTRY_POINTS, ids=lambda p: p.name)
def test_entry_point_compiles(entry_point: Path):
    """The file must parse and py-compile cleanly."""
    assert entry_point.exists(), f"missing entry point: {entry_point}"
    py_compile.compile(str(entry_point), doraise=True)


@pytest.mark.parametrize("entry_point", ENTRY_POINTS, ids=lambda p: p.name)
def test_entry_point_uses_finbase_namespace(entry_point: Path):
    """
    Imports must not reference the historical `src.*` layout or bare
    `data.*` / `config.*` / `dashboard.*` names that only worked under
    `sys.path` hacks.
    """
    modules = _imported_modules(entry_point)
    forbidden_prefixes = ("src.", "src")
    forbidden_bare_roots = {"data", "config", "dashboard", "client", "utils"}

    bad: list[str] = []
    for module in modules:
        if module == "src" or module.startswith("src."):
            bad.append(module)
            continue
        root = module.split(".", 1)[0]
        if root in forbidden_bare_roots:
            bad.append(module)

    assert not bad, (
        f"{entry_point.name} imports stale modules {bad}; "
        f"use the finbase.* namespace instead"
    )


@pytest.mark.parametrize("entry_point", ENTRY_POINTS, ids=lambda p: p.name)
def test_entry_point_finbase_imports_resolve(entry_point: Path):
    """
    Every `from finbase.X import …` statement in the entry point must
    reference a module that actually exists in the installed package.
    """
    modules = _imported_modules(entry_point)
    finbase_modules = [m for m in modules if m == "finbase" or m.startswith("finbase.")]

    unresolved = [m for m in finbase_modules if importlib.util.find_spec(m) is None]
    assert not unresolved, (
        f"{entry_point.name} imports nonexistent finbase modules: {unresolved}"
    )
