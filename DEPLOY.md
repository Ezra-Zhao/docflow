# Deploying DocFlow

## Any Docker host

```bash
docker build -t docflow .
docker run -p 7860:7860 docflow
# UI: http://localhost:7860/   API docs: http://localhost:7860/docs
```

## Hugging Face Spaces (free, Docker SDK) — prepared, one step left

The Space repo needs three things, all ready in this repo / prepared
alongside it:

1. `README.md` with Spaces frontmatter (`sdk: docker`, `app_port: 7860`) —
   prepared text below.
2. `Dockerfile` — already in this repo (installs LibreOffice for
   DOCX → PDF and tesseract for OCR, runs uvicorn on port 7860).
3. The `app/` package and `requirements.txt` — copy from this repo.

Remaining step: creating the Space requires a logged-in Hugging Face
account (huggingface.co → New Space → name `docflow`, SDK: Docker,
visibility: Public), then push the files above to the Space repo.
Expected public URL once created under the owner's account:
`https://huggingface.co/spaces/<owner>/docflow`, app served at
`https://<owner>-docflow.hf.space`.

Space `README.md` frontmatter:

```markdown
---
title: DocFlow — Document Processing Service (Live Demo)
emoji: 📄
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
---
```

## Local verification of the exact container command (2026-10-29)

No Docker on the build host, so the image's CMD was verified directly:

```
DOCFLOW_DATA_DIR=<tmp> uvicorn app.main:app --host 0.0.0.0 --port 7860
GET  /            -> 200 (UI loads)
POST /jobs (txt)  -> done; title/emails/amounts extracted correctly
POST /jobs (docx) -> done; converted/demo-agreement.pdf produced via
                     LibreOffice, fields extracted; converted PDF
                     downloads back as real %PDF-1.7 bytes
pytest            -> 6 passed
```
