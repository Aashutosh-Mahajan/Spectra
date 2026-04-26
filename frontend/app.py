"""
Streamlit Frontend — 3-screen audit UI.
Screen 1: Input (repo URL, branch, token, excludes)
Screen 2: Live Progress (polling /status every 2s)
Screen 3: Results Dashboard (findings + downloads)
"""

import os
import time
import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────
FASTAPI_BASE_URL = os.environ.get("FASTAPI_BASE_URL", "http://localhost:8000")

# ─────────────────────────────────────────────
# Page Config
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Codebase Audit Agent",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─────────────────────────────────────────────
# Custom CSS
# ─────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    .stApp { font-family: 'Inter', sans-serif; }

    .main-header {
        text-align: center;
        padding: 2rem 0 1rem;
    }
    .main-header h1 {
        font-size: 2.5rem;
        font-weight: 800;
        background: linear-gradient(135deg, #3b82f6, #8b5cf6);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
    }
    .main-header p {
        color: #6b7280;
        font-size: 1.1rem;
    }

    .severity-card {
        padding: 1.2rem;
        border-radius: 12px;
        text-align: center;
        font-weight: 700;
        font-size: 1.8rem;
        margin-bottom: 0.5rem;
    }
    .severity-extreme { background: linear-gradient(135deg, #fee2e2, #fecaca); color: #dc2626; border: 2px solid #fca5a5; }
    .severity-high { background: linear-gradient(135deg, #ffedd5, #fed7aa); color: #ea580c; border: 2px solid #fdba74; }
    .severity-medium { background: linear-gradient(135deg, #fef9c3, #fef08a); color: #ca8a04; border: 2px solid #fde047; }
    .severity-low { background: linear-gradient(135deg, #dbeafe, #bfdbfe); color: #2563eb; border: 2px solid #93c5fd; }

    .severity-label {
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-top: 4px;
    }

    .agent-card {
        padding: 0.8rem 1.2rem;
        border-radius: 10px;
        margin: 0.4rem 0;
        display: flex;
        align-items: center;
        gap: 0.8rem;
        font-size: 0.95rem;
    }
    .agent-done { background: #f0fdf4; border: 1px solid #bbf7d0; color: #166534; }
    .agent-running { background: #eff6ff; border: 1px solid #bfdbfe; color: #1e40af; }
    .agent-queued { background: #f9fafb; border: 1px solid #e5e7eb; color: #6b7280; }

    .risk-score {
        font-size: 3rem;
        font-weight: 800;
        text-align: center;
        padding: 1.5rem;
        border-radius: 16px;
        background: linear-gradient(135deg, #1e293b, #334155);
        color: white;
    }
    .risk-label {
        text-align: center;
        color: #94a3b8;
        font-size: 0.85rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 1px;
    }

    .finding-card {
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 12px;
        padding: 1.2rem 1.5rem;
        margin: 0.8rem 0;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    }

    .stButton>button {
        background: linear-gradient(135deg, #3b82f6, #2563eb);
        color: white;
        font-weight: 600;
        padding: 0.6rem 2rem;
        border-radius: 10px;
        border: none;
        font-size: 1rem;
        transition: all 0.2s;
    }
    .stButton>button:hover {
        background: linear-gradient(135deg, #2563eb, #1d4ed8);
        box-shadow: 0 4px 12px rgba(37,99,235,0.3);
        transform: translateY(-1px);
    }

    div[data-testid="stExpander"] {
        border: 1px solid #e5e7eb;
        border-radius: 10px;
        margin-bottom: 8px;
    }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# Session State Init
# ─────────────────────────────────────────────
if "screen" not in st.session_state:
    st.session_state.screen = "input"
if "job_id" not in st.session_state:
    st.session_state.job_id = None
if "results" not in st.session_state:
    st.session_state.results = None


# ─────────────────────────────────────────────
# API Helpers
# ─────────────────────────────────────────────
def start_audit(repo_url, branch, github_token, exclude_patterns):
    """POST /audit to start a new audit job."""
    payload = {
        "repo_url": repo_url,
        "branch": branch,
        "exclude_patterns": [p.strip() for p in exclude_patterns.split(",") if p.strip()],
    }
    if github_token:
        payload["github_token"] = github_token

    try:
        resp = requests.post(f"{FASTAPI_BASE_URL}/audit", json=payload, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.ConnectionError:
        st.error("❌ Cannot connect to backend. Make sure the FastAPI server is running on " + FASTAPI_BASE_URL)
        return None
    except Exception as e:
        st.error(f"❌ Failed to start audit: {e}")
        return None


def get_status(job_id):
    """GET /audit/{job_id}/status."""
    try:
        resp = requests.get(f"{FASTAPI_BASE_URL}/audit/{job_id}/status", timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


# ─────────────────────────────────────────────
# SCREEN 1: Input
# ─────────────────────────────────────────────
def render_input_screen():
    st.markdown('<div class="main-header"><h1>🔍 Codebase Audit Agent</h1><p>AI-powered multi-agent code auditing system</p></div>', unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("### Repository Details")

        repo_url = st.text_input(
            "GitHub Repository URL",
            placeholder="https://github.com/user/repo",
            help="Public or private GitHub repository URL",
        )

        c1, c2 = st.columns(2)
        with c1:
            branch = st.text_input("Branch", value="main", help="Branch to audit")
        with c2:
            github_token = st.text_input(
                "GitHub Token (optional)",
                type="password",
                placeholder="ghp_xxx...",
                help="Required for private repositories",
            )

        exclude_patterns = st.text_area(
            "Exclude patterns (comma-separated)",
            value="node_modules, .git, dist, __pycache__, .venv, venv",
            help="Directories and files to skip during audit",
            height=80,
        )

        st.markdown("")
        col_btn = st.columns([1, 2, 1])
        with col_btn[1]:
            if st.button("🚀 Start Audit", use_container_width=True):
                if not repo_url:
                    st.warning("Please enter a repository URL.")
                elif not repo_url.startswith("http"):
                    st.warning("Please enter a valid URL starting with http:// or https://")
                else:
                    with st.spinner("Starting audit..."):
                        result = start_audit(repo_url, branch, github_token, exclude_patterns)
                        if result and "job_id" in result:
                            st.session_state.job_id = result["job_id"]
                            st.session_state.repo_url = repo_url
                            st.session_state.screen = "progress"
                            st.rerun()


# ─────────────────────────────────────────────
# SCREEN 2: Live Progress
# ─────────────────────────────────────────────
def render_progress_screen():
    job_id = st.session_state.job_id
    repo_url = st.session_state.get("repo_url", "")

    st.markdown(f'<div class="main-header"><h1>🔍 Auditing Repository</h1><p>{repo_url}</p></div>', unsafe_allow_html=True)

    status_data = get_status(job_id)
    if not status_data:
        st.error("Failed to fetch job status. Is the backend running?")
        if st.button("← Back to Input"):
            st.session_state.screen = "input"
            st.rerun()
        return

    status = status_data.get("status", "unknown")
    progress = status_data.get("progress_percent", 0)
    current_step = status_data.get("current_step", "Processing...")

    # Progress bar
    st.progress(progress / 100, text=f"{progress}% — {current_step}")

    # Agent status cards
    st.markdown("### Agent Status")
    agents_done = status_data.get("agents_done", [])
    agents_running = status_data.get("agents_running", [])
    agents_queued = status_data.get("agents_queued", [])

    all_agents = ["frontend", "backend", "database", "security", "devops", "dependency"]
    agent_icons = {"frontend": "🎨", "backend": "⚙️", "database": "🗄️", "security": "🔒", "devops": "🐳", "dependency": "📦"}

    cols = st.columns(3)
    for i, agent in enumerate(all_agents):
        with cols[i % 3]:
            icon = agent_icons.get(agent, "🔧")
            if agent in agents_done:
                st.markdown(f'<div class="agent-card agent-done">✅ {icon} <strong>{agent.capitalize()}</strong> — done</div>', unsafe_allow_html=True)
            elif agent in agents_running:
                st.markdown(f'<div class="agent-card agent-running">🔄 {icon} <strong>{agent.capitalize()}</strong> — scanning...</div>', unsafe_allow_html=True)
            elif agent in agents_queued:
                st.markdown(f'<div class="agent-card agent-queued">⏳ {icon} <strong>{agent.capitalize()}</strong> — queued</div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="agent-card agent-queued">⬜ {icon} <strong>{agent.capitalize()}</strong></div>', unsafe_allow_html=True)

    # Handle completion or failure
    if status == "done":
        st.success("✅ Audit complete!")
        st.session_state.results = status_data
        st.session_state.screen = "results"
        time.sleep(1)
        st.rerun()
    elif status == "failed":
        st.error(f"❌ Audit failed: {status_data.get('error', 'Unknown error')}")
        if st.button("← Try Again"):
            st.session_state.screen = "input"
            st.rerun()
    else:
        # Auto-refresh every 2 seconds
        time.sleep(2)
        st.rerun()


# ─────────────────────────────────────────────
# SCREEN 3: Results Dashboard
# ─────────────────────────────────────────────
def render_results_screen():
    results = st.session_state.results
    job_id = st.session_state.job_id
    repo_url = st.session_state.get("repo_url", "")

    if not results:
        st.session_state.screen = "input"
        st.rerun()
        return

    st.markdown('<div class="main-header"><h1>🔍 Audit Complete</h1></div>', unsafe_allow_html=True)

    counts = results.get("finding_counts", {})
    total = results.get("total_findings", 0)

    # Severity cards
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.markdown(f'<div class="severity-card severity-extreme">{counts.get("EXTREME", 0)}<div class="severity-label">🔴 Extreme</div></div>', unsafe_allow_html=True)
    with col2:
        st.markdown(f'<div class="severity-card severity-high">{counts.get("HIGH", 0)}<div class="severity-label">🟠 High</div></div>', unsafe_allow_html=True)
    with col3:
        st.markdown(f'<div class="severity-card severity-medium">{counts.get("MEDIUM", 0)}<div class="severity-label">🟡 Medium</div></div>', unsafe_allow_html=True)
    with col4:
        st.markdown(f'<div class="severity-card severity-low">{counts.get("LOW", 0)}<div class="severity-label">🔵 Low</div></div>', unsafe_allow_html=True)
    with col5:
        st.markdown(f'<div class="severity-card" style="background: linear-gradient(135deg,#1e293b,#334155); color: white; border: 2px solid #475569;">{total}<div class="severity-label" style="color:#94a3b8;">Total</div></div>', unsafe_allow_html=True)

    st.markdown("---")

    # Download buttons
    st.markdown("### 📥 Download Reports")
    dl1, dl2, dl3 = st.columns([1, 1, 2])
    with dl1:
        try:
            md_resp = requests.get(f"{FASTAPI_BASE_URL}/report/{job_id}/download?format=md", timeout=30)
            if md_resp.status_code == 200:
                st.download_button("⬇️ Download .md Report", data=md_resp.content, file_name=f"audit_report_{job_id[:8]}.md", mime="text/markdown", use_container_width=True)
        except Exception:
            st.warning("Markdown report not available")

    with dl2:
        try:
            pdf_resp = requests.get(f"{FASTAPI_BASE_URL}/report/{job_id}/download?format=pdf", timeout=30)
            if pdf_resp.status_code == 200:
                st.download_button("⬇️ Download .pdf Report", data=pdf_resp.content, file_name=f"audit_report_{job_id[:8]}.pdf", mime="application/pdf", use_container_width=True)
        except Exception:
            st.info("PDF report not available")

    st.markdown("---")

    # New audit button
    if st.button("🔄 Start New Audit"):
        st.session_state.screen = "input"
        st.session_state.job_id = None
        st.session_state.results = None
        st.rerun()


# ─────────────────────────────────────────────
# Router
# ─────────────────────────────────────────────
screen = st.session_state.screen

if screen == "input":
    render_input_screen()
elif screen == "progress":
    render_progress_screen()
elif screen == "results":
    render_results_screen()
else:
    st.session_state.screen = "input"
    st.rerun()
