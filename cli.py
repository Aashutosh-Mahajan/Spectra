import os
import sys

# Force UTF-8 encoding on Windows to prevent UnicodeEncodeError in legacy consoles
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import asyncio
import uuid
import click
import time
import logging
from dotenv import load_dotenv, set_key
from rich.align import Align
from rich.console import Console, Group
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.rule import Rule
from rich.padding import Padding
from rich import box


# Suppress debug logs from other libraries
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

console = Console()

# --- Color Palette ----------------------------------------------------------------
C_PRIMARY   = "#00D4FF"   # Electric cyan
C_ACCENT    = "#0066FF"   # Vibrant royal blue
C_SUCCESS   = "#00FFB2"   # Neon mint
C_WARN      = "#FFB800"   # Amber
C_DANGER    = "#FF3C5F"   # Hot red
C_DIM       = "#4A5568"   # Slate grey
C_GLOW      = "#00A8FF"   # Softer cyan for borders
C_TITLE     = "#E2E8F0"   # Near-white
C_SUBTLE    = "#718096"   # Muted grey

HELP_TEXT = f"""
[bold {C_PRIMARY}]SPECTRA[/bold {C_PRIMARY}] [dim {C_SUBTLE}]|[/dim {C_SUBTLE}] [bold {C_TITLE}]Multi-Agent Codebase Audit System[/bold {C_TITLE}]

[{C_SUBTLE}]Audits any local codebase or GitHub repository, detects bugs &
vulnerabilities across the full stack, and generates professional
Markdown and PDF audit reports.[/{C_SUBTLE}]

[bold {C_TITLE}]USAGE[/bold {C_TITLE}]
  [bold {C_SUCCESS}]spectra[/bold {C_SUCCESS}]                  Run interactive audit in the current directory
  [bold {C_SUCCESS}]spectra -d [/bold {C_SUCCESS}][{C_PRIMARY}]<path>[/{C_PRIMARY}]        Run audit on a specific directory
  [bold {C_SUCCESS}]spectra -help[/bold {C_SUCCESS}]             Show this help message and exit

[bold {C_TITLE}]WORKFLOW[/bold {C_TITLE}]
  [bold {C_PRIMARY}]01[/bold {C_PRIMARY}]  Navigate to the project you want to audit
  [bold {C_PRIMARY}]02[/bold {C_PRIMARY}]  Run [bold {C_SUCCESS}]spectra[/bold {C_SUCCESS}] -- a [cyan].spectra/[/cyan] workspace will be created
  [bold {C_PRIMARY}]03[/bold {C_PRIMARY}]  Add your API key to the generated [cyan].env[/cyan] file
  [bold {C_PRIMARY}]04[/bold {C_PRIMARY}]  Run [bold {C_SUCCESS}]spectra[/bold {C_SUCCESS}] again to start the audit

[bold {C_TITLE}]OUTPUT[/bold {C_TITLE}]
  Reports are saved to [cyan].spectra/reports/[/cyan] as [bold].md[/bold] and [bold].pdf[/bold] files.
"""

CONFIG_DIR_NAME = ".spectra"

# --- Logo -------------------------------------------------------------------------

LOGO_LINES = [
    " ███████╗██████╗ ███████╗ ██████╗████████╗██████╗  █████╗ ",
    " ██╔════╝██╔══██╗██╔════╝██╔════╝╚══██╔══╝██╔══██╗██╔══██╗",
    " ███████╗██████╔╝█████╗  ██║        ██║   ██████╔╝███████║",
    " ╚════██║██╔═══╝ ██╔══╝  ██║        ██║   ██╔══██╗██╔══██║",
    " ███████║██║     ███████╗╚██████╗   ██║   ██║  ██║██║  ██║",
    " ╚══════╝╚═╝     ╚══════╝ ╚═════╝   ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝",
]

# Gradient: deep electric blue -> bright neon cyan (left to right)
LOGO_GRADIENT = [
    "#0052D4", "#0066FF", "#007BFF", "#0091FF",
    "#00A6FF", "#00BCFF", "#00D4FF", "#00E5FF", "#00F2FE",
]


