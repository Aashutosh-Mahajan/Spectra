"""
LangGraph StateGraph — Full audit pipeline with parallel fan-out.

Flow: orchestrator → [Send() fan-out: 6 agents in parallel] → aggregator → report_writer → END
"""

import os
import logging
import operator
from typing import Annotated, Optional, TypedDict

from langgraph.graph import StateGraph, START, END
from langgraph.types import Send

from backend.utils.repo_cloner import clone_repo, cleanup_repo, CloneError
from backend.utils.file_router import route_files
from backend.agents.frontend_agent import FrontendAgent
from backend.agents.backend_agent import BackendAgent
from backend.agents.database_agent import DatabaseAgent
from backend.agents.security_agent import SecurityAgent
from backend.agents.devops_agent import DevOpsAgent
from backend.agents.dependency_agent import DependencyAgent
from backend.agents.aggregator_agent import AggregatorAgent
from backend.report.generator import generate_markdown_report

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# In-memory job store (shared with FastAPI routes)
# ─────────────────────────────────────────────
jobs_store: dict[str, dict] = {}

AGENT_CLASSES = {
    "frontend": FrontendAgent,
    "backend": BackendAgent,
    "database": DatabaseAgent,
    "security": SecurityAgent,
    "devops": DevOpsAgent,
    "dependency": DependencyAgent,
}

ALL_AGENT_NAMES = list(AGENT_CLASSES.keys())


def _update_job_status(job_id: str, **kwargs) -> None:
    if job_id in jobs_store:
        jobs_store[job_id].update(kwargs)


# ─────────────────────────────────────────────
# Graph State
# ─────────────────────────────────────────────

def _merge_findings(existing: dict, new: dict) -> dict:
    merged = dict(existing) if existing else {}
    for key, findings in (new or {}).items():
        if key in merged:
            merged[key] = merged[key] + findings
        else:
            merged[key] = findings
    return merged


class AuditState(TypedDict):
    job_id: str
    repo_url: str
    branch: str
    github_token: Optional[str]
    exclude_patterns: list[str]
    repo_path: str
    file_map: dict[str, list[str]]
    agent_findings: Annotated[dict[str, list], _merge_findings]
    aggregated_findings: list
    report_md: str
    report_pdf_path: str
    status: str
    current_step: str
    agents_done: Annotated[list[str], operator.add]
    error: Optional[str]


# ─────────────────────────────────────────────
# Node: Orchestrator (clone + route + fan-out)
# ─────────────────────────────────────────────

async def orchestrator_node(state: AuditState) -> dict:
    job_id = state["job_id"]
    repo_url = state["repo_url"]
    github_token = state.get("github_token")
    exclude_patterns = state.get("exclude_patterns", [])

    _update_job_status(job_id, status="cloning", current_step=f"Cloning {repo_url}...", progress_percent=5)

    try:
        storage_base = os.environ.get("JOB_STORAGE_PATH", "./storage/jobs")
        repo_path = clone_repo(repo_url=repo_url, job_id=job_id, github_token=github_token, storage_base=storage_base)
    except CloneError as e:
        _update_job_status(job_id, status="failed", error=str(e), current_step="Clone failed")
        return {"error": str(e), "status": "failed"}

    _update_job_status(job_id, status="routing", current_step="Analyzing file structure...", progress_percent=15)
    file_map = route_files(repo_path, exclude_patterns)

    active_agents = [name for name in ALL_AGENT_NAMES if file_map.get(name)]
    file_summary = ", ".join(f"{k}: {len(v)}" for k, v in file_map.items() if v)
    _update_job_status(
        job_id, current_step=f"Routed files ({file_summary})",
        progress_percent=20, agents_queued=active_agents,
    )

    return {"repo_path": repo_path, "file_map": file_map, "status": "running"}


# ─────────────────────────────────────────────
# Conditional edge: fan-out to agents via Send()
# ─────────────────────────────────────────────

def route_to_agents(state: AuditState):
    if state.get("error"):
        return [Send("aggregator", state)]

    file_map = state.get("file_map", {})
    sends = []
    for agent_name in ALL_AGENT_NAMES:
        if file_map.get(agent_name):
            sends.append(Send("agent_worker", {**state, "_agent_name": agent_name}))

    if not sends:
        return [Send("aggregator", state)]
    return sends


# ─────────────────────────────────────────────
# Node: Generic agent worker (runs any specialist)
# ─────────────────────────────────────────────

