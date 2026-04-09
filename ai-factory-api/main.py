import json
import os
import re
import subprocess
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import FastAPI, Header, HTTPException, status
from fastapi.responses import PlainTextResponse

app = FastAPI(title="AI Factory API")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNS_DIR = os.path.join(BASE_DIR, "workspace", "runs")
_RUNS_DIR_REAL = os.path.realpath(RUNS_DIR)
PIPELINE_SCRIPT = os.path.join(BASE_DIR, "run_pipeline.sh")
API_KEY = os.environ.get("API_KEY", "")

_RUN_ID_RE = re.compile(r"^run_\d{8}_\d{6}$")


def _validate_run_id(run_id: str) -> None:
    if not _RUN_ID_RE.match(run_id):
        raise HTTPException(status_code=400, detail="Invalid run_id format")
    run_dir = os.path.realpath(os.path.join(RUNS_DIR, run_id))
    if not run_dir.startswith(_RUNS_DIR_REAL + os.sep):
        raise HTTPException(status_code=400, detail="Invalid run_id")


def check_auth(x_api_key: str) -> None:
    if not API_KEY:
        raise HTTPException(status_code=500, detail="API_KEY not configured on server")
    if x_api_key != API_KEY:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")


def read_json(path: str) -> Optional[dict]:
    try:
        with open(path) as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
        return None
    except Exception:
        return None


def get_run_data(run_id: str) -> Optional[dict]:
    run_dir = os.path.join(RUNS_DIR, run_id)
    if not os.path.isdir(run_dir):
        return None

    data: dict[str, Any] = {"run_id": run_id}

    status_data = read_json(os.path.join(run_dir, "status.json"))
    if status_data:
        data["step"] = status_data.get("step")
        data["status"] = status_data.get("status")
        data["retries"] = status_data.get("retries", 0)
        data["errors"] = status_data.get("errors", [])

    report = read_json(os.path.join(run_dir, "report.json"))
    if report:
        data["report"] = report

    validated_dir = os.path.join(run_dir, "validated")
    ideas = []
    if os.path.isdir(validated_dir):
        for fname in sorted(os.listdir(validated_dir)):
            if fname.endswith(".md"):
                fpath = os.path.join(validated_dir, fname)
                with open(fpath) as f:
                    ideas.append({"file": fname, "content": f.read()})
    data["validated_ideas"] = ideas

    return data


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.post("/run", status_code=202)
def start_run(dry_run: bool = False, x_api_key: str = Header(...)) -> dict:
    check_auth(x_api_key)

    run_id = "run_" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_dir = os.path.join(RUNS_DIR, run_id)
    os.makedirs(os.path.join(run_dir, "validated"), exist_ok=True)
    logs_path = os.path.join(run_dir, "logs.txt")

    cmd = ["bash", PIPELINE_SCRIPT]
    if dry_run:
        cmd.append("--dry-run")

    try:
        logs_file = open(logs_path, "ab")  # append-binary so script's tee -a merges cleanly
        proc = subprocess.Popen(
            cmd,
            cwd=BASE_DIR,
            stdout=subprocess.DEVNULL,
            stderr=logs_file,
            start_new_session=True,
        )
        logs_file.close()  # parent doesn't need the fd; child has its own copy
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start pipeline: {e}")

    return {"message": "Pipeline started", "run_id": run_id, "pid": proc.pid, "dry_run": dry_run}


@app.get("/runs/{run_id}/logs", response_class=PlainTextResponse)
def get_run_logs(run_id: str, x_api_key: str = Header(...)) -> str:
    check_auth(x_api_key)
    _validate_run_id(run_id)

    logs_path = os.path.join(RUNS_DIR, run_id, "logs.txt")
    if not os.path.isfile(logs_path):
        raise HTTPException(status_code=404, detail=f"No logs for run '{run_id}'")
    with open(logs_path) as f:
        return f.read()


@app.get("/runs/{run_id}")
def get_run(run_id: str, x_api_key: str = Header(...)) -> dict:
    check_auth(x_api_key)
    _validate_run_id(run_id)

    data = get_run_data(run_id)
    if data is None:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    return data


@app.get("/runs")
def list_runs(x_api_key: str = Header(...)) -> dict:
    check_auth(x_api_key)

    os.makedirs(RUNS_DIR, exist_ok=True)
    runs = []
    for name in sorted(os.listdir(RUNS_DIR), reverse=True):
        run_dir = os.path.join(RUNS_DIR, name)
        if not os.path.isdir(run_dir):
            continue
        status_data = read_json(os.path.join(run_dir, "status.json"))
        if status_data is None:
            continue
        runs.append({
            "run_id": name,
            "step": status_data.get("step"),
            "status": status_data.get("status"),
        })
    return {"runs": runs, "total": len(runs)}
