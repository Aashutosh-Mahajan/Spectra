# 🔍 Codebase Audit Agent System — Project Plan

> **Team:** Neural Ninjas  
> **Stack:** FastAPI · Streamlit · LangGraph · GPT-4.5  
> **Goal:** A multi-agent AI pipeline that audits any GitHub repository, finds bugs and issues across the full stack, and generates a downloadable structured report in `.md` and `.pdf`.

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [High-Level Architecture Flow](#2-high-level-architecture-flow)
3. [Directory Structure](#3-directory-structure)
4. [Backend — Component Breakdown](#4-backend--component-breakdown)
   - 4.1 FastAPI Entry Point & Routes
   - 4.2 Repo Cloner
   - 4.3 File Router
   - 4.4 LangGraph Pipeline
   - 4.5 Specialist Agents
   - 4.6 Aggregator Agent
   - 4.7 Report Generator
5. [Frontend — Streamlit UI](#5-frontend--streamlit-ui)
6. [Data Schemas](#6-data-schemas)
7. [Tech Stack Summary](#7-tech-stack-summary)
8. [Key Design Decisions](#8-key-design-decisions)
9. [Development Phases](#9-development-phases)
10. [Environment Variables](#10-environment-variables)

---

## 1. System Overview

The **Codebase Audit Agent System** accepts a GitHub repository URL from the user, clones the repository, and dispatches a fleet of specialized AI agents — each responsible for a different layer of the codebase (frontend, backend, database, security, DevOps, dependencies). Each agent independently scans its assigned files using GPT-4.5, identifies bugs and issues, and returns structured findings. A final aggregator agent deduplicates and scores everything, and a report writer produces a professional audit report in both Markdown and PDF formats, downloadable directly from the Streamlit frontend.

### Core Capabilities

- Clone any public or private GitHub repository
- Automatically detect and route files to the correct specialist agent
- Run all specialist agents **in parallel** using LangGraph's `Send()` API
- Classify every finding by severity: `EXTREME`, `HIGH`, `MEDIUM`, `LOW`
- For each finding, document: what it is, why it occurs, how it occurred, where it is (file + line)
- Export audit report as `.md` and `.pdf`
- Live progress tracking per agent in the Streamlit UI

---

## 2. High-Level Architecture Flow

```
┌─────────────────────────────────────────────────────────┐
│                   STREAMLIT FRONTEND                    │
│  Input Screen → Progress Screen → Results + Downloads   │
└────────────────────────┬────────────────────────────────┘
                         │  POST /audit
                         ▼
┌─────────────────────────────────────────────────────────┐
│                    FASTAPI BACKEND                      │
│   /audit  ·  /audit/{job_id}/status  ·  /report/download│
└────────────────────────┬────────────────────────────────┘
                         │  Background Task
                         ▼
┌─────────────────────────────────────────────────────────┐
│                  LANGGRAPH PIPELINE                     │
│                                                         │
│  [ORCHESTRATOR NODE]                                    │
│   └── Clone repo (GitPython)                           │
│   └── Walk file tree → map files to agents             │
│        │                                               │
│        ├──── [FRONTEND AGENT]    .jsx .tsx .vue .html  │
│        ├──── [BACKEND AGENT]     .py .js .go .java     │
│        ├──── [DATABASE AGENT]    .sql .prisma models/  │
│        ├──── [SECURITY AGENT]    auth/token/secret/*   │
│        ├──── [DEVOPS AGENT]      Dockerfile CI/CD k8s  │
│        └──── [DEPENDENCY AGENT]  package.json reqs.txt │
│                  │  (all run in parallel via Send())   │
│                  ▼                                      │
│          [AGGREGATOR NODE]                              │
│           └── Deduplicate · Cross-reference · Score    │
│                  │                                      │
│                  ▼                                      │
│          [REPORT WRITER NODE]                           │
│           └── Generate .md + .pdf                      │
└─────────────────────────────────────────────────────────┘
```

---

## 3. Directory Structure

```
codebase-audit/
│
├── backend/
│   ├── main.py                          # FastAPI app entry point
│   ├── api/
│   │   ├── routes/
│   │   │   ├── audit.py                 # POST /audit, GET /audit/{job_id}/status
│   │   │   └── report.py                # GET /report/{job_id}/download
│   │   └── models.py                    # Pydantic request/response models
│   │
│   ├── agents/
│   │   ├── base_agent.py                # Abstract base class for all agents
│   │   ├── orchestrator.py              # Clone repo + file mapping + dispatch
│   │   ├── frontend_agent.py            # UI/client-side code auditor
│   │   ├── backend_agent.py             # Server-side logic auditor
│   │   ├── database_agent.py            # DB queries, ORM, migrations auditor
│   │   ├── security_agent.py            # OWASP / auth / secrets auditor
│   │   ├── devops_agent.py              # Dockerfile / CI/CD / k8s auditor
│   │   ├── dependency_agent.py          # Package CVE + version auditor
│   │   └── aggregator_agent.py          # Dedup + cross-ref + severity scoring
│   │
│   ├── graph/
│   │   └── audit_graph.py               # LangGraph StateGraph definition
│   │
│   ├── report/
│   │   ├── generator.py                 # MD + PDF generation logic
│   │   └── templates/
│   │       ├── report_template.md       # Markdown report template
│   │       └── report_style.css         # PDF styling for WeasyPrint
│   │
│   ├── utils/
│   │   ├── repo_cloner.py               # GitPython shallow clone wrapper
│   │   ├── file_router.py               # Extension/name → agent mapping logic
│   │   ├── chunker.py                   # Large file splitting (token-safe)
│   │   └── severity.py                  # Severity scoring rubric logic
│   │
│   └── storage/
│       └── jobs/                        # Ephemeral: cloned repos + reports per job_id
│
├── frontend/
│   └── app.py                           # Streamlit UI (3-screen flow)
│
├── .env                                 # API keys and config
├── docker-compose.yml                   # FastAPI + Streamlit services
├── Dockerfile.backend
├── Dockerfile.frontend
└── requirements.txt
```

---

## 4. Backend — Component Breakdown

### 4.1 FastAPI Entry Point & Routes

**File:** `backend/main.py`, `backend/api/routes/audit.py`, `backend/api/routes/report.py`

Three core API endpoints:

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/audit` | Accepts repo URL, starts audit pipeline as background task, returns `job_id` |
| `GET` | `/audit/{job_id}/status` | Returns live status — agents done/running, progress %, current step |
| `GET` | `/report/{job_id}/download` | Streams the `.md` or `.pdf` file back to the client |

**Request body for `POST /audit`:**
```json
{
  "repo_url": "https://github.com/user/repo",
  "branch": "main",
  "github_token": "ghp_xxx",
  "include_patterns": [],
  "exclude_patterns": ["node_modules", ".git", "dist", "__pycache__"]
}
```

**Status response for `GET /audit/{job_id}/status`:**
```json
{
  "job_id": "abc-123",
  "status": "running",
  "progress_percent": 60,
  "current_step": "Security Agent scanning 18 files...",
  "agents_done": ["frontend", "devops"],
  "agents_running": ["backend", "security"],
  "agents_queued": ["database", "dependency"]
}
```

Jobs use an **in-memory dictionary** in development. In production, swap to **Redis** for persistence and multi-worker support.

---

### 4.2 Repo Cloner

**File:** `backend/utils/repo_cloner.py`

- Uses **GitPython** to perform a shallow clone (`--depth=1`) of the target repository
- Clones into `storage/jobs/{job_id}/repo/`
- Supports private repos via `https://<token>@github.com/user/repo` URL construction
- GitHub token is used only during clone and never persisted to disk
- After the audit finishes, the cloned directory is deleted to free disk space
- Raises structured errors for: invalid URL, auth failure, repo not found, clone timeout

---

### 4.3 File Router

**File:** `backend/utils/file_router.py`

Walks the cloned repo's file tree using `os.walk()` and groups every file into one or more agent buckets based on extension and filename patterns:

| Agent | File Patterns |
|-------|--------------|
| **Frontend** | `.jsx`, `.tsx`, `.vue`, `.svelte`, `.html`, `.css`, `.scss`, `.less`, `.js` (UI), `.ts` (UI) |
| **Backend** | `.py`, `.js` / `.ts` (server-side), `.java`, `.go`, `.rb`, `.php`, `.rs` |
| **Database** | `.sql`, `schema.prisma`, `models.py`, `migrations/*`, `*.orm.*` |
| **Security** | Files matching: `*auth*`, `*login*`, `*token*`, `*secret*`, `*password*`, `*jwt*`, `*.env*`, `*crypto*` |
| **DevOps** | `Dockerfile*`, `docker-compose*.yml`, `.github/workflows/*.yml`, `k8s/*.yml`, `*.tf` (Terraform) |
| **Dependency** | `package.json`, `requirements.txt`, `go.mod`, `pom.xml`, `Gemfile`, `Cargo.toml`, `pyproject.toml` |

> Note: A single file can appear in multiple buckets (e.g., `auth_routes.py` goes to both Backend and Security agents).

---

### 4.4 LangGraph Pipeline

**File:** `backend/graph/audit_graph.py`

The LangGraph `StateGraph` is the core orchestration layer. It defines the full audit pipeline as a directed graph with typed state.

**Graph State (`AuditState`):**
```python
class AuditState(TypedDict):
    job_id: str
    repo_url: str
    repo_path: str
    file_map: dict[str, list[str]]           # agent_name → [file_paths]
    agent_findings: dict[str, list[Finding]] # raw findings per agent
    aggregated_findings: list[Finding]        # final deduplicated list
    report_md: str
    report_pdf_path: str
    status: str
    current_step: str
    agents_done: list[str]
    agents_running: list[str]
    error: Optional[str]
```

**Graph Node Flow:**
```
START
  └──▶ orchestrator_node
            └──▶ [Send() fan-out — all 6 agents run in parallel]
                  ├──▶ frontend_agent_node
                  ├──▶ backend_agent_node
                  ├──▶ database_agent_node
                  ├──▶ security_agent_node
                  ├──▶ devops_agent_node
                  └──▶ dependency_agent_node
                            └──▶ [all join] aggregator_node
                                        └──▶ report_writer_node
                                                    └──▶ END
```

LangGraph's `Send()` API is used inside the orchestrator node to dispatch all six agent nodes simultaneously. Each agent node writes its findings back into `agent_findings[agent_name]` in the shared state. The aggregator node waits for all six to complete before executing.

---

### 4.5 Specialist Agents

**Files:** `backend/agents/frontend_agent.py`, `backend_agent.py`, etc.

All agents extend `BaseAuditAgent` which provides:
- File reading with chunking (via `chunker.py`)
- OpenAI GPT-4.5 API call wrapper
- Structured JSON response parsing into `Finding` objects
- Per-chunk retry logic (max 3 retries on API failure)

Each agent is initialized with a specialized **system prompt** that focuses its attention:

#### Frontend Agent
Focuses on: XSS via `dangerouslySetInnerHTML`, unescaped user input rendered in templates, memory leaks in `useEffect` (missing cleanup), improper `key` props causing re-render bugs, exposed API keys in client-side code, missing CSRF tokens, insecure `localStorage` usage for sensitive data, broken accessibility (missing ARIA, unlabeled inputs).

#### Backend Agent
Focuses on: Missing input validation, improper error handling exposing stack traces, race conditions in async code, business logic flaws, insecure direct object references (IDOR), missing rate limiting, broken authentication middleware, unhandled exceptions causing 500s.

#### Database Agent
Focuses on: Raw SQL with unsanitized user input (SQL injection), missing indexes causing N+1 query patterns, unprotected mass assignment in ORM models, missing database-level constraints, dangerous migration operations (column drops, destructive changes), missing transaction handling.

#### Security Agent
Focuses on: OWASP Top 10 comprehensively — injection flaws, broken auth, sensitive data exposure, XXE, broken access control, security misconfiguration, stored/reflected XSS, insecure deserialization, using components with known vulnerabilities, insufficient logging. Also checks for: hardcoded secrets/API keys, weak JWT configuration, missing HTTPS enforcement, overly permissive CORS.

#### DevOps Agent
Focuses on: Containers running as root, missing resource limits (CPU/memory), exposed secrets in Dockerfiles or CI/CD YAML, insecure base images (outdated/unverified), world-readable sensitive volume mounts, missing health checks, insecure Terraform configurations, public S3 buckets or open security groups.

#### Dependency Agent
Focuses on: Outdated packages with known CVEs (cross-referenced against OSV.dev API), packages with no recent maintenance, license compliance issues, conflicting/incompatible version pinning, packages with excessive permissions or suspicious origins.

---

### 4.6 Aggregator Agent

**File:** `backend/agents/aggregator_agent.py`

After all six specialist agents complete, the aggregator:

1. **Deduplicates** — findings pointing to the same file + approximate line range + same bug type are merged into one canonical finding, crediting all agents that detected it.

2. **Cross-references** — chains related findings across agents. Example: an unsanitized user input (Frontend) that flows into a raw SQL call (Database) gets merged and flagged as a critical injection chain with severity bumped to `EXTREME`.

3. **Severity Scoring** — applies a weighted rubric:

| Factor | Weight |
|--------|--------|
| Exploitability (can it be triggered remotely?) | 35% |
| Impact (data loss, auth bypass, service down?) | 40% |
| Exposure (public endpoint vs internal only?) | 25% |

Final severity bands:
- **EXTREME** — Score ≥ 90 · Immediate critical risk (e.g., unauthenticated RCE, hardcoded root credentials)
- **HIGH** — Score 70–89 · Significant risk requiring urgent fix (e.g., SQL injection, auth bypass)
- **MEDIUM** — Score 40–69 · Notable issue, fix before next release (e.g., insecure deserialization, CORS misconfiguration)
- **LOW** — Score < 40 · Best practice violation, low exploitability (e.g., missing security headers, verbose errors)

---

### 4.7 Report Generator

**File:** `backend/report/generator.py`

Takes the final `aggregated_findings` list and generates two output files:

#### Markdown Report (`report_{job_id}.md`)

Structure:
```
# Codebase Audit Report
**Repository:** <url>  **Branch:** <branch>  **Date:** <timestamp>

---

## Executive Summary
| Severity | Count |
|----------|-------|
| 🔴 EXTREME | X |
| 🟠 HIGH    | X |
| 🟡 MEDIUM  | X |
| 🔵 LOW     | X |
| **Total**  | X |

**Risk Score:** XX/100

### Top 3 Critical Findings
(callout cards for the 3 most severe issues)

---

## Findings by Severity

### 🔴 EXTREME SEVERITY

#### [E-001] <Finding Title>
| Field            | Detail |
|------------------|--------|
| **Bug Type**     | e.g. SQL Injection |
| **What is it**   | Plain-English description |
| **Why it occurs**| Root cause explanation |
| **How it occurred**| Code pattern that caused it |
| **Where**        | `src/api/users.py` · Lines 42–58 |
| **Affected Code**| ```python\n<snippet>\n``` |
| **Recommended Fix** | Detailed fix instructions |
| **References**   | CWE-89, OWASP A03:2021 |

(repeats for each finding)

### 🟠 HIGH SEVERITY ...
### 🟡 MEDIUM SEVERITY ...
### 🔵 LOW SEVERITY ...

---

## Findings by Agent
(summary table per agent with their finding counts)

## Dependency CVE Table
(package · version · CVE ID · severity · fix version)

## Appendix: File Scan Coverage
(list of all files scanned, grouped by agent)
```

#### PDF Report (`report_{job_id}.pdf`)

- Convert Markdown → styled HTML using a custom CSS template
- Render HTML → PDF using **WeasyPrint**
- Styling: dark severity-colored section headers, monospace code blocks with syntax highlighting, color-coded severity badges, Neural Ninjas branding header/footer, page numbers

---

## 5. Frontend — Streamlit UI

**File:** `frontend/app.py`

Three screens managed via `st.session_state`:

### Screen 1 — Input

```
┌──────────────────────────────────────────────┐
│  🔍 CODEBASE AUDIT SYSTEM                    │
│                                              │
│  GitHub Repository URL                       │
│  [ https://github.com/user/repo          ]   │
│                                              │
│  Branch (optional)   GitHub Token (optional) │
│  [ main           ]  [ ghp_xxx...        ]   │
│                                              │
│  Exclude patterns (comma-separated)          │
│  [ node_modules, dist, __pycache__       ]   │
│                                              │
│           [ 🚀 Start Audit ]                 │
└──────────────────────────────────────────────┘
```

### Screen 2 — Live Progress

Polls `GET /audit/{job_id}/status` every 2 seconds using `time.sleep()` + `st.rerun()`.

```
┌──────────────────────────────────────────────┐
│  Auditing: github.com/user/repo              │
│  ████████████████░░░░░░░░░░  62%             │
│                                              │
│  Current: Security Agent scanning 18 files  │
│                                              │
│  ✅ Frontend Agent      (done · 12 findings) │
│  ✅ DevOps Agent        (done · 4 findings)  │
│  🔄 Backend Agent       (running...)         │
│  🔄 Security Agent      (running...)         │
│  ⏳ Database Agent      (queued)             │
│  ⏳ Dependency Agent    (queued)             │
└──────────────────────────────────────────────┘
```

### Screen 3 — Results Dashboard

```
┌──────────────────────────────────────────────┐
│  Audit Complete ✅                            │
│                                              │
│  🔴 EXTREME   🟠 HIGH   🟡 MEDIUM   🔵 LOW  │
│      3            8         14          21   │
│                                              │
│  Risk Score: 78/100                          │
│                                              │
│  ▼ EXTREME (3)                               │
│    [E-001] SQL Injection in user_query()     │
│    [E-002] Hardcoded AWS credentials...      │
│    [E-003] Unauthenticated admin endpoint... │
│                                              │
│  ▼ HIGH (8)  ▼ MEDIUM (14)  ▼ LOW (21)      │
│                                              │
│  [ ⬇ Download .md Report ]                  │
│  [ ⬇ Download .pdf Report ]                 │
└──────────────────────────────────────────────┘
```

---

## 6. Data Schemas

### Finding (Pydantic Model)

```python
class FileLocation(BaseModel):
    file_path: str        # relative to repo root, e.g. "src/api/users.py"
    line_start: int
    line_end: int

class Finding(BaseModel):
    id: str               # UUID4
    agent: str            # "security", "backend", etc.
    severity: Literal["EXTREME", "HIGH", "MEDIUM", "LOW"]
    title: str            # Short name, e.g. "SQL Injection in user_query()"
    bug_type: str         # e.g. "Injection", "Memory Leak", "CORS Misconfiguration"
    what_is_it: str       # Plain-English description of the bug
    why_it_occurs: str    # Root cause explanation
    how_it_occurred: str  # What code pattern caused it
    where_it_is: FileLocation
    affected_code: str    # Code snippet
    recommended_fix: str  # How to fix it
    references: list[str] # CWE IDs, OWASP links, docs
    score: float          # 0.0–100.0 severity score
    detected_by: list[str]# Agents that flagged this (post-dedup)
```

### Job Status (Pydantic Model)

```python
class JobStatus(BaseModel):
    job_id: str
    status: Literal["queued", "cloning", "routing", "running", "aggregating", "reporting", "done", "failed"]
    progress_percent: int
    current_step: str
    agents_done: list[str]
    agents_running: list[str]
    agents_queued: list[str]
    finding_counts: dict[str, int]  # {"EXTREME": 3, "HIGH": 8, ...}
    error: Optional[str]
```

---

## 7. Tech Stack Summary

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Frontend | **Streamlit** | User interface, progress display, report download |
| Backend API | **FastAPI** + Uvicorn | REST API, job management, file serving |
| Agent Orchestration | **LangGraph** (StateGraph + Send API) | Stateful parallel agent pipeline |
| LLM | **GPT-4.5** (`gpt-4.5-preview`) via OpenAI SDK | Code analysis, bug detection |
| Repo Cloning | **GitPython** | Shallow clone of target repositories |
| PDF Generation | **WeasyPrint** | HTML → PDF conversion with custom styling |
| Job State (dev) | In-memory Python dict | Simple single-worker job tracking |
| Job State (prod) | **Redis** | Multi-worker persistent job state |
| Async Jobs | FastAPI `BackgroundTasks` / asyncio | Non-blocking pipeline execution |
| CVE Lookup | **OSV.dev REST API** | Open source vulnerability database lookup |
| Env Management | **python-dotenv** | API keys and configuration |
| Containerization | **Docker Compose** | FastAPI + Streamlit as isolated services |

---

## 8. Key Design Decisions

### Why LangGraph over plain asyncio?
LangGraph provides a stateful, inspectable execution graph with built-in support for parallel fan-out via `Send()`, per-node retry logic, and streaming state updates. Plain `asyncio.gather()` would work for parallelism, but provides no state management, no retry logic, and no clean way to inspect mid-pipeline state for the progress UI.

### Why polling instead of WebSocket streaming?
Each agent processes batches of files — streaming individual LLM tokens to the UI is not meaningful. What matters is per-agent completion events. Simple HTTP polling (`GET /status` every 2 seconds) is sufficient, far simpler to implement, and works natively with Streamlit.

### Token budget management for large repos
Files over ~3,000 tokens are split into overlapping chunks (200-token overlap) by `chunker.py`. Each agent processes one chunk at a time and accumulates findings across chunks. This allows auditing arbitrarily large codebases without hitting the context window limit.

### Security of cloned repos
Each job gets an isolated ephemeral directory. GitHub tokens are never written to disk — they are constructed into the clone URL in memory and discarded immediately after the clone completes. Cloned repos are deleted after report generation.

### Why WeasyPrint over ReportLab for PDF?
WeasyPrint allows us to write the report style in standard CSS (which is maintainable and readable) and convert the already-generated Markdown report into a polished PDF without maintaining a separate programmatic layout in Python. ReportLab is powerful but verbose for document-style output.

---

## 9. Development Phases

### Phase 1 — Core Pipeline *(Week 1)*
- [ ] FastAPI skeleton with `/audit` and `/status` endpoints
- [ ] `repo_cloner.py` + `file_router.py` utilities
- [ ] LangGraph graph definition with state schema
- [ ] Orchestrator node (clone + route)
- [ ] **One complete working agent** (Security Agent as the most impactful)
- [ ] Basic Markdown report generation
- [ ] End-to-end test: URL in → `.md` report out

### Phase 2 — All Agents + Aggregator *(Week 2)*
- [ ] Frontend, Backend, Database, DevOps, Dependency agents
- [ ] Parallel execution via LangGraph `Send()` API
- [ ] Aggregator agent (deduplication + cross-referencing + severity scoring)
- [ ] OSV.dev CVE integration for Dependency Agent
- [ ] PDF report generation (WeasyPrint + CSS template)

### Phase 3 — Streamlit UI + Polish *(Week 3)*
- [ ] 3-screen Streamlit flow (input → progress → results)
- [ ] Live status polling with per-agent progress cards
- [ ] `.md` and `.pdf` download buttons
- [ ] Error states (invalid URL, clone failure, API error)
- [ ] Docker Compose setup for both services

### Phase 4 — Hardening *(Week 4)*
- [ ] Redis for job state (production-ready)
- [ ] Large repo handling (file count limits, timeout guards)
- [ ] Private repo GitHub token auth
- [ ] Rate limiting on `/audit` endpoint
- [ ] Graceful error recovery in LangGraph nodes
- [ ] Cleanup cron: delete old job directories after 24 hours

---

## 10. Environment Variables

```env
# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4.5-preview

# FastAPI
API_HOST=0.0.0.0
API_PORT=8000
JOB_STORAGE_PATH=./storage/jobs

# Streamlit
FASTAPI_BASE_URL=http://localhost:8000

# Optional: Redis (production)
REDIS_URL=redis://localhost:6379

# Optional: OSV.dev CVE lookup
OSV_API_BASE=https://api.osv.dev/v1
```

---

*Plan authored for Neural Ninjas · Codebase Audit Agent System*
