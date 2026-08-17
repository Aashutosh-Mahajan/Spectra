import json
import hashlib
import os
import logging
from pathlib import Path
from backend.api.models import Finding
from backend.utils.file_router import is_crucial_or_sensitive_file

logger = logging.getLogger(__name__)

class FileCache:
    """Caches agent findings based on file content hashes."""

    def __init__(self, repo_path: str):
        self.repo_path = repo_path
        # Store cache in .spectra/.spectra_cache.json
        self.cache_dir = os.path.join(repo_path, ".spectra")
        self.cache_file = os.path.join(self.cache_dir, ".spectra_cache.json")
        self.cache_data = self._load_cache()

    def _load_cache(self) -> dict:
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load cache from {self.cache_file}: {e}")
        return {}

    def _save_cache(self):
        try:
            os.makedirs(self.cache_dir, exist_ok=True)
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self.cache_data, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save cache to {self.cache_file}: {e}")

    def _hash_file(self, abs_path: str) -> str | None:
        """Returns the SHA-256 hash of a file's contents."""
        if is_crucial_or_sensitive_file(abs_path):
            return None
        hasher = hashlib.sha256()
        try:
            with open(abs_path, 'rb') as f:
                while chunk := f.read(8192):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except Exception as e:
            logger.debug(f"Failed to hash file {abs_path}: {e}")
            return None

    def get_cached_findings(self, agent_name: str, abs_path: str, rel_path: str) -> list[Finding] | None:
        """
        Retrieves cached findings if the file hasn't changed.
        Returns None if cache miss or file modified.
        """
        if is_crucial_or_sensitive_file(rel_path) or is_crucial_or_sensitive_file(abs_path):
            return None

        file_hash = self._hash_file(abs_path)
        if not file_hash:
            return None

        cache_key = f"{agent_name}:{rel_path}"
        entry = self.cache_data.get(cache_key)

        if entry and entry.get("hash") == file_hash:
            try:
                # Reconstruct Finding objects from cached dicts
                findings = [Finding(**f_dict) for f_dict in entry.get("findings", [])]
                logger.debug(f"Cache hit for {cache_key}")
                return findings
            except Exception as e:
                logger.warning(f"Failed to parse cached findings for {cache_key}: {e}")
                
        return None

    def set_cached_findings(self, agent_name: str, abs_path: str, rel_path: str, findings: list[Finding]):
        """Saves findings to the cache."""
        if is_crucial_or_sensitive_file(rel_path) or is_crucial_or_sensitive_file(abs_path):
            return

        file_hash = self._hash_file(abs_path)
        if not file_hash:
            return

        cache_key = f"{agent_name}:{rel_path}"
        
        self.cache_data[cache_key] = {
            "hash": file_hash,
            "findings": [f.model_dump() for f in findings]
        }
        self._save_cache()
