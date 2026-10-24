"""Tiny .env reader (no python-dotenv: KEY=VALUE lines don't need a library).

Reads `.env` at the repo root, then `<home>/.env` (which wins). Real environment
variables win over both.
"""
import os

from . import paths


def load_env() -> dict:
    values: dict[str, str] = {}
    for env_path in (paths.REPO_ROOT / ".env", paths.home() / ".env"):
        if not env_path.exists():
            continue
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            values[key.strip()] = val.strip().strip('"').strip("'")
    for key in list(values):
        values[key] = os.environ.get(key, values[key])
    for key in ("ADZUNA_APP_ID", "ADZUNA_APP_KEY", "SHERPA_BACKUP_DIR", "SHERPA_BACKUP_KEEP"):
        if key in os.environ:
            values[key] = os.environ[key]
    return values
