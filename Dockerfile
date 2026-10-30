# DocFlow — container image (used by the Hugging Face Spaces demo and any
# Docker host). LibreOffice enables DOCX -> PDF conversion; tesseract
# enables image OCR. Both are optional at runtime: without them the
# pipeline degrades gracefully and says so in the job result.
FROM python:3.12-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      libreoffice-writer libreoffice-core fonts-dejavu tesseract-ocr \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY data/.gitkeep ./data/.gitkeep

ENV DOCFLOW_DATA_DIR=/app/data \
    PYTHONUNBUFFERED=1
# Hugging Face Spaces (Docker SDK) serves port 7860 by default.
EXPOSE 7860
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
