from __future__ import annotations

import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Lock
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dharanokxa import DesignRequest, design


class RunRequest(BaseModel):
    scheme_name: str = Field(default="Demo JJM 2.0 Rural Scheme", min_length=1, max_length=120)
    household_count: int = Field(default=100, ge=10, le=5000)
    seed: int = 20260926
    source_latitude: float = Field(default=26.182145, ge=-90, le=90)
    source_longitude: float = Field(default=91.743281, ge=-180, le=180)


app = FastAPI(title="DharaNokxa", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"], allow_methods=["*"], allow_headers=["*"])
executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="dharanokxa-design")
run_lock = Lock()
runs: dict[str, dict] = {}


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "engine": "EPANET 2.2 through WNTR"}


@app.post("/runs", status_code=202)
def create_run(payload: RunRequest) -> dict:
    job_id = uuid4().hex
    _set_run(job_id, {"job_id": job_id, "state": "QUEUED", "stage": "Validate"})
    executor.submit(_execute, job_id, payload)
    return runs[job_id]


@app.get("/runs/{job_id}")
def get_run(job_id: str) -> dict:
    with run_lock:
        run = runs.get(job_id)
    if run is None:
        raise HTTPException(404, "Run not found")
    return run


@app.get("/demo")
def get_demo() -> dict:
    path = ROOT / "results" / "demo_jjm_scheme" / "design_result.json"
    if not path.exists():
        raise HTTPException(404, "Run python main.py demo first")
    return json.loads(path.read_text(encoding="utf-8"))


@app.get("/artifacts/{job_id}/{name}")
def artifact(job_id: str, name: str):
    run = get_run(job_id)
    if run.get("state") != "COMPLETE":
        raise HTTPException(409, "Run is not complete")
    allowed = {Path(value).name: Path(value) for value in run["result"]["artifacts"].values()}
    target = allowed.get(name)
    if target is None or not target.is_file():
        raise HTTPException(404, "Artifact not found")
    return FileResponse(target)


def _execute(job_id: str, payload: RunRequest) -> None:
    try:
        _set_run(job_id, {"job_id": job_id, "state": "RUNNING", "stage": "Design → Simulate → Correct → Verify → Package"})
        result = design(DesignRequest(
            scheme_name=payload.scheme_name,
            household_count=payload.household_count,
            seed=payload.seed,
            source_latitude=payload.source_latitude,
            source_longitude=payload.source_longitude,
            output_dir=ROOT / "results" / "runs" / job_id,
        ))
        _set_run(job_id, {"job_id": job_id, "state": "COMPLETE", "stage": "Complete", "result": result.to_dict()})
    except Exception as exc:
        _set_run(job_id, {"job_id": job_id, "state": "FAILED", "stage": "Failed", "error": str(exc)})


def _set_run(job_id: str, value: dict) -> None:
    with run_lock:
        runs[job_id] = value
    job_dir = ROOT / "results" / "jobs"
    job_dir.mkdir(parents=True, exist_ok=True)
    (job_dir / f"{job_id}.json").write_text(json.dumps(value, indent=2, default=str), encoding="utf-8")
