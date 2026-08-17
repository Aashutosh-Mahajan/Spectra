import asyncio
import logging
import os
import re
import sys
import time
import uuid

# Force UTF-8 encoding on Windows to prevent UnicodeEncodeError in legacy consoles
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import click
from dotenv import load_dotenv
from rich import box
from rich.console import Console, Group
from rich.live import Live
from rich.padding import Padding
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

# Suppress noisy library logs
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)

console = Console()

# ─────────────────────────────────────────────
# Modern Cyberpunk / Developer Aesthetic Palette
# ─────────────────────────────────────────────
C_BRAND     = "#38BDF8"  # Electric Sky Blue
C_ACCENT    = "#818CF8"  # Cyber Indigo / Violet
C_MINT      = "#34D399"  # Neon Mint / Emerald
C_AMBER     = "#FBBF24"  # Warm Gold / Amber
C_ROSE      = "#F43F5E"  # Rose Red / Danger
C_ORANGE    = "#FB923C"  # Neon Orange / High
C_WHITE     = "#F8FAFC"  # Crisp Bright White
C_MUTED     = "#94A3B8"  # Slate 400
C_DIM       = "#64748B"  # Slate 500
C_BORDER    = "#334155"  # Slate 700 (Sleek dark frame)
C_BORDER_HI = "#38BDF8"  # Active Cyan Highlight
C_BG_CARD   = "#0F172A"  # Dark Slate Card Background

CONFIG_DIR_NAME = ".spectra"

SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

AGENT_DEFINITIONS = [
    ("security", "🔒", "Security"),
    ("backend", "⚙️ ", "Backend"),
    ("frontend", "🎨", "Frontend"),
    ("database", "🗄️ ", "Database"),
    ("devops", "🚀", "DevOps"),
    ("dependency", "📦", "Dependency"),
]

# ─────────────────────────────────────────────
# Sleek Typography & Smooth Color Gradient
# ─────────────────────────────────────────────
LOGO_LINES = [
    "  ███████╗██████╗ ███████╗ ██████╗████████╗██████╗  █████╗  ",
    "  ██╔════╝██╔══██╗██╔════╝██╔════╝╚══██╔══╝██╔══██╗██╔══██╗ ",
    "  ███████╗██████╔╝█████╗  ██║        ██║   ██████╔╝███████║ ",
    "  ╚════██║██╔═══╝ ██╔══╝  ██║        ██║   ██╔══██╗██╔══██║ ",
    "  ███████║██║     ███████╗╚██████╗   ██║   ██║  ██║██║  ██║ ",
    "  ╚══════╝╚═╝     ╚══════╝ ╚═════╝   ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝ ",
]

# Color gradient stops: Cyber Indigo -> Electric Royal Blue -> Sky Cyan -> Neon Mint
GRADIENT_STOPS = [
    "#4338CA",  # Indigo
    "#3B82F6",  # Electric Blue
    "#38BDF8",  # Sky Cyan
    "#06B6D4",  # Neon Cyan
    "#10B981",  # Mint Emerald
]


def _hex_to_rgb(hex_str: str) -> tuple[int, int, int]:
    """Convert hex color string to RGB tuple."""
    hex_str = hex_str.lstrip("#")
    return int(hex_str[0:2], 16), int(hex_str[2:4], 16), int(hex_str[4:6], 16)


def _interpolate_color(stops: list[str], t: float) -> str:
    """Interpolate smoothly between color stops for t in [0.0, 1.0]."""
    t = max(0.0, min(1.0, t))
    num_segments = len(stops) - 1
    scaled_t = t * num_segments
    segment_idx = min(int(scaled_t), num_segments - 1)
    local_t = scaled_t - segment_idx

    r1, g1, b1 = _hex_to_rgb(stops[segment_idx])
    r2, g2, b2 = _hex_to_rgb(stops[segment_idx + 1])

    r = int(r1 + (r2 - r1) * local_t)
    g = int(g1 + (g2 - g1) * local_t)
    b = int(b1 + (b2 - b1) * local_t)

    return f"#{r:02x}{g:02x}{b:02x}"


