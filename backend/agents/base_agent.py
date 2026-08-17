"""
Abstract base class for all specialist audit agents.
Provides file reading, chunking, LLM integration, and structured response parsing.
"""

import os
import asyncio
import logging
from abc import ABC

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, Field

from backend.api.models import Finding, FileLocation
from backend.utils.chunker import chunk_file
from backend.utils.cache import FileCache
from backend.utils.rag_manager import RAGContextManager
from backend.utils.file_router import is_crucial_or_sensitive_file

logger = logging.getLogger(__name__)

# Maximum retries per LLM call
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 2  # seconds
DEFAULT_CONCURRENCY = 10
DEFAULT_MAX_CHUNKS_PER_FILE = 2
DEFAULT_MAX_TOKENS_PER_CHUNK = 100000  # Updated from 3000 for modern LLMs


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


# Define a Pydantic model for structured output
class FindingOutput(BaseModel):
    severity: str = Field(description="one of 'EXTREME', 'HIGH', 'MEDIUM', 'LOW'")
    title: str = Field(description="short descriptive title (e.g., 'SQL Injection in user_query()')")
    bug_type: str = Field(description="category (e.g., 'Injection', 'Memory Leak', 'CORS Misconfiguration')")
    what_is_it: str = Field(description="concise, plain-English description of the issue")
    why_it_occurs: str = Field(description="root cause explanation")
    how_it_occurred: str = Field(description="exact code pattern or execution flow that caused it")
    line_start: int = Field(description="starting line number")
    line_end: int = Field(description="ending line number")
    affected_code: str = Field(description="the exact code snippet showing the issue")
    recommended_fix: str = Field(description="concrete, drop-in replacement code or exact steps to fix the issue")
    references: list[str] = Field(description="array of relevant CWE IDs, OWASP references, or documentation links")
    score: float = Field(description="severity score from 0.0 to 100.0")

class AgentFindingsOutput(BaseModel):
    findings: list[FindingOutput] = Field(description="List of detected findings. Empty list if none found.")


class BaseAuditAgent(ABC):
    """
    Abstract base class for specialist audit agents.

    Each subclass must define:
    - agent_name: str — identifier (e.g., "security")
    - system_prompt: str — specialized prompt for the agent's domain
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
        # Instead of strict sequential intervals, we use a concurrency semaphore
        # which lets us burst in parallel up to max_concurrency.
        concurrency = _read_int_env("MAX_CONCURRENCY", DEFAULT_CONCURRENCY, min_value=1)
        self.semaphore = asyncio.Semaphore(concurrency)

        # Initialize LLM with structured output mapping to our Pydantic model
        self.llm = ChatOpenAI(
            model=model_name,
            temperature=temperature,
        ).with_structured_output(AgentFindingsOutput)

        self.max_chunks_per_file = (
            max_chunks_per_file
            if max_chunks_per_file is not None
            else _read_int_env("MAX_CHUNKS_PER_FILE", DEFAULT_MAX_CHUNKS_PER_FILE, min_value=1)
        )

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
        cache = FileCache(repo_path)

        # Filter out any sensitive/crucial files (defense-in-depth)
        safe_file_paths = []
        for p in file_paths:
            if is_crucial_or_sensitive_file(p):
                logger.warning(f"[{self.agent_name}] Skipping sensitive/crucial file {p}")
            else:
                safe_file_paths.append(p)

        file_paths = safe_file_paths

        # Load the RAG Context Manager locally for this agent
        rag_manager = RAGContextManager(repo_path)
        try:
            rag_manager.build_or_load_index({}) # Just load, don't build
        except Exception:
            pass

        # Gather concurrent tasks for all files
        tasks = []
        for rel_path in file_paths:
            abs_path = os.path.join(repo_path, rel_path)
            if is_crucial_or_sensitive_file(abs_path):
                continue

            # Check cache first
            cached = cache.get_cached_findings(self.agent_name, abs_path, rel_path)
            if cached is not None:
                all_findings.extend(cached)
                continue

            tasks.append(self._analyze_single_file_with_cache(cache, rag_manager, abs_path, rel_path))

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"[{self.agent_name}] Error analyzing file: {result}")
                else:
                    all_findings.extend(result)

        logger.info(f"[{self.agent_name}] Analyzed {len(file_paths)} files, found {len(all_findings)} issues")
        return all_findings

    async def _analyze_single_file_with_cache(self, cache: FileCache, rag_manager: RAGContextManager, abs_path: str, rel_path: str) -> list[Finding]:
        """Wraps single file analysis to save results to cache."""
        if is_crucial_or_sensitive_file(rel_path) or is_crucial_or_sensitive_file(abs_path):
            return []
        findings = await self._analyze_single_file(rag_manager, abs_path, rel_path)
        cache.set_cached_findings(self.agent_name, abs_path, rel_path, findings)
        return findings

    async def _analyze_single_file(self, rag_manager: RAGContextManager, abs_path: str, rel_path: str) -> list[Finding]:
        """
        Analyze a single file. Modern LLMs get the full file up to 100k tokens.

        Args:
            abs_path: Absolute path to the file
            rel_path: Relative path from repo root (for reporting)

        Returns:
            List of findings for this file
        """
        if is_crucial_or_sensitive_file(rel_path) or is_crucial_or_sensitive_file(abs_path):
            return []
        # Read with high chunk limit to preserve full context for modern LLMs
        chunks = chunk_file(
            abs_path,
            max_tokens=DEFAULT_MAX_TOKENS_PER_CHUNK,
            overlap_tokens=500
        )
        if not chunks:
            return []

        if len(chunks) > self.max_chunks_per_file:
            logger.info(
                f"[{self.agent_name}] Limiting {rel_path} from {len(chunks)} chunks "
                f"to {self.max_chunks_per_file} to reduce token usage"
            )
            chunks = chunks[:self.max_chunks_per_file]

        file_findings: list[Finding] = []

        # We can concurrently process chunks if a file is massive
        tasks = []
        for chunk in chunks:
            chunk_info = (
                f"(chunk {chunk['chunk_index'] + 1}/{chunk['total_chunks']}, "
                f"lines {chunk['start_line']}–{chunk['end_line']})"
                if chunk["total_chunks"] > 1 else ""
            )

            # Query RAG for cross-file context
            query = f"Provide definitions, types, imports, and context for {rel_path}:\n{chunk['content'][:500]}"
            rag_context = rag_manager.retrieve(query, top_k=3)

            user_prompt = self._build_user_prompt(
                file_path=rel_path,
                code_content=chunk["content"],
                start_line=chunk["start_line"],
                end_line=chunk["end_line"],
                chunk_info=chunk_info,
                rag_context=rag_context,
            )

            tasks.append(self._call_llm_with_retry(user_prompt, rel_path, chunk_info, chunk["start_line"]))

        chunk_results = await asyncio.gather(*tasks, return_exceptions=True)
        for res in chunk_results:
            if isinstance(res, Exception):
                logger.warning(f"[{self.agent_name}] Failed processing chunk for {rel_path}: {res}")
            else:
                file_findings.extend(res)

        return file_findings

    def _build_user_prompt(
        self,
        file_path: str,
        code_content: str,
        start_line: int,
        end_line: int,
        chunk_info: str = "",
        rag_context: str = "",
    ) -> str:
        """Build the user prompt for the LLM with file context."""
        return f"""Analyze the following code file for high-confidence bugs, vulnerabilities, and critical issues in your domain of expertise.
