"""
Pydantic models for API request/response schemas and core data structures.
"""

import uuid
from typing import Literal, Optional
from pydantic import BaseModel, Field, HttpUrl


# ─────────────────────────────────────────────
# Request / Response Models
# ─────────────────────────────────────────────

class AuditRequest(BaseModel):
    """Request body for POST /audit."""
    repo_url: str = Field(..., description="GitHub repository URL to audit")
    branch: str = Field(default="main", description="Branch to clone")
    github_token: Optional[str] = Field(default=None, description="GitHub personal access token for private repos")
    include_patterns: list[str] = Field(default_factory=list, description="File patterns to include")
    exclude_patterns: list[str] = Field(
        default_factory=lambda: ["node_modules", ".git", "dist", "__pycache__", ".venv", "venv", ".env"],
        description="File/directory patterns to exclude"
    )


class AuditResponse(BaseModel):
    """Response for POST /audit."""
    job_id: str = Field(..., description="Unique job identifier")
    message: str = Field(default="Audit started successfully")


# ─────────────────────────────────────────────
# Core Data Models
# ─────────────────────────────────────────────

class FileLocation(BaseModel):
    """Location of a finding within the repository."""
    file_path: str = Field(..., description="Relative path from repo root, e.g. 'src/api/users.py'")
    line_start: int = Field(..., description="Starting line number")
    line_end: int = Field(..., description="Ending line number")


class Finding(BaseModel):
    """A single audit finding from an agent."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique finding ID")
    agent: str = Field(..., description="Agent that detected this: 'security', 'backend', etc.")
    severity: Literal["EXTREME", "HIGH", "MEDIUM", "LOW"] = Field(..., description="Severity classification")
    title: str = Field(..., description="Short descriptive title, e.g. 'SQL Injection in user_query()'")
    bug_type: str = Field(..., description="Category: 'Injection', 'Memory Leak', 'CORS Misconfiguration', etc.")
    what_is_it: str = Field(..., description="Plain-English description of the bug")
    why_it_occurs: str = Field(..., description="Root cause explanation")
    how_it_occurred: str = Field(..., description="What code pattern caused it")
    where_it_is: FileLocation = Field(..., description="File location of the finding")
    affected_code: str = Field(default="", description="Code snippet showing the issue")
    recommended_fix: str = Field(..., description="How to fix the issue")
    references: list[str] = Field(default_factory=list, description="CWE IDs, OWASP links, docs")
    score: float = Field(default=0.0, ge=0.0, le=100.0, description="Severity score 0.0–100.0")
    detected_by: list[str] = Field(default_factory=list, description="All agents that flagged this (post-dedup)")


# ─────────────────────────────────────────────
# Job Status Model
# ─────────────────────────────────────────────

class JobStatus(BaseModel):
    """Status of an audit job, returned by GET /audit/{job_id}/status."""
    job_id: str
    status: Literal["queued", "cloning", "routing", "running", "aggregating", "reporting", "done", "failed"] = "queued"
    progress_percent: int = Field(default=0, ge=0, le=100)
    current_step: str = Field(default="Initializing...")
    agents_done: list[str] = Field(default_factory=list)
    agents_running: list[str] = Field(default_factory=list)
    agents_queued: list[str] = Field(default_factory=list)
    finding_counts: dict[str, int] = Field(
        default_factory=lambda: {"EXTREME": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    )
    total_findings: int = 0
    error: Optional[str] = None
    report_md_ready: bool = False
    report_pdf_ready: bool = False