def _colorize_logo_line(line: str) -> Text:
    """Apply a left-to-right gradient across a logo line."""
    t = Text()
    width = len(line)
    grad_len = len(LOGO_GRADIENT)
    for i, ch in enumerate(line):
        color_idx = int(i / max(width, 1) * (grad_len - 1))
        t.append(ch, style=f"bold {LOGO_GRADIENT[color_idx]}")
    return t


def get_version() -> str:
    """Extract version dynamically from setup.py in the project directory."""
    try:
        setup_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "setup.py")
        if os.path.exists(setup_path):
            with open(setup_path, "r", encoding="utf-8") as f:
                content = f.read()
            import re
            match = re.search(r'version\s*=\s*["\']([^"\']+)["\']', content)
            if match:
                return match.group(1)
    except Exception:
        pass
    return "1.0.0"


# --- Helpers ----------------------------------------------------------------------

def _icon(kind: str) -> str:
    return {
        "ok":    f"[bold {C_SUCCESS}]>>>[/bold {C_SUCCESS}]",
        "warn":  f"[bold {C_WARN}]!!![/bold {C_WARN}]",
        "error": f"[bold {C_DANGER}]XXX[/bold {C_DANGER}]",
        "info":  f"[bold {C_PRIMARY}]>>>[/bold {C_PRIMARY}]",
        "arrow": f"[{C_ACCENT}]>>>[/{C_ACCENT}]",
        "dot":   f"[{C_DIM}]|[/{C_DIM}]",
    }.get(kind, "")


def _rule(label: str = ""):
    if label:
        console.print(Rule(f"[bold {C_PRIMARY}]{label}[/bold {C_PRIMARY}]", style=C_GLOW))
    else:
        console.print(Rule(style=C_GLOW))


# --- Intro ------------------------------------------------------------------------

def show_intro():
    console.clear()
    version = get_version()

    sys.stdout.write("\033[H\033[J")
    sys.stdout.flush()

    # Render each line of the block-art logo with gradient
    logo_parts = [_colorize_logo_line(line) for line in LOGO_LINES]

    subtitle = Text()
    subtitle.append("\n")
    subtitle.append("  MULTI-AGENT CODEBASE AUDIT SYSTEM", style=f"bold {C_DIM}")
    subtitle.append(f"\n  v{version}", style=f"dim {C_SUBTLE}")

    inner = Group(*logo_parts, subtitle)

    panel = Panel(
        inner,
        border_style=C_GLOW,
        padding=(1, 3),
        expand=False,
        box=box.ROUNDED,
    )
    console.print(panel)
    console.print()


# --- Config Setup -----------------------------------------------------------------

