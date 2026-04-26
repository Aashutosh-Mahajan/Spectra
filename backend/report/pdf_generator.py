"""
PDF Report Generator — converts Markdown reports to styled PDFs using WeasyPrint.
"""

import os
import logging

import markdown
from pygments.formatters import HtmlFormatter
from weasyprint import HTML

logger = logging.getLogger(__name__)

# Path to CSS template
CSS_TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "templates", "report_style.css")


def generate_pdf_report(
    markdown_content: str,
    job_id: str,
    storage_base: str = "./storage/jobs",
) -> str:
    """
    Convert a Markdown audit report to a styled PDF.

    Args:
        markdown_content: The markdown report string
        job_id: Job identifier for output path
        storage_base: Base storage directory

    Returns:
        Absolute path to the generated PDF file
    """
    # Convert Markdown to HTML
    md_extensions = ["tables", "fenced_code", "codehilite", "toc", "nl2br"]
    html_body = markdown.markdown(markdown_content, extensions=md_extensions)

    # Load CSS
    css_content = _load_css()

    # Pygments syntax highlighting CSS
    pygments_css = HtmlFormatter(style="monokai").get_style_defs(".codehilite")

    # Build full HTML document
    full_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>Codebase Audit Report — {job_id[:8]}</title>
    <style>
        {css_content}
        {pygments_css}
    </style>
</head>
<body>
    <header class="report-header">
        <div class="brand">🔍 Codebase Audit Agent System</div>
        <div class="team">Neural Ninjas</div>
    </header>
    <main>
        {html_body}
    </main>
    <footer class="report-footer">
        <span>Codebase Audit Agent System — Neural Ninjas</span>
        <span class="page-number"></span>
    </footer>
</body>
</html>"""

    # Generate PDF
    output_dir = os.path.join(storage_base, job_id)
    os.makedirs(output_dir, exist_ok=True)
    pdf_path = os.path.join(output_dir, f"report_{job_id}.pdf")

    HTML(string=full_html).write_pdf(pdf_path)

    logger.info(f"PDF report generated: {pdf_path}")
    return os.path.abspath(pdf_path)


def _load_css() -> str:
    """Load the report CSS template."""
    if os.path.exists(CSS_TEMPLATE_PATH):
        with open(CSS_TEMPLATE_PATH, "r", encoding="utf-8") as f:
            return f.read()

    # Fallback inline CSS if template file is missing
    return _get_default_css()


def _get_default_css() -> str:
    """Default CSS styling for the PDF report."""
    return """
@page {
    size: A4;
    margin: 2cm 1.5cm;
    @bottom-center {
        content: "Page " counter(page) " of " counter(pages);
        font-size: 9pt;
        color: #6b7280;
    }
}

body {
    font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
    font-size: 11pt;
    line-height: 1.6;
    color: #1f2937;
}

h1 { font-size: 22pt; color: #111827; border-bottom: 3px solid #3b82f6; padding-bottom: 8px; }
h2 { font-size: 16pt; color: #1e40af; margin-top: 24px; border-bottom: 1px solid #e5e7eb; padding-bottom: 6px; }
h3 { font-size: 13pt; color: #374151; margin-top: 18px; }
h4 { font-size: 11pt; color: #4b5563; margin-top: 14px; }

table { width: 100%; border-collapse: collapse; margin: 12px 0; font-size: 10pt; }
th { background: #1e293b; color: white; padding: 8px 10px; text-align: left; font-weight: 600; }
td { padding: 6px 10px; border-bottom: 1px solid #e5e7eb; }
tr:nth-child(even) { background: #f9fafb; }

code { background: #f3f4f6; padding: 2px 5px; border-radius: 3px; font-family: 'Consolas', 'Courier New', monospace; font-size: 9.5pt; }
pre { background: #1e293b; color: #e2e8f0; padding: 14px; border-radius: 6px; overflow-x: auto; font-size: 9pt; line-height: 1.5; }
pre code { background: none; color: inherit; padding: 0; }

blockquote { border-left: 4px solid #3b82f6; margin: 12px 0; padding: 8px 16px; background: #eff6ff; color: #1e40af; }

.report-header { text-align: center; margin-bottom: 24px; padding-bottom: 16px; border-bottom: 2px solid #3b82f6; }
.report-header .brand { font-size: 18pt; font-weight: 700; color: #1e40af; }
.report-header .team { font-size: 11pt; color: #6b7280; margin-top: 4px; }

hr { border: none; border-top: 1px solid #e5e7eb; margin: 20px 0; }
"""
