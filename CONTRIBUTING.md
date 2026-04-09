# Contributing to AI Factory

## Setup

```bash
git clone https://github.com/petro-nazarenko/ai-factory
cd ai-factory
pip install -r requirements.txt
cp Moneymaker/.env.example Moneymaker/.env
# Add at least one LLM key to Moneymaker/.env
```

## Running tests

```bash
# Moneymaker
cd Moneymaker && pytest --tb=short

# Workspace
cd workspace && pytest tests/ --tb=short

# All (from root)
ruff check Moneymaker/ workspace/
```

## Code style

All Python code is linted with [ruff](https://docs.astral.sh/ruff/). Run before committing:

```bash
ruff check . --fix
ruff check .        # must show: All checks passed!
```

Pre-commit hooks are configured in `.pre-commit-config.yaml`. Install once:

```bash
pip install pre-commit
pre-commit install
```

## Branch naming

| Type | Pattern |
|---|---|
| Feature | `feat/<short-description>` |
| Bug fix | `fix/<short-description>` |
| Docs | `docs/<short-description>` |
| Refactor | `refactor/<short-description>` |

## Commit style

```
type: short imperative description

Optional longer explanation.
```

Types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`.

## Pull requests

1. Branch off `master`.
2. Run the full test + lint suite locally.
3. Open a PR — CI (lint + pytest) runs automatically.
4. One approval required before merge.

## Hard rules

- Never skip validation (`--no-verify`).
- Never commit secrets (`.env`, API keys). `.gitleaks` scans on every push.
- Never modify `Moneymaker/` or `ai-knowledge-filler/` core logic without a matching test.
- Pipeline output files (`workspace/runs/`) are gitignored — do not force-add them.