def setup_config(target_dir):
    config_dir = os.path.join(target_dir, CONFIG_DIR_NAME)
    env_file   = os.path.join(config_dir, ".env")

    needs_user_edit = False

    if not os.path.exists(config_dir):
        with console.status(
            f"[{C_PRIMARY}]Initializing workspace...[/{C_PRIMARY}]",
            spinner="dots",
            spinner_style=f"bold {C_PRIMARY}",
        ):
            time.sleep(0.6)
            os.makedirs(config_dir, exist_ok=True)

        with open(env_file, "w", encoding="utf-8") as f:
            f.write("# SPECTRA Configuration\n")
            f.write("# OpenAI API Key\n")
            f.write("OPENAI_API_KEY=\n\n")
            f.write("# Model selection:\n")
            f.write("#   gpt-4o-mini   Fast & cost-effective  (recommended)\n")
            f.write("#   gpt-4o        High accuracy\n")
            f.write("OPENAI_MODEL=gpt-4o-mini\n")

        console.print(f"  {_icon('ok')} [{C_TITLE}]Workspace created[/{C_TITLE}]  [{C_SUBTLE}]{config_dir}[/{C_SUBTLE}]")
        needs_user_edit = True
    else:
        console.print(f"  {_icon('ok')} [{C_TITLE}]Workspace found[/{C_TITLE}]  [{C_SUBTLE}]{config_dir}[/{C_SUBTLE}]")
        # Load existing env vars
        load_dotenv(env_file)
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key or api_key.strip() == "":
            needs_user_edit = True

    if needs_user_edit:
        # --- Setup Required Panel ---
        setup_lines = Text(justify="left")
        setup_lines.append(f"  {'config':<8}", style=f"bold {C_PRIMARY}")
        setup_lines.append(f"{env_file}\n", style=C_SUBTLE)

        setup_lines.append(f"  {'key':<8}", style=f"bold {C_PRIMARY}")
        setup_lines.append("OPENAI_API_KEY", style=f"bold {C_TITLE}")
        setup_lines.append("=", style=C_DIM)
        setup_lines.append("sk-your-key-here\n", style=C_SUBTLE)

        setup_lines.append(f"  {'model':<8}", style=f"bold {C_PRIMARY}")
        setup_lines.append("OPENAI_MODEL", style=f"bold {C_TITLE}")
        setup_lines.append("=", style=C_DIM)
        setup_lines.append("gpt-4o-mini", style=C_SUBTLE)

        hint = Text(justify="left")
        hint.append("\n  ")
        hint.append(">>>", style=f"bold {C_ACCENT}")
        hint.append(" Edit the config file, then run ", style=f"dim {C_SUBTLE}")
        hint.append("spectra", style=f"bold {C_SUCCESS}")
        hint.append(" again.", style=f"dim {C_SUBTLE}")

        body = Group(
            Text(f"  Setup Required", style=f"bold {C_WARN}", justify="left"),
            Text("  Add your OpenAI key before running the audit.\n", style=C_SUBTLE, justify="left"),
            setup_lines,
            hint,
        )

        console.print(
            Panel(
                body,
                border_style=C_WARN,
                padding=(1, 2),
                expand=False,
                box=box.ROUNDED,
            )
        )
        console.print()
        sys.exit(0)

    os.environ["OPENAI_API_KEY"]  = os.getenv("OPENAI_API_KEY")
    os.environ["OPENAI_MODEL"]    = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    os.environ["JOB_STORAGE_PATH"] = os.path.join(config_dir, "reports")


# --- Audit Runner -----------------------------------------------------------------

