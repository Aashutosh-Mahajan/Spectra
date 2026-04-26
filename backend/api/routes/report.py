"""
Report download routes — GET /report/{job_id}/download
"""

import os
import logging

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from backend.graph.audit_graph import jobs_store

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/report/{job_id}/download")
async def download_report(
    job_id: str,
    format: str = Query(default="md", description="Report format: 'md' or 'pdf'"),
):
    """
    Download the generated audit report.

    Args:
        job_id: Job identifier
        format: Report format — "md" for Markdown, "pdf" for PDF

    Returns:
        FileResponse streaming the report file
    """
    # Check job exists
    if job_id not in jobs_store:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    job_data = jobs_store[job_id]

    # Check job is complete
    if job_data.get("status") != "done":
        raise HTTPException(
            status_code=400,
            detail=f"Report not ready. Job status: {job_data.get('status')}. "
                   f"Current step: {job_data.get('current_step')}"
        )

    storage_base = os.environ.get("JOB_STORAGE_PATH", "./storage/jobs")

    if format == "md":
        if not job_data.get("report_md_ready"):
            raise HTTPException(status_code=400, detail="Markdown report not available")

        report_path = os.path.join(storage_base, job_id, f"report_{job_id}.md")
        if not os.path.exists(report_path):
            raise HTTPException(status_code=404, detail="Report file not found on disk")

        return FileResponse(
            path=report_path,
            filename=f"audit_report_{job_id}.md",
            media_type="text/markdown",
        )

    elif format == "pdf":
        if not job_data.get("report_pdf_ready"):
            raise HTTPException(status_code=400, detail="PDF report not available (Phase 2 feature)")

        report_path = os.path.join(storage_base, job_id, f"report_{job_id}.pdf")
        if not os.path.exists(report_path):
            raise HTTPException(status_code=404, detail="PDF report file not found on disk")

        return FileResponse(
            path=report_path,
            filename=f"audit_report_{job_id}.pdf",
            media_type="application/pdf",
        )

    else:
        raise HTTPException(status_code=400, detail=f"Invalid format: {format}. Use 'md' or 'pdf'.")
