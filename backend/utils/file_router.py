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

# ─────────────────────────────────────────────
# Protected Excludes (Crucial & Sensitive Files)
# ─────────────────────────────────────────────
# These files and directories are ALWAYS excluded across all audit scans,
# routing, chunking, caching, and LLM analysis. They contain credentials,
# local/production secrets, private keys, certificates, cloud tokens,
# or internal tool state that must NEVER be exposed or audited.
PROTECTED_EXCLUDES: list[str] = [
    # 1. Environment files
    ".env",
    ".env.*",
    "*.env",
    "*.env.*",
    ".env*",
    ".envrc",
    ".envfile",
    "env.json",
    "env.yaml",
    "env.yml",

    # 2. Secret & Credential configuration files
    "secrets.json",
    "secrets.yaml",
    "secrets.yml",
    "secrets.toml",
    "secrets.ini",
    "secrets.xml",
    "secret.json",
    "secret.yaml",
    "secret.yml",
    "secret.toml",
    "secret.ini",
    "secret.xml",
    "credentials.json",
    "credentials.yaml",
    "credentials.yml",
    "credentials.toml",
    "credentials.ini",
    "credentials.xml",
    "credential.json",
    "credential.yaml",
    "credential.yml",
    "*credentials*.json",
    "*credentials*.yaml",
    "*credentials*.yml",
    "*service_account*.json",
    "*service-account*.json",
    "*serviceaccount*.json",
    "*firebase-adminsdk*.json",
    "google-services.json",
    "googleservice-info.plist",
    "client_secret*.json",
    "client_secrets*.json",
    "oauth-credentials.json",
    "local.settings.json",
    "appsettings.*.json",
    "master.key",
    "credentials.yml.enc",
    "auth.json",
    ".netrc",
    ".htpasswd",
    ".npmrc",
    ".pypirc",
    ".git-credentials",
    "terraform.tfvars",
    "terraform.tfvars.json",
    "*.tfvars",
    "*.tfvars.json",
    "terraform.tfstate*",
    "*.tfstate*",
    ".vault-token",
    "*.kdbx",
    "*.ovpn",

    # 3. Keys, Certificates & Keystores
    "*.pem",
    "*.key",
    "*.pkcs12",
    "*.pfx",
    "*.p12",
    "*.crt",
    "*.cer",
    "*.der",
    "*.keystore",
    "*.jks",
    "*.truststore",
    "*.ppk",
    "id_rsa",
    "id_rsa.*",
    "*.id_rsa",
    "*.id_rsa.*",
    "id_ecdsa",
    "id_ecdsa.*",
    "*.id_ecdsa",
    "*.id_ecdsa.*",
    "id_ed25519",
    "id_ed25519.*",
    "*.id_ed25519",
    "*.id_ed25519.*",
    "id_dsa",
    "id_dsa.*",
    "*.id_dsa",
    "*.id_dsa.*",

    # 4. History & Log files containing interactive secrets
    ".*_history",
    ".history",
    "*.history",
    ".bash_history",
    ".zsh_history",
    ".sh_history",
    ".psql_history",
    ".mysql_history",
    ".sqlite_history",

    # 5. Sensitive directories (Cloud / Tool / Auth config)
    ".spectra",
    ".spectra/*",
    ".aws",
    ".aws/*",
    "aws_credentials",
    "aws_config",
    ".kube",
    ".kube/*",
    "kubeconfig",
    ".kubeconfig",
    "*kubeconfig*",
    ".docker",
    ".docker/*",
    ".dockercfg",
    ".ssh",
    ".ssh/*",
    ".gnupg",
    ".gnupg/*",
    ".secrets",
    ".secrets/*",
]

# Default exclusion patterns (build artifacts, dependencies, caches, VC + protected)
DEFAULT_EXCLUDES: list[str] = [
    *PROTECTED_EXCLUDES,
    "node_modules",
    "node_modules/*",
    "vendor",
    "vendor/*",
    ".git",
    ".git/*",
    ".svn",
    ".svn/*",
    ".hg",
    ".hg/*",
    "dist",
    "dist/*",
    "build",
    "build/*",
    "out",
    "out/*",
    "target",
    "target/*",
    "__pycache__",
    "__pycache__/*",
    ".venv",
    ".venv/*",
    "venv",
    "venv/*",
    "env",
    "env/*",
    "virtualenv",
    "virtualenv/*",
    ".tox",
    ".tox/*",
    ".pytest_cache",
    ".pytest_cache/*",
    ".mypy_cache",
    ".mypy_cache/*",
    ".ruff_cache",
    ".ruff_cache/*",
    "*.min.js",
    "*.min.css",
    "*.map",
    ".next",
    ".next/*",
    ".nuxt",
    ".nuxt/*",
    ".turbo",
    ".turbo/*",
    "coverage",
    "coverage/*",
    ".nyc_output",
    ".nyc_output/*",
    ".idea",
    ".idea/*",
    ".vscode",
    ".vscode/*",
    ".ds_store",
    "thumbs.db",
]


