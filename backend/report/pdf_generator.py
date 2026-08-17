"""
PDF Report Generator — converts Markdown reports to styled PDFs using xhtml2pdf.
"""

import os
import re
import logging

import markdown
from pygments.formatters import HtmlFormatter
from xhtml2pdf import pisa

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

    # Sanitize untested HTML to avoid xhtml2pdf NoneType exceptions
    html_body = _sanitize_html_tags(html_body)
    html_body = _normalize_tables_for_xhtml2pdf(html_body)

    # Load CSS
    css_content = _load_css()

    # Pygments syntax highlighting CSS
    pygments_css = HtmlFormatter(style="monokai").get_style_defs(".codehilite")

    # Build full HTML document for xhtml2pdf
    full_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>SPECTRA Audit Report — {job_id[:8]}</title>
    <style>
        {css_content}
        {pygments_css}
    </style>
</head>
<body>
    <div id="header">
        <div class="brand">🔍 SPECTRA</div>
    </div>
    <div id="footer">
        SPECTRA | Page <pdf:pagenumber> of <pdf:pagecount>
    </div>
    <main>
        {html_body}
    </main>
</body>
</html>"""

    # Generate PDF
    output_dir = os.path.join(storage_base, job_id)
    os.makedirs(output_dir, exist_ok=True)
    pdf_path = os.path.join(output_dir, f"report_{job_id}.pdf")

    try:
        with open(pdf_path, "w+b") as result_file:
            pisa_status = pisa.CreatePDF(full_html, dest=result_file)

        if pisa_status.err:
            logger.error("PDF generation failed with pisa errors.")
            return ""

        logger.info(f"PDF report generated: {pdf_path}")
        return os.path.abspath(pdf_path)
    except Exception as e:
        logger.error(f"PDF generation failed: {e}")
        return ""

_ALLOWED_TAGS = {
    'html', 'head', 'meta', 'title', 'style', 'body', 'div', 'main',
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'br', 'a', 'ul', 'ol', 'li',
    'table', 'thead', 'tbody', 'tr', 'th', 'td', 'pre', 'code', 'blockquote',
    'strong', 'b', 'em', 'i', 'span', 'img', 'hr', 'dl', 'dt', 'dd'
}

def _sanitize_html_tags(html: str) -> str:
    """Sanitize arbitrary HTML from markdown to prevent xhtml2pdf NoneType parsing errors."""
    def replacer(match):
        tag_full = match.group(0)
        tag_name = match.group(2).lower()
        if tag_name not in _ALLOWED_TAGS:
            if not tag_name.startswith('pdf:'):
                return tag_full.replace('<', '&lt;').replace('>', '&gt;')
        return tag_full
    return re.sub(r'<(/?)([a-zA-Z0-9:]+)\b[^>]*>', replacer, html)

def _normalize_tables_for_xhtml2pdf(html: str) -> str:
    """
    Add explicit widths to table cells for xhtml2pdf.

    xhtml2pdf/ReportLab can collapse auto-sized Markdown tables to tiny
    columns when cells contain long inline code or KeepInFrame content. If the
    column becomes narrower than its padding, ReportLab raises:
    "flowable given negative availWidth". Cell-level widths are more reliable
    than colgroup widths for xhtml2pdf, so we inject both conservative padding
    and explicit widths into every generated table row.
    """
    def normalize_table(match):
        table_html = match.group(0)

        first_row = re.search(r'<tr\b[^>]*>(.*?)</tr>', table_html, re.DOTALL | re.IGNORECASE)
        if not first_row:
            return table_html

        col_count = len(re.findall(r'<t[hd]\b[^>]*>', first_row.group(1), re.IGNORECASE))
        if col_count <= 0:
            return table_html

        if col_count == 2:
            # Finding detail tables: short label + long explanation.
            widths = [28, 72]
        elif col_count == 6:
            # Agent summary table: keep the agent name readable.
            widths = [24, 15, 15, 16, 15, 15]
        else:
            base_width = int(100 / col_count)
            widths = [base_width] * col_count
            widths[-1] += 100 - sum(widths)

        table_html = re.sub(
            r'<table\b([^>]*)>',
            r'<table\1 width="100%" style="width:100%; table-layout:fixed;">',
            table_html,
            count=1,
            flags=re.IGNORECASE,
        )

        def normalize_row(row_match):
            row_html = row_match.group(0)
            cell_index = -1

            def normalize_cell(cell_match):
                nonlocal cell_index
                cell_index += 1
                tag = cell_match.group(1)
                attrs = cell_match.group(2) or ""
                width = widths[min(cell_index, len(widths) - 1)]

                attrs = re.sub(r'\swidth="[^"]*"', "", attrs, flags=re.IGNORECASE)
                attrs = re.sub(r"\swidth='[^']*'", "", attrs, flags=re.IGNORECASE)
                attrs = re.sub(r'\sstyle="[^"]*"', "", attrs, flags=re.IGNORECASE)
                return (
                    f'<{tag}{attrs} width="{width}%" '
                    f'style="width:{width}%; padding:3px 4px; vertical-align:top;">'
                )

            return re.sub(
                r'<(td|th)\b([^>]*)>',
                normalize_cell,
                row_html,
                flags=re.IGNORECASE,
            )

        table_html = re.sub(
            r'<tr\b[^>]*>.*?</tr>',
            normalize_row,
            table_html,
            flags=re.DOTALL | re.IGNORECASE,
        )

        return table_html

    return re.sub(
        r'<table\b[^>]*>.*?</table>',
        normalize_table,
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )


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
    size: a4;
    margin: 2cm;
    @frame header_frame {
        -pdf-frame-content: header;
        margin-top: 1cm;
        margin-left: 2cm;
        margin-right: 2cm;
        height: 1cm;
    }
    @frame footer_frame {
        -pdf-frame-content: footer;
        margin-bottom: 1cm;
        margin-left: 2cm;
        margin-right: 2cm;
        height: 1cm;
    }
}

body {
    font-family: Helvetica, Arial, sans-serif;
    font-size: 11pt;
    line-height: 1.5;
    color: #333333;
}

#header {
    text-align: center;
    border-bottom: 1px solid #3b82f6;
    padding-bottom: 10px;
}
.brand {
    font-size: 16pt;
    font-weight: bold;
    color: #1e40af;
}

#footer {
    text-align: center;
    font-size: 9pt;
    color: #666666;
    border-top: 1px solid #cccccc;
    padding-top: 5px;
}

h1 { font-size: 20pt; color: #111827; border-bottom: 2px solid #3b82f6; padding-bottom: 5px; }
h2 { font-size: 15pt; color: #1e40af; margin-top: 15px; border-bottom: 1px solid #e5e7eb; padding-bottom: 3px; }
h3 { font-size: 12pt; color: #374151; margin-top: 12px; }
h4 { font-size: 11pt; color: #4b5563; margin-top: 10px; }

table { width: 100%; border: 1px solid #cccccc; margin: 10px 0; font-size: 10pt; table-layout: fixed; }
th { background-color: #1e293b; color: #ffffff; padding: 6px; text-align: left; font-weight: bold; }
td { padding: 5px; border-bottom: 1px solid #e5e7eb; word-wrap: break-word; }

code { background-color: #f3f4f6; font-family: Courier, monospace; font-size: 9pt; word-wrap: break-word; }
pre { background-color: #1e293b; color: #e2e8f0; padding: 10px; font-size: 9pt; white-space: pre-wrap; word-wrap: break-word; }
pre code { background-color: transparent; }

blockquote { border-left: 3px solid #3b82f6; margin: 10px 0; padding: 5px 10px; background-color: #eff6ff; color: #1e40af; }
hr { border: none; border-top: 1px solid #e5e7eb; margin: 15px 0; }
"""
