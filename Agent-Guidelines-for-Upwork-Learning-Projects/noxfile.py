"""Noxfile - Unified development interface.

Usage:
    nox                    # Run all sessions
    nox -l                # List all sessions
    nox -s test           # Run specific session
    nox -s lint           # Lint only
    nox -s test -- tests/integrations/test_google_sheets.py  # Specific test

Sessions:
    test        - Run all tests with pytest
    test-fast   - Run tests without coverage (faster)
    lint        - Run ruff check
    format      - Format code with ruff
    typecheck   - Run mypy type checking
    docs        - Build documentation with mkdocs
    docs-serve  - Serve documentation locally
    security    - Run gitleaks secret scanning
    spell       - Run codespell spell checking
    all         - Run all quality checks (lint, typecheck, test, spell)
"""

import shutil
from pathlib import Path

import nox

PYTHON_VERSIONS = ["3.11", "3.12"]
DEFAULT_PYTHON = "3.12"
SOURCE_PATHS = ("src/", "tests/")
SPELL_PATHS = ("src/", "tests/", "docs/", "examples/")
SPELL_SKIP = "*.pyc,*.svg,*.lock,.venv,venv,dist,build,htmlcov,.mypy_cache"
SPELL_IGNORE = "crate,nd,te,als,ot,ro,hist,ser"

nox.options.sessions = ["all"]


def install_dev_tools(session: nox.Session) -> None:
    """Install shared development dependencies for validation sessions."""
    session.install(".[dev]", "ruff", "codespell")


def run_spellcheck(session: nox.Session) -> None:
    """Run codespell with the repository defaults."""
    session.run(
        "codespell",
        f"--ignore-words-list={SPELL_IGNORE}",
        f"--skip={SPELL_SKIP}",
        *SPELL_PATHS,
    )


def run_lint(session: nox.Session) -> None:
    """Run Ruff lint checks."""
    session.run("ruff", "check", *SOURCE_PATHS)


def run_format_check(session: nox.Session) -> None:
    """Run Ruff format in check mode."""
    session.run("ruff", "format", "--check", *SOURCE_PATHS)


def run_typecheck(session: nox.Session) -> None:
    """Run mypy checks."""
    session.run("mypy", "src/")


def run_tests(session: nox.Session) -> None:
    """Run pytest with coverage settings used in CI."""
    session.run("pytest", "--cov=src", "--cov-report=xml", "tests/")


@nox.session(python=PYTHON_VERSIONS)
def test(session: nox.Session) -> None:
    """Run pytest with coverage."""
    session.install(".[dev]")
    session.run(
        "pytest",
        "--cov=src",
        "--cov-report=term-missing",
        "--cov-report=xml",
        "--cov-fail-under=70",
        *session.posargs,
    )


@nox.session(python=PYTHON_VERSIONS)
def test_fast(session: nox.Session) -> None:
    """Run pytest without coverage (faster)."""
    session.install(".[dev]")
    session.run("pytest", "-v", "--tb=short", *session.posargs)


@nox.session(python=DEFAULT_PYTHON)
def lint(session: nox.Session) -> None:
    """Run ruff check for linting."""
    session.install("ruff")
    session.run("ruff", "check", *SOURCE_PATHS, *session.posargs)


@nox.session(python=DEFAULT_PYTHON)
def format_code(session: nox.Session) -> None:
    """Format code with ruff."""
    session.install("ruff")
    session.run("ruff", "format", *SOURCE_PATHS, *session.posargs)


@nox.session(python=DEFAULT_PYTHON)
def format_check(session: nox.Session) -> None:
    """Check code formatting with ruff."""
    session.install("ruff")
    session.run("ruff", "format", "--check", *SOURCE_PATHS, *session.posargs)


@nox.session(python=DEFAULT_PYTHON)
def typecheck(session: nox.Session) -> None:
    """Run mypy type checking."""
    session.install(".[dev]")
    session.run("mypy", "src/", *session.posargs)


@nox.session(python=DEFAULT_PYTHON)
def docs(session: nox.Session) -> None:
    """Build documentation with mkdocs."""
    session.install("mkdocs-material[imaging]")
    session.run("mkdocs", "build", "--strict", "--site-dir", "site", *session.posargs)