def _colorize_logo_line(line: str, max_width: int) -> Text:
    """Apply a continuous, silky-smooth 24-bit RGB horizontal gradient across a line."""
    t = Text()
    for i, ch in enumerate(line):
        ratio = i / max(max_width - 1, 1)
        color = _interpolate_color(GRADIENT_STOPS, ratio)
        t.append(ch, style=f"bold {color}")
    return t


def get_version() -> str:
    """Extract version dynamically from setup.py in the project directory."""
    try:
        setup_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "setup.py")
        if os.path.exists(setup_path):
            with open(setup_path, "r", encoding="utf-8") as f:
                content = f.read()
            match = re.search(r'version\s*=\s*["\']([^"\']+)["\']', content)
            if match:
                return match.group(1)
    except Exception:
        pass
    return "1.0.4"


def _rule(label: str = ""):
    """Render a sleek, subtle horizontal divider."""
    if label:
        console.print(Rule(f"[bold {C_BRAND}] {label} [/bold {C_BRAND}]", style=C_BORDER))
    else:
        console.print(Rule(style=C_BORDER))


# ─────────────────────────────────────────────
# Header & Intro Screen
# ─────────────────────────────────────────────
def show_intro():
    """Render a sleek, modern developer banner aligned to the left."""
    console.clear()
    version = get_version()

    sys.stdout.write("\033[H\033[J")
    sys.stdout.flush()

    max_width = max(len(line) for line in LOGO_LINES)
    logo_parts = [_colorize_logo_line(line, max_width) for line in LOGO_LINES]

    meta_bar = Text()
    meta_bar.append("\n  ")
    meta_bar.append("✦ AI-POWERED MULTI-AGENT CODEBASE AUDITOR\n", style=f"bold {C_WHITE}")
    meta_bar.append("  ", style=C_WHITE)
    meta_bar.append(f"v{version}", style=f"bold {C_MINT}")
    meta_bar.append("  •  ", style=C_DIM)
    meta_bar.append("6 Specialist Agents", style=C_MUTED)
    meta_bar.append("  •  ", style=C_DIM)
    meta_bar.append("Zero False-Positives", style=C_MUTED)

    inner = Group(*logo_parts, meta_bar)

    panel = Panel(
        inner,
        border_style=C_BORDER,
        padding=(1, 2),
        expand=False,
        box=box.ROUNDED,
    )
    console.print(panel)
    console.print()


