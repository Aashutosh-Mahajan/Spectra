"""
Audit report generator — produces Markdown reports from aggregated findings.
Phase 2 will add PDF generation via WeasyPrint.
"""

import logging
from datetime import datetime, timezone

from backend.utils.severity import get_severity_emoji, get_severity_order

logger = logging.getLogger(__name__)


def generate_markdown_report(
    findings: list[dict],
    repo_url: str,
    branch: str = "main",
) -> str:
    """
    Generate a professional Markdown audit report from findings.

    Args:
        findings: List of finding dicts (from Finding.model_dump())
        repo_url: Repository URL that was audited
        branch: Branch that was audited

    Returns:
        Complete Markdown report as a string
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Count findings by severity
    counts = {"EXTREME": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for f in findings:
        sev = f.get("severity", "LOW")
        if sev in counts:
            counts[sev] += 1
    total = sum(counts.values())

    # Calculate risk score (average of all finding scores, or 0 if no findings)
    if findings:
        risk_score = round(sum(f.get("score", 0) for f in findings) / len(findings), 1)
    else:
        risk_score = 0.0

    # Sort findings by severity (EXTREME first) then by score (highest first)
    sorted_findings = sorted(
        findings,
        key=lambda f: (get_severity_order(f.get("severity", "LOW")), -f.get("score", 0)),
    )

    # ─── Build the report ───
    lines: list[str] = []

    # Header
    lines.append("# 🔍 Codebase Audit Report\n")
    lines.append(f"**Repository:** {repo_url}  ")
    lines.append(f"**Branch:** {branch}  ")
    lines.append(f"**Date:** {timestamp}  ")
    lines.append(f"**Audited by:** Codebase Audit Agent System (Neural Ninjas)\n")
    lines.append("---\n")

    # Executive Summary
    lines.append("## Executive Summary\n")
    lines.append("| Severity | Count |")
    lines.append("|----------|-------|")
    lines.append(f"| 🔴 EXTREME | {counts['EXTREME']} |")
    lines.append(f"| 🟠 HIGH    | {counts['HIGH']} |")
    lines.append(f"| 🟡 MEDIUM  | {counts['MEDIUM']} |")
    lines.append(f"| 🔵 LOW     | {counts['LOW']} |")
    lines.append(f"| **Total**  | **{total}** |")
    lines.append("")
    lines.append(f"**Risk Score:** {risk_score}/100\n")

    # Top 3 Critical Findings
    if sorted_findings:
        top_3 = sorted_findings[:3]
        lines.append("### Top Critical Findings\n")
        for i, f in enumerate(top_3, 1):
            emoji = get_severity_emoji(f.get("severity", "LOW"))
            lines.append(f"> **{i}. {emoji} {f.get('title', 'Unknown')}**  ")
            lines.append(f"> {f.get('what_is_it', '')}  ")
            lines.append(f"> 📍 `{f.get('where_it_is', {}).get('file_path', 'unknown')}`\n")
        lines.append("")

    lines.append("---\n")

    # Findings by Severity
    lines.append("## Findings by Severity\n")

    severity_order = ["EXTREME", "HIGH", "MEDIUM", "LOW"]
    finding_counter = 0

    for severity in severity_order:
        severity_findings = [f for f in sorted_findings if f.get("severity") == severity]
        if not severity_findings:
            continue

        emoji = get_severity_emoji(severity)
        prefix_map = {"EXTREME": "E", "HIGH": "H", "MEDIUM": "M", "LOW": "L"}
        prefix = prefix_map[severity]

        lines.append(f"### {emoji} {severity} SEVERITY ({len(severity_findings)})\n")

        for idx, f in enumerate(severity_findings, 1):
            finding_counter += 1
            finding_id = f"[{prefix}-{idx:03d}]"
            where = f.get("where_it_is", {})
            file_path = where.get("file_path", "unknown")
            line_start = where.get("line_start", 0)
            line_end = where.get("line_end", 0)

            lines.append(f"#### {finding_id} {f.get('title', 'Unknown Issue')}\n")
            lines.append("| Field | Detail |")
            lines.append("|-------|--------|")
            lines.append(f"| **Bug Type** | {f.get('bug_type', 'Unknown')} |")
            lines.append(f"| **What is it** | {f.get('what_is_it', '')} |")
            lines.append(f"| **Why it occurs** | {f.get('why_it_occurs', '')} |")
            lines.append(f"| **How it occurred** | {f.get('how_it_occurred', '')} |")
            lines.append(f"| **Where** | `{file_path}` · Lines {line_start}–{line_end} |")
            lines.append(f"| **Score** | {f.get('score', 0)}/100 |")
            lines.append(f"| **Detected by** | {', '.join(f.get('detected_by', [f.get('agent', 'unknown')]))} |")
            lines.append("")

            # Affected code
            affected_code = f.get("affected_code", "")
            if affected_code:
                lines.append("**Affected Code:**")
                lines.append(f"```")
                lines.append(affected_code)
                lines.append("```\n")

            # Recommended fix
            fix = f.get("recommended_fix", "")
            if fix:
                lines.append(f"**Recommended Fix:** {fix}\n")

            # References
            refs = f.get("references", [])
            if refs:
                lines.append(f"**References:** {', '.join(refs)}\n")

            lines.append("---\n")

    # Findings by Agent
    lines.append("## Findings by Agent\n")
    agent_counts: dict[str, dict[str, int]] = {}
    for f in findings:
        agent = f.get("agent", "unknown")
        sev = f.get("severity", "LOW")
        if agent not in agent_counts:
            agent_counts[agent] = {"EXTREME": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "total": 0}
        agent_counts[agent][sev] += 1
        agent_counts[agent]["total"] += 1

    if agent_counts:
        lines.append("| Agent | 🔴 EXTREME | 🟠 HIGH | 🟡 MEDIUM | 🔵 LOW | Total |")
        lines.append("|-------|-----------|---------|----------|--------|-------|")
        for agent, ac in sorted(agent_counts.items()):
            lines.append(
                f"| {agent.capitalize()} | {ac['EXTREME']} | {ac['HIGH']} | "
                f"{ac['MEDIUM']} | {ac['LOW']} | **{ac['total']}** |"
            )
        lines.append("")
    else:
        lines.append("*No agents reported findings.*\n")

    lines.append("---\n")

    # File Scan Coverage
    lines.append("## Appendix: Scan Summary\n")
    unique_files = set()
    for f in findings:
        where = f.get("where_it_is", {})
        fp = where.get("file_path", "")
        if fp:
            unique_files.add(fp)

    lines.append(f"- **Total findings:** {total}")
    lines.append(f"- **Unique files with findings:** {len(unique_files)}")
    lines.append(f"- **Risk score:** {risk_score}/100")
    lines.append("")

    if unique_files:
        lines.append("**Files with findings:**")
        for fp in sorted(unique_files):
            file_findings = [f for f in findings if f.get("where_it_is", {}).get("file_path") == fp]
            lines.append(f"- `{fp}` ({len(file_findings)} findings)")
        lines.append("")

    # Footer
    lines.append("---\n")
    lines.append("*Report generated by Codebase Audit Agent System — Neural Ninjas*")

    return "\n".join(lines)
