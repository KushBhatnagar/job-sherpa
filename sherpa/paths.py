"""Where things live.

Code lives in the repo. Everything personal lives in ONE folder, the "home":
`me/` inside the repo by default (gitignored), or wherever SHERPA_HOME points.
One folder means one thing to back up and one thing that must never be committed.

Functions, not constants, so tests (and people with several profiles) can switch
SHERPA_HOME at runtime.
"""
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = REPO_ROOT / "templates"
STARTER_LISTS = REPO_ROOT / "starter-lists"


def home() -> Path:
    value = os.environ.get("SHERPA_HOME", "").strip()
    return Path(value).expanduser().resolve() if value else REPO_ROOT / "me"


def db_path() -> Path:
    return home() / "sherpa.db"


def profile_path() -> Path:
    return home() / "profile.toml"


def bullets_path() -> Path:
    return home() / "bullets.yaml"


def companies_path() -> Path:
    return home() / "companies.yaml"


def drafts_dir() -> Path:
    return home() / "drafts"


def applications_dir() -> Path:
    return home() / "applications"


def show(path: Path) -> str:
    """A path as people should read it: relative to the repo when it's inside it."""
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path)