# ─────────────────────────────────────────────
# Workspace & Configuration Setup
# ─────────────────────────────────────────────
def setup_config(target_dir: str):
    """Setup or verify the .spectra workspace and API credentials."""
    config_dir = os.path.join(target_dir, CONFIG_DIR_NAME)
    env_file = os.path.join(config_dir, ".env")

    needs_user_edit = False

    if not os.path.exists(config_dir):
        with console.status(
            f"[{C_BRAND}]✦ Initializing workspace environment...[/{C_BRAND}]",
            spinner="dots12",
            spinner_style=f"bold {C_BRAND}",
        ):
            time.sleep(0.4)
            os.makedirs(config_dir, exist_ok=True)

        with open(env_file, "w", encoding="utf-8") as f:
            f.write("# SPECTRA Configuration\n")
            f.write("# OpenAI API Key (Required)\n")
            f.write("OPENAI_API_KEY=\n\n")
            f.write("# Model selection:\n")
            f.write("#   gpt-4o-mini   Fast & cost-effective (recommended)\n")
            f.write("#   gpt-4o        High accuracy deep-dive\n")
            f.write("OPENAI_MODEL=gpt-4o-mini\n")

        console.print(f"  [bold {C_MINT}]✓[/bold {C_MINT}] [bold {C_WHITE}]Workspace Created[/bold {C_WHITE}]  [{C_MUTED}]{config_dir}[/{C_MUTED}]")
        needs_user_edit = True
    else:
        console.print(f"  [bold {C_MINT}]✓[/bold {C_MINT}] [bold {C_WHITE}]Workspace Ready[/bold {C_WHITE}]    [{C_MUTED}]{config_dir}[/{C_MUTED}]")
        load_dotenv(env_file)
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key or api_key.strip() == "" or api_key.strip() == "sk-your-key-here":
            needs_user_edit = True

    if needs_user_edit:
        # Structured, beautiful settings table
        table = Table(
            box=box.SIMPLE_HEAD,
            border_style=C_BORDER,
            header_style=f"bold {C_BRAND}",
            padding=(0, 2),
            expand=True,
        )
        table.add_column("Parameter", style=f"bold {C_WHITE}", width=18)
        table.add_column("Value / Target", style=C_MUTED)
        table.add_column("Status", justify="right", width=14)

        table.add_row(
            "Config File",
            f"[bold {C_BRAND}]{CONFIG_DIR_NAME}/.env[/bold {C_BRAND}]",
            f"[bold {C_MINT}]● READY[/bold {C_MINT}]",
        )
        table.add_row(
            "OPENAI_API_KEY",
            f"[{C_ROSE}]sk-... (Paste API key)[/{C_ROSE}]",
            f"[bold {C_ROSE}]● REQUIRED[/bold {C_ROSE}]",
        )
        table.add_row(
            "OPENAI_MODEL",
            "[dim]gpt-4o-mini (Recommended)[/dim]",
            f"[bold {C_BRAND}]● DEFAULT[/bold {C_BRAND}]",
        )

        guide = Text()
        guide.append("\n  ")
        guide.append("➜ Next Step: ", style=f"bold {C_MINT}")
        guide.append("Open ", style=C_MUTED)
        guide.append(f"{CONFIG_DIR_NAME}/.env", style=f"bold {C_BRAND}")
        guide.append(", paste your API key, then re-run ", style=C_MUTED)
        guide.append("spectra", style=f"bold {C_MINT}")
        guide.append(" to start the audit.\n", style=C_MUTED)

        card_body = Group(
            Text("  Add your OpenAI API credentials to unlock multi-agent codebase analysis.\n", style=C_MUTED),
            table,
            guide,
        )

        console.print()
        console.print(
            Panel(
                card_body,
                title=f"[bold {C_AMBER}] ✦ CONFIGURATION REQUIRED [/bold {C_AMBER}]",
                title_align="left",
                border_style=C_AMBER,
                padding=(1, 2),
                expand=False,
                box=box.ROUNDED,
            )
        )
        console.print()
        sys.exit(0)

    os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY", "")
    os.environ["OPENAI_MODEL"] = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    os.environ["JOB_STORAGE_PATH"] = os.path.join(config_dir, "reports")


