"""
Abstract base class for all specialist audit agents.
Provides file reading, chunking, LLM integration, and structured response parsing.
"""

import json
import os
import time
import asyncio
import logging
from abc import ABC, abstractmethod

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from backend.api.models import Finding, FileLocation
from backend.utils.chunker import chunk_file

logger = logging.getLogger(__name__)

# Maximum retries per LLM call
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 2  # seconds
DEFAULT_RATE_LIMIT_RPM = 20
DEFAULT_MAX_CHUNKS_PER_FILE = 2


def _read_int_env(var_name: str, default: int, min_value: int = 1) -> int:
    """Read an integer env var safely with bounds and fallback."""
    raw = os.environ.get(var_name)
    if raw is None:
        return default

    try:
        parsed = int(raw)
        if parsed < min_value:
            raise ValueError()
        return parsed
    except ValueError:
        logger.warning(
            f"Invalid {var_name}={raw!r}; using default {default}."
        )
        return default


class AsyncRateLimiter:
    """Simple async rate limiter that enforces a global minimum interval."""

    def __init__(self, requests_per_minute: int):
        self._interval_seconds = 60.0 / max(requests_per_minute, 1)
        self._next_allowed_at = 0.0
        self._lock = asyncio.Lock()

    async def wait_for_slot(self) -> None:
        async with self._lock:
            now = time.monotonic()
            wait_time = self._next_allowed_at - now
            if wait_time > 0:
                await asyncio.sleep(wait_time)
            self._next_allowed_at = time.monotonic() + self._interval_seconds


_RATE_LIMITERS: dict[int, AsyncRateLimiter] = {}


def _get_rate_limiter(requests_per_minute: int) -> AsyncRateLimiter:
    limiter = _RATE_LIMITERS.get(requests_per_minute)
    if limiter is None:
        limiter = AsyncRateLimiter(requests_per_minute)
        _RATE_LIMITERS[requests_per_minute] = limiter
    return limiter


