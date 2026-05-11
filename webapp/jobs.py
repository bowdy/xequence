"""
Tiny in-process job manager.

The web UI fires off operations that take minutes (scraping mutuals, running
a tick). They have to run in a background thread so the request can return
immediately, and the UI needs to poll for status + log lines.

This module is intentionally simple — no Redis, no Celery, no Postgres. One
dict, one lock, one thread per job. The whole app lives on localhost on a
single Mac; that's all the durability we need.
"""
from __future__ import annotations

import threading
import time
import traceback
import uuid
from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Deque, Literal

JobStatus = Literal["running", "succeeded", "failed", "cancelled"]


@dataclass
class Job:
    id: str
    name: str
    status: JobStatus = "running"
    log: Deque[str] = field(default_factory=lambda: deque(maxlen=500))
    started_at: float = field(default_factory=time.time)
    finished_at: float | None = None
    result: object = None
    error: str | None = None
    _cancel: threading.Event = field(default_factory=threading.Event)

    def append(self, line: str) -> None:
        self.log.append(line)

    def cancel(self) -> None:
        self._cancel.set()

    @property
    def cancelled(self) -> bool:
        return self._cancel.is_set()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status,
            "log": list(self.log),
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "result": self.result,
            "error": self.error,
        }


_jobs: dict[str, Job] = {}
_lock = threading.Lock()


def start_job(name: str, target: Callable[[Job], object]) -> Job:
    """Spawn a thread to run `target(job)`. The target is responsible for
    writing log lines and respecting `job.cancelled`. Its return value is
    stored on `job.result`."""
    job = Job(id=str(uuid.uuid4())[:8], name=name)
    with _lock:
        _jobs[job.id] = job

    def _runner():
        try:
            result = target(job)
            job.result = result
            job.status = "cancelled" if job.cancelled else "succeeded"
        except Exception as e:
            job.status = "failed"
            job.error = f"{type(e).__name__}: {e}"
            job.append(f"ERROR: {job.error}")
            job.append(traceback.format_exc())
        finally:
            job.finished_at = time.time()

    t = threading.Thread(target=_runner, name=f"xq-job-{job.id}", daemon=True)
    t.start()
    return job


def get(job_id: str) -> Job | None:
    return _jobs.get(job_id)


def recent(limit: int = 10) -> list[Job]:
    with _lock:
        return sorted(_jobs.values(), key=lambda j: j.started_at, reverse=True)[:limit]


def is_running(name: str) -> bool:
    """Has any job with this name started and not finished yet?"""
    return any(j.name == name and j.status == "running" for j in _jobs.values())
