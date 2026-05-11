"""Shared helpers loaded by every tool."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(REPO_ROOT / ".env")


def env(name: str, default: str | None = None, *, required: bool = False) -> str:
    val = os.environ.get(name, default)
    if required and not val:
        sys.stderr.write(f"ERROR: required env var {name} is not set (see .env.example)\n")
        sys.exit(2)
    return val or ""


def storage_state_path() -> Path:
    path = Path(env("XEQUENCE_STORAGE_STATE", str(REPO_ROOT / ".playwright_session/storage_state.json")))
    path.parent.mkdir(parents=True, exist_ok=True)
    return path
