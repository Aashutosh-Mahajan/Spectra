"""
Repository cloner using GitPython.
Performs shallow clones of GitHub repositories into the job storage directory.
"""

import os
import shutil
import logging
from pathlib import Path
from urllib.parse import urlparse

import git

logger = logging.getLogger(__name__)


class CloneError(Exception):
    """Structured error for clone failures."""

    def __init__(self, reason: str, message: str):
        self.reason = reason  # "invalid_url", "auth_failure", "not_found", "timeout", "unknown"
        self.message = message
        super().__init__(f"[{reason}] {message}")


def _construct_clone_url(repo_url: str, github_token: str | None = None) -> str:
    """
    Construct the clone URL, injecting the GitHub token for private repo access.
    Token is used only in-memory and never written to disk.
    """
    if not github_token:
        return repo_url

    parsed = urlparse(repo_url)
    # Construct: https://<token>@github.com/user/repo
    authed_url = f"{parsed.scheme}://{github_token}@{parsed.netloc}{parsed.path}"
    return authed_url


def _validate_repo_url(repo_url: str) -> None:
    """Validate that the URL looks like a valid GitHub repository URL."""
    parsed = urlparse(repo_url)
    if parsed.scheme not in ("http", "https"):
        raise CloneError("invalid_url", f"URL scheme must be http or https, got: {parsed.scheme}")
    if not parsed.netloc:
        raise CloneError("invalid_url", f"Invalid URL: {repo_url}")
    # Basic path validation - should have at least /user/repo
    path_parts = [p for p in parsed.path.strip("/").split("/") if p]
    if len(path_parts) < 2:
        raise CloneError("invalid_url", f"URL must contain owner/repo path: {repo_url}")


def clone_repo(
    repo_url: str,
    job_id: str,
    github_token: str | None = None,
    storage_base: str = "./storage/jobs",
    clone_timeout: int = 120,
) -> str:
    """
    Shallow clone a GitHub repository.

    Args:
        repo_url: GitHub repository URL
        job_id: Unique job identifier
        github_token: Optional GitHub PAT for private repos
        storage_base: Base directory for job storage
        clone_timeout: Timeout in seconds for the clone operation

    Returns:
        Absolute path to the cloned repository directory

    Raises:
        CloneError: If the clone fails for any reason
    """
    _validate_repo_url(repo_url)

    clone_dir = os.path.join(storage_base, job_id, "repo")
    os.makedirs(clone_dir, exist_ok=True)

    clone_url = _construct_clone_url(repo_url, github_token)

    logger.info(f"Cloning repository {repo_url} into {clone_dir} (depth=1)")

    try:
        git.Repo.clone_from(
            clone_url,
            clone_dir,
            depth=1,
            single_branch=True,
            kill_after_timeout=clone_timeout,
        )
    except git.exc.GitCommandError as e:
        stderr = str(e.stderr) if e.stderr else str(e)

        if "Authentication failed" in stderr or "could not read Username" in stderr:
            raise CloneError("auth_failure", f"Authentication failed for {repo_url}. Check your GitHub token.")
        elif "Repository not found" in stderr or "not found" in stderr.lower():
            raise CloneError("not_found", f"Repository not found: {repo_url}")
        elif "timed out" in stderr.lower() or "timeout" in stderr.lower():
            raise CloneError("timeout", f"Clone timed out after {clone_timeout}s for {repo_url}")
        else:
            raise CloneError("unknown", f"Git clone failed: {stderr}")
    except Exception as e:
        raise CloneError("unknown", f"Unexpected error during clone: {str(e)}")

    repo_path = os.path.abspath(clone_dir)
    logger.info(f"Successfully cloned {repo_url} to {repo_path}")
    return repo_path


def cleanup_repo(job_id: str, storage_base: str = "./storage/jobs") -> None:
    """
    Delete the cloned repository directory to free disk space.

    Args:
        job_id: Job identifier whose repo directory to clean up
        storage_base: Base directory for job storage
    """
    job_dir = os.path.join(storage_base, job_id)
    if os.path.exists(job_dir):
        try:
            shutil.rmtree(job_dir)
            logger.info(f"Cleaned up job directory: {job_dir}")
        except OSError as e:
            logger.warning(f"Failed to clean up {job_dir}: {e}")
