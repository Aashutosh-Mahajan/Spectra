<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12+-3776AB?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white" />
  <img src="https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white" />
  <img src="https://img.shields.io/badge/LangGraph-1C3C3C?style=for-the-badge&logo=langchain&logoColor=white" />
  <img src="https://img.shields.io/badge/GPT--5.4_Mini-412991?style=for-the-badge&logo=openai&logoColor=white" />
  <img src="https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white" />
</p>

<h1 align="center">🔍 Codebase Audit Agent System</h1>

<p align="center">
  <strong>A multi-agent AI pipeline that audits any GitHub repository, detects bugs & vulnerabilities across the full stack, and generates professional audit reports.</strong>
</p>

<p align="center">
  <em>Built by Neural Ninjas</em>
</p>

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Key Features](#-key-features)
- [System Architecture](#-system-architecture)
- [Specialist Agents](#-specialist-agents)
- [Project Structure](#-project-structure)
- [Getting Started](#-getting-started)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
  - [Configuration](#configuration)
  - [Running Locally](#running-locally)
  - [Running with Docker](#running-with-docker)
- [API Reference](#-api-reference)
- [Streamlit Frontend](#-streamlit-frontend)
- [Report Format](#-report-format)
- [Data Schemas](#-data-schemas)
- [LangGraph Pipeline](#-langgraph-pipeline)
- [Configuration Reference](#-configuration-reference)
- [Design Decisions](#-design-decisions)
- [Troubleshooting](#-troubleshooting)
- [Contributing](#-contributing)

---

## 🌐 Overview

The **Codebase Audit Agent System** accepts a GitHub repository URL from the user, clones the repository, and dispatches a fleet of **6 specialized AI agents** — each responsible for a different layer of the codebase. Every agent independently scans its assigned files using **GPT-5.4 mini**, identifies bugs, vulnerabilities, and best-practice violations, and returns structured findings. A final **Aggregator Agent** deduplicates, cross-references, and scores everything, and a **Report Writer** produces professional audit reports in both **Markdown** and **PDF** formats.

The entire system is orchestrated through **LangGraph's StateGraph** with parallel fan-out execution via the `Send()` API, exposed through a **FastAPI** backend, and presented through a polished **Streamlit** frontend with live progress tracking.

---

## ✨ Key Features

| Feature | Description |
|---------|-------------|
| 🔄 **Multi-Agent Parallel Auditing** | 6 specialist agents run simultaneously via LangGraph's `Send()` API |
| 🔒 **OWASP Top 10 Coverage** | Security Agent comprehensively covers all OWASP 2021 categories |
| 📦 **Real CVE Lookup** | Dependency Agent cross-references packages against the OSV.dev vulnerability database |
| 🎯 **Weighted Severity Scoring** | Findings scored by Exploitability (35%), Impact (40%), and Exposure (25%) |
| 🔗 **Cross-Agent Chain Detection** | Aggregator links related findings across agents (e.g., unsanitized input → SQL injection) |
| 📊 **Professional Reports** | Downloadable `.md` and `.pdf` reports with executive summaries, severity breakdowns, and code snippets |
| 📡 **Live Progress Tracking** | Real-time per-agent status updates in the Streamlit UI |
| 🐳 **Docker Ready** | Full Docker Compose setup for one-command deployment |
| 🔑 **Private Repo Support** | GitHub PAT token support for auditing private repositories |

---

## 🏗 System Architecture

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
│   └── Clone repo (GitPython, depth=1)                  │
│   └── Walk file tree → map files to agents             │
│        │                                               │
│        ├──── [FRONTEND AGENT]    .jsx .tsx .vue .html   │
│        ├──── [BACKEND AGENT]     .py .js .go .java     │
│        ├──── [DATABASE AGENT]    .sql .prisma models/   │
│        ├──── [SECURITY AGENT]    auth/token/secret/*    │
│        ├──── [DEVOPS AGENT]      Dockerfile CI/CD k8s   │
│        └──── [DEPENDENCY AGENT]  package.json reqs.txt  │
│                  │  (all run in parallel via Send())    │
│                  ▼                                      │
│          [AGGREGATOR NODE]                              │
│           └── Deduplicate · Cross-reference · Score     │
│                  │                                      │
│                  ▼                                      │
│          [REPORT WRITER NODE]                           │
│           └── Generate .md + .pdf                      │
└─────────────────────────────────────────────────────────┘
```

### Data Flow

1. **User** submits a GitHub repo URL via the Streamlit UI
2. **FastAPI** creates a job, generates a `job_id`, and launches the LangGraph pipeline as a background task
3. **Orchestrator** clones the repo (shallow, `--depth=1`) and routes files to agent buckets
4. **6 Specialist Agents** run in parallel, each analyzing their assigned files with GPT-5.4 mini
5. **Aggregator** deduplicates findings, cross-references related issues, and applies severity scoring
6. **Report Writer** generates `.md` and `.pdf` reports
7. **Streamlit** polls `/status` every 2 seconds to show live progress, then displays results and download links

---

## 🤖 Specialist Agents

Each agent extends `BaseAuditAgent` which provides file chunking, LLM integration with retry logic, and structured JSON response parsing.

### 🔒 Security Agent
**Files:** `*auth*`, `*token*`, `*secret*`, `*jwt*`, `*.env*`, `*crypto*`

| Focus Area | Examples |
|------------|---------|
| OWASP Top 10 (2021) | Injection, broken auth, sensitive data exposure, SSRF, XSS |
| Secrets & Credentials | Hardcoded API keys, tokens in source, default passwords |
| Authentication | Weak JWT config, broken session management, missing MFA |
| Transport Security | Missing HTTPS, overly permissive CORS, missing security headers |

### 🎨 Frontend Agent
**Files:** `.jsx`, `.tsx`, `.vue`, `.svelte`, `.html`, `.css`, `.scss`

| Focus Area | Examples |
|------------|---------|
| XSS | `dangerouslySetInnerHTML`, `v-html`, `innerHTML`, `eval()` |
| Data Exposure | API keys in client code, secrets in `localStorage` |
| React Issues | Memory leaks in `useEffect`, missing `key` props, stale closures |
| Accessibility | Missing ARIA labels, unlabeled inputs, missing alt text |

### ⚙️ Backend Agent
**Files:** `.py`, `.java`, `.go`, `.rb`, `.php`, `.rs`, `.js`/`.ts` (server-side)

| Focus Area | Examples |
|------------|---------|
| Input Validation | Missing validation, type coercion, ReDoS |
| Error Handling | Stack traces in responses, swallowed errors |
| Auth/Authz | IDOR, missing RBAC, privilege escalation |
| Race Conditions | TOCTOU, non-atomic operations, missing locks |

### 🗄️ Database Agent
**Files:** `.sql`, `.prisma`, `models.py`, `migrations/*`

| Focus Area | Examples |
|------------|---------|
| SQL Injection | Raw SQL with string concatenation, partial parameterization |
| Performance | N+1 queries, missing indexes, full table scans |
| Data Integrity | Missing constraints, no transactions, orphaned records |
| Migration Safety | Destructive migrations, missing rollback plans |

### 🐳 DevOps Agent
**Files:** `Dockerfile*`, `docker-compose*.yml`, `.github/workflows/*`, `k8s/*`, `*.tf`

| Focus Area | Examples |
|------------|---------|
| Container Security | Running as root, unpinned images, secrets in Dockerfiles |
| CI/CD | Hardcoded tokens, unpinned actions, overly permissive perms |
| Kubernetes | Privileged containers, missing network policies, no probes |
| Infrastructure | Public S3 buckets, open security groups, unencrypted storage |

### 📦 Dependency Agent
**Files:** `package.json`, `requirements.txt`, `go.mod`, `pom.xml`, `Cargo.toml`, `pyproject.toml`

| Focus Area | Examples |
|------------|---------|
| Known CVEs | Cross-referenced via OSV.dev REST API |
| Version Pinning | Unpinned versions, conflicting requirements |
| Package Health | Unmaintained, low downloads, deprecated |
| License Compliance | GPL in proprietary projects, incompatibilities |

### 🔗 Aggregator Agent
Post-processing agent that runs after all specialists complete:

1. **Deduplicates** — merges findings at same file + line range + bug type
2. **Cross-references** — chains related findings across agents (severity bump)
3. **Scores** — applies weighted rubric: Exploitability (35%), Impact (40%), Exposure (25%)

**Severity Bands:**

| Band | Score | Description |
|------|-------|-------------|
| 🔴 **EXTREME** | ≥ 90 | Immediate critical risk (RCE, hardcoded root credentials) |
| 🟠 **HIGH** | 70–89 | Urgent fix required (SQL injection, auth bypass) |
| 🟡 **MEDIUM** | 40–69 | Fix before next release (CORS misconfig, insecure deserialization) |
| 🔵 **LOW** | < 40 | Best practice violation (verbose errors, missing headers) |

---

## 📁 Project Structure

```
codebase-audit-agent/
│
├── backend/
│   ├── main.py                          # FastAPI app entry point
│   ├── api/
│   │   ├── routes/
│   │   │   ├── audit.py                 # POST /audit, GET /audit/{job_id}/status
│   │   │   └── report.py               # GET /report/{job_id}/download
│   │   └── models.py                   # Pydantic request/response schemas
│   │
│   ├── agents/
│   │   ├── base_agent.py               # Abstract base class (LLM, chunking, retry)
│   │   ├── frontend_agent.py           # UI/client-side code auditor
│   │   ├── backend_agent.py            # Server-side logic auditor
│   │   ├── database_agent.py           # DB queries, ORM, migrations auditor
│   │   ├── security_agent.py           # OWASP / auth / secrets auditor
│   │   ├── devops_agent.py             # Dockerfile / CI/CD / k8s auditor
│   │   ├── dependency_agent.py         # Package CVE + version auditor (OSV.dev)
│   │   └── aggregator_agent.py         # Dedup + cross-ref + severity scoring
│   │
│   ├── graph/
│   │   └── audit_graph.py              # LangGraph StateGraph (parallel fan-out)
│   │
│   ├── report/
│   │   ├── generator.py                # Markdown report generation
│   │   ├── pdf_generator.py            # PDF generation (WeasyPrint)
│   │   └── templates/
│   │       └── report_style.css        # PDF styling
│   │
│   ├── utils/
│   │   ├── repo_cloner.py              # GitPython shallow clone wrapper
│   │   ├── file_router.py              # Extension/name → agent mapping
│   │   ├── chunker.py                  # Token-safe file splitting (tiktoken)
│   │   └── severity.py                 # Severity scoring rubric
│   │
│   └── storage/
│       └── jobs/                       # Ephemeral: cloned repos + reports per job
│
├── frontend/
│   └── app.py                          # Streamlit UI (3-screen flow)
│
├── .env.example                        # Environment variable template
├── .gitignore
├── requirements.txt                    # Python dependencies
├── Dockerfile.backend
├── Dockerfile.frontend
├── docker-compose.yml
└── README.md                           # ← You are here
```

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.12+**
- **Git** (for GitPython to clone repos)
- **OpenAI API Key** with access to `gpt-5.4-mini`
- **Docker & Docker Compose** (optional, for containerized deployment)

### Installation

```bash
# 1. Clone the project
git clone https://github.com/your-org/codebase-audit-agent.git
cd codebase-audit-agent

# 2. Create a virtual environment
python -m venv venv

# 3. Activate it
# Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# macOS/Linux:
source venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt
```

### Configuration

```bash
# Copy the environment template
cp .env.example .env

# Edit .env with your API key
```

Open `.env` and set your values:

```env
# Required
OPENAI_API_KEY=sk-your-openai-api-key-here
OPENAI_MODEL=gpt-5.4-mini

# Backend
API_HOST=0.0.0.0
API_PORT=8000
JOB_STORAGE_PATH=./storage/jobs

# Frontend
FASTAPI_BASE_URL=http://localhost:8000

# Optional: OSV.dev CVE lookup
OSV_API_BASE=https://api.osv.dev/v1
```

### Running Locally

You need **two terminal windows** — one for the backend, one for the frontend:

**Terminal 1 — FastAPI Backend:**
```bash
# From the project root
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

**Terminal 2 — Streamlit Frontend:**
```bash
# From the project root
streamlit run frontend/app.py
```

Then open **http://localhost:8501** in your browser.

### Running with Docker

```bash
# Build and start both services
docker-compose up --build

# Backend: http://localhost:8000
# Frontend: http://localhost:8501
```

To stop:
```bash
docker-compose down
```

---

## 📡 API Reference

### `POST /audit`

Start a new codebase audit.

**Request Body:**
```json
{
  "repo_url": "https://github.com/user/repo",
  "branch": "main",
  "github_token": "ghp_xxx",
  "include_patterns": [],
  "exclude_patterns": ["node_modules", ".git", "dist", "__pycache__"]
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `repo_url` | `string` | ✅ | — | GitHub repository URL |
| `branch` | `string` | ❌ | `"main"` | Branch to clone and audit |
| `github_token` | `string` | ❌ | `null` | GitHub PAT for private repos |
| `include_patterns` | `string[]` | ❌ | `[]` | File patterns to include |
| `exclude_patterns` | `string[]` | ❌ | *(see defaults)* | Patterns to exclude |

**Response** `200 OK`:
```json
{
  "job_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "message": "Audit started successfully"
}
```

---

### `GET /audit/{job_id}/status`

Get live status of an audit job.

**Response** `200 OK`:
```json
{
  "job_id": "a1b2c3d4-...",
  "status": "running",
  "progress_percent": 60,
  "current_step": "Security Agent scanning 18 files...",
  "agents_done": ["frontend", "devops"],
  "agents_running": ["backend", "security"],
  "agents_queued": ["database", "dependency"],
  "finding_counts": { "EXTREME": 1, "HIGH": 3, "MEDIUM": 5, "LOW": 8 },
  "total_findings": 17,
  "error": null,
  "report_md_ready": false,
  "report_pdf_ready": false
}
```

**Status Lifecycle:**
```
queued → cloning → routing → running → aggregating → reporting → done
                                                                  ↘ failed
```

---

### `GET /report/{job_id}/download`

Download the generated audit report.

**Query Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `format` | `string` | `"md"` | Report format: `"md"` or `"pdf"` |

**Response:** File download (streaming `FileResponse`)

---

### `GET /health`

Health check endpoint.

**Response** `200 OK`:
```json
{
  "status": "healthy",
  "service": "Codebase Audit Agent System",
  "version": "1.0.0"
}
```

---

## 🎨 Streamlit Frontend

The frontend provides a 3-screen flow:

### Screen 1 — Input
- GitHub repository URL field
- Branch selector (default: `main`)
- GitHub token field (password masked, optional)
- Exclude patterns textarea
- **🚀 Start Audit** button

### Screen 2 — Live Progress
- Real-time progress bar with percentage
- Current operation description
- Per-agent status cards:
  - ✅ **Done** — green card with finding count
  - 🔄 **Running** — blue card with spinner
  - ⏳ **Queued** — gray card
- Auto-refreshes every 2 seconds via `st.rerun()`

### Screen 3 — Results Dashboard
- Severity count cards (EXTREME / HIGH / MEDIUM / LOW / Total)
- Download buttons for `.md` and `.pdf` reports
- **🔄 Start New Audit** button

---

## 📄 Report Format

### Markdown Report Structure

```
# 🔍 Codebase Audit Report
**Repository:** <url>  **Branch:** <branch>  **Date:** <timestamp>

## Executive Summary
| Severity | Count |
|----------|-------|
| 🔴 EXTREME | X |
| 🟠 HIGH    | X |
| 🟡 MEDIUM  | X |
| 🔵 LOW     | X |
| **Total**  | X |

**Risk Score:** XX/100

### Top Critical Findings
(Top 3 most severe issues)

## Findings by Severity

### 🔴 EXTREME SEVERITY
#### [E-001] <Finding Title>
| Field | Detail |
|-------|--------|
| **Bug Type** | e.g., SQL Injection |
| **What is it** | Plain-English description |
| **Why it occurs** | Root cause |
| **How it occurred** | Code pattern |
| **Where** | `file.py` · Lines 42–58 |
| **Score** | 95/100 |

**Affected Code:** (code snippet)
**Recommended Fix:** (detailed fix)
**References:** CWE-89, OWASP A03:2021

### 🟠 HIGH SEVERITY ...
### 🟡 MEDIUM SEVERITY ...
### 🔵 LOW SEVERITY ...

## Findings by Agent
(summary table per agent with finding counts)

## Appendix: Scan Summary
(files scanned, files with findings, risk score)
```

### PDF Report
- Converted from Markdown via **WeasyPrint**
- Professional CSS styling with:
  - Dark severity-colored headers
  - Monospace code blocks with syntax highlighting (Pygments)
  - Color-coded severity badges
  - Neural Ninjas branded header/footer
  - Page numbers via CSS `@page` rules

---

## 📊 Data Schemas

### Finding

```python
class Finding(BaseModel):
    id: str                          # UUID4
    agent: str                       # "security", "backend", etc.
    severity: Literal["EXTREME", "HIGH", "MEDIUM", "LOW"]
    title: str                       # "SQL Injection in user_query()"
    bug_type: str                    # "Injection", "Memory Leak", etc.
    what_is_it: str                  # Plain-English description
    why_it_occurs: str               # Root cause explanation
    how_it_occurred: str             # Code pattern that caused it
    where_it_is: FileLocation        # file_path, line_start, line_end
    affected_code: str               # Code snippet
    recommended_fix: str             # How to fix it
    references: list[str]            # CWE IDs, OWASP links
    score: float                     # 0.0–100.0 severity score
    detected_by: list[str]           # Agents that flagged this (post-dedup)
```

### JobStatus

```python
class JobStatus(BaseModel):
    job_id: str
    status: Literal["queued", "cloning", "routing", "running",
                     "aggregating", "reporting", "done", "failed"]
    progress_percent: int            # 0–100
    current_step: str
    agents_done: list[str]
    agents_running: list[str]
    agents_queued: list[str]
    finding_counts: dict[str, int]   # {"EXTREME": 3, "HIGH": 8, ...}
    total_findings: int
    error: Optional[str]
    report_md_ready: bool
    report_pdf_ready: bool
```

---

## 🔄 LangGraph Pipeline

The core orchestration is built on **LangGraph's `StateGraph`** with typed state and parallel execution.

### Graph Definition

```
START
  └──▶ orchestrator_node
            └──▶ [Send() fan-out — agents run in parallel]
                  ├──▶ agent_worker (frontend)
                  ├──▶ agent_worker (backend)
                  ├──▶ agent_worker (database)
                  ├──▶ agent_worker (security)
                  ├──▶ agent_worker (devops)
                  └──▶ agent_worker (dependency)
                            └──▶ [all join] aggregator_node
                                        └──▶ report_writer_node
                                                    └──▶ END
```

### Key Implementation Details

| Concept | Implementation |
|---------|---------------|
| **Parallel Execution** | `Send()` API dispatches all 6 agents simultaneously |
| **State Safety** | `Annotated[list, operator.add]` reducers for safe concurrent state merging |
| **File Chunking** | Files > 3,000 tokens are split with 200-token overlap via `tiktoken` |
| **Retry Logic** | Per-chunk LLM calls retry up to 3 times with exponential backoff |
| **Progress Tracking** | Each node updates the shared `jobs_store` dict for live status polling |

### File Routing

The **File Router** maps files to agents based on multiple criteria:

| Routing Method | Example |
|---------------|---------|
| **Extension** | `.py` → Backend, `.jsx` → Frontend |
| **Filename** | `package.json` → Dependency, `Dockerfile` → DevOps |
| **Directory** | `.github/workflows/` → DevOps, `migrations/` → Database |
| **Keyword** | filename contains `auth`, `token`, `secret` → Security |
| **Ambiguous** | `.js`/`.ts` → both Frontend and Backend |

> A single file can appear in **multiple** agent buckets. For example, `auth_routes.py` is sent to both the Backend and Security agents.

---

## ⚙ Configuration Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | ✅ | — | OpenAI API key |
| `OPENAI_MODEL` | ❌ | `gpt-5.4-mini` | Model to use for code analysis |
| `API_HOST` | ❌ | `0.0.0.0` | FastAPI bind host |
| `API_PORT` | ❌ | `8000` | FastAPI bind port |
| `JOB_STORAGE_PATH` | ❌ | `./storage/jobs` | Directory for cloned repos and reports |
| `FASTAPI_BASE_URL` | ❌ | `http://localhost:8000` | Backend URL for Streamlit |
| `OSV_API_BASE` | ❌ | `https://api.osv.dev/v1` | OSV.dev API base URL |
| `REDIS_URL` | ❌ | — | Redis URL (production job store) |

---

## 🧠 Design Decisions

### Why LangGraph over plain asyncio?
LangGraph provides a **stateful, inspectable execution graph** with built-in support for parallel fan-out via `Send()`, typed state with reducers for safe concurrent merging, and streaming state updates. Plain `asyncio.gather()` works for parallelism but provides no state management, no built-in retry logic, and no way to inspect mid-pipeline state for the progress UI.

### Why polling instead of WebSocket streaming?
Each agent processes batches of files — streaming individual LLM tokens to the UI is not meaningful. What matters is **per-agent completion events**. Simple HTTP polling (`GET /status` every 2 seconds) is sufficient, far simpler to implement, and works natively with Streamlit's `st.rerun()` pattern.

### Token budget management for large repos
Files over ~3,000 tokens are split into **overlapping chunks** (200-token overlap) by `chunker.py` using `tiktoken`. Each agent processes one chunk at a time and accumulates findings across chunks. This allows auditing arbitrarily large codebases without hitting the context window limit.

### Security of cloned repos
Each job gets an **isolated ephemeral directory**. GitHub tokens are never written to disk — they are constructed into the clone URL in memory and discarded immediately after the clone completes. Cloned repos are deleted after report generation.

### Why WeasyPrint over ReportLab for PDF?
WeasyPrint allows writing the report style in **standard CSS** (maintainable and readable) and converts the already-generated Markdown report into a polished PDF without maintaining a separate programmatic layout in Python.

---

## 🔧 Troubleshooting

### Common Issues

| Problem | Solution |
|---------|----------|
| `ConnectionError: Cannot connect to backend` | Ensure FastAPI is running on the correct port. Check `FASTAPI_BASE_URL` in `.env` |
| `OpenAI API error: 401` | Verify your `OPENAI_API_KEY` is valid and has access to the specified model |
| `CloneError: auth_failure` | For private repos, provide a valid GitHub PAT with `repo` scope |
| `CloneError: timeout` | Large repos may exceed the 120s clone timeout. Try a specific branch or shallower clone |
| PDF generation fails | WeasyPrint requires system libraries (Cairo, Pango). On Windows, try `pip install weasyprint` which bundles them. On Linux, install `libcairo2 libpango-1.0-0 libgdk-pixbuf-2.0-0` |
| `UnicodeEncodeError` on Windows | Set `PYTHONIOENCODING=utf-8` environment variable or use `chcp 65001` in terminal |

### Logs

The backend logs to stdout with structured format:
```
2026-04-26 12:00:00 [INFO] backend.graph.audit_graph: [job-id] Status update: {...}
```

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Make your changes
4. Run the test suite: `pytest tests/`
5. Submit a pull request

### Code Style
- Python: Follow PEP 8 and type-annotate all function signatures
- Use `async`/`await` for all LLM calls and I/O operations
- Add docstrings to all public functions and classes

---

## 📝 Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Frontend | **Streamlit** | User interface, progress display, report download |
| Backend API | **FastAPI** + Uvicorn | REST API, job management, file serving |
| Agent Orchestration | **LangGraph** (StateGraph + Send API) | Stateful parallel agent pipeline |
| LLM | **GPT-5.4 mini** via OpenAI SDK | Code analysis, bug detection |
| Repo Cloning | **GitPython** | Shallow clone of target repositories |
| File Chunking | **tiktoken** | Token-accurate file splitting |
| PDF Generation | **WeasyPrint** + Pygments | HTML → PDF with syntax highlighting |
| CVE Lookup | **OSV.dev REST API** | Open source vulnerability database |
| Job State (dev) | In-memory Python dict | Single-worker job tracking |
| Containerization | **Docker Compose** | FastAPI + Streamlit as isolated services |

---

<p align="center">
  <strong>Built with ❤️ by Neural Ninjas</strong><br>
  <em>Codebase Audit Agent System — Making code safer, one repo at a time.</em>
</p>