def render_audit_dashboard(
    status: dict,
    start_time: float,
    frame_idx: int,
    file_map: dict[str, list[str]],
) -> Panel:
    """Render a live, animated multi-agent task execution board."""
    pct = status.get("progress_percent", 0)
    current_step = status.get("current_step", "Initializing audit pipeline...")
    job_status = status.get("status", "running").upper()
    agents_running = set(status.get("agents_running", []))
    agents_done = set(status.get("agents_done", []))
    agents_queued = set(status.get("agents_queued", []))
    active_file_map = status.get("file_map", file_map)

    spinner = SPINNER_FRAMES[frame_idx % len(SPINNER_FRAMES)]

    elapsed = int(time.time() - start_time)
    mins, secs = divmod(elapsed, 60)
    time_str = f"{mins:02d}:{secs:02d}"

    # Smooth progress bar
    bar_width = 24
    filled = int(bar_width * (min(pct, 100) / 100.0))

    # Top pipeline status line
    header = Text()
    if pct >= 100 or job_status == "COMPLETED":
        header.append("  ✓ ", style=f"bold {C_MINT}")
        header.append("PIPELINE COMPLETE  ", style=f"bold {C_WHITE}")
        header.append("━" * bar_width, style=f"bold {C_MINT}")
    else:
        header.append(f"  {spinner} ", style=f"bold {C_BRAND}")
        header.append(f"PIPELINE [{job_status}]  ", style=f"bold {C_WHITE}")
        header.append("━" * filled, style=f"bold {C_BRAND}")
        header.append("─" * max(0, bar_width - filled), style=f"dim {C_DIM}")

    header.append(f"  {pct:>3d}% ", style=f"bold {C_WHITE}")
    header.append(f" [{time_str}]", style=C_MUTED)

    # Agent Table (2 columns of 3 agents each)
    table = Table.grid(padding=(0, 2))
    table.add_column(width=34)
    table.add_column(width=34)

    cells = []
    for key, icon, name in AGENT_DEFINITIONS:
        files = active_file_map.get(key, [])
        file_count = len(files)

        cell_text = Text()
        cell_text.append(f"{icon} {name:<11} ", style=f"bold {C_WHITE}" if key in agents_running or key in agents_done else C_MUTED)

        if key in agents_done:
            cell_text.append("✓ DONE   ", style=f"bold {C_MINT}")
            tag = f"({file_count} files)" if file_count else "(scanned)"
            cell_text.append(tag, style=f"dim {C_MUTED}")
        elif key in agents_running:
            cell_text.append(f"{spinner} ACTIVE ", style=f"bold {C_BRAND}")
            tag = f"({file_count} files)" if file_count else "(scanning)"
            cell_text.append(tag, style=f"bold {C_BRAND}")
        elif key in agents_queued or file_count > 0:
            cell_text.append("⋯ QUEUED ", style=f"dim {C_MUTED}")
            tag = f"({file_count} files)" if file_count else "(pending)"
            cell_text.append(tag, style=f"dim {C_DIM}")
        else:
            cell_text.append("— IDLE   ", style=f"dim {C_DIM}")
            cell_text.append("(0 files)", style=f"dim {C_DIM}")

        cells.append(cell_text)

    # Add pairs to 2-column grid
    table.add_row(cells[0], cells[1])
    table.add_row(cells[2], cells[3])
    table.add_row(cells[4], cells[5])

    # Activity text
    activity = Text()
    activity.append("\n  ")
    activity.append("✦ Activity: ", style=f"bold {C_BRAND}")
    activity.append(f"{current_step}", style=C_WHITE if pct >= 100 else C_MUTED)

    body = Group(
        header,
        Text("\n"),
        Padding(table, (0, 1)),
        activity,
    )

    border_color = C_MINT if pct >= 100 else (C_BORDER_HI if pct > 0 else C_BORDER)
    return Panel(
        body,
        title=f"[bold {C_BRAND}] ✦ MULTI-AGENT AUDIT PIPELINE [/bold {C_BRAND}]",
        title_align="left",
        border_style=border_color,
        padding=(1, 2),
        expand=False,
        box=box.ROUNDED,
    )


