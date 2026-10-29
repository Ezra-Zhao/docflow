"""Text extraction per file type.

- PDF  : pypdf
- DOCX : python-docx (paragraphs + tables)
- TXT  : decoded as UTF-8 (falls back to latin-1)
- Image: OCR via tesseract when the binary is installed; otherwise the
  extractor returns an explanatory note instead of failing the job.
"""
import shutil
import subprocess
from pathlib import Path


def extract_pdf(path: Path) -> tuple[str, dict]:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    pages = []
    for page in reader.pages:
        pages.append(page.extract_text() or "")
    return "\n".join(pages), {"pages": len(reader.pages)}


def extract_docx(path: Path) -> tuple[str, dict]:
    import docx

    doc = docx.Document(str(path))
    parts = [p.text for p in doc.paragraphs]
    for table in doc.tables:
        for row in table.rows:
            parts.append(" | ".join(cell.text for cell in row.cells))
    return "\n".join(parts), {"paragraphs": len(doc.paragraphs), "tables": len(doc.tables)}


def extract_txt(path: Path) -> tuple[str, dict]:
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
    return text, {"encoding_fallback": "utf-8"}


def extract_image(path: Path) -> tuple[str, dict]:
    """OCR hook. Uses tesseract if present; otherwise reports unavailable."""
    if shutil.which("tesseract") is None:
        return "", {
            "ocr": "unavailable",
            "ocr_note": "tesseract binary not installed on this host; "
            "install tesseract-ocr to enable image OCR.",
        }
    out_base = path.with_suffix("")
    subprocess.run(
        ["tesseract", str(path), str(out_base), "--quiet"],
        check=True,
        timeout=120,
    )
    txt_file = out_base.with_suffix(".txt")
    text = txt_file.read_text(encoding="utf-8", errors="replace") if txt_file.exists() else ""
    return text, {"ocr": "tesseract"}


EXTRACTORS = {
    "pdf": extract_pdf,
    "docx": extract_docx,
    "txt": extract_txt,
    "png": extract_image,
    "jpg": extract_image,
    "jpeg": extract_image,
    "gif": extract_image,
    "webp": extract_image,
    "bmp": extract_image,
    "tiff": extract_image,
}


def extract_text(path: Path, ext: str) -> tuple[str, dict]:
    """Return (text, meta). Raises on unreadable/corrupt input."""
    fn = EXTRACTORS[ext]
    return fn(path)
