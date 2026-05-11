"""Shared helpers loaded by every tool."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(REPO_ROOT / ".env")


class MissingEnv(RuntimeError):
    """Raised when a required env var is unset.

    A regular exception (not SystemExit) so callers like the web UI can catch
    it and surface a useful message in the page. CLI tools handle it in main()
    by printing a hint and exiting non-zero.
    """


def env(name: str, default: str | None = None, *, required: bool = False) -> str:
    val = os.environ.get(name, default)
    if required and not val:
        raise MissingEnv(f"required env var {name} is not set (see .env.example)")
    return val or ""


def storage_state_path() -> Path:
    path = Path(env("XEQUENCE_STORAGE_STATE", str(REPO_ROOT / ".playwright_session/storage_state.json")))
    path.parent.mkdir(parents=True, exist_ok=True)
    return path