# ─────────────────────────────────────────────
# Multi-Agent Audit Runner
# ─────────────────────────────────────────────
async def run_audit(target_dir: str):
    """Execute the multi-agent LangGraph audit workflow."""
    setup_config(target_dir)

    console.print()
    console.print(f"  [bold {C_BRAND}]✦[/bold {C_BRAND}] [bold {C_WHITE}]Initializing Multi-Agent Audit Engine...[/bold {C_WHITE}]")
    console.print()

    from backend.graph.audit_graph import audit_graph, jobs_store
    from backend.utils.file_router import DEFAULT_EXCLUDES

    job_id = str(uuid.uuid4())

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

    initial_state = {
        "job_id": job_id,
        "repo_url": "",
        "repo_path": target_dir,
        "branch": "",
        "github_token": None,
        "include_patterns": [],
        "exclude_patterns": list(DEFAULT_EXCLUDES),
        "max_files_per_agent": int(os.environ.get("MAX_FILES_PER_AGENT", "20")),
        "max_chunks_per_file": int(os.environ.get("MAX_CHUNKS_PER_FILE", "2")),
        "rate_limit_rpm": int(os.environ.get("OPENAI_RATE_LIMIT_RPM", "20")),
        "file_map": {},
        "agent_findings": {},
        "aggregated_findings": [],
        "report_md": "",
        "report_md_path": "",
        "report_pdf_path": "",
        "status": "queued",
        "current_step": "Starting audit...",
        "agents_done": [],
        "error": None,
    }

    task = asyncio.create_task(audit_graph.ainvoke(initial_state))

    start_time = time.time()
    frame_idx = 0

    with Live(
        render_audit_dashboard(jobs_store[job_id], start_time, frame_idx, {}),
        console=console,
        refresh_per_second=10,
        transient=False,
    ) as live:
        while not task.done():
            status = jobs_store.get(job_id, {})
            frame_idx += 1
            live.update(
                render_audit_dashboard(status, start_time, frame_idx, status.get("file_map", {}))
            )
            await asyncio.sleep(0.1)

        try:
            result = task.result()
            status = jobs_store.get(job_id, {})
            status["progress_percent"] = 100
            status["status"] = "completed"
            status["current_step"] = "Audit completed successfully. Compiling findings..."
            live.update(
                render_audit_dashboard(status, start_time, frame_idx, status.get("file_map", {}))
            )

            if result.get("error"):
                console.print(f"\n  [bold {C_ROSE}]✗[/bold {C_ROSE}] [bold {C_WHITE}]Audit Error:[/bold {C_WHITE}] {result['error']}", style=C_ROSE)
                sys.exit(1)

        except Exception as e:
            console.print(f"\n  [bold {C_ROSE}]✗[/bold {C_ROSE}] [bold {C_WHITE}]Audit Failed:[/bold {C_WHITE}] {e}", style=C_ROSE)
            import traceback
            traceback.print_exc()
            sys.exit(1)

    # ─────────────────────────────────────────────
    # Findings & Severity Dashboard
    # ─────────────────────────────────────────────
    console.print()
    _rule("AUDIT FINDINGS")
    console.print()

    counts = status.get("finding_counts", {})
    total = status.get("total_findings", 0)

    # Severity table
    sev_table = Table(
        box=box.ROUNDED,
        border_style=C_BORDER,
        header_style=f"bold {C_WHITE}",
        padding=(0, 2),
        expand=False,
    )
    sev_table.add_column("Severity Level", width=18)
    sev_table.add_column("Count", justify="right", width=10)
    sev_table.add_column("Severity Level", width=18)
    sev_table.add_column("Count", justify="right", width=10)

    sev_table.add_row(
        f"[bold {C_ROSE}]● EXTREME[/bold {C_ROSE}]",
        f"[bold {C_WHITE}]{counts.get('EXTREME', 0)}[/bold {C_WHITE}]",
        f"[bold {C_ORANGE}]● HIGH[/bold {C_ORANGE}]",
        f"[bold {C_WHITE}]{counts.get('HIGH', 0)}[/bold {C_WHITE}]",
    )
    sev_table.add_row(
        f"[bold {C_AMBER}]● MEDIUM[/bold {C_AMBER}]",
        f"[bold {C_WHITE}]{counts.get('MEDIUM', 0)}[/bold {C_WHITE}]",
        f"[bold {C_BRAND}]● LOW[/bold {C_BRAND}]",
        f"[bold {C_WHITE}]{counts.get('LOW', 0)}[/bold {C_WHITE}]",
    )

    total_msg = Text()
    total_msg.append("\n  ")
    if total == 0:
        total_msg.append("🛡️  Zero vulnerabilities detected — Codebase is in exceptional health!", style=f"bold {C_MINT}")
    else:
        total_msg.append(f"⚠️  {total} Total Findings Detected across specialist agent reviews.", style=f"bold {C_AMBER}")

    summary_body = Group(
        sev_table,
        total_msg,
    )

    console.print(
        Panel(
            summary_body,
            title=f"[bold {C_WHITE}] ✦ EXECUTIVE SUMMARY [/bold {C_WHITE}]",
            title_align="left",
            border_style=C_BORDER_HI if total == 0 else C_AMBER,
            padding=(1, 3),
            expand=False,
            box=box.ROUNDED,
        )
    )

    # ─────────────────────────────────────────────
    # Report Artifact Links
    # ─────────────────────────────────────────────
    md_path = result.get("report_md_path")
    pdf_path = result.get("report_pdf_path")

    console.print()
    if md_path and os.path.exists(md_path):
        abs_md = os.path.abspath(md_path)
        console.print(f"  [bold {C_MINT}]📄 Markdown Report[/bold {C_MINT}]  [link=file://{abs_md}][{C_BRAND}]{abs_md}[/{C_BRAND}][/link]")
    if pdf_path and os.path.exists(pdf_path):
        abs_pdf = os.path.abspath(pdf_path)
        console.print(f"  [bold {C_ACCENT}]📊 PDF Report[/bold {C_ACCENT}]       [link=file://{abs_pdf}][{C_ACCENT}]{abs_pdf}[/{C_ACCENT}][/link]")

    console.print()
    console.print(Rule(style=C_BORDER))
    console.print()


