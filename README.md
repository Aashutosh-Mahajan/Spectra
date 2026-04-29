<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12+-3776AB?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white" />
  <img src="https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white" />
  <img src="https://img.shields.io/badge/LangGraph-1C3C3C?style=for-the-badge&logo=langchain&logoColor=white" />
  <img src="https://img.shields.io/badge/OpenAI-412991?style=for-the-badge&logo=openai&logoColor=white" />
  <img src="https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white" />
</p>

<h1 align="center">🔍 SPECTRA</h1>

<p align="center">
  <strong>A comprehensive multi-agent AI pipeline designed to audit local codebases and GitHub repositories, detect full-stack vulnerabilities and bugs, and generate professional PDF & Markdown reports.</strong>
</p>

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Key Features](#-key-features)
- [System Architecture](#-system-architecture)
- [Specialist Agents](#-specialist-agents)
- [Installation & Setup](#-installation--setup)
  - [Public Installation (Recommended)](#public-installation-recommended)
  - [Manual Clone & Install](#manual-clone--install)
- [How to Use the CLI](#-how-to-use-the-cli)
  - [Configuration Flow](#configuration-flow)
- [Generated Reports](#-generated-reports)
- [API Reference](#-api-reference)
- [Docker Deployment](#-docker-deployment)
- [Troubleshooting](#-troubleshooting)
- [Contributing](#-contributing)

---

## 🌐 Overview

The **SPECTRA** system provides an intelligent, automated pipeline for code analysis. You can provide it with a local directory path or a remote GitHub repository URL. The system orchestrates **6 specialized AI agents**—each focused on a different technology stack layer—to analyze your code in parallel.

Powered by OpenAI models (like `gpt-4o-mini`, `gpt-4o`, or `gpt-5.4-mini`), the system detects vulnerabilities, bugs, code-smells, and architectural issues. After scanning, an **Aggregator Agent** combines the findings, deduplicates them, and scores them by severity. A final **Report Writer** generates clean, professional audit reports in both `.md` and `.pdf` formats directly in your project folder.

---

## ✨ Key Features

| Feature | Description |
|---------|-------------|
| 🔄 **Multi-Agent Parallel Auditing** | 6 specialist agents run simultaneously via LangGraph's orchestration. |
| 🔒 **OWASP Top 10 Coverage** | Security Agent rigorously hunts for vulnerabilities, exposed secrets, and broken auth. |
| 📦 **Real CVE Lookup** | Cross-references package dependencies against the OSV.dev vulnerability database. |
| 🎯 **Weighted Severity Scoring** | Findings are scored on Exploitability (35%), Impact (40%), and Exposure (25%). |
| 📊 **Professional Reports** | Beautifully formatted `.md` and `.pdf` reports with code snippets, severity breakdowns, and remediation steps. |
| 💻 **Interactive CLI** | User-friendly command-line interface with real-time progress tracking, animations, and zero-configuration setups. |
| 🐳 **Docker Ready** | Easily deploy the underlying FastAPI and Streamlit interfaces using Docker Compose. |
| 🔑 **Private Repo Support** | Pass GitHub PAT tokens to audit private repositories effortlessly. |

---

## 🏗 System Architecture

The core of the system is built on **LangGraph**, utilizing a `StateGraph` with parallel fan-out execution. 

1. **Orchestrator Node**: Takes the input (local path or cloned GitHub repo). Walks the file tree and maps files to the relevant specialist agents based on extensions, file names, and path structures.
2. **Parallel Agents**: Uses LangGraph's `Send()` API to dispatch batches of files to 6 distinct agents. Each agent chunks large files (via `tiktoken`) to fit LLM context windows and parses the JSON response.
3. **Aggregator Node**: Merges findings, deduplicates issues found by multiple agents on the same line, and calculates severity scores.
4. **Report Writer Node**: Uses `Markdown` and `WeasyPrint` to compile the final outputs.

---

## 🤖 Specialist Agents

The system divides the auditing labor among these specialized AI agents:

1. **🔒 Security Agent**: Focuses on `auth`, `token`, `secret`, `jwt`, and `.env` files. Hunts for OWASP Top 10 vulnerabilities like SQLi, XSS, SSRF, and exposed credentials.
2. **🎨 Frontend Agent**: Focuses on `.jsx`, `.tsx`, `.vue`, `.html`, and `.css`. Looks for dangerous innerHTML usage, React memory leaks, stale closures, and accessibility issues.
3. **⚙️ Backend Agent**: Focuses on server-side logic in `.py`, `.java`, `.go`, `.js`, etc. Checks for input validation flaws, unhandled exceptions, race conditions, and business logic bugs.
4. **🗄️ Database Agent**: Focuses on `.sql`, ORM models, and `migrations/`. Looks for N+1 query problems, missing indexes, destructive migrations, and injection flaws.
5. **🐳 DevOps Agent**: Focuses on `Dockerfile`, `docker-compose.yml`, CI/CD workflows, and Kubernetes configs. Detects containers running as root, unpinned images, and missing security policies.
6. **📦 Dependency Agent**: Focuses on `package.json`, `requirements.txt`, etc. Looks up known CVEs and identifies unmaintained or deprecated packages.

---

## 🚀 Installation & Setup

### Prerequisites
- **Python 3.12+**
- **Git**
- An **OpenAI API Key** ([Get one here](https://platform.openai.com/api-keys))

### Public Installation (Recommended)
You can install the CLI globally within your Python environment directly from GitHub using a single command:

```bash
pip install git+https://github.com/Aashutosh-Mahajan/codebase-audit-agent.git
```

### Manual Clone & Install
If you wish to modify the code or contribute:

```bash
# 1. Clone the repository
git clone https://github.com/Aashutosh-Mahajan/codebase-audit-agent.git
cd codebase-audit-agent

# 2. Create and activate a virtual environment
python -m venv venv
# Windows: .\venv\Scripts\Activate.ps1
# Mac/Linux: source venv/bin/activate

# 3. Install in editable mode
pip install -e .
```

---

## 🎮 How to Use the CLI

Once installed, the `spectra` command will be available in your terminal.

```bash
# To view the help menu:
spectra -help

# To audit the current directory you are in:
spectra

# To audit a specific directory path:
spectra -d /path/to/your/project
```

### Configuration Flow

When you run `spectra` for the **first time** in a new project:
1. The CLI creates a hidden `.spectra` folder in that project.
2. It generates a template `.env` file inside that folder.
3. The CLI pauses and asks you to open `.spectra/.env` to provide your **OpenAI API Key** and select your **Model** (e.g., `gpt-4o-mini`).
4. Once you save the file, simply run `spectra` again.

The configuration is saved securely to that specific project, meaning future runs require zero setup!

---

## 📊 Generated Reports

When the audit completes, the CLI will save the results in the `.spectra/reports` directory of your audited project. 

The output includes:
1. **`report_<job_id>.md`**: A GitHub-flavored markdown file perfect for viewing in your code editor or uploading to a repository wiki.
2. **`report_<job_id>.pdf`**: A beautifully styled PDF document with syntax highlighting, severity color coding, and a professional layout, ideal for sharing with clients or management.

---

## 📡 API Reference

If you prefer to use the system as a backend service rather than a CLI, it exposes a full **FastAPI** application.

**Start the backend server:**
```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

### Key Endpoints

- `POST /audit`: Start a new codebase audit job (pass a GitHub `repo_url`, optional `github_token`, and `branch`). Returns a `job_id`.
- `GET /audit/{job_id}/status`: Poll for live status, progress percentages, and current agent states.
- `GET /report/{job_id}/download`: Download the generated report (pass `?format=md` or `?format=pdf`).

*(Refer to the Swagger UI at `http://localhost:8000/docs` for full request/response schemas).*

---

## 🐳 Docker Deployment

The project includes Docker support to run the FastAPI backend and Streamlit UI as isolated containers.

```bash
# Build and start the services
docker-compose up --build
```
- **Backend API**: `http://localhost:8000`
- **Streamlit Frontend**: `http://localhost:8501`

---

## 🔧 Troubleshooting

### API Rate Limits
If you encounter `429 Too Many Requests` from OpenAI, edit your `.spectra/.env` file and lower the `OPENAI_RATE_LIMIT_RPM` variable (default is 20) or ensure your OpenAI account has sufficient credits/tier level.

---

## 🤝 Contributing

Contributions are welcome!
1. Fork the repository.
2. Create a feature branch (`git checkout -b feature/amazing-feature`).
3. Commit your changes (`git commit -m 'Add amazing feature'`).
4. Push to the branch (`git push origin feature/amazing-feature`).
5. Open a Pull Request.

Please ensure your code follows standard Python PEP-8 styling and uses proper type hints.

---
<p align="center">
  <em>SPECTRA — Automated, thorough, and professional code auditing.</em>
</p>
GTK-for-Windows-Runtime-Environment-Installer/releases).
2. Install the latest `.exe` release.
3. **Important**: Check the box **"Add GTK+ to your PATH"** during installation.
4. Restart your terminal and try again.

### API Rate Limits
If you encounter `429 Too Many Requests` from OpenAI, edit your `.spectra/.env` file and lower the `OPENAI_RATE_LIMIT_RPM` variable (default is 20) or ensure your OpenAI account has sufficient credits/tier level.

---

## 🤝 Contributing

Contributions are welcome!
1. Fork the repository.
2. Create a feature branch (`git checkout -b feature/amazing-feature`).
3. Commit your changes (`git commit -m 'Add amazing feature'`).
4. Push to the branch (`git push origin feature/amazing-feature`).
5. Open a Pull Request.

Please ensure your code follows standard Python PEP-8 styling and uses proper type hints.

---
<p align="center">
  <em>SPECTRA — Automated, thorough, and professional code auditing.</em>
</p>
