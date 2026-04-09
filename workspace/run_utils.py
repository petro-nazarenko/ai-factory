"""run_utils.py — Shared workspace utilities for AI Factory pipelines."""

from pathlib import Path


def find_connector_json(runs_dir: Path, run_id: str | None) -> Path:
    """Return the connector.json path for a given run_id or the latest run."""
    if not runs_dir.exists():
        raise FileNotFoundError(f"Runs directory not found: {runs_dir}")

    if run_id:
        candidate = runs_dir / run_id / "connector.json"
        if not candidate.exists():
            raise FileNotFoundError(
                f"connector.json not found for run '{run_id}': {candidate}"
            )
        return candidate

    # Find all run dirs that contain a connector.json, sorted newest first.
    # Run IDs follow the format run_YYYYMMDD_HHMMSS so lexicographic sort
    # is equivalent to chronological order.
    candidates = sorted(
        [
            d / "connector.json"
            for d in runs_dir.iterdir()
            if d.is_dir() and (d / "connector.json").exists()
        ],
        key=lambda p: p.parent.name,
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError(f"No run with connector.json found in {runs_dir}")
    return candidates[0]