async def agent_worker_node(state: dict) -> dict:
    agent_name = state.get("_agent_name", "unknown")
    job_id = state["job_id"]
    repo_path = state["repo_path"]
    file_map = state["file_map"]

    if state.get("error"):
        return {"agents_done": [agent_name], "agent_findings": {agent_name: []}}

    agent_files = file_map.get(agent_name, [])
    if not agent_files:
        return {"agents_done": [agent_name], "agent_findings": {agent_name: []}}

    _update_job_status(job_id, current_step=f"{agent_name.capitalize()} Agent scanning {len(agent_files)} files...")

    # Update running agents
    if job_id in jobs_store:
        running = list(set(jobs_store[job_id].get("agents_running", []) + [agent_name]))
        jobs_store[job_id]["agents_running"] = running

    model_name = os.environ.get("OPENAI_MODEL", "gpt-5.4-mini")
    agent_cls = AGENT_CLASSES[agent_name]
    agent = agent_cls(model_name=model_name)

    try:
        findings = await agent.analyze_files(agent_files, repo_path)
        findings_dicts = [f.model_dump() for f in findings]
    except Exception as e:
        logger.error(f"[{job_id}] {agent_name} agent failed: {e}")
        findings_dicts = []

    # Update status
    if job_id in jobs_store:
        running = jobs_store[job_id].get("agents_running", [])
        jobs_store[job_id]["agents_running"] = [a for a in running if a != agent_name]
        done = jobs_store[job_id].get("agents_done", [])
        if agent_name not in done:
            jobs_store[job_id]["agents_done"] = done + [agent_name]
        # Update progress based on how many agents are done
        total_agents = len([n for n in ALL_AGENT_NAMES if file_map.get(n)])
        done_count = len(jobs_store[job_id]["agents_done"])
        progress = 20 + int((done_count / max(total_agents, 1)) * 50)
        jobs_store[job_id]["progress_percent"] = progress

    return {"agents_done": [agent_name], "agent_findings": {agent_name: findings_dicts}}


# ─────────────────────────────────────────────
# Node: Aggregator
# ─────────────────────────────────────────────

async def aggregator_node(state: AuditState) -> dict:
    job_id = state["job_id"]

    if state.get("error"):
        return {}

    _update_job_status(job_id, status="aggregating", current_step="Aggregating and deduplicating findings...", progress_percent=75)

    all_findings = []
    for agent_name, findings in (state.get("agent_findings") or {}).items():
        all_findings.extend(findings)

    aggregator = AggregatorAgent()
    aggregated = aggregator.aggregate(all_findings)

    _update_job_status(job_id, current_step=f"Aggregated: {len(aggregated)} unique findings", progress_percent=80)

    return {"aggregated_findings": aggregated}


# ─────────────────────────────────────────────
# Node: Report Writer
# ─────────────────────────────────────────────

async def report_writer_node(state: AuditState) -> dict:
    job_id = state["job_id"]
    repo_url = state["repo_url"]
    branch = state.get("branch", "main")

    if state.get("error"):
        return {}

    _update_job_status(job_id, status="reporting", current_step="Generating audit report...", progress_percent=85)

    findings = state.get("aggregated_findings", [])
    report_md = generate_markdown_report(findings=findings, repo_url=repo_url, branch=branch)

    storage_base = os.environ.get("JOB_STORAGE_PATH", "./storage/jobs")
    report_dir = os.path.join(storage_base, job_id)
    os.makedirs(report_dir, exist_ok=True)

    md_path = os.path.join(report_dir, f"report_{job_id}.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(report_md)

    # Generate PDF report
    pdf_ready = False
    try:
        from backend.report.pdf_generator import generate_pdf_report
        pdf_path = generate_pdf_report(report_md, job_id, storage_base)
        pdf_ready = True
    except Exception as e:
        logger.warning(f"PDF generation failed (non-critical): {e}")
        pdf_path = ""

    # Count findings by severity
    finding_counts = {"EXTREME": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for f in findings:
        sev = f.get("severity", "LOW")
        if sev in finding_counts:
            finding_counts[sev] += 1

    _update_job_status(
        job_id, status="done", current_step="Audit complete!", progress_percent=100,
        finding_counts=finding_counts, total_findings=len(findings),
        report_md_ready=True, report_pdf_ready=pdf_ready,
    )

    return {"report_md": report_md, "report_pdf_path": pdf_path, "status": "done"}


# ─────────────────────────────────────────────
# Build the Graph
# ─────────────────────────────────────────────

def build_audit_graph() -> StateGraph:
    graph = StateGraph(AuditState)

    graph.add_node("orchestrator", orchestrator_node)
    graph.add_node("agent_worker", agent_worker_node)
    graph.add_node("aggregator", aggregator_node)
    graph.add_node("report_writer", report_writer_node)

    graph.add_edge(START, "orchestrator")
    graph.add_conditional_edges("orchestrator", route_to_agents)
    graph.add_edge("agent_worker", "aggregator")
    graph.add_edge("aggregator", "report_writer")
    graph.add_edge("report_writer", END)

    return graph.compile()


audit_graph = build_audit_graph()