DO NOT report theoretical risks or subjective best-practice deviations. Only report issues that are demonstrably exploitable or fundamentally broken.

{rag_context}

**File:** `{file_path}` {chunk_info}
**Lines:** {start_line}–{end_line}

```
{code_content}
```

Identify any critical issues and return them structured. If NO issues are found, return an empty findings list."""

    async def _call_llm_with_retry(self, user_prompt: str, rel_path: str, chunk_info: str, chunk_start_line: int) -> list[Finding]:
        """Call LLM via structured output with semaphore and retry logic."""
        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=user_prompt),
        ]

        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                async with self.semaphore:
                    # `ainvoke` with `.with_structured_output` returns the parsed Pydantic model directly
                    structured_res: AgentFindingsOutput = await self.llm.ainvoke(messages)

                findings = []
                for f in structured_res.findings:
                    findings.append(
                        Finding(
                            agent=self.agent_name,
                            severity=f.severity,
                            title=f.title,
                            bug_type=f.bug_type,
                            what_is_it=f.what_is_it,
                            why_it_occurs=f.why_it_occurs,
                            how_it_occurred=f.how_it_occurred,
                            where_it_is=FileLocation(
                                file_path=rel_path,
                                line_start=f.line_start if f.line_start > 0 else chunk_start_line,
                                line_end=f.line_end if f.line_end > 0 else chunk_start_line,
                            ),
                            affected_code=f.affected_code,
                            recommended_fix=f.recommended_fix,
                            references=f.references,
                            score=f.score,
                            detected_by=[self.agent_name],
                        )
                    )
                return findings
            except Exception as e:
                last_error = e
                wait_time = RETRY_BACKOFF_BASE ** (attempt + 1)
                logger.warning(
                    f"[{self.agent_name}] LLM call attempt {attempt + 1}/{MAX_RETRIES} failed for {rel_path}: {e}. "
                    f"Retrying in {wait_time}s..."
                )
                await asyncio.sleep(wait_time)

        raise Exception(f"LLM call failed after {MAX_RETRIES} retries: {last_error}")
