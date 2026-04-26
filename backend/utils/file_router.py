"""
File router — walks the cloned repository file tree and maps each file
to one or more specialist agent buckets based on extension and filename patterns.
"""

import os
import fnmatch
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# Agent → File Pattern Mapping
# ─────────────────────────────────────────────

# Extension-based routing
EXTENSION_MAP: dict[str, list[str]] = {
    "frontend": [
        ".jsx", ".tsx", ".vue", ".svelte", ".html",
        ".css", ".scss", ".less", ".sass",
    ],
    "backend": [
        ".py", ".java", ".go", ".rb", ".php", ".rs",
    ],
    "database": [
        ".sql", ".prisma",
    ],
    "devops": [
        ".tf", ".hcl",
    ],
}

# Filename-based routing (exact matches or patterns)
FILENAME_MAP: dict[str, list[str]] = {
    "dependency": [
        "package.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
        "requirements.txt", "requirements*.txt", "Pipfile", "Pipfile.lock",
        "pyproject.toml", "setup.py", "setup.cfg",
        "go.mod", "go.sum",
        "pom.xml", "build.gradle", "build.gradle.kts",
        "Gemfile", "Gemfile.lock",
        "Cargo.toml", "Cargo.lock",
        "composer.json", "composer.lock",
    ],
    "devops": [
        "Dockerfile", "Dockerfile.*",
        "docker-compose.yml", "docker-compose.yaml", "docker-compose*.yml",
        ".dockerignore",
        "Makefile",
        "Procfile",
        "Vagrantfile",
    ],
    "database": [
        "models.py", "schema.prisma",
    ],
}

# Directory-based routing
DIRECTORY_MAP: dict[str, list[str]] = {
    "devops": [
        ".github/workflows",
        ".gitlab-ci",
        "k8s", "kubernetes",
        ".circleci",
        "terraform",
        "ansible",
        "helm",
    ],
    "database": [
        "migrations",
        "alembic",
    ],
}

# Keyword-based routing (filename contains these keywords)
KEYWORD_MAP: dict[str, list[str]] = {
    "security": [
        "auth", "login", "token", "secret", "password", "passwd",
        "jwt", "crypto", "crypt", "oauth", "session", "permission",
        "credential", "apikey", "api_key",
    ],
}

# Files that could be either frontend or backend based on context
# .js and .ts are ambiguous — route to both frontend and backend
AMBIGUOUS_EXTENSIONS = {".js", ".ts"}

# Environment / config files always go to security
ENV_PATTERNS = [".env", ".env.*", "*.env", ".env.local", ".env.production"]

# Default exclusion patterns
DEFAULT_EXCLUDES = [
    "node_modules", ".git", "dist", "build", "__pycache__",
    ".venv", "venv", ".env", ".tox", ".pytest_cache",
    ".mypy_cache", "*.min.js", "*.min.css", "*.map",
    ".next", ".nuxt", "coverage", ".nyc_output",
]


def _should_exclude(path: str, exclude_patterns: list[str]) -> bool:
    """Check if a file path matches any exclusion pattern."""
    parts = Path(path).parts
    for pattern in exclude_patterns:
        # Check if any path component matches the pattern
        for part in parts:
            if fnmatch.fnmatch(part, pattern):
                return True
        # Also check the full path
        if fnmatch.fnmatch(path, pattern):
            return True
    return False


def _is_binary_file(file_path: str) -> bool:
    """Quick heuristic check if a file is binary (skip binary files)."""
    try:
        with open(file_path, "rb") as f:
            chunk = f.read(1024)
            # If there are null bytes, it's likely binary
            if b"\x00" in chunk:
                return True
    except (IOError, OSError):
        return True
    return False


