"""
Audit API routes — POST /audit, GET /audit/{job_id}/status
"""

import os
import uuid
import logging
import asyncio

from fastapi import APIRouter, BackgroundTasks, HTTPException

from backend.api.models import AuditRequest, AuditResponse, JobStatus
from backend.graph.audit_graph import audit_graph, jobs_store

logger = logging.getLogger(__name__)

router = APIRouter()


async def run_audit_pipeline(job_id: str, request: AuditRequest) -> None:
    """
    Background task: execute the full LangGraph audit pipeline.

    Args:
        job_id: Unique job identifier
        request: Audit request parameters
    """
    try:
        logger.info(f"[{job_id}] Starting audit pipeline for {request.repo_url}")

        # Build initial state
        initial_state = {
            "job_id": job_id,
            "repo_url": request.repo_url,
            "branch": request.branch,
            "github_token": request.github_token,
            "exclude_patterns": request.exclude_patterns,
            "repo_path": "",
            "file_map": {},
            "agent_findings": {},
            "aggregated_findings": [],
            "report_md": "",
            "report_pdf_path": "",
            "status": "queued",
            "current_step": "Starting audit...",
            "agents_done": [],
            "error": None,
        }

        # Execute the graph
        result = await audit_graph.ainvoke(initial_state)

        # Check for errors
        if result.get("error"):
            logger.error(f"[{job_id}] Pipeline failed: {result['error']}")
        else:
            logger.info(f"[{job_id}] Pipeline completed successfully")

    except Exception as e:
        logger.exception(f"[{job_id}] Unhandled error in pipeline: {e}")
        jobs_store[job_id].update({
            "status": "failed",
            "error": f"Internal error: {str(e)}",
            "current_step": "Pipeline crashed",
        })


@router.post("/audit", response_model=AuditResponse)
async def start_audit(request: AuditRequest, background_tasks: BackgroundTasks):
    """
    Start a new codebase audit.

    Accepts a GitHub repository URL, creates a job, and launches the
    audit pipeline as a background task.
    """
    # Generate unique job ID
    job_id = str(uuid.uuid4())

    # Initialize job status in the store
    jobs_store[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "progress_percent": 0,
        "current_step": "Job created, queued for processing...",
        "agents_done": [],
        "agents_running": [],
        "agents_queued": [],
        "finding_counts": {"EXTREME": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0},
        "total_findings": 0,
        "error": None,
        "report_md_ready": False,
        "report_pdf_ready": False,
    }

    logger.info(f"[{job_id}] Audit job created for {request.repo_url}")

    # Launch pipeline as background task
    background_tasks.add_task(run_audit_pipeline, job_id, request)

    return AuditResponse(job_id=job_id, message="Audit started successfully")


@router.get("/audit/{job_id}/status", response_model=JobStatus)
async def get_audit_status(job_id: str):
    """
    Get the current status of an audit job.

    Returns progress, agent states, and finding counts.
    """
    if job_id not in jobs_store:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    job_data = jobs_store[job_id]
    return JobStatus(**job_data)
