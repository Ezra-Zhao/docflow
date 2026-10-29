"""In-process async job pipeline.

The jobs table doubles as the work queue: uploading inserts a row with
status `queued`, and a single background worker (started from the FastAPI
lifespan) polls for queued rows and walks each through:
    queued -> processing -> (convert -> extract -> analyze) -> done
Any exception lands the job in `failed` with the error recorded.
DB-backed queuing also means queued jobs survive a process restart.

Files live under data/jobs/<job_id>/ : original upload, converted output,
extracted.txt and result.json. The DB row tracks status only; result.json
is the source of truth for results.
"""
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from sqlmodel import select

from app import convert, extract, llm
from app.db import DATA_DIR, get_session
from app.models import Job, JobStatus

JOBS_DIR = DATA_DIR / "jobs"
JOBS_DIR.mkdir(parents=True, exist_ok=True)


def job_dir(job_id: str) -> Path:
    return JOBS_DIR / job_id


def enqueue(job_id: str) -> None:
    """No-op hook kept for API symmetry: the queued DB row IS the queue."""


def _set_status(job_id: str, status: JobStatus, error: str | None = None) -> None:
    with get_session() as session:
        job = session.get(Job, job_id)
        if job is None:
            return
        job.status = status
        job.error = error
        job.updated_at = datetime.now(timezone.utc)
        session.add(job)
        session.commit()


def process_job(job_id: str) -> dict:
    """Synchronous core (runs in a worker thread). Returns the result dict."""
    with get_session() as session:
        job = session.get(Job, job_id)
        if job is None:
            raise RuntimeError(f"job {job_id} not found")
        filename, ext = job.filename, job.ext

    _set_status(job_id, JobStatus.PROCESSING)
    jdir = job_dir(job_id)
    src = jdir / f"input.{ext}"

    result: dict = {"job_id": job_id, "filename": filename, "ext": ext}

    # 1) conversion
    result.update(convert.convert(src, ext, jdir))
    # The upload is stored as input.<ext>, so a converted file comes out as
    # e.g. converted/input.pdf — rename it to the original file's stem so
    # download paths match what the user uploaded.
    if result.get("converted_file"):
        produced = jdir / result["converted_file"]
        target = produced.with_name(Path(filename).stem + produced.suffix)
        if produced.exists() and target != produced:
            produced.rename(target)
            result["converted_file"] = f"{produced.parent.name}/{target.name}"

    # 2) text extraction
    text, meta = extract.extract_text(src, ext)
    (jdir / "extracted.txt").write_text(text, encoding="utf-8")
    result["extract_meta"] = meta

    # 3) field extraction / summary (LLM if configured, else rules)
    result["analysis"] = llm.analyze(text, meta)

    (jdir / "result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    _set_status(job_id, JobStatus.DONE)
    return result


def _next_queued_id() -> str | None:
    with get_session() as session:
        job = session.exec(
            select(Job).where(Job.status == JobStatus.QUEUED).order_by(Job.created_at)
        ).first()
        return job.id if job else None


async def worker() -> None:
    while True:
        job_id = _next_queued_id()
        if job_id is None:
            await asyncio.sleep(0.3)
            continue
        try:
            await asyncio.to_thread(process_job, job_id)
        except Exception as exc:  # noqa: BLE001 - record and move on
            _set_status(job_id, JobStatus.FAILED, f"{type(exc).__name__}: {exc}"[:500])


def read_result(job_id: str) -> dict | None:
    path = job_dir(job_id) / "result.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))
