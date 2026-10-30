# DocFlow — Document Processing & Conversion Service

Upload a document (PDF / DOCX / TXT / image) and DocFlow runs it through a
three-step pipeline: **format conversion → text extraction → structured
field extraction & summary**. Jobs are processed asynchronously by an
in-process background worker with a `queued → processing → done / failed`
state machine.

Built as a portfolio proof-of-work for back-end / full-stack file-processing
roles. Clean-room implementation, all code written for this project.

## Quick start

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8077
# UI:  http://127.0.0.1:8077/
# API docs (FastAPI): http://127.0.0.1:8077/docs
```

Optional system dependency: **LibreOffice** (`soffice`) enables DOCX → PDF
conversion. Without it, conversion is skipped with a note and the rest of
the pipeline still runs. **tesseract** enables image OCR (see matrix below).

Run the tests:

```bash
.venv/bin/python -m pytest tests/ -q   # 6 tests, incl. full upload→result chain
```

## API

| Method | Path | Description |
|---|---|---|
| POST | `/jobs` | Upload a file (multipart, max 25 MB). Returns `202 {id, status: "queued"}` |
| GET | `/jobs` | List recent jobs with status |
| GET | `/jobs/{id}` | Job status; when `done`, includes the full `result` |
| GET | `/jobs/{id}/file/{name}` | Download an artifact (e.g. `converted/<name>.pdf`, `extracted.txt`) |
| GET | `/health` | Liveness probe |
| GET | `/` | Single-page UI (upload + job list + result viewer, vanilla JS) |

### Example

```bash
curl -F "file=@agreement.docx" http://127.0.0.1:8077/jobs
# {"id":"aa3717bc2048","status":"queued","filename":"agreement.docx"}

curl http://127.0.0.1:8077/jobs/aa3717bc2048
```

Result (`result.json`, also stored on disk per job):

```json
{
  "converted_file": "converted/agreement.pdf",
  "conversion": "docx->pdf via LibreOffice headless",
  "analysis": {
    "backend": "rules",
    "title": "Master Service Agreement",
    "emails": ["legal@acme-corp.com"],
    "amounts": ["$12,750.00"],
    "dates": ["October 5, 2026"],
    "summary": "The total contract value is $12,750.00. ...",
    "word_count": 20, "pages": 1
  }
}
```

## Architecture

```
app/
  main.py      FastAPI app: routes, upload validation, UI serving
  pipeline.py  Background worker: polls the jobs table (the table IS the
               queue, so queued jobs survive restarts), walks each job
               through convert -> extract -> analyze, records failures
  convert.py   DOCX -> PDF via LibreOffice headless
  extract.py   Text extraction: pypdf (PDF), python-docx (DOCX), OCR hook
  llm.py       Pluggable field extraction (see below)
  models.py    SQLModel Job row + status enum
  db.py        Engine setup; SQLite by default
data/
  docflow.db   SQLite database (jobs)
  jobs/<id>/   input.<ext>, converted/, extracted.txt, result.json
```

**Storage / DB swap points.** Files are stored on local disk under
`data/jobs/<job_id>/`. Metadata lives in SQLite via SQLModel. To move to
PostgreSQL, set one environment variable — no code changes:

```bash
DOCFLOW_DATABASE_URL=postgresql+psycopg://user:pass@host:5432/docflow
```

To scale out, the worker loop in `pipeline.py` is the single seam: swap the
poll for Celery/RQ/Arq and point `job_dir` at object storage (S3) — the
route layer and processing steps do not change.

## Pluggable LLM field extraction

`app/llm.py` exposes one interface, `analyze(text, meta)`, with two backends:

- **Rules (default, no key needed):** title heuristic, word/char counts,
  regex extraction of emails, money amounts and dates, one-line summary.
- **LLM (OpenAI-compatible):** set `DOCFLOW_LLM_API_KEY` (plus optional
  `DOCFLOW_LLM_BASE_URL`, `DOCFLOW_LLM_MODEL`) and extraction calls any
  OpenAI-compatible chat endpoint, requesting structured JSON. If the call
  fails, the pipeline falls back to rules and records `llm_error` in the
  result instead of failing the job.

## Conversion & extraction matrix (verified on this host, 2026-10-29)

| Input | Conversion | Text extraction | Status |
|---|---|---|---|
| DOCX | → PDF via LibreOffice headless | python-docx (paragraphs + tables) | working, verified end-to-end |
| PDF | → TXT (extracted text) | pypdf | working, verified end-to-end |
| PDF → DOCX | not offered | — | LibreOffice imports PDF via Draw; layout is unreliable, so this direction is deliberately not faked |
| TXT | n/a | UTF-8 decode (latin-1 fallback) | working, verified end-to-end |
| Image (png/jpg/…) | n/a | tesseract OCR hook | interface implemented; tesseract is **not installed on this host**, so results carry `ocr: "unavailable"` with an explanatory note — install `tesseract-ocr` to activate |

## How this maps to the job requirements

| Typical requirement (file-processing / AI back-end roles) | Where it is demonstrated |
|---|---|
| REST API design with a modern Python framework | FastAPI app, typed responses, proper status codes (202/400/404/413), OpenAPI docs at `/docs` |
| Async job processing / background workers | In-process worker + DB-backed queue, `queued → processing → done/failed` state machine in `pipeline.py` |
| File handling: upload validation, size limits, safe downloads | `main.py` (extension allow-list, 25 MB cap, path-traversal guard on downloads) |
| Document conversion at scale | LibreOffice headless integration (`convert.py`), subprocess timeouts and error capture |
| PDF / DOCX parsing | pypdf and python-docx extractors (`extract.py`), incl. table flattening |
| OCR integration | tesseract hook with graceful degradation when the binary is absent |
| LLM integration for extraction/summarization | Pluggable OpenAI-compatible backend with rule-based fallback (`llm.py`) |
| Relational data modeling | SQLModel/SQLAlchemy `Job` model; SQLite → PostgreSQL via one env var |
| Front-end for a full-stack demo | Single-page UI served by FastAPI (no build chain): upload, live job list, result viewer |
| Automated testing | pytest suite: full chain (TXT + DOCX), unsupported-type rejection, 404, corrupt-file failure path |
| Error handling & observability | Failures land in `failed` with the exception recorded on the job; results persisted as `result.json` per job |

## Verification

See `VERIFY.md` for the live run transcript (real uvicorn server, curl
end-to-end: TXT/DOCX/PDF uploads → `done`, corrupt PDF → `failed`,
`.exe` → 400, converted PDF download byte-checked).

## Live demo

Hosted demo: see `DEPLOY.md` (Hugging Face Spaces package prepared; one account step left).
