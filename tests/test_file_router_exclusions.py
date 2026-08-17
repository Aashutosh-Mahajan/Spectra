import os
import shutil
import tempfile
from pathlib import Path

from backend.utils.file_router import (
    is_crucial_or_sensitive_file,
    _should_exclude,
    route_files,
)
from backend.utils.chunker import chunk_file, read_file_content
from backend.utils.cache import FileCache


def test_is_crucial_or_sensitive_file_env_files():
    env_files = [
        ".env",
        ".env.local",
        ".env.production",
        ".env.staging",
        ".env.development",
        ".env.test",
        ".env.prod",
        ".env.dev",
        ".env.secrets",
        ".env.vault",
        ".env.sample",
        ".env.example",
        ".envrc",
        ".envfile",
        "custom.env",
        "app.env",
        "prod.env",
        "env.json",
        "env.yaml",
        "env.yml",
        "backend/.env",
        "config/sub/.env.production",
        "docker/app.env",
    ]
    for path in env_files:
        assert is_crucial_or_sensitive_file(path) is True, f"Failed to identify {path} as sensitive"


def test_is_crucial_or_sensitive_file_secrets_and_creds():
    secret_files = [
        "secrets.json",
        "secrets.yaml",
        "secrets.yml",
        "secrets.toml",
        "secrets.ini",
        "secrets.xml",
        "secret.json",
        "secret.yaml",
        "credentials.json",
        "credentials.yaml",
        "credentials.yml",
        "credential.json",
        "my_credentials.json",
        "service_account.json",
        "service-account.json",
        "serviceaccount.json",
        "my-firebase-adminsdk-12345.json",
        "google-services.json",
        "GoogleService-Info.plist",
        "client_secret.json",
        "client_secrets.json",
        "oauth-credentials.json",
        "local.settings.json",
        "appsettings.Development.json",
        "appsettings.Production.json",
        "appsettings.Local.json",
        "appsettings.Secrets.json",
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
        "vars.tfvars",
        "terraform.tfstate",
        "terraform.tfstate.backup",
        ".vault-token",
        "passwords.kdbx",
        "client.ovpn",
    ]
    for path in secret_files:
        assert is_crucial_or_sensitive_file(path) is True, f"Failed to identify {path} as sensitive"


def test_is_crucial_or_sensitive_file_keys_and_certs():
    key_files = [
        "server.key",
        "private.key",
        "cert.pem",
        "ca.crt",
        "bundle.cer",
        "identity.p12",
        "identity.pfx",
        "client.pkcs12",
        "server.der",
        "app.keystore",
        "truststore.jks",
        "app.truststore",
        "putty.ppk",
        "id_rsa",
        "id_rsa.pub",
        "id_ecdsa",
        "id_ed25519",
        "id_ed25519.pub",
        "id_dsa",
        ".ssh/id_rsa",
        "certs/private.key",
    ]
    for path in key_files:
        assert is_crucial_or_sensitive_file(path) is True, f"Failed to identify {path} as sensitive"


def test_is_crucial_or_sensitive_file_cloud_dirs_and_history():
    cloud_and_history = [
        ".spectra/config.json",
        ".spectra/.env",
        ".aws/credentials",
        ".aws/config",
        ".kube/config",
        "kubeconfig",
        ".kubeconfig",
        ".docker/config.json",
        ".dockercfg",
        ".bash_history",
        ".zsh_history",
        ".sh_history",
        ".psql_history",
        ".mysql_history",
        ".sqlite_history",
    ]
    for path in cloud_and_history:
        assert is_crucial_or_sensitive_file(path) is True, f"Failed to identify {path} as sensitive"


def test_is_crucial_or_sensitive_file_safe_files():
    safe_files = [
        "src/App.tsx",
        "src/components/Header.jsx",
        "backend/main.py",
        "backend/routes/auth_routes.py",
        "backend/services/token_manager.py",
        "backend/security_agent.py",
        "backend/models.py",
        "package.json",
        "requirements.txt",
        "Dockerfile",
        "docker-compose.yml",
        "README.md",
        "appsettings.json",
        "environment.ts",
        "services/user_service.go",
        "src/lib/crypto_utils.rs",
    ]
    for path in safe_files:
        assert is_crucial_or_sensitive_file(path) is False, f"Erroneously flagged safe file {path}"


def test_should_exclude_protected_even_with_empty_caller_excludes():
    assert _should_exclude(".env", []) is True
    assert _should_exclude("backend/.env.production", []) is True
    assert _should_exclude("secrets.json", []) is True
    assert _should_exclude("certs/private.pem", []) is True
    assert _should_exclude(".aws/credentials", []) is True
    assert _should_exclude("src/App.tsx", []) is False


