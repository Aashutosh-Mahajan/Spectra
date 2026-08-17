"""
LangGraph StateGraph — Full audit pipeline with parallel fan-out.

Flow: orchestrator → [Send() fan-out: 6 agents in parallel] → aggregator → report_writer → END
"""

import os
import logging
import operator
import fnmatch
from typing import Annotated, Optional, TypedDict

from langgraph.graph import StateGraph, START, END
from langgraph.types import Send

from backend.utils.repo_cloner import clone_repo, CloneError
from backend.utils.file_router import route_files
from backend.utils.rag_manager import RAGContextManager
from backend.agents.frontend_agent import FrontendAgent
from backend.agents.backend_agent import BackendAgent
from backend.agents.database_agent import DatabaseAgent
from backend.agents.security_agent import SecurityAgent
from backend.agents.devops_agent import DevOpsAgent
from backend.agents.dependency_agent import DependencyAgent
from backend.agents.aggregator_agent import AggregatorAgent
from backend.report.generator import generate_markdown_report

logger = logging.getLogger(__name__)


def _read_int_env(var_name: str, default: int, min_value: int = 1) -> int:
    """Read an integer env var safely and fall back to default when invalid."""
    raw = os.environ.get(var_name)
    if raw is None:
        return default

    try:
        parsed = int(raw)
        if parsed < min_value:
            raise ValueError()
        return parsed
    except ValueError:
        logger.warning(f"Invalid {var_name}={raw!r}; using default {default}.")
        return default


DEFAULT_MAX_FILES_PER_AGENT = _read_int_env("MAX_FILES_PER_AGENT", 20, min_value=1)
DEFAULT_RATE_LIMIT_RPM = _read_int_env("OPENAI_RATE_LIMIT_RPM", 20, min_value=1)
DEFAULT_MAX_CHUNKS_PER_FILE = _read_int_env("MAX_CHUNKS_PER_FILE", 2, min_value=1)

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

AGENT_PRIORITY_PATTERNS: dict[str, list[str]] = {
    "security": [
        "**/auth*", "**/*auth*", "**/*login*", "**/*token*", "**/*secret*",
        "**/*jwt*", "**/*oauth*", "**/*permission*",
    ],
    "backend": [
        "**/api/**", "**/routes/**", "**/controllers/**", "**/views/**",
        "**/service*/**", "**/handler*/**", "**/main.py", "**/app.py",
    ],
    "frontend": [
        "**/src/**", "**/pages/**", "**/components/**", "**/app.*", "**/index.*",
    ],
    "database": [
        "**/migrations/**", "**/*model*", "**/*.sql", "**/*schema*", "**/*repository*",
    ],
    "devops": [
        "**/dockerfile*", "**/docker-compose*.yml", "**/docker-compose*.yaml",
        "**/.github/workflows/**", "**/k8s/**", "**/kubernetes/**", "**/*.tf", "**/*.hcl",
    ],
    "dependency": [
        "**/package.json", "**/package-lock.json", "**/yarn.lock", "**/pnpm-lock.yaml",
        "**/requirements*.txt", "**/pyproject.toml", "**/go.mod", "**/pom.xml",
        "**/cargo.toml", "**/gemfile", "**/composer.json",
    ],
}


def _score_file_for_agent(agent_name: str, rel_path: str) -> int:
    """Assign a lightweight relevance score so we scan high-value files first."""
    normalized = rel_path.lower()
    score = 0

    for pattern in AGENT_PRIORITY_PATTERNS.get(agent_name, []):
        if fnmatch.fnmatch(normalized, pattern):
            score += 10

    # Prefer shallower files as a tie-breaker (entry points/config files).
    depth = normalized.count("/")
    score += max(0, 3 - depth)
    return score


