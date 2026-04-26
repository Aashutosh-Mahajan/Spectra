"""
Token-safe file chunker.
Splits large files into overlapping chunks that respect line boundaries
and stay within the LLM context window token budget.
"""

import logging
from pathlib import Path

import tiktoken

logger = logging.getLogger(__name__)

# Default encoding for GPT models
DEFAULT_ENCODING = "cl100k_base"


def _get_encoder(encoding_name: str = DEFAULT_ENCODING) -> tiktoken.Encoding:
    """Get a tiktoken encoder, cached after first call."""
    return tiktoken.get_encoding(encoding_name)


def count_tokens(text: str, encoding_name: str = DEFAULT_ENCODING) -> int:
    """Count the number of tokens in a text string."""
    encoder = _get_encoder(encoding_name)
    return len(encoder.encode(text))


def chunk_file(
    file_path: str,
    max_tokens: int = 3000,
    overlap_tokens: int = 200,
    encoding_name: str = DEFAULT_ENCODING,
) -> list[dict]:
    """
    Read a file and split it into token-safe chunks with overlap.

    Each chunk respects line boundaries (never cuts mid-line) and includes
    metadata about which lines it covers for accurate finding locations.

    Args:
        file_path: Path to the file to chunk
        max_tokens: Maximum tokens per chunk
        overlap_tokens: Number of overlap tokens between consecutive chunks
        encoding_name: Tiktoken encoding to use

    Returns:
        List of chunk dicts, each containing:
        - "content": str — the chunk text
        - "start_line": int — 1-indexed starting line number
        - "end_line": int — 1-indexed ending line number
        - "chunk_index": int — 0-indexed chunk number
        - "total_chunks": int — total number of chunks
    """
    try:
        content = Path(file_path).read_text(encoding="utf-8", errors="replace")
    except (IOError, OSError) as e:
        logger.warning(f"Could not read file {file_path}: {e}")
        return []

    if not content.strip():
        return []

    lines = content.splitlines(keepends=True)
    total_tokens = count_tokens(content, encoding_name)

    # If the file fits in a single chunk, return it directly
    if total_tokens <= max_tokens:
        return [{
            "content": content,
            "start_line": 1,
            "end_line": len(lines),
            "chunk_index": 0,
            "total_chunks": 1,
        }]

    # Split into chunks respecting line boundaries
    encoder = _get_encoder(encoding_name)
    chunks = []
    current_start_idx = 0  # Index into `lines` list

    while current_start_idx < len(lines):
        chunk_lines = []
        chunk_token_count = 0

        line_idx = current_start_idx
        while line_idx < len(lines):
            line = lines[line_idx]
            line_tokens = len(encoder.encode(line))

            # If adding this line would exceed the budget, stop
            # (unless we haven't added any lines yet — always include at least one)
            if chunk_token_count + line_tokens > max_tokens and chunk_lines:
                break

            chunk_lines.append(line)
            chunk_token_count += line_tokens
            line_idx += 1

        chunk_text = "".join(chunk_lines)
        chunks.append({
            "content": chunk_text,
            "start_line": current_start_idx + 1,  # 1-indexed
            "end_line": current_start_idx + len(chunk_lines),  # 1-indexed
            "chunk_index": len(chunks),
            "total_chunks": -1,  # Will be set after all chunks are created
        })

        # Calculate overlap: move back by overlap_tokens worth of lines
        if line_idx < len(lines):
            overlap_line_count = 0
            overlap_token_count = 0
            for back_idx in range(len(chunk_lines) - 1, 0, -1):
                line = chunk_lines[back_idx]
                line_tokens = len(encoder.encode(line))
                if overlap_token_count + line_tokens > overlap_tokens:
                    break
                overlap_token_count += line_tokens
                overlap_line_count += 1

            # Next chunk starts with overlap
            current_start_idx = current_start_idx + len(chunk_lines) - overlap_line_count
        else:
            break

    # Set total_chunks on all chunks
    for chunk in chunks:
        chunk["total_chunks"] = len(chunks)

    logger.info(
        f"Chunked {file_path}: {total_tokens} tokens → {len(chunks)} chunks "
        f"(max {max_tokens} tokens/chunk, {overlap_tokens} overlap)"
    )

    return chunks


def read_file_content(file_path: str) -> str | None:
    """
    Read a file's content safely with UTF-8 encoding.

    Returns None if the file cannot be read.
    """
    try:
        return Path(file_path).read_text(encoding="utf-8", errors="replace")
    except (IOError, OSError) as e:
        logger.warning(f"Could not read file {file_path}: {e}")
        return None