def route_files(
    repo_path: str,
    exclude_patterns: list[str] | None = None,
) -> dict[str, list[str]]:
    """
    Walk the cloned repo's file tree and group every file into agent buckets.

    A single file can appear in multiple buckets (e.g., `auth_routes.py` → backend + security).

    Args:
        repo_path: Absolute path to the cloned repository root
        exclude_patterns: Glob patterns for files/dirs to skip

    Returns:
        Dictionary mapping agent names to lists of relative file paths.
        Keys: "frontend", "backend", "database", "security", "devops", "dependency"
    """
    if exclude_patterns is None:
        exclude_patterns = DEFAULT_EXCLUDES

    file_map: dict[str, list[str]] = {
        "frontend": [],
        "backend": [],
        "database": [],
        "security": [],
        "devops": [],
        "dependency": [],
    }

    total_files = 0
    skipped_files = 0

    for root, dirs, files in os.walk(repo_path):
        # Get relative directory path
        rel_dir = os.path.relpath(root, repo_path)
        if rel_dir == ".":
            rel_dir = ""

        # Filter out excluded directories in-place (prevents os.walk from descending)
        dirs[:] = [
            d for d in dirs
            if not _should_exclude(os.path.join(rel_dir, d) if rel_dir else d, exclude_patterns)
        ]

        for filename in files:
            abs_path = os.path.join(root, filename)
            rel_path = os.path.relpath(abs_path, repo_path).replace("\\", "/")

            # Skip excluded files
            if _should_exclude(rel_path, exclude_patterns):
                skipped_files += 1
                continue

            # Skip binary files
            if _is_binary_file(abs_path):
                skipped_files += 1
                continue

            total_files += 1
            ext = os.path.splitext(filename)[1].lower()
            filename_lower = filename.lower()
            matched_agents: set[str] = set()

            # 1. Extension-based routing
            for agent, extensions in EXTENSION_MAP.items():
                if ext in extensions:
                    matched_agents.add(agent)

            # 2. Ambiguous extensions (.js, .ts) → route to both frontend and backend
            if ext in AMBIGUOUS_EXTENSIONS:
                matched_agents.add("frontend")
                matched_agents.add("backend")

            # 3. Filename-based routing
            for agent, patterns in FILENAME_MAP.items():
                for pattern in patterns:
                    if fnmatch.fnmatch(filename, pattern) or fnmatch.fnmatch(filename_lower, pattern.lower()):
                        matched_agents.add(agent)
                        break

            # 4. Directory-based routing
            for agent, dir_patterns in DIRECTORY_MAP.items():
                for dir_pattern in dir_patterns:
                    if rel_dir.replace("\\", "/").startswith(dir_pattern) or \
                       f"/{dir_pattern}/" in f"/{rel_dir.replace(chr(92), '/')}/" or \
                       rel_dir.replace("\\", "/") == dir_pattern:
                        matched_agents.add(agent)
                        break

            # 5. Keyword-based routing (security keywords in filename)
            for agent, keywords in KEYWORD_MAP.items():
                for keyword in keywords:
                    if keyword in filename_lower:
                        matched_agents.add(agent)
                        break

            # 6. Environment file routing → security
            for env_pattern in ENV_PATTERNS:
                if fnmatch.fnmatch(filename, env_pattern) or fnmatch.fnmatch(filename_lower, env_pattern):
                    matched_agents.add("security")
                    break

            # 7. CI/CD YAML files in specific directories → devops
            if ext in (".yml", ".yaml"):
                if any(d in rel_dir.replace("\\", "/") for d in [".github", ".gitlab", ".circleci", "k8s"]):
                    matched_agents.add("devops")

            # 8. ORM-related files → database
            if ".orm." in filename_lower or "migration" in rel_dir.lower():
                matched_agents.add("database")

            # Add to matched agent buckets
            for agent in matched_agents:
                file_map[agent].append(rel_path)

    # Log summary
    total_routed = sum(len(files) for files in file_map.values())
    logger.info(
        f"File routing complete: {total_files} files scanned, "
        f"{skipped_files} skipped, {total_routed} agent assignments "
        f"({', '.join(f'{k}:{len(v)}' for k, v in file_map.items())})"
    )

    return file_map