def test_route_files_excludes_crucial_files():
    temp_dir = tempfile.mkdtemp()
    try:
        # Create normal files
        os.makedirs(os.path.join(temp_dir, "src", "components"), exist_ok=True)
        os.makedirs(os.path.join(temp_dir, "backend", "routes"), exist_ok=True)
        os.makedirs(os.path.join(temp_dir, "config"), exist_ok=True)
        os.makedirs(os.path.join(temp_dir, ".aws"), exist_ok=True)
        os.makedirs(os.path.join(temp_dir, ".spectra"), exist_ok=True)
        os.makedirs(os.path.join(temp_dir, "node_modules", "pkg"), exist_ok=True)

        Path(os.path.join(temp_dir, "src", "App.tsx")).write_text("export const App = () => <div>Hello</div>;")
        Path(os.path.join(temp_dir, "src", "components", "Header.jsx")).write_text("export default function Header() {}")
        Path(os.path.join(temp_dir, "backend", "routes", "auth.py")).write_text("def login(): pass")
        Path(os.path.join(temp_dir, "backend", "models.py")).write_text("class User: pass")
        Path(os.path.join(temp_dir, "requirements.txt")).write_text("fastapi==0.100.0")
        Path(os.path.join(temp_dir, "Dockerfile")).write_text("FROM python:3.11")

        # Create sensitive files that must be excluded
        Path(os.path.join(temp_dir, ".env")).write_text("OPENAI_API_KEY=sk-test-12345")
        Path(os.path.join(temp_dir, ".env.production")).write_text("DATABASE_URL=postgres://user:pass@db:5432/prod")
        Path(os.path.join(temp_dir, "config", ".env.local")).write_text("SECRET_KEY=supersecret")
        Path(os.path.join(temp_dir, "secrets.json")).write_text('{"api_key": "secret"}')
        Path(os.path.join(temp_dir, "credentials.yaml")).write_text("aws_secret: 12345")
        Path(os.path.join(temp_dir, "private.pem")).write_text("-----BEGIN RSA PRIVATE KEY-----")
        Path(os.path.join(temp_dir, "id_rsa")).write_text("-----BEGIN OPENSSH PRIVATE KEY-----")
        Path(os.path.join(temp_dir, ".aws", "credentials")).write_text("[default]\naws_access_key_id=test")
        Path(os.path.join(temp_dir, ".spectra", ".env")).write_text("OPENAI_API_KEY=sk-spectra")
        Path(os.path.join(temp_dir, "node_modules", "pkg", "index.js")).write_text("module.exports = {}")

        file_map = route_files(temp_dir)

        all_routed_files = set()
        for files in file_map.values():
            all_routed_files.update(files)

        # Check sensitive files are NOT in any routed list
        forbidden_substrings = [
            ".env",
            "secrets.json",
            "credentials.yaml",
            "private.pem",
            "id_rsa",
            ".aws",
            ".spectra",
            "node_modules",
        ]
        for routed_file in all_routed_files:
            for forbidden in forbidden_substrings:
                assert forbidden not in routed_file, f"Forbidden file routed: {routed_file}"

        # Check valid files ARE routed properly
        assert "src/App.tsx" in file_map["frontend"]
        assert "src/components/Header.jsx" in file_map["frontend"]
        assert "backend/routes/auth.py" in file_map["backend"]
        assert "backend/routes/auth.py" in file_map["security"]
        assert "backend/models.py" in file_map["database"]
        assert "backend/models.py" in file_map["backend"]
        assert "requirements.txt" in file_map["dependency"]
        assert "Dockerfile" in file_map["devops"]

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_chunker_and_reader_refuse_sensitive_files():
    temp_dir = tempfile.mkdtemp()
    try:
        env_file = os.path.join(temp_dir, ".env")
        secret_file = os.path.join(temp_dir, "secrets.json")
        code_file = os.path.join(temp_dir, "main.py")

        Path(env_file).write_text("OPENAI_API_KEY=sk-test-secret")
        Path(secret_file).write_text('{"token": "xyz"}')
        Path(code_file).write_text("print('hello world')\n")

        # Crucial files must return empty / None
        assert chunk_file(env_file) == []
        assert read_file_content(env_file) is None

        assert chunk_file(secret_file) == []
        assert read_file_content(secret_file) is None

        # Code file must be chunked / read normally
        code_chunks = chunk_file(code_file)
        assert len(code_chunks) == 1
        assert "hello world" in code_chunks[0]["content"]

        code_content = read_file_content(code_file)
        assert code_content is not None
        assert "hello world" in code_content

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_file_cache_refuses_sensitive_files():
    temp_dir = tempfile.mkdtemp()
    try:
        cache = FileCache(temp_dir)
        env_file = os.path.join(temp_dir, ".env")
        Path(env_file).write_text("OPENAI_API_KEY=sk-test-secret")

        assert cache._hash_file(env_file) is None
        assert cache.get_cached_findings("security", env_file, ".env") is None

        cache.set_cached_findings("security", env_file, ".env", [])
        assert "security:.env" not in cache.cache_data

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_dependency_agent_refuses_sensitive_files(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test12345678901234567890")
    from backend.agents.dependency_agent import DependencyAgent
    agent = DependencyAgent()
    temp_dir = tempfile.mkdtemp()
    try:
        env_file = os.path.join(temp_dir, ".env")
        Path(env_file).write_text("OPENAI_API_KEY=sk-test-secret")

        assert agent._extract_packages(env_file, ".env") == []
        assert agent._extract_packages(env_file, "backend/.env.local") == []
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

