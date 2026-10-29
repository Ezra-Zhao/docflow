# Verification — live run, 2026-10-29

Environment: Python 3.12.3 venv, LibreOffice present (`soffice`),
tesseract **absent**. Server started for real:

```
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8077
```

## Automated tests

```
$ .venv/bin/python -m pytest tests/ -q
6 passed in 11.03s
```

(test_health, TXT full chain, DOCX chain incl. PDF conversion,
unsupported-type rejection, job-not-found 404, corrupt-PDF failure path)

## Live curl chain (abridged transcript, real output)

```
== GET /health ==
{"status":"ok","service":"docflow"}

== POST evil.exe (expect 400) ==
{"detail":"unsupported file type: .exe; allowed: bmp, docx, gif, jpeg, jpg, pdf, png, tiff, txt, webp"} [HTTP 400]

== GET /jobs/nope (expect 404) ==
{"detail":"job not found"} [HTTP 404]

== TXT job ff177deecfb1 final: done ==
result.analysis:
  backend: rules, title: "Invoice INV-2026-1042",
  emails: ["ap@acme-corp.com"], amounts: ["$2,380.00"],
  dates: ["2026-12-01"], word_count: 25

== DOCX job aa3717bc2048 final: done ==
result:
  converted_file: "converted/sample.pdf",
  conversion: "docx->pdf via LibreOffice headless",
  analysis.title: "Master Service Agreement",
  emails: ["legal@acme-corp.com", "finance@acme-corp.com"],
  amounts: ["$12,750.00"], dates: ["October 5, 2026"]

== PDF job 6464dc00fcd8 final: done ==
  conversion: "pdf->txt via pypdf text extraction",
  extract_meta.pages: 1, same fields extracted as the DOCX original

== BROKEN job f46f6b4e5dc1 final: failed ==
  error: "PdfStreamError: Stream has ended unexpectedly"

== download converted PDF (DOCX job) ==
HTTP 200, 17038 bytes
%PDF-1.7            <- real PDF bytes, matches the LibreOffice output size

== image job (pixel.png) final: done ==
  extract_meta: {'ocr': 'unavailable', 'ocr_note': 'tesseract binary not
  installed on this host; install tesseract-ocr to enable image OCR.'}
  (job completes honestly instead of pretending OCR ran)

== files on disk ==
data/jobs/<id>/input.<ext>, extracted.txt, result.json,
data/jobs/<docx-id>/converted/sample.pdf
```

## Bugs found by verification (and fixed)

1. First live run: the converted file was stored as `converted/input.pdf`
   (LibreOffice names output after the stored upload name). Fixed in
   `pipeline.py`: converted artifacts are renamed to the original file's
   stem (`converted/sample.pdf`), re-verified with the download above.
2. First pytest run: jobs intermittently stuck in `queued` — the
   module-level `asyncio.Queue` was bound to a previous event loop when
   the app was re-entered (multiple TestClient contexts). Fixed by making
   the jobs table itself the queue (worker polls for `queued` rows);
   suite now passes deterministically, and queued jobs survive restarts.