def is_crucial_or_sensitive_file(path: str) -> bool:
    """
    Check whether a file path points to a crucial/sensitive file (e.g. .env,
    private key, credentials file, cloud token, cert, internal state).
    """
    if not path:
        return False
    normalized = path.replace("\\", "/").lower().strip("/")
    parts = Path(normalized).parts
    filename = parts[-1] if parts else normalized

    for pattern in PROTECTED_EXCLUDES:
        pattern_lower = pattern.replace("\\", "/").lower().strip("/")
        # Check against every part in the path
        for part in parts:
            if fnmatch.fnmatch(part, pattern_lower):
                return True
        # Check against filename directly
        if fnmatch.fnmatch(filename, pattern_lower):
            return True
        # Check against normalized full path
        if fnmatch.fnmatch(normalized, pattern_lower):
            return True
        # Check with leading wildcard if pattern is a file pattern
        if "/" not in pattern_lower and fnmatch.fnmatch(normalized, f"*/{pattern_lower}"):
            return True

    return False


def _should_exclude(path: str, exclude_patterns: list[str]) -> bool:
    """Check if a file path matches any exclusion pattern or is a protected sensitive file."""
    if not path:
        return False
    if is_crucial_or_sensitive_file(path):
        return True

    normalized_path = path.replace("\\", "/").lower().strip("/")
    parts = Path(normalized_path).parts
    filename = parts[-1] if parts else normalized_path

    for pattern in exclude_patterns:
        pattern = pattern.replace("\\", "/").lower().strip("/")
        # Check if any path component matches the pattern
        for part in parts:
            if fnmatch.fnmatch(part, pattern):
                return True
        # Check filename directly
        if fnmatch.fnmatch(filename, pattern):
            return True
        # Also check the full path
        if fnmatch.fnmatch(normalized_path, pattern):
            return True
        # Check with leading wildcard if pattern is a file pattern
        if "/" not in pattern and fnmatch.fnmatch(normalized_path, f"*/{pattern}"):
            return True
    return False


def _normalize_exclude_patterns(exclude_patterns: list[str] | None) -> list[str]:
    """Merge caller excludes with SPECTRA's protected local-state patterns."""
    if exclude_patterns is None:
        exclude_patterns = DEFAULT_EXCLUDES

    normalized = []
    seen = set()
    for pattern in [*exclude_patterns, *PROTECTED_EXCLUDES]:
        cleaned = pattern.strip()
        if cleaned and cleaned not in seen:
            normalized.append(cleaned)
            seen.add(cleaned)
    return normalized


def _matches_include_patterns(rel_path: str, filename: str, include_patterns: list[str]) -> bool:
    """Check whether a file should be included when include patterns are provided."""
    rel_path_lower = rel_path.lower()
    filename_lower = filename.lower()

    for pattern in include_patterns:
        normalized = pattern.strip()
        if not normalized:
            continue

        normalized_lower = normalized.lower()
        if fnmatch.fnmatch(rel_path_lower, normalized_lower):
            return True
        if fnmatch.fnmatch(filename_lower, normalized_lower):
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


def _is_backend_js(content: str) -> bool:
    """Heuristic to guess if a JS/TS file is backend (Node.js)."""
    if not content: return False
    # Common Node.js imports/globals
    backend_indicators = [
        "express(", "require('express')", "require('http')",
        "require('fs')", "require('path')", "mongoose", "sequelize",
        "process.env", "NestFactory"
    ]
    # Common Frontend imports/globals
    frontend_indicators = [
        "import React", "from 'react'", "document.getElement", 
        "window.", "vue", "svelte", "angular"
    ]
    
    b_score = sum(1 for ind in backend_indicators if ind in content)
    f_score = sum(1 for ind in frontend_indicators if ind in content)
    
    return b_score > f_score

def route_files(
    repo_path: str,
    exclude_patterns: list[str] | None = None,
    include_patterns: list[str] | None = None,
) -> dict[str, list[str]]:
    """
    Walk the cloned repo's file tree and group every file into agent buckets.

    A single file can appear in multiple buckets (e.g., `auth_routes.py` → backend + security).

    Args:
        repo_path: Absolute path to the cloned repository root
        exclude_patterns: Glob patterns for files/dirs to skip
        include_patterns: Optional allowlist glob patterns. If provided,
            only matching files are routed.

    Returns:
        Dictionary mapping agent names to lists of relative file paths.
        Keys: "frontend", "backend", "database", "security", "devops", "dependency"
    """
    exclude_patterns = _normalize_exclude_patterns(exclude_patterns)
    if include_patterns is None:
        include_patterns = []

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

            if include_patterns and not _matches_include_patterns(rel_path, filename, include_patterns):
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

            # 2. Ambiguous extensions (.js, .ts) → route with heuristics
            if ext in AMBIGUOUS_EXTENSIONS:
                try:
                    with open(abs_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read(4000) # Read first 4kb for heuristics
                    if _is_backend_js(content):
                        matched_agents.add("backend")
                    else:
                        matched_agents.add("frontend")
                except Exception:
                    # Fallback to frontend if read fails
                    matched_agents.add("frontend")

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

            # 6. CI/CD YAML files in specific directories → devops
            if ext in (".yml", ".yaml"):
                if any(d in rel_dir.replace("\\", "/") for d in [".github", ".gitlab", ".circleci", "k8s"]):
                    matched_agents.add("devops")

            # 7. ORM-related files → database
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