class BaseAuditAgent(ABC):
    """
    Abstract base class for specialist audit agents.

    Each subclass must define:
    - agent_name: str — identifier (e.g., "security")
    - system_prompt: str — specialized prompt for the agent's domain

    The base class provides:
    - File reading with chunking
    - LLM call wrapper with retry logic
    - Structured JSON parsing into Finding objects
    """

    agent_name: str = "base"
    system_prompt: str = ""

    def __init__(
        self,
        model_name: str = "gpt-5.4-mini",
        temperature: float = 0.1,
        rate_limit_rpm: int | None = None,
        max_chunks_per_file: int | None = None,
    ):
        """
        Initialize the agent with an LLM instance.

        Args:
            model_name: OpenAI model to use
            temperature: LLM temperature (lower = more deterministic)
        """
        self.llm = ChatOpenAI(
            model=model_name,
            temperature=temperature,
        )
        self.rate_limit_rpm = (
            rate_limit_rpm
            if rate_limit_rpm is not None
            else _read_int_env("OPENAI_RATE_LIMIT_RPM", DEFAULT_RATE_LIMIT_RPM, min_value=1)
        )
        self.max_chunks_per_file = (
            max_chunks_per_file
            if max_chunks_per_file is not None
            else _read_int_env("MAX_CHUNKS_PER_FILE", DEFAULT_MAX_CHUNKS_PER_FILE, min_value=1)
        )
        self.rate_limiter = _get_rate_limiter(self.rate_limit_rpm)

    async def analyze_files(self, file_paths: list[str], repo_path: str) -> list[Finding]:
        """
        Main entry point: analyze a list of files and return findings.

        Args:
            file_paths: List of relative file paths to analyze
            repo_path: Absolute path to the repository root

        Returns:
            List of Finding objects detected by this agent
        """
        all_findings: list[Finding] = []

        for rel_path in file_paths:
            import os
            abs_path = os.path.join(repo_path, rel_path)

            try:
                file_findings = await self._analyze_single_file(abs_path, rel_path)
                all_findings.extend(file_findings)
            except Exception as e:
                logger.error(f"[{self.agent_name}] Error analyzing {rel_path}: {e}")
                continue

        logger.info(f"[{self.agent_name}] Analyzed {len(file_paths)} files, found {len(all_findings)} issues")
        return all_findings

    async def _analyze_single_file(self, abs_path: str, rel_path: str) -> list[Finding]:
        """
        Analyze a single file by chunking it and sending each chunk to the LLM.

        Args:
            abs_path: Absolute path to the file
            rel_path: Relative path from repo root (for reporting)

        Returns:
            List of findings for this file
        """
        chunks = chunk_file(abs_path, max_tokens=3000, overlap_tokens=200)
        if not chunks:
            return []

        if len(chunks) > self.max_chunks_per_file:
            logger.info(
                f"[{self.agent_name}] Limiting {rel_path} from {len(chunks)} chunks "
                f"to {self.max_chunks_per_file} to reduce token usage"
            )
            chunks = chunks[:self.max_chunks_per_file]

        file_findings: list[Finding] = []

        for chunk in chunks:
            chunk_info = (
                f"(chunk {chunk['chunk_index'] + 1}/{chunk['total_chunks']}, "
                f"lines {chunk['start_line']}–{chunk['end_line']})"
                if chunk["total_chunks"] > 1 else ""
            )

            user_prompt = self._build_user_prompt(
                file_path=rel_path,
                code_content=chunk["content"],
                start_line=chunk["start_line"],
                end_line=chunk["end_line"],
                chunk_info=chunk_info,
            )

            try:
                response = await self._call_llm(self.system_prompt, user_prompt)
                findings = self._parse_findings(response, rel_path, chunk["start_line"])
                file_findings.extend(findings)
            except Exception as e:
                logger.warning(
                    f"[{self.agent_name}] LLM call failed for {rel_path} {chunk_info}: {e}"
                )
                continue

        return file_findings

    def _build_user_prompt(
        self,
        file_path: str,
        code_content: str,
        start_line: int,
        end_line: int,
        chunk_info: str = "",
    ) -> str:
        """Build the user prompt for the LLM with file context."""
        return f"""Analyze the following code file for bugs, vulnerabilities, and issues in your domain of expertise.

**File:** `{file_path}` {chunk_info}
**Lines:** {start_line}–{end_line}

```
{code_content}
```

For each issue found, respond with a JSON array of objects. Each object MUST have these exact fields:
- "severity": one of "EXTREME", "HIGH", "MEDIUM", "LOW"
- "title": short descriptive title (e.g., "SQL Injection in user_query()")
- "bug_type": category (e.g., "Injection", "Memory Leak", "CORS Misconfiguration")
- "what_is_it": plain-English description of the bug
- "why_it_occurs": root cause explanation
- "how_it_occurred": what code pattern caused it
- "line_start": starting line number (absolute, based on the line numbers shown)
- "line_end": ending line number
- "affected_code": the specific code snippet showing the issue
- "recommended_fix": detailed instructions on how to fix it
- "references": array of relevant CWE IDs, OWASP references, or documentation links
- "score": severity score from 0.0 to 100.0 based on exploitability (35%), impact (40%), and exposure (25%)

If NO issues are found, respond with an empty JSON array: []

IMPORTANT: Respond with ONLY the JSON array, no markdown formatting, no explanation outside the JSON."""

    async def _call_llm(self, system_prompt: str, user_prompt: str) -> str:
        """
        Call the LLM with retry logic.

        Args:
            system_prompt: The system message
            user_prompt: The user message with code to analyze

        Returns:
            Raw LLM response text

        Raises:
            Exception: If all retries are exhausted
        """
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]

        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                await self.rate_limiter.wait_for_slot()
                response = await self.llm.ainvoke(messages)
                return response.content
            except Exception as e:
                last_error = e
                wait_time = RETRY_BACKOFF_BASE ** (attempt + 1)
                logger.warning(
                    f"[{self.agent_name}] LLM call attempt {attempt + 1}/{MAX_RETRIES} failed: {e}. "
                    f"Retrying in {wait_time}s..."
                )
                await asyncio.sleep(wait_time)

        raise Exception(f"LLM call failed after {MAX_RETRIES} retries: {last_error}")

    def _parse_findings(self, response: str, file_path: str, chunk_start_line: int) -> list[Finding]:
        """
        Parse the LLM response JSON into Finding objects.

        Args:
            response: Raw LLM response text (should be a JSON array)
            file_path: Relative file path for the finding location
            chunk_start_line: Starting line of the chunk (for line number adjustment)

        Returns:
            List of validated Finding objects
        """
        # Clean up response — robustly extract JSON array
        cleaned = response.strip()
        start_idx = cleaned.find('[')
        end_idx = cleaned.rfind(']')
        
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            cleaned = cleaned[start_idx:end_idx+1]
        else:
            # Fallback if the LLM returned a single object instead of an array
            start_idx = cleaned.find('{')
            end_idx = cleaned.rfind('}')
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                cleaned = "[" + cleaned[start_idx:end_idx+1] + "]"
            else:
                cleaned = "[]"

        try:
            raw_findings = json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.warning(f"[{self.agent_name}] Failed to parse LLM response as JSON: {e}")
            logger.debug(f"[{self.agent_name}] Raw response: {response[:500]}")
            return []

        if not isinstance(raw_findings, list):
            logger.warning(f"[{self.agent_name}] LLM response is not a JSON array")
            return []

        findings: list[Finding] = []
        for raw in raw_findings:
            try:
                finding = Finding(
                    agent=self.agent_name,
                    severity=raw.get("severity", "LOW"),
                    title=raw.get("title", "Unknown Issue"),
                    bug_type=raw.get("bug_type", "Unknown"),
                    what_is_it=raw.get("what_is_it", ""),
                    why_it_occurs=raw.get("why_it_occurs", ""),
                    how_it_occurred=raw.get("how_it_occurred", ""),
                    where_it_is=FileLocation(
                        file_path=file_path,
                        line_start=raw.get("line_start", chunk_start_line),
                        line_end=raw.get("line_end", chunk_start_line),
                    ),
                    affected_code=raw.get("affected_code", ""),
                    recommended_fix=raw.get("recommended_fix", ""),
                    references=raw.get("references", []),
                    score=float(raw.get("score", 0.0)),
                    detected_by=[self.agent_name],
                )
                findings.append(finding)
            except Exception as e:
                logger.warning(f"[{self.agent_name}] Failed to parse finding: {e}")
                continue

        return findings
