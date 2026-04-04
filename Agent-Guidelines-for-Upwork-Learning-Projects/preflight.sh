#!/usr/bin/env bash
# preflight.sh — локальный CI: lint + typecheck (soft) + tests
# Использование: bash preflight.sh
# Возвращает: 0 если всё ок, 1 если lint или tests упали.
# mypy — мягкий: выводит ошибки, но не блокирует.

set -eo pipefail
cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)"

if [ -f .claude/settings.json.bak ] && [ ! -f .claude/settings.json ]; then
  mv .claude/settings.json.bak .claude/settings.json
  echo 'WARNING: settings.json restored from backup'
fi

# Флаги пропуска отдельных шагов:
#   SKIP_PREFLIGHT=1  — пропустить всё
#   SKIP_LINT=1       — пропустить ruff
#   SKIP_MYPY=1       — пропустить mypy
#   SKIP_TESTS=1      — пропустить pytest
if [ "${SKIP_PREFLIGHT:-0}" = "1" ]; then
    echo "⚡ Preflight skipped (SKIP_PREFLIGHT=1)"
    exit 0
fi

FAILED=0

# ── цвета ─────────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; RESET='\033[0m'; BOLD='\033[1m'

pass() { echo -e "${GREEN}✓ $1${RESET}"; }
fail() { echo -e "${RED}✗ $1${RESET}"; }
soft() { echo -e "${YELLOW}⚠ $1 (soft — не блокирует)${RESET}"; }
section() { echo -e "\n${BLUE}${BOLD}── $1 ──${RESET}"; }

# ── 1. lint (ruff) ─────────────────────────────────────────────────────────────
if [ "${SKIP_LINT:-0}" != "1" ]; then
    section "lint  ruff"
    if python3 -m ruff check src/ tests/; then
        pass "ruff: нарушений нет"
    else
        fail "ruff: есть нарушения"
        FAILED=1
    fi
else
    echo -e "${YELLOW}⚡ lint skipped (SKIP_LINT=1)${RESET}"
fi

# ── 2. typecheck (mypy) ────────────────────────────────────────────────────────
if [ "${SKIP_MYPY:-0}" != "1" ]; then
    section "typecheck  mypy"
    if python3 -m mypy src/ 2>&1; then
        pass "mypy: ошибок нет"
    else
        fail "mypy: есть ошибки типов"
        FAILED=1
    fi
else
    echo -e "${YELLOW}⚡ mypy skipped (SKIP_MYPY=1)${RESET}"
fi

# ── 3. tests (pytest) ──────────────────────────────────────────────────────────
if [ "${SKIP_TESTS:-0}" != "1" ]; then
    section "tests  pytest"
    if python3 -m pytest -q; then
        pass "pytest: все тесты зелёные"
    else
        fail "pytest: есть упавшие тесты"
        FAILED=1
    fi
else
    echo -e "${YELLOW}⚡ tests skipped (SKIP_TESTS=1)${RESET}"
fi

# ── итог ───────────────────────────────────────────────────────────────────────
echo ""
if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}${BOLD}✓ Preflight passed${RESET}"
else
    echo -e "${RED}${BOLD}✗ Preflight FAILED${RESET}"
fi

exit $FAILED