@nox.session(python=DEFAULT_PYTHON)
def docs_serve(session: nox.Session) -> None:
    """Serve documentation locally."""
    session.install("mkdocs-material[imaging]")
    session.run("mkdocs", "serve", "--dev-addr", "localhost:8000", *session.posargs)


@nox.session(python=DEFAULT_PYTHON)
def security(session: nox.Session) -> None:
    """Run gitleaks for secret scanning."""
    if shutil.which("gitleaks") is None:
        session.error(
            "gitleaks binary is not installed. Install it from https://github.com/gitleaks/gitleaks/releases or via your system package manager."
        )
    session.run("gitleaks", "detect", "--source", ".", "--config", ".gitleaks.toml", "-v")


@nox.session(python=DEFAULT_PYTHON)
def spell(session: nox.Session) -> None:
    """Run codespell spell checking."""
    session.install("codespell")
    session.run(
        "codespell",
        f"--ignore-words-list={SPELL_IGNORE}",
        f"--skip={SPELL_SKIP}",
        *SPELL_PATHS,
        *session.posargs,
    )


@nox.session(python=DEFAULT_PYTHON)
def all_checks(session: nox.Session) -> None:
    """Run the full local validation pipeline."""
    install_dev_tools(session)

    print("\n" + "=" * 60)
    print("Running all quality checks...")
    print("=" * 60)

    # 1. Spell check
    print("\n[1/5] Running codespell...")
    run_spellcheck(session)

    # 2. Lint
    print("\n[2/5] Running ruff check...")
    run_lint(session)

    # 3. Format check
    print("\n[3/5] Checking code format...")
    run_format_check(session)

    # 4. Type check
    print("\n[4/5] Running mypy type check...")
    run_typecheck(session)

    # 5. Test
    print("\n[5/5] Running pytest...")
    session.run(
        "pytest",
        "--cov=src",
        "--cov-report=term-missing",
        "--cov-fail-under=70",
        "tests/",
    )

    print("\n" + "=" * 60)
    print("All checks passed!")
    print("=" * 60)


@nox.session(python=DEFAULT_PYTHON)
def clean(session: nox.Session) -> None:
    """Clean up build artifacts."""
    dirs_to_remove = [
        "build",
        "dist",
        "*.egg-info",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "htmlcov",
        ".coverage",
        "site",
        ".nox",
    ]

    for pattern in dirs_to_remove:
        if "*" in pattern:
            for path in Path(".").glob(pattern):
                if path.is_dir():
                    print(f"Removing {path}/")
                    shutil.rmtree(path)
                elif path.is_file():
                    print(f"Removing {path}")
                    path.unlink()
        else:
            path = Path(pattern)
            if path.exists():
                if path.is_dir():
                    print(f"Removing {path}/")
                    shutil.rmtree(path)
                else:
                    print(f"Removing {path}")
                    path.unlink()

    print("Cleanup complete!")


@nox.session(python=DEFAULT_PYTHON)
def pre_commit(session: nox.Session) -> None:
    """Run pre-commit hooks on all files."""
    session.install("pre-commit")
    session.run("pre-commit", "run", "--all-files", *session.posargs)


@nox.session(python=DEFAULT_PYTHON)
def install_hooks(session: nox.Session) -> None:
    """Install pre-commit hooks."""
    session.install("pre-commit")
    session.run("pre-commit", "install")
    print("Pre-commit hooks installed!")


@nox.session(python=DEFAULT_PYTHON)
def ci(session: nox.Session) -> None:
    """Run the same validation pipeline used by GitHub Actions."""
    install_dev_tools(session)

    print("\n" + "=" * 60)
    print("Running CI pipeline...")
    print("=" * 60)

    # Lint
    print("\n[1/4] Linting...")
    run_lint(session)

    # Format
    print("\n[2/4] Checking format...")
    run_format_check(session)

    # Type check
    print("\n[3/4] Type checking...")
    run_typecheck(session)

    # Test
    print("\n[4/4] Testing...")
    run_tests(session)

    print("\n" + "=" * 60)
    print("CI pipeline passed!")
    print("=" * 60)
