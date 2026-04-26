"""
Aggregator Agent — deduplicates, cross-references, and scores findings
from all specialist agents.
"""

import logging
from collections import defaultdict

from backend.api.models import Finding, FileLocation
from backend.utils.severity import score_to_severity, calculate_severity_score

logger = logging.getLogger(__name__)


class AggregatorAgent:
    """
    Post-processing agent that runs after all specialists complete.
    Deduplicates findings, cross-references related issues, and applies
    the weighted severity scoring rubric.
    """

    def aggregate(self, all_findings: list[dict]) -> list[dict]:
        """
        Main entry: deduplicate, cross-reference, and re-score all findings.

        Args:
            all_findings: Raw findings from all agents (as dicts)

        Returns:
            Deduplicated and scored findings list
        """
        if not all_findings:
            return []

        # Step 1: Deduplicate
        deduped = self._deduplicate(all_findings)
        logger.info(f"Aggregator: {len(all_findings)} → {len(deduped)} after dedup")

        # Step 2: Cross-reference related findings
        cross_referenced = self._cross_reference(deduped)

        # Step 3: Re-score with weighted rubric
        scored = self._apply_scoring(cross_referenced)

        # Sort by score descending
        scored.sort(key=lambda f: -f.get("score", 0))

        logger.info(f"Aggregator: final {len(scored)} findings")
        return scored

    def _deduplicate(self, findings: list[dict]) -> list[dict]:
        """
        Merge findings that point to the same file + approximate line range + same bug type.
        Credits all agents that detected the issue.
        """
        # Group by (file_path, bug_type, approximate_line_range)
        groups: dict[str, list[dict]] = defaultdict(list)

        for f in findings:
            where = f.get("where_it_is", {})
            file_path = where.get("file_path", "unknown")
            bug_type = f.get("bug_type", "unknown").lower().strip()
            line_start = where.get("line_start", 0)
            # Bucket lines into ranges of 10 for fuzzy matching
            line_bucket = line_start // 10

            key = f"{file_path}::{bug_type}::{line_bucket}"
            groups[key].append(f)

        deduped = []
        for key, group in groups.items():
            if len(group) == 1:
                deduped.append(group[0])
            else:
                # Merge: keep the finding with the highest score, combine detected_by
                best = max(group, key=lambda f: f.get("score", 0))
                all_agents = set()
                for f in group:
                    all_agents.update(f.get("detected_by", [f.get("agent", "unknown")]))
                best["detected_by"] = list(all_agents)
                deduped.append(best)

        return deduped

    def _cross_reference(self, findings: list[dict]) -> list[dict]:
        """
        Chain related findings across agents.
        E.g., unsanitized input (frontend) flowing into raw SQL (database)
        gets severity bumped.
        """
        # Build a map of files with issues
        file_issues: dict[str, list[dict]] = defaultdict(list)
        for f in findings:
            fp = f.get("where_it_is", {}).get("file_path", "")
            if fp:
                file_issues[fp].append(f)

        # Look for cross-agent chains
        injection_keywords = {"injection", "sql injection", "xss", "command injection", "unsanitized"}
        input_keywords = {"input validation", "missing validation", "unsanitized", "unescaped"}

        for f in findings:
            bug_type_lower = f.get("bug_type", "").lower()
            title_lower = f.get("title", "").lower()
            combined = bug_type_lower + " " + title_lower

            # If this is an injection finding, check if there's a related input validation finding
            if any(kw in combined for kw in injection_keywords):
                fp = f.get("where_it_is", {}).get("file_path", "")
                related = file_issues.get(fp, [])
                for other in related:
                    if other is f:
                        continue
                    other_combined = other.get("bug_type", "").lower() + " " + other.get("title", "").lower()
                    if any(kw in other_combined for kw in input_keywords):
                        # Cross-agent chain found — bump severity
                        f["score"] = min(f.get("score", 0) + 15, 100)
                        agents = set(f.get("detected_by", []))
                        agents.update(other.get("detected_by", []))
                        f["detected_by"] = list(agents)
                        f["title"] = f.get("title", "") + " [Cross-Agent Chain]"
                        break

        return findings

    def _apply_scoring(self, findings: list[dict]) -> list[dict]:
        """Re-classify severity based on the final score."""
        for f in findings:
            score = f.get("score", 0)
            f["severity"] = score_to_severity(score)
        return findings
