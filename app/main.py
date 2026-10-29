"""DocFlow API.

POST /jobs           upload a document (PDF/DOCX/TXT/image) -> job id
GET  /jobs           list recent jobs
GET  /jobs/{id}      job status + result (when done)
GET  /jobs/{id}/file/{name}  download an artifact (converted/extracted)
GET  /health         liveness
GET  /               minimal single-page UI
"""
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse

from app import pipeline
from app.db import get_session, init_db
from app.models import Job, JobStatus
from sqlmodel import select

ALLOWED_EXTS = {"pdf", "docx", "txt", "png", "jpg", "jpeg", "gif", "webp", "bmp", "tiff"}
MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB
STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    worker_task = asyncio.create_task(pipeline.worker())
    yield
    worker_task.cancel()


app = FastAPI(title="DocFlow", version="1.0.0", lifespan=lifespan)


def _job_view(job: Job) -> dict:
    view = {
        "id": job.id,
        "filename": job.filename,
        "ext": job.ext,
        "status": job.status.value,
        "error": job.error,
        "created_at": job.created_at.isoformat(),
        "updated_at": job.updated_at.isoformat(),
    }
    if job.status == JobStatus.DONE:
        view["result"] = pipeline.read_result(job.id)
    return view


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "docflow"}


@app.post("/jobs", status_code=202)
async def create_job(file: UploadFile = File(...)) -> dict:
    ext = Path(file.filename or "").suffix.lower().lstrip(".")
    if ext not in ALLOWED_EXTS:
        raise HTTPException(
            status_code=400,
            detail=f"unsupported file type: .{ext or '(none)'}; "
            f"allowed: {', '.join(sorted(ALLOWED_EXTS))}",
        )
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="empty file")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="file too large (max 25 MB)")

    with get_session() as session:
        job = Job(filename=file.filename, ext=ext)
        session.add(job)
        session.commit()
        session.refresh(job)
        job_id = job.id

    jdir = pipeline.job_dir(job_id)
    jdir.mkdir(parents=True, exist_ok=True)
    (jdir / f"input.{ext}").write_bytes(data)

    pipeline.enqueue(job_id)
    return {"id": job_id, "status": JobStatus.QUEUED.value, "filename": file.filename}


@app.get("/jobs")
def list_jobs(limit: int = 50) -> list[dict]:
    with get_session() as session:
        jobs = session.exec(
            select(Job).order_by(Job.created_at.desc()).limit(limit)
        ).all()
        return [_job_view(j) for j in jobs]


@app.get("/jobs/{job_id}")
def get_job(job_id: str) -> dict:
    with get_session() as session:
        job = session.get(Job, job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="job not found")
        return _job_view(job)


@app.get("/jobs/{job_id}/file/{name:path}")
def get_job_file(job_id: str, name: str) -> FileResponse:
    base = pipeline.job_dir(job_id).resolve()
    target = (base / name).resolve()
    if base not in target.parents and target != base:
        raise HTTPException(status_code=400, detail="invalid path")
    if not target.is_file():
        raise HTTPException(status_code=404, detail="file not found")
    return FileResponse(target)


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return (STATIC_DIR / "index.html").read_text(encoding="utf-8")
