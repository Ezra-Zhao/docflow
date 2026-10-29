"""Format conversion.

Primary path: DOCX -> PDF via LibreOffice headless (`soffice`), which is
installed on this host. PDF input is converted to TXT through the pypdf
extraction step (LibreOffice's PDF->DOCX import goes through Draw and
produces unreliable layout, so it is intentionally not used).
See README "Conversion matrix" for the honest per-format status.
"""
import shutil
import subprocess
from pathlib import Path


class ConversionError(RuntimeError):
    pass


def docx_to_pdf(src: Path, out_dir: Path) -> Path:
    if shutil.which("soffice") is None:
        raise ConversionError("LibreOffice (soffice) not available on this host")
    out_dir.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [
            "soffice",
            "--headless",
            "--norestore",
            "--convert-to",
            "pdf",
            "--outdir",
            str(out_dir),
            str(src),
        ],
        capture_output=True,
        text=True,
        timeout=180,
    )
    produced = out_dir / (src.stem + ".pdf")
    if proc.returncode != 0 or not produced.exists():
        raise ConversionError(
            f"LibreOffice conversion failed: {proc.stderr.strip()[:300]}"
        )
    return produced


def convert(src: Path, ext: str, job_dir: Path) -> dict:
    """Run the conversion step for a job. Returns a result fragment:
    {"converted_file": <name or None>, "conversion": <status string>}
    Conversion problems degrade to a note; they do not fail the whole job
    unless the file itself is unreadable (handled by the extraction step).
    """
    if ext == "docx":
        try:
            produced = docx_to_pdf(src, job_dir / "converted")
            return {
                "converted_file": f"converted/{produced.name}",
                "conversion": "docx->pdf via LibreOffice headless",
            }
        except ConversionError as exc:
            return {"converted_file": None, "conversion": f"skipped: {exc}"}
    if ext == "pdf":
        return {
            "converted_file": "extracted.txt",
            "conversion": "pdf->txt via pypdf text extraction "
            "(pdf->docx not offered: LibreOffice Draw import is unreliable)",
        }
    if ext == "txt":
        return {"converted_file": None, "conversion": "not applicable for txt input"}
    return {"converted_file": None, "conversion": "not applicable for image input"}
