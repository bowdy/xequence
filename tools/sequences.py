"""Sequence YAML loader + step resolver."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

from tools._common import REPO_ROOT


SEQUENCES_DIR = REPO_ROOT / "sequences"


@dataclass
class Step:
    day_offset: int
    message: str


@dataclass
class Sequence:
    name: str
    steps: list[Step]


def load_sequence(name: str) -> Sequence:
    path = SEQUENCES_DIR / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"No sequence file at {path}")
    data = yaml.safe_load(path.read_text())
    steps = [Step(day_offset=int(s["day_offset"]), message=str(s["message"])) for s in data["steps"]]
    if not steps:
        raise ValueError(f"Sequence {name} has no steps")
    # Validate that day_offsets are monotonically non-decreasing — otherwise
    # an earlier step would be scheduled after a later one and the state
    # machine would deadlock.
    for a, b in zip(steps, steps[1:]):
        if b.day_offset < a.day_offset:
            raise ValueError(
                f"Sequence {name}: step day_offsets must be non-decreasing "
                f"(found {a.day_offset} → {b.day_offset})"
            )
    return Sequence(name=data.get("name", name), steps=steps)


def render(template: str, *, handle: str, display_name: str | None) -> str:
    name = display_name or handle
    first = name.split(" ")[0] if name else handle
    return template.format(
        handle=handle,
        display_name=name,
        first_name=first,
    )


def schedule_for_step(enrolled_at: datetime, step: Step) -> datetime:
    return enrolled_at + timedelta(days=step.day_offset)


def parse_iso(value: str) -> datetime:
    # Accept either a naive datetime (assume UTC) or an offset-aware one.
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt
