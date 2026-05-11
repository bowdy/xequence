"""
FastAPI app for Xequence.

Routes (HTML pages):
  GET  /                       dashboard

Routes (HTMX partials — return HTML fragments):
  GET  /partials/session       session-status badge
  GET  /partials/contacts      contacts table
  GET  /partials/jobs          recent-jobs panel
  GET  /partials/sequences     list of sequence files
  GET  /partials/mutuals       result of the most recent pull_mutuals job

Routes (actions — return HTML fragment of the kicked-off job):
  POST /actions/pull-mutuals
  POST /actions/enroll         body: handles=, sequence=
  POST /actions/tick           body: dry_run=on|off
  POST /actions/save-sequence  body: name=, body=
  POST /jobs/{id}/cancel
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# Make `tools` importable when running uvicorn from anywhere.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools._common import REPO_ROOT, env, storage_state_path  # noqa: E402
from tools.browser_session import x_session  # noqa: E402
from tools.sequences import (  # noqa: E402
    SEQUENCES_DIR,
    load_sequence,
    parse_iso,
    render,
    schedule_for_step,
)
from tools.sheets_client import Contact, now_iso, read_all, update_contact, upsert_contact  # noqa: E402
from tools.twitter_client import fetch_display_name, fetch_followers, fetch_mutuals, send_dm  # noqa: E402
from webapp import jobs  # noqa: E402

app = FastAPI(title="Xequence")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def view(request: Request, name: str, **context) -> HTMLResponse:
    """Thin wrapper around TemplateResponse using the starlette 1.0+ signature
    (request first, then template name, then context dict). Named `view` to
    avoid shadowing `tools.sequences.render`."""
    return templates.TemplateResponse(request, name, context)


# ---------- helpers --------------------------------------------------------


def session_ok() -> tuple[bool, str]:
    """Light check: does storage_state.json exist on disk?

    A full check would open a browser and hit x.com/home, but that's slow.
    The full check is exposed as a separate button.
    """
    path = storage_state_path()
    if not path.exists():
        return False, "Not logged in. Run `python tools/browser_session.py login` in a terminal."
    age_days = (datetime.now().timestamp() - path.stat().st_mtime) / 86400
    return True, f"Session cookie present (last refreshed {age_days:.1f}d ago)."


def list_sequences() -> list[dict]:
    out = []
    for p in sorted(SEQUENCES_DIR.glob("*.yaml")):
        raw = p.read_text()
        try:
            seq = load_sequence(p.stem)
            out.append({
                "name": seq.name,
                "file": p.name,
                "step_count": len(seq.steps),
                "day_offsets": [s.day_offset for s in seq.steps],
                "raw": raw,
                "error": None,
            })
        except Exception as e:
            out.append({
                "name": p.stem,
                "file": p.name,
                "step_count": 0,
                "day_offsets": [],
                "raw": raw,
                "error": str(e),
            })
    return out


AUDIENCE_SOURCES = {
    "mutuals": REPO_ROOT / ".tmp" / "mutuals.txt",
    "followers": REPO_ROOT / ".tmp" / "followers.txt",
}


def read_audience(source: str) -> dict:
    """Return the audience for `source` plus its file metadata.

    Each source maps to one .tmp file. Files are plain text, one handle per
    line. Missing files are treated as empty, not an error — the UI should
    surface "no list yet, click pull".
    """
    p = AUDIENCE_SOURCES.get(source)
    if p is None or not p.exists():
        return {"source": source, "handles": [], "pulled_at": None}
    handles = [line.strip() for line in p.read_text().splitlines() if line.strip()]
    pulled_at = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)
    return {"source": source, "handles": handles, "pulled_at": pulled_at.isoformat()}


def audience_summary() -> dict[str, int]:
    """Count of handles in each known source file (for the source switcher)."""
    return {src: len(read_audience(src)["handles"]) for src in AUDIENCE_SOURCES}


# ---------- pages ----------------------------------------------------------


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    ok, msg = session_ok()
    return view(
        request,
        "index.html",
        session_ok=ok,
        session_msg=msg,
        sequences=list_sequences(),
        audience_counts=audience_summary(),
    )


# ---------- partials -------------------------------------------------------


@app.get("/partials/session", response_class=HTMLResponse)
def partial_session(request: Request):
    ok, msg = session_ok()
    return view(request, "_session.html", session_ok=ok, session_msg=msg)


@app.get("/partials/contacts", response_class=HTMLResponse)
def partial_contacts(request: Request):
    try:
        contacts = read_all()
        error = None
    except Exception as e:
        contacts = []
        error = f"{type(e).__name__}: {e}"

    now = datetime.now(tz=timezone.utc)
    rows = []
    for c in contacts:
        due = False
        if c.next_send_at and c.status in ("pending", "in_progress"):
            try:
                due = parse_iso(c.next_send_at) <= now
            except ValueError:
                pass
        rows.append({"c": c, "due": due})

    return view(request, "_contacts.html", rows=rows, error=error, total=len(rows))


@app.get("/partials/jobs", response_class=HTMLResponse)
def partial_jobs(request: Request):
    return view(request, "_jobs.html", jobs=[j.to_dict() for j in jobs.recent()])


@app.get("/partials/audience", response_class=HTMLResponse)
def partial_audience(request: Request, source: str = "mutuals"):
    if source not in AUDIENCE_SOURCES:
        raise HTTPException(400, f"unknown source: {source}")
    data = read_audience(source)
    return view(
        request,
        "_audience.html",
        source=source,
        handles=data["handles"],
        count=len(data["handles"]),
        pulled_at=data["pulled_at"],
        counts=audience_summary(),
        sequences=list_sequences(),
    )


@app.get("/partials/sequences", response_class=HTMLResponse)
def partial_sequences(request: Request):
    return view(request, "_sequences.html", sequences=list_sequences())


@app.get("/sequences/{name}/raw", response_class=HTMLResponse)
def sequence_raw(name: str):
    path = SEQUENCES_DIR / f"{name}.yaml"
    if not path.exists():
        raise HTTPException(404)
    # Plain text so the textarea-edit flow can grab it via fetch().
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(path.read_text())


# ---------- actions --------------------------------------------------------


@app.post("/actions/pull-mutuals", response_class=HTMLResponse)
def action_pull_mutuals(request: Request):
    if jobs.is_running("pull_mutuals"):
        raise HTTPException(409, "A pull_mutuals job is already running.")

    handle = env("X_HANDLE", required=True).lstrip("@")

    def work(job: jobs.Job):
        job.append(f"Opening X session for @{handle}…")
        with x_session(headless=True) as (_ctx, page):
            job.append("Scrolling /following and /followers (this can take several minutes)…")
            mutuals = fetch_mutuals(page, handle)
        out = REPO_ROOT / ".tmp" / "mutuals.txt"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("\n".join(mutuals) + "\n")
        job.append(f"Wrote {len(mutuals)} mutuals to {out}")
        return {"count": len(mutuals), "file": str(out)}

    job = jobs.start_job("pull_mutuals", work)
    return view(request, "_job_row.html", job=job.to_dict())


@app.post("/actions/pull-followers", response_class=HTMLResponse)
def action_pull_followers(request: Request):
    if jobs.is_running("pull_followers"):
        raise HTTPException(409, "A pull_followers job is already running.")

    handle = env("X_HANDLE", required=True).lstrip("@")

    def work(job: jobs.Job):
        job.append(f"Opening X session for @{handle}…")
        with x_session(headless=True) as (_ctx, page):
            job.append("Scrolling /followers (this can take several minutes for large accounts)…")
            followers = sorted(fetch_followers(page, handle))
        out = AUDIENCE_SOURCES["followers"]
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("\n".join(followers) + "\n")
        job.append(f"Wrote {len(followers)} followers to {out}")
        return {"count": len(followers), "file": str(out)}

    job = jobs.start_job("pull_followers", work)
    return view(request, "_job_row.html", job=job.to_dict())


@app.post("/actions/enroll-selected", response_class=HTMLResponse)
def action_enroll_selected(
    request: Request,
    handles: list[str] = Form(default_factory=list),
    sequence: str = Form("default"),
):
    """Enroll handles selected via checkboxes in the audience list.

    Each checked checkbox in `_audience.html` carries name="handles" and the
    handle as its value. FastAPI collects them as a list automatically.
    """
    parsed = [h.strip().lstrip("@").lower() for h in handles if h.strip()]
    if not parsed:
        raise HTTPException(400, "No handles selected.")

    seq = load_sequence(sequence)
    enrolled_at = datetime.now(tz=timezone.utc).replace(microsecond=0)
    first_send = schedule_for_step(enrolled_at, seq.steps[0])

    existing = {(c.handle, c.sequence) for c in read_all()}
    added, skipped = 0, 0
    for handle in parsed:
        if (handle, sequence) in existing:
            skipped += 1
            continue
        upsert_contact(
            Contact(
                handle=handle,
                sequence=sequence,
                enrolled_at=enrolled_at.isoformat(),
                current_step=0,
                next_send_at=first_send.isoformat(),
                status="pending",
            )
        )
        added += 1

    return view(request, "_enroll_result.html", added=added, skipped=skipped, sequence=sequence)


@app.post("/actions/enroll", response_class=HTMLResponse)
def action_enroll(
    request: Request,
    handles: str = Form(""),
    sequence: str = Form("default"),
):
    parsed: list[str] = []
    seen = set()
    for raw in handles.replace(",", "\n").splitlines():
        h = raw.strip().lstrip("@").lower()
        if h and h not in seen:
            seen.add(h)
            parsed.append(h)
    if not parsed:
        raise HTTPException(400, "No handles provided.")

    seq = load_sequence(sequence)
    enrolled_at = datetime.now(tz=timezone.utc).replace(microsecond=0)
    first_send = schedule_for_step(enrolled_at, seq.steps[0])

    existing = {(c.handle, c.sequence) for c in read_all()}
    added, skipped = 0, 0
    for handle in parsed:
        if (handle, sequence) in existing:
            skipped += 1
            continue
        upsert_contact(
            Contact(
                handle=handle,
                sequence=sequence,
                enrolled_at=enrolled_at.isoformat(),
                current_step=0,
                next_send_at=first_send.isoformat(),
                status="pending",
            )
        )
        added += 1

    return view(request, "_enroll_result.html", added=added, skipped=skipped, sequence=sequence)


@app.post("/actions/tick", response_class=HTMLResponse)
def action_tick(request: Request, dry_run: str = Form("")):
    is_dry = dry_run in ("on", "true", "1")

    if not is_dry and jobs.is_running("tick"):
        raise HTTPException(409, "A tick job is already running.")

    max_per_run = int(env("XEQUENCE_MAX_PER_RUN", "20"))

    if is_dry:
        # Cheap, synchronous: just shows what would be sent.
        now = datetime.now(tz=timezone.utc)
        contacts = read_all()
        seq_cache: dict[str, object] = {}
        previews = []
        for c in contacts:
            if c.status not in ("pending", "in_progress"):
                continue
            try:
                if parse_iso(c.next_send_at) > now:
                    continue
            except (ValueError, AttributeError):
                continue
            if c.sequence not in seq_cache:
                seq_cache[c.sequence] = load_sequence(c.sequence)
            s = seq_cache[c.sequence]
            if c.current_step >= len(s.steps):
                continue
            step = s.steps[c.current_step]
            previews.append({
                "handle": c.handle,
                "step": c.current_step,
                "message": render(step.message, handle=c.handle, display_name=c.display_name),
            })
            if len(previews) >= max_per_run:
                break
        return view(request, "_tick_preview.html", previews=previews, cap=max_per_run)

    # Real send — spawn a job. The job mirrors send_due_messages.py.
    def work(job: jobs.Job):
        import random
        import time
        min_delay = int(env("XEQUENCE_MIN_DELAY_SECONDS", "35"))
        max_delay = int(env("XEQUENCE_MAX_DELAY_SECONDS", "75"))

        now = datetime.now(tz=timezone.utc)
        contacts = read_all()
        due = []
        for c in contacts:
            if c.status not in ("pending", "in_progress"):
                continue
            try:
                if parse_iso(c.next_send_at) <= now:
                    due.append(c)
            except ValueError:
                continue
        job.append(f"{len(due)} contacts due. Will send up to {max_per_run}.")

        if not due:
            return {"sent": 0}

        seq_cache: dict[str, object] = {}
        sent = 0
        with x_session(headless=True) as (_ctx, page):
            for c in due:
                if job.cancelled:
                    job.append("Cancelled.")
                    break
                if sent >= max_per_run:
                    job.append(f"Hit per-run cap ({max_per_run}). Stopping.")
                    break
                if c.sequence not in seq_cache:
                    seq_cache[c.sequence] = load_sequence(c.sequence)
                s = seq_cache[c.sequence]
                if c.current_step >= len(s.steps):
                    c.status = "completed"
                    update_contact(c)
                    continue
                step = s.steps[c.current_step]
                if not c.display_name:
                    name = fetch_display_name(page, c.handle)
                    if name:
                        c.display_name = name
                message = render(step.message, handle=c.handle, display_name=c.display_name)
                job.append(f"→ @{c.handle} (step {c.current_step})")
                result = send_dm(page, c.handle, message)
                if result.status == "sent":
                    c.last_sent_at = now_iso()
                    c.current_step += 1
                    if c.current_step >= len(s.steps):
                        c.status = "completed"
                        c.next_send_at = ""
                    else:
                        enrolled = parse_iso(c.enrolled_at) if c.enrolled_at else datetime.now(tz=timezone.utc)
                        c.next_send_at = schedule_for_step(enrolled, s.steps[c.current_step]).isoformat()
                        c.status = "in_progress"
                    c.notes = ""
                    update_contact(c)
                    sent += 1
                    if sent < max_per_run and not job.cancelled:
                        delay = random.uniform(min_delay, max_delay)
                        job.append(f"  sent. sleeping {delay:.1f}s")
                        # Sleep in small chunks so cancellation responds quickly.
                        slept = 0.0
                        while slept < delay and not job.cancelled:
                            time.sleep(min(1.0, delay - slept))
                            slept += 1.0
                elif result.status == "no_dm_button":
                    c.status = "stopped"
                    c.notes = f"{result.status}: {result.detail}"
                    update_contact(c)
                    job.append(f"  skip: {result.status}")
                else:
                    c.notes = f"{result.status}: {result.detail}"
                    c.status = "error"
                    update_contact(c)
                    job.append(f"  HARD FAIL: {result.status} — {result.detail}. Stopping the batch.")
                    break
        return {"sent": sent}

    job = jobs.start_job("tick", work)
    return view(request, "_job_row.html", job=job.to_dict())


@app.post("/actions/save-sequence", response_class=HTMLResponse)
def action_save_sequence(
    request: Request,
    name: str = Form(...),
    body: str = Form(...),
):
    # Validate by parsing as YAML and running through the loader.
    import yaml
    if not name.replace("_", "").replace("-", "").isalnum():
        raise HTTPException(400, "Sequence name must be alphanumeric, '-' or '_'.")
    try:
        data = yaml.safe_load(body)
        assert isinstance(data, dict) and "steps" in data and data["steps"], "must have a non-empty 'steps' list"
    except (yaml.YAMLError, AssertionError) as e:
        raise HTTPException(400, f"Invalid sequence YAML: {e}")

    path = SEQUENCES_DIR / f"{name}.yaml"
    path.write_text(body)
    try:
        load_sequence(name)
    except Exception as e:
        path.unlink(missing_ok=True)
        raise HTTPException(400, f"Sequence failed validation: {e}")

    return view(request, "_sequences.html", sequences=list_sequences(), saved=name)


@app.post("/jobs/{job_id}/cancel", response_class=HTMLResponse)
def cancel_job(job_id: str, request: Request):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404)
    job.cancel()
    return view(request, "_job_row.html", job=job.to_dict())


@app.get("/jobs/{job_id}", response_class=HTMLResponse)
def get_job(job_id: str, request: Request):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404)
    return view(request, "_job_row.html", job=job.to_dict())