def _limit_file_map(file_map: dict[str, list[str]], max_files_per_agent: int) -> tuple[dict[str, list[str]], dict[str, int]]:
    """Cap each agent's file list to reduce LLM calls and token spend."""
    limited_map: dict[str, list[str]] = {}
    dropped_counts: dict[str, int] = {}

    for agent_name, files in file_map.items():
        unique_files = sorted(set(files))
        ranked_files = sorted(
            unique_files,
            key=lambda p: (-_score_file_for_agent(agent_name, p), p.count("/"), p),
        )

        if len(ranked_files) > max_files_per_agent:
            limited_map[agent_name] = ranked_files[:max_files_per_agent]
            dropped_counts[agent_name] = len(ranked_files) - max_files_per_agent
        else:
            limited_map[agent_name] = ranked_files

    return limited_map, dropped_counts


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
    include_patterns: list[str]
    exclude_patterns: list[str]
    max_files_per_agent: int
    rate_limit_rpm: int
    max_chunks_per_file: int
    repo_path: str
    file_map: dict[str, list[str]]
    agent_findings: Annotated[dict[str, list], _merge_findings]
    aggregated_findings: list
    orchestrator_summary: dict
    report_md: str
    report_md_path: str
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
    repo_url = state.get("repo_url")
    github_token = state.get("github_token")
    include_patterns = state.get("include_patterns", [])
    exclude_patterns = state.get("exclude_patterns", [])
    max_files_per_agent = state.get("max_files_per_agent") or DEFAULT_MAX_FILES_PER_AGENT

    if repo_url:
        _update_job_status(job_id, status="cloning", current_step=f"Cloning {repo_url}...", progress_percent=5)
        try:
            storage_base = os.environ.get("JOB_STORAGE_PATH", "./storage/jobs")
            repo_path = clone_repo(repo_url=repo_url, job_id=job_id, github_token=github_token, storage_base=storage_base)
        except CloneError as e:
            _update_job_status(job_id, status="failed", error=str(e), current_step="Clone failed")
            return {"error": str(e), "status": "failed"}
    else:
        # It's a local folder audit, repo_path is already provided in state.
        repo_path = state.get("repo_path")
        if not repo_path or not os.path.isdir(repo_path):
            error_msg = f"Invalid local directory: {repo_path}"
            _update_job_status(job_id, status="failed", error=error_msg, current_step="Init failed")
            return {"error": error_msg, "status": "failed"}
        _update_job_status(job_id, status="routing", current_step=f"Scanning local directory {repo_path}...", progress_percent=5)

    _update_job_status(job_id, status="routing", current_step="Analyzing file structure...", progress_percent=15)
    file_map = route_files(
        repo_path=repo_path,
        exclude_patterns=exclude_patterns,
        include_patterns=include_patterns,
    )
    file_map, dropped_counts = _limit_file_map(file_map, max_files_per_agent)

    active_agents = [name for name in ALL_AGENT_NAMES if file_map.get(name)]
    file_summary = ", ".join(f"{k}: {len(v)}" for k, v in file_map.items() if v)
    dropped_summary = ", ".join(f"{k}: -{v}" for k, v in dropped_counts.items() if v)

    step_msg = f"Routed files ({file_summary})"
    if dropped_summary:
        step_msg += f" | file cap applied ({dropped_summary})"

    _update_job_status(job_id, current_step="Building RAG index...", progress_percent=20)
    try:
        rag_manager = RAGContextManager(repo_path)
        rag_manager.build_or_load_index(file_map)
    except Exception as e:
        logger.warning(f"Failed to build RAG index: {e}")

    _update_job_status(
        job_id, current_step=step_msg,
        progress_percent=20, agents_queued=active_agents, file_map=file_map,
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
    rate_limit_rpm = state.get("rate_limit_rpm", DEFAULT_RATE_LIMIT_RPM)
    max_chunks_per_file = state.get("max_chunks_per_file", DEFAULT_MAX_CHUNKS_PER_FILE)
    agent_cls = AGENT_CLASSES[agent_name]
    agent = agent_cls(
        model_name=model_name,
        rate_limit_rpm=rate_limit_rpm,
        max_chunks_per_file=max_chunks_per_file,
    )

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

    _update_job_status(job_id, status="reporting", current_step="Synthesizing executive summary...", progress_percent=85)

    findings = state.get("aggregated_findings", [])

    from backend.agents.orchestrator_agent import OrchestratorAgent
    orchestrator = OrchestratorAgent()
    orchestrator_summary = await orchestrator.synthesize(findings)

    _update_job_status(job_id, current_step="Generating audit report...", progress_percent=90)

    report_md = generate_markdown_report(
        findings=findings,
        repo_url=repo_url,
        branch=branch,
        orchestrator_summary=orchestrator_summary
    )

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

    return {
        "orchestrator_summary": orchestrator_summary,
        "report_md": report_md,
        "report_md_path": os.path.abspath(md_path),
        "report_pdf_path": pdf_path,
        "status": "done"
    }


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
