"""
PDF Report Generator — converts Markdown reports to styled PDFs using xhtml2pdf.
"""

import os
import re
import logging
from io import BytesIO

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
    html_body = _add_col_widths_to_tables(html_body)

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

def _add_col_widths_to_tables(html: str) -> str:
    """Add <col> elements to tables for xhtml2pdf compatibility to prevent NoneType layout errors."""
    def add_cols(match):
        table_html = match.group(0)
        thead_match = re.search(r'<thead>\s*<tr>(.*?)</tr>\s*</thead>', table_html, re.DOTALL | re.IGNORECASE)
        if not thead_match:
            return table_html
        
        th_content = thead_match.group(1)
        th_count = len(re.findall(r'<th\b[^>]*>', th_content, re.IGNORECASE))
        
        if th_count > 0:
            width_pct = 100.0 / th_count
            colgroup = "<colgroup>" + "".join([f'<col width="{width_pct:.2f}%">' for _ in range(th_count)]) + "</colgroup>\n"
            table_html = table_html.replace('<thead>', colgroup + '<thead>', 1)
        return table_html
    return re.sub(r'<table\b[^>]*>.*?</table>', add_cols, html, flags=re.DOTALL | re.IGNORECASE)


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

table { width: 100%; border: 1px solid #cccccc; margin: 10px 0; font-size: 10pt; }
th { background-color: #1e293b; color: #ffffff; padding: 6px; text-align: left; font-weight: bold; }
td { padding: 5px; border-bottom: 1px solid #e5e7eb; }

code { background-color: #f3f4f6; font-family: Courier, monospace; font-size: 9pt; }
pre { background-color: #1e293b; color: #e2e8f0; padding: 10px; font-size: 9pt; }
pre code { background-color: transparent; }

blockquote { border-left: 3px solid #3b82f6; margin: 10px 0; padding: 5px 10px; background-color: #eff6ff; color: #1e40af; }
hr { border: none; border-top: 1px solid #e5e7eb; margin: 15px 0; }
"""