async def run_audit(target_dir: str):
    # Setup config in target directory
    setup_config(target_dir)

    # Now load the backend graph
    console.print(f"\n  {_icon('info')} [{C_TITLE}]Initializing audit pipeline...[/{C_TITLE}]\n")
    from backend.graph.audit_graph import audit_graph, jobs_store
    from backend.utils.file_router import DEFAULT_EXCLUDES

    job_id = str(uuid.uuid4())

    # Initialize job in store
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
        "max_files_per_agent": int(os.environ.get("MAX_FILES_PER_AGENT", 20)),
        "max_chunks_per_file": int(os.environ.get("MAX_CHUNKS_PER_FILE", 2)),
        "rate_limit_rpm": int(os.environ.get("OPENAI_RATE_LIMIT_RPM", 20)),
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

    with Progress(
        SpinnerColumn("dots12", style=f"bold {C_PRIMARY}"),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(
            bar_width=40,
            style=f"bold {C_DIM}",
            complete_style=f"bold {C_PRIMARY}",
            finished_style=f"bold {C_SUCCESS}",
        ),
        TextColumn(f"[bold {C_TITLE}]{{task.percentage:>3.0f}}%[/bold {C_TITLE}]"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        job_task = progress.add_task(f"[{C_PRIMARY}]Starting...", total=100)

        while not task.done():
            status   = jobs_store.get(job_id, {})
            pct      = status.get("progress_percent", 0)
            step     = status.get("current_step", "")
            state_v  = status.get("status", "running").upper()
            progress.update(
                job_task,
                completed=pct,
                description=f"[bold {C_PRIMARY}]{state_v}[/bold {C_PRIMARY}] [{C_SUBTLE}]{step}[/{C_SUBTLE}]",
            )
            await asyncio.sleep(0.4)

        try:
            result = task.result()
            status = jobs_store.get(job_id, {})
            pct    = status.get("progress_percent", 100)
            progress.update(job_task, completed=pct, description=f"[bold {C_SUCCESS}]DONE[/bold {C_SUCCESS}]")

            if result.get("error"):
                console.print(f"\n  {_icon('error')} Audit error: {result['error']}", style=C_DANGER)
                sys.exit(1)

        except Exception as e:
            console.print(f"\n  {_icon('error')} Audit failed: {e}", style=C_DANGER)
            import traceback; traceback.print_exc()
            sys.exit(1)

    # --- Results ------------------------------------------------------------------
    console.print()
    _rule("RESULTS")
    console.print()

    counts = status.get("finding_counts", {})
    total  = status.get("total_findings", 0)

    SEVERITY_CONFIG = [
        ("EXTREME", C_DANGER,  ">>>"),
        ("HIGH",    "#FF6B35", ">>>"),
        ("MEDIUM",  C_WARN,    ">>>"),
        ("LOW",     C_PRIMARY, ">>>"),
    ]

    # --- Severity grid ------------------------------------------------------------
    sev_table = Table.grid(padding=(0, 4))
    sev_table.add_column(justify="left")
    sev_table.add_column(justify="right")
    sev_table.add_column(justify="left")
    sev_table.add_column(justify="right")

    rows = list(zip(SEVERITY_CONFIG[::2], SEVERITY_CONFIG[1::2]))
    for (lbl1, col1, dot1), (lbl2, col2, dot2) in rows:
        cnt1 = counts.get(lbl1, 0)
        cnt2 = counts.get(lbl2, 0)
        sev_table.add_row(
            f"[bold {col1}]{dot1} {lbl1:<8}[/bold {col1}]",
            f"[bold {C_TITLE}]{cnt1}[/bold {C_TITLE}]",
            f"[bold {col2}]{dot2} {lbl2:<8}[/bold {col2}]",
            f"[bold {C_TITLE}]{cnt2}[/bold {C_TITLE}]",
        )

    total_line = Text(justify="left")
    total_line.append("\n")
    total_line.append(f"  {total} findings total  ", style=f"bold {C_TITLE}")

    summary_body = Group(
        Padding(Align.left(sev_table), (0, 2)),
        Align.left(total_line),
    )

    console.print(
        Panel(
            summary_body,
            title=f"[bold {C_TITLE}]Audit Complete[/bold {C_TITLE}]",
            title_align="left",
            border_style=C_GLOW,
            padding=(1, 3),
            expand=False,
            box=box.DOUBLE,
        )
    )

    # --- Report Links -------------------------------------------------------------
    md_path  = result.get("report_md_path")
    pdf_path = result.get("report_pdf_path")

    console.print()
    if md_path and os.path.exists(md_path):
        abs_md = os.path.abspath(md_path)
        console.print(f"  {_icon('ok')} [bold {C_TITLE}]Markdown[/bold {C_TITLE}]  [link=file://{abs_md}][{C_PRIMARY}]{abs_md}[/{C_PRIMARY}][/link]")
    if pdf_path and os.path.exists(pdf_path):
        abs_pdf = os.path.abspath(pdf_path)
        console.print(f"  {_icon('ok')} [bold {C_TITLE}]PDF[/bold {C_TITLE}]       [link=file://{abs_pdf}][{C_ACCENT}]{abs_pdf}[/{C_ACCENT}][/link]")

    console.print()
    console.print(Rule(style=C_DIM))
    console.print()


# --- Entry Point ------------------------------------------------------------------

@click.command(add_help_option=False)
@click.option("--dir", "-d",
              type=click.Path(exists=True, file_okay=False, dir_okay=True),
              default=".",
              help="Target directory to audit.")
@click.option("--help", "-help", "-h", is_flag=True, help="Show this message and exit.")
def main(dir, help):
    if help:
        console.print(
            Panel(
                HELP_TEXT,
                border_style=C_GLOW,
                padding=(1, 4),
                box=box.ROUNDED,
                title=f"[bold {C_PRIMARY}]spectra --help[/bold {C_PRIMARY}]",
                title_align="left",
            )
        )
        sys.exit(0)

    show_intro()

    target_dir = os.path.abspath(dir)

    _rule()
    console.print(f"\n  {_icon('info')} [bold {C_TITLE}]Target[/bold {C_TITLE}]  [{C_SUBTLE}]{target_dir}[/{C_SUBTLE}]\n")

    asyncio.run(run_audit(target_dir))


if __name__ == "__main__":
    main()
