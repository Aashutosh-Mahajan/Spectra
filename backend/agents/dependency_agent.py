"""
Dependency Agent — package CVE, version, and supply chain auditor.
Integrates with OSV.dev API for vulnerability lookup.
"""

import os
import json
import logging

import httpx

from backend.agents.base_agent import BaseAuditAgent
from backend.api.models import Finding, FileLocation
from backend.utils.file_router import is_crucial_or_sensitive_file

logger = logging.getLogger(__name__)
OSV_API_BASE = "https://api.osv.dev/v1"


class DependencyAgent(BaseAuditAgent):
    agent_name = "dependency"

    system_prompt = """You are an elite dependency and supply chain security auditor. Your objective is to analyze dependency manifests (package.json, requirements.txt, go.mod, pom.xml, etc.) to identify high-confidence security risks, supply chain vulnerabilities, and severe hygiene issues.

## Core Mandates for High-Quality Output:
- **Zero False Positives**: Focus strictly on verifiable risks. Do NOT flag theoretical issues.
- **Precision**: Cite exact package names, versions, and line numbers. Explain the supply chain risk clearly and concisely.
- **Actionable Fixes**: Recommend exact safe versions or dependency management strategies. Avoid abstract advice.

## Priority Focus Areas:
1. **Known CVEs & Compromised Packages**: Identification of packages with known vulnerabilities or malicious typosquatting.
2. **Version Pinning & Lockfiles**: Unpinned versions (`*`, `latest`), missing lockfiles, conflicting version requirements.
3. **Package Health**: Unmaintained/deprecated packages, abandoned projects used in critical paths.
4. **License Compliance**: GPL/copyleft licenses in proprietary project manifests.
5. **Dependency Hygiene**: Developer dependencies (e.g., testing frameworks) included in production builds.

## Scoring Guidelines:
- **EXTREME (90-100)**: Known malicious packages, critical CVEs (RCE) in direct dependencies.
- **HIGH (70-89)**: High-severity CVEs, unpinned core dependencies, missing lockfiles.
- **MEDIUM (40-69)**: Medium CVEs, deprecated packages, copyleft license violations.
- **LOW (0-39)**: Minor hygiene issues, dev-deps in prod (non-exploitable).

## Rules for Analysis:
- Be specific with package names and version constraints.
- Always provide the exact updated version string or command for the recommended fix."""

    async def analyze_files(self, file_paths: list[str], repo_path: str) -> list[Finding]:
        llm_findings = await super().analyze_files(file_paths, repo_path)
        osv_findings = await self._check_osv(file_paths, repo_path)
        return llm_findings + osv_findings

    async def _check_osv(self, file_paths: list[str], repo_path: str) -> list[Finding]:
        findings = []
        osv_base = os.environ.get("OSV_API_BASE", OSV_API_BASE)
        for rel_path in file_paths:
            if is_crucial_or_sensitive_file(rel_path):
                continue
            abs_path = os.path.join(repo_path, rel_path)
            if is_crucial_or_sensitive_file(abs_path):
                continue
            for name, ver, eco in self._extract_packages(abs_path, rel_path):
                if not ver or ver in ("*", "latest"):
                    continue
                try:
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        resp = await client.post(f"{osv_base}/query", json={"version": ver, "package": {"name": name, "ecosystem": eco}})
                        if resp.status_code == 200:
                            for vuln in resp.json().get("vulns", []):
                                findings.append(Finding(
                                    agent=self.agent_name, severity="HIGH",
                                    title=f"CVE in {name}@{ver}: {vuln.get('summary', 'Known vulnerability')[:80]}",
                                    bug_type="Known Vulnerability (CVE)",
                                    what_is_it=vuln.get("summary", "Known vulnerability")[:200],
                                    why_it_occurs=f"Package {name}@{ver} has a known vulnerability.",
                                    how_it_occurred=f"Dependency listed in {rel_path}.",
                                    where_it_is=FileLocation(file_path=rel_path, line_start=1, line_end=1),
                                    affected_code=f"{name}=={ver}", recommended_fix=f"Upgrade {name} to a patched version.",
                                    references=[vuln.get("id", "")], score=75.0, detected_by=[self.agent_name],
                                ))
                except Exception as e:
                    logger.debug(f"OSV lookup failed for {name}@{ver}: {e}")
        return findings

    def _extract_packages(self, abs_path, rel_path):
        packages = []
        if is_crucial_or_sensitive_file(rel_path) or is_crucial_or_sensitive_file(abs_path):
            return packages
        filename = os.path.basename(rel_path).lower()
        try:
            content = open(abs_path, "r", encoding="utf-8", errors="replace").read()
        except (IOError, OSError):
            return packages
        if "requirements" in filename:
            for line in content.splitlines():
                line = line.strip()
                if not line or line.startswith("#") or line.startswith("-"):
                    continue
                for sep in ["==", ">=", "~="]:
                    if sep in line:
                        parts = line.split(sep, 1)
                        packages.append((parts[0].strip().split("[")[0], parts[1].strip().split(",")[0].split(";")[0].strip(), "PyPI"))
                        break
        elif filename == "package.json":
            try:
                data = json.loads(content)
                for dep_type in ["dependencies", "devDependencies"]:
                    for n, v in data.get(dep_type, {}).items():
                        packages.append((n, v.lstrip("^~>=<!"), "npm"))
            except json.JSONDecodeError:
                pass
        return packages
