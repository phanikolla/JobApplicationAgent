"""
FastAPI web dashboard for the AI Job Application Agent.
Provides config management, pipeline triggering, and result viewing.
"""

import asyncio
import logging
import os
import json
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv

from src.core.config import load_config, save_config, AppConfig, PROJECT_ROOT

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="AI Job Application Agent", version="1.0.0")

# Serve static files
static_dir = os.path.join(PROJECT_ROOT, "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# --- In-memory state for pipeline runs ---
pipeline_state = {
    "status": "idle",  # idle, running, completed, failed
    "started_at": None,
    "completed_at": None,
    "logs": [],
    "current_task": None,
    "result": None,
}

runs_history = []

RUNS_FILE = os.path.join(PROJECT_ROOT, "runs_history.json")


def _load_runs_history():
    global runs_history
    if os.path.exists(RUNS_FILE):
        try:
            with open(RUNS_FILE, "r", encoding="utf-8") as f:
                runs_history = json.load(f)
        except Exception:
            runs_history = []


def _save_runs_history():
    try:
        with open(RUNS_FILE, "w", encoding="utf-8") as f:
            json.dump(runs_history, f, indent=2, default=str)
    except Exception as e:
        logger.error(f"Failed to save runs history: {e}")


_load_runs_history()


# --- Custom log handler to capture pipeline logs ---
class PipelineLogHandler(logging.Handler):
    def emit(self, record):
        timestamp = datetime.now().strftime("%H:%M:%S")
        msg = f"[{timestamp}] {record.getMessage()}"
        pipeline_state["logs"].append(msg)
        # Keep only last 200 log lines
        if len(pipeline_state["logs"]) > 200:
            pipeline_state["logs"] = pipeline_state["logs"][-200:]


# --- Request models ---
class SingleJobRequest(BaseModel):
    job_url: str = ""
    job_text: str = ""


class ApplyRequest(BaseModel):
    application_url: str
    resume_pdf_path: str


# --- Routes ---
@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    """Serve the main dashboard page."""
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>Dashboard not found. Place index.html in static/</h1>")


@app.get("/api/config")
async def get_config():
    """Return current configuration."""
    cfg = load_config()
    return cfg.model_dump()


@app.post("/api/config")
async def update_config(config_data: dict):
    """Update and save configuration."""
    try:
        cfg = AppConfig(**config_data)
        save_config(cfg)
        return {"success": True, "message": "Configuration saved."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/run")
async def trigger_full_pipeline(background_tasks: BackgroundTasks):
    """Trigger the full automated job scraping + tailoring pipeline."""
    if pipeline_state["status"] == "running":
        raise HTTPException(status_code=409, detail="Pipeline is already running.")

    background_tasks.add_task(_run_full_pipeline)
    return {"success": True, "message": "Pipeline started."}


@app.post("/api/run-single")
async def trigger_single_job(request: SingleJobRequest, background_tasks: BackgroundTasks):
    """Tailor a resume for a single job - either by URL or plain-text JD."""
    if pipeline_state["status"] == "running":
        raise HTTPException(status_code=409, detail="Pipeline is already running.")

    if not request.job_url and not request.job_text:
        raise HTTPException(status_code=400, detail="Provide either a job URL or job description text.")

    background_tasks.add_task(_run_single_pipeline, request.job_url, request.job_text)
    return {"success": True, "message": "Processing job..."}


@app.get("/api/status")
async def get_status():
    """Return current pipeline status and logs."""
    return {
        "status": pipeline_state["status"],
        "started_at": pipeline_state["started_at"],
        "completed_at": pipeline_state["completed_at"],
        "current_task": pipeline_state["current_task"],
        "logs": pipeline_state["logs"][-50:],  # Last 50 lines
        "result": pipeline_state["result"],
    }


@app.get("/api/runs")
async def get_runs():
    """Return history of previous runs."""
    return runs_history


@app.get("/api/download/{filename}")
async def download_file(filename: str):
    """Download a generated file."""
    cfg = load_config()
    file_path = os.path.join(cfg.output_dir, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found.")
    return FileResponse(
        file_path,
        media_type="application/octet-stream",
        filename=filename
    )


@app.get("/api/resumes")
async def list_resumes():
    """List all generated resume files (PDFs and MDs) in the output directory."""
    cfg = load_config()
    output_dir = cfg.output_dir
    if not os.path.exists(output_dir):
        return []

    files = []
    for f in sorted(os.listdir(output_dir), reverse=True):
        if f.lower().endswith((".pdf", ".md")):
            fpath = os.path.join(output_dir, f)
            files.append({
                "filename": f,
                "path": fpath,
                "size_kb": round(os.path.getsize(fpath) / 1024, 1),
                "is_pdf": f.lower().endswith(".pdf"),
            })
    return files


# --- Auto-Apply state ---
apply_session_state = {
    "status": "idle",  # idle, running, waiting_approval, completed, failed
    "message": "",
    "screenshots": [],
    "current_step": 0,
    "application_url": "",
    "error": "",
}


@app.post("/api/apply")
async def trigger_apply(request: ApplyRequest, background_tasks: BackgroundTasks):
    """Start the auto-apply process for a job application."""
    if apply_session_state["status"] == "running":
        raise HTTPException(status_code=409, detail="Auto-apply is already running.")

    if not os.path.exists(request.resume_pdf_path):
        # Try in output directory
        cfg = load_config()
        alt_path = os.path.join(cfg.output_dir, os.path.basename(request.resume_pdf_path))
        if os.path.exists(alt_path):
            request.resume_pdf_path = alt_path
        else:
            raise HTTPException(status_code=404, detail=f"Resume PDF not found: {request.resume_pdf_path}")

    background_tasks.add_task(_run_apply, request.application_url, request.resume_pdf_path)
    return {"success": True, "message": "Auto-apply started."}


@app.get("/api/apply/status")
async def get_apply_status():
    """Return current auto-apply status."""
    return apply_session_state


@app.post("/api/apply/confirm")
async def confirm_apply(background_tasks: BackgroundTasks):
    """Confirm and submit the application after human review."""
    if apply_session_state["status"] != "waiting_approval":
        raise HTTPException(status_code=400, detail="No application waiting for approval.")

    background_tasks.add_task(_confirm_apply)
    return {"success": True, "message": "Submitting application..."}


@app.get("/api/apply/screenshot/{filename}")
async def get_apply_screenshot(filename: str):
    """Serve an apply process screenshot."""
    cfg = load_config()
    screenshots_dir = os.path.join(cfg.output_dir, "apply_screenshots")
    file_path = os.path.join(screenshots_dir, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Screenshot not found.")
    return FileResponse(file_path, media_type="image/png")


# --- Background pipeline runners ---
async def _run_full_pipeline():
    """Run the full automated pipeline in the background."""
    from src.main import run_agent_pipeline

    _reset_pipeline_state("Full Auto Pipeline")

    # Attach log handler
    handler = PipelineLogHandler()
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)

    try:
        await run_agent_pipeline()
        pipeline_state["status"] = "completed"
        pipeline_state["result"] = {"type": "full", "message": "Pipeline completed. Check email for results."}
    except Exception as e:
        pipeline_state["status"] = "failed"
        pipeline_state["result"] = {"type": "full", "error": str(e)}
        logger.error(f"Pipeline failed: {e}")
    finally:
        pipeline_state["completed_at"] = datetime.now().isoformat()
        root_logger.removeHandler(handler)
        _record_run()


async def _run_single_pipeline(job_url: str, job_text: str = ""):
    """Run the single job tailoring pipeline in the background."""
    from src.main import run_single_job_pipeline

    label = f"Quick Tailor: {job_url or 'Plain-text JD'}"
    _reset_pipeline_state(label)

    handler = PipelineLogHandler()
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)

    try:
        result = await run_single_job_pipeline(job_url=job_url, job_text=job_text)
        pipeline_state["status"] = "completed"
        pipeline_state["result"] = {"type": "single", **result}
    except Exception as e:
        pipeline_state["status"] = "failed"
        pipeline_state["result"] = {"type": "single", "success": False, "error": str(e)}
        logger.error(f"Single job pipeline failed: {e}")
    finally:
        pipeline_state["completed_at"] = datetime.now().isoformat()
        root_logger.removeHandler(handler)
        _record_run()


def _reset_pipeline_state(task_name: str):
    pipeline_state["status"] = "running"
    pipeline_state["started_at"] = datetime.now().isoformat()
    pipeline_state["completed_at"] = None
    pipeline_state["logs"] = []
    pipeline_state["current_task"] = task_name
    pipeline_state["result"] = None


def _record_run():
    run_entry = {
        "task": pipeline_state["current_task"],
        "status": pipeline_state["status"],
        "started_at": pipeline_state["started_at"],
        "completed_at": pipeline_state["completed_at"],
        "result": pipeline_state["result"],
    }
    runs_history.insert(0, run_entry)
    # Keep only last 50 runs
    if len(runs_history) > 50:
        runs_history.pop()
    _save_runs_history()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


# --- Auto-Apply background runners ---
import threading


async def _run_apply(application_url: str, resume_pdf_path: str):
    """Run the auto-apply in a completely separate thread (no asyncio context)."""
    from src.core.config import load_config

    cfg = load_config()
    apply_session_state["status"] = "running"
    apply_session_state["message"] = "Starting auto-apply..."
    apply_session_state["screenshots"] = []
    apply_session_state["current_step"] = 0
    apply_session_state["application_url"] = application_url
    apply_session_state["error"] = ""

    handler = PipelineLogHandler()
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)

    def _thread_target():
        try:
            from src.agents.form_filler import run_auto_apply
            result = run_auto_apply(
                application_url,
                resume_pdf_path,
                cfg.apply.applicant_profile_path
            )
            apply_session_state["status"] = result.get("status", "failed")
            apply_session_state["message"] = result.get("message", "")
            apply_session_state["screenshots"] = result.get("screenshots", [])
            apply_session_state["current_step"] = result.get("current_step", 0)
            apply_session_state["error"] = result.get("error", "")
        except Exception as e:
            apply_session_state["status"] = "failed"
            apply_session_state["error"] = str(e)
            apply_session_state["message"] = f"Auto-apply failed: {e}"
            logger.error(f"Auto-apply failed: {e}")
        finally:
            root_logger.removeHandler(handler)

    t = threading.Thread(target=_thread_target, daemon=True)
    t.start()


async def _confirm_apply():
    """Confirm and submit after human approval (in separate thread)."""
    apply_session_state["status"] = "running"
    apply_session_state["message"] = "Submitting application..."

    handler = PipelineLogHandler()
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)

    def _thread_target():
        try:
            from src.agents.form_filler import confirm_and_submit
            result = confirm_and_submit()
            apply_session_state["status"] = result.get("status", "failed")
            apply_session_state["message"] = result.get("message", "")
            if result.get("screenshots"):
                apply_session_state["screenshots"].extend(result["screenshots"])
            apply_session_state["error"] = result.get("error", "")
        except Exception as e:
            apply_session_state["status"] = "failed"
            apply_session_state["error"] = str(e)
            logger.error(f"Confirm apply failed: {e}")
        finally:
            root_logger.removeHandler(handler)

    t = threading.Thread(target=_thread_target, daemon=True)
    t.start()

