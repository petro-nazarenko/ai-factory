import json
import os
import subprocess
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, status
from fastapi.responses import JSONResponse

app = FastAPI(title="AI Factory API")

REPO_ROOT = Path(__file__).parent.parent
RUNS_DIR = REPO_ROOT / "workspace" / "runs"
PIPELINE_SCRIPT = REPO_ROOT / "run_pipeline.sh"
API_KEY = os.environ.get("API_KEY", "")


def check_auth(x_api_key: str = Header(...)):
    if not API_KEY:
        raise HTTPException(status_code=500, detail="API_KEY not configured on server")
    if x_api_key != API_KEY:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")


def read_json(path: Path) -> dict | list | None:
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def get_run_data(run_id: str) -> dict:
    run_dir = RUNS_DIR / run_id
    if not run_dir.exists():
        return None

    data = {"run_id": run_id}

    status_data = read_json(run_dir / "status.json")
    if status_data:
        data["step"] = status_data.get("step")
        data["status"] = status_data.get("status")
        data["retries"] = status_data.get("retries", 0)
        data["errors"] = status_data.get("errors", [])

    report = read_json(run_dir / "report.json")
    if report:
        data["report"] = report

    validated_dir = run_dir / "validated"
    ideas = []
    if validated_dir.exists():
        for md_file in sorted(validated_dir.glob("*.md")):
            ideas.append({"file": md_file.name, "content": md_file.read_text()})
    data["validated_ideas"] = ideas

    return data


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.post("/run", status_code=202)
def start_run(
    dry_run: bool = False,
    x_api_key: str = Header(...),
):
    check_auth(x_api_key)

    cmd = ["bash", str(PIPELINE_SCRIPT)]
    if dry_run:
        cmd.append("--dry-run")

    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(REPO_ROOT),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start pipeline: {e}")

    # Derive the run_id that the script will create (same timestamp format)
    # We can't know the exact RUN_ID until the script runs, so we return the pid
    # and instruct the caller to poll GET /runs for the new entry.
    return {"message": "Pipeline started", "pid": proc.pid, "dry_run": dry_run}


@app.get("/runs/{run_id}")
def get_run(run_id: str, x_api_key: str = Header(...)):
    check_auth(x_api_key)

    data = get_run_data(run_id)
    if data is None:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    return data


@app.get("/runs")
def list_runs(x_api_key: str = Header(...)):
    check_auth(x_api_key)

    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    runs = []
    for run_dir in sorted(RUNS_DIR.iterdir(), reverse=True):
        if not run_dir.is_dir():
            continue
        status_data = read_json(run_dir / "status.json")
        if status_data is None:
            continue
        runs.append({
            "run_id": run_dir.name,
            "step": status_data.get("step"),
            "status": status_data.get("status"),
        })
    return {"runs": runs, "total": len(runs)}