# ─────────────────────────────────────────────
# Help Screen
# ─────────────────────────────────────────────
def show_help():
    """Render a polished, modern help manual."""
    version = get_version()

    help_table = Table(
        box=box.SIMPLE_HEAD,
        border_style=C_BORDER,
        header_style=f"bold {C_BRAND}",
        padding=(0, 2),
        expand=True,
    )
    help_table.add_column("Command / Option", style=f"bold {C_WHITE}", width=24)
    help_table.add_column("Description", style=C_MUTED)

    help_table.add_row(
        f"[bold {C_MINT}]spectra[/bold {C_MINT}]",
        "Launch interactive audit in the current project directory.",
    )
    help_table.add_row(
        f"[bold {C_MINT}]spectra -d <path>[/bold {C_MINT}]",
        "Audit a specific directory path or local repository clone.",
    )
    help_table.add_row(
        f"[bold {C_MINT}]spectra --help[/bold {C_MINT}]",
        "Display this help manual and exit.",
    )

    workflow = Table(
        box=box.SIMPLE_HEAD,
        border_style=C_BORDER,
        header_style=f"bold {C_ACCENT}",
        padding=(0, 2),
        expand=True,
    )
    workflow.add_column("Step", style=f"bold {C_BRAND}", width=8)
    workflow.add_column("Action", style=C_WHITE)

    workflow.add_row("01", "Navigate to your target codebase in your terminal.")
    workflow.add_row("02", f"Run [bold {C_MINT}]spectra[/bold {C_MINT}] to initialize the [cyan].spectra/[/cyan] workspace.")
    workflow.add_row("03", "Add your OpenAI key to [bold cyan].spectra/.env[/bold cyan].")
    workflow.add_row("04", f"Re-run [bold {C_MINT}]spectra[/bold {C_MINT}] to launch 6 parallel specialist agents.")

    content = Group(
        Text(f"SPECTRA v{version} — Multi-Agent AI Codebase Security & Architecture Auditor\n", style=f"bold {C_WHITE}"),
        Text("Audits codebases for OWASP Top 10 vulnerabilities, supply chain flaws, infrastructure gaps, and architectural defects with zero false positives.\n", style=C_MUTED),
        Text("COMMANDS & OPTIONS", style=f"bold {C_BRAND}"),
        help_table,
        Text("\nWORKFLOW", style=f"bold {C_ACCENT}"),
        workflow,
        Text("\nREPORTS", style=f"bold {C_MINT}"),
        Text("  Reports are compiled in Markdown (.md) and PDF (.pdf) under .spectra/reports/.\n", style=C_MUTED),
    )

    console.print()
    console.print(
        Panel(
            content,
            title=f"[bold {C_BRAND}] ✦ SPECTRA CLI MANUAL [/bold {C_BRAND}]",
            title_align="left",
            border_style=C_BORDER,
            padding=(1, 3),
            expand=False,
            box=box.ROUNDED,
        )
    )
    console.print()


# ─────────────────────────────────────────────
# CLI Entry Point
# ─────────────────────────────────────────────
@click.command(add_help_option=False)
@click.option(
    "--dir",
    "-d",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    default=".",
    help="Target directory to audit.",
)
@click.option("--help", "-help", "-h", is_flag=True, help="Show this message and exit.")
def main(dir, help):
    if help:
        show_help()
        sys.exit(0)

    show_intro()
    target_dir = os.path.abspath(dir)

    console.print(f"  [bold {C_BRAND}]◆ Target Directory[/bold {C_BRAND}]   [{C_WHITE}]{target_dir}[/{C_WHITE}]")

    asyncio.run(run_audit(target_dir))


if __name__ == "__main__":
    main()
